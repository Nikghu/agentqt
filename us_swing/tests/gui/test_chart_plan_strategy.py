"""Tests for the chart plan strategy made by Send to Execution (SRD-GUI-045.001 – .005)."""
from __future__ import annotations

import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import numpy as np
import pandas as pd
import pytest
from PyQt6.QtCore import QObject, pyqtSignal

import us_swing.data  # noqa: F401  — load data before db (db ↔ data import cycle)
from us_swing.gui import manual_picks_store, strategy_store
from us_swing.gui.app_service import AppService
from us_swing.gui.chart_plan import build_chart_plan
from us_swing.gui.strategy_store import StrategyConfig, load_strategies, save_strategies

_TODAY = datetime.date(2026, 11, 20)


@pytest.fixture(autouse=True)
def stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(strategy_store, "_DB_PATH", tmp_path / "candles.db")
    monkeypatch.setattr(strategy_store, "_engine_cache", None)
    monkeypatch.setattr(manual_picks_store, "_STORE_FILE", tmp_path / "picks.json")
    yield
    if strategy_store._engine_cache is not None:
        strategy_store._engine_cache.dispose()


class _Rex:
    def __init__(self) -> None:
        self.reset_names: list[str] = []

    def reset(self, name: str) -> int:
        self.reset_names.append(name)
        return 0


class _Svc(QObject):
    """The real chart plan methods of AppService on a light stand-in."""

    strategies_changed = pyqtSignal()
    send_chart_plan = AppService.send_chart_plan
    purge_old_chart_plans = AppService.purge_old_chart_plans
    remove_manual_pick = AppService.remove_manual_pick
    _drop_chart_plans = AppService._drop_chart_plans
    _reset_rex = AppService._reset_rex
    _after_strategies_saved = AppService._after_strategies_saved
    _clear_pending_exits = AppService._clear_pending_exits

    def __init__(self) -> None:
        super().__init__()
        self._active_uid = 1
        self._rex_counters = _Rex()
        self._strategy_engine = None
        self._pending_store = None
        self._filtered_symbols: list[str] = []
        self._cycle_symbols: set[str] = set()
        self.open: dict[str, list[str]] = {}
        self.refused: str | None = None

    def add_manual_pick(self, symbol: str) -> str | None:
        if self.refused:
            return self.refused
        picks = manual_picks_store.load_manual_picks("1")
        manual_picks_store.save_manual_picks("1", picks + [symbol])
        return None

    def get_open_symbols_for_strategy(self, name: str) -> list[str]:
        return self.open.get(name, [])

    def get_latest_screener_results(self) -> list[Any]:
        return []

    def _refresh_after_pick_change(self) -> None:
        pass

    def _market_today(self) -> datetime.date:
        return _TODAY


@pytest.fixture()
def svc(qtbot: Any) -> _Svc:
    return _Svc()


def _plans() -> list[StrategyConfig]:
    return [c for c in load_strategies() if c.strategy_type == "chart_plan"]


def test_send_saves_one_trade_auto_strategy(svc: _Svc) -> None:
    """UT-GUI-045.001.M01.T01: Send with a plan saves the auto strategy for that stock."""
    assert svc.send_chart_plan("VRSN", 310.0, 300.0, 330.0, 25) is None

    [cfg] = _plans()
    assert cfg.name == "Chart plan - VRSN"
    assert cfg.symbol_mode == "include" and cfg.symbols_include == ["VRSN"]
    assert (cfg.mode, cfg.auto_trade, cfg.run_state) == ("auto", True, "RUNNING")
    assert (cfg.trade_type, cfg.rex_count, cfg.direction) == ("Positional", 0, "LONG")
    assert cfg.entry_condition == "Price('Stock', 'current', 'close', '3m') > 310.00"
    assert (cfg.stoploss_value, cfg.target_value) == (3.23, 6.45)
    assert cfg.start_date == cfg.end_date == "2026-11-20"
    assert manual_picks_store.load_manual_picks("1") == ["VRSN"]


def test_plan_saves_exact_shares() -> None:
    """UT-GUI-045.008.M01.T01: the chart plan stores the share count; other strategies keep 0."""
    other = StrategyConfig(name="Breakout", mode="auto", capital_max=10, start_time="09:30",
                           end_time="16:00", start_date="2026-01-01", end_date="2026-01-02",
                           days=["Monday"], entry_condition="", exit_condition="")
    save_strategies([build_chart_plan("VRSN", 108.0, 103.5, 122.0, 25, _TODAY), other])

    saved = {c.name: c for c in load_strategies()}

    plan = saved["Chart plan - VRSN"]
    assert (plan.fixed_qty, plan.capital_max, plan.per_trade_pct) == (25, 100, 100)
    assert saved["Breakout"].fixed_qty == 0


def test_engine_buys_fixed_shares() -> None:
    """UT-GUI-045.008.M01.T02: engine sizing uses the fixed share count, else the percent rule."""
    from us_swing.execution.strategy_engine._router import _Router

    router = SimpleNamespace(_effective_capital_provider=lambda: 50_000.0)
    plan = build_chart_plan("VRSN", 108.0, 103.5, 122.0, 25, _TODAY)
    ctx = SimpleNamespace(cfg=plan)

    assert _Router._size_entry(router, ctx, 108.0) == 25  # type: ignore[arg-type]
    ctx.cfg = SimpleNamespace(fixed_qty=0, capital_max=10, per_trade_pct=100)
    assert _Router._size_entry(router, ctx, 108.0) == 46  # type: ignore[arg-type]


def test_refused_pick_saves_no_strategy(svc: _Svc) -> None:
    """UT-GUI-045.001.M01.T03: a refused stock gets no strategy."""
    svc.refused = "XYZ is not in the stock universe"

    assert svc.send_chart_plan("XYZ", 10.0, 9.0, 12.0, 25) == "XYZ is not in the stock universe"
    assert _plans() == []


def test_resend_replaces_but_open_trade_blocks(svc: _Svc) -> None:
    """UT-GUI-045.001.M01.T04: resend replaces the plan; an open trade keeps the old one."""
    svc.send_chart_plan("VRSN", 310.0, 300.0, 330.0, 25)
    svc.send_chart_plan("VRSN", 312.0, 300.0, 340.0, 25)
    [cfg] = _plans()
    assert cfg.entry_condition.endswith("> 312.00")

    svc.open["Chart plan - VRSN"] = ["VRSN"]
    message = svc.send_chart_plan("VRSN", 320.0, 300.0, 350.0, 25)

    assert message == "VRSN already has an open chart plan trade"
    assert _plans()[0].entry_condition.endswith("> 312.00")


def test_remove_pick_removes_plan_unless_trade_open(svc: _Svc) -> None:
    """UT-GUI-045.001.M01.T05: removing the pick removes its plan, not one with an open trade."""
    svc.send_chart_plan("VRSN", 310.0, 300.0, 330.0, 25)
    svc.send_chart_plan("AAPL", 200.0, 190.0, 220.0, 25)
    svc.open["Chart plan - AAPL"] = ["AAPL"]

    svc.remove_manual_pick("VRSN")
    svc.remove_manual_pick("AAPL")

    assert [c.name for c in _plans()] == ["Chart plan - AAPL"]
    assert "Chart plan - VRSN" in svc._rex_counters.reset_names


def test_closed_trade_removes_plan(svc: _Svc) -> None:
    """UT-GUI-045.001.M01.T06: when the chart plan trade closes, its strategy is removed."""
    svc.send_chart_plan("VRSN", 310.0, 300.0, 330.0, 25)
    changed: list[bool] = []
    svc.strategies_changed.connect(lambda: changed.append(True))

    svc._clear_pending_exits("Chart plan - VRSN", "VRSN")

    assert _plans() == []
    assert changed == [True]


def test_purge_removes_only_old_plans(svc: _Svc) -> None:
    """UT-GUI-045.001.M01.T07: past-day plans are removed; today's and other strategies stay."""
    old = build_chart_plan("AAPL", 200.0, 190.0, 220.0, 10, _TODAY - datetime.timedelta(days=1))
    today = build_chart_plan("VRSN", 310.0, 300.0, 330.0, 10, _TODAY)
    other = StrategyConfig(name="Breakout", mode="auto", capital_max=10, start_time="09:30",
                           end_time="16:00", start_date="2026-01-01", end_date="2026-01-02",
                           days=["Monday"], entry_condition="", exit_condition="")
    save_strategies([old, today, other])

    svc.purge_old_chart_plans()

    assert sorted(c.name for c in load_strategies()) == ["Breakout", "Chart plan - VRSN"]


def test_entry_condition_runs_in_engine_evaluator() -> None:
    """UT-GUI-045.001.M01.T08: the entry rule fires only when the 3m close is above Entry."""
    from us_swing.execution.strategy_engine._evaluator import ConditionEvaluator

    cfg =build_chart_plan("VRSN", 310.0, 300.0, 330.0, 10, _TODAY)
    evaluator = ConditionEvaluator()

    def _candles(last: float) -> dict[str, pd.DataFrame]:
        closes = np.array([305.0] * 9 + [last])
        return {"3m": pd.DataFrame({"open": closes, "high": closes + 1, "low": closes - 1,
                                    "close": closes, "volume": np.full(10, 1000)})}

    assert evaluator.evaluate(cfg.entry_condition, _candles(310.5), "VRSN") is True
    assert evaluator.evaluate(cfg.entry_condition, _candles(309.9), "VRSN") is False
