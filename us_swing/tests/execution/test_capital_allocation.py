"""
Tests for FO-EXE-017 — capital-max sizing, advisory risk warnings, rex reset.
Parent SRD: SRD-EXE-017.003 — .011
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from pytestqt.qtbot import QtBot

from us_swing.data.models import AccountState, RiskConfig
from us_swing.execution import ExecutionEnums
from us_swing.execution.risk_manager import RiskManager
from us_swing.execution.strategy_engine._context import _StrategyContext
from us_swing.execution.strategy_engine._engine import StrategyEngine
from us_swing.execution.strategy_engine._evaluator import ConditionEvaluator
from us_swing.execution.strategy_engine._events import RiskWarning, StrategySignalDropped
from us_swing.execution.strategy_engine._router import _Router
from us_swing.execution.strategy_engine._signals import Action, TradeSignal

_ET = ZoneInfo("America/New_York")
_RS = ExecutionEnums.StrategyRunState


# ── size_for_strategy ─────────────────────────────────────────────────────────

def test_size_for_strategy_standard() -> None:
    """UT-EXE-017.003.M01.T01: standard sizing — $2000 × 25% / $96 → 5 shares."""
    assert RiskManager.size_for_strategy(96.0, 25, 2_000.0) == 5


def test_size_for_strategy_exact_boundary() -> None:
    """UT-EXE-017.003.M01.T02: exact budget boundary — $500 / $100 → 5 shares."""
    assert RiskManager.size_for_strategy(100.0, 25, 2_000.0) == 5


def test_size_for_strategy_price_over_budget() -> None:
    """UT-EXE-017.003.M01.T03: entry price exceeds the whole budget → 0 shares."""
    assert RiskManager.size_for_strategy(520.0, 25, 2_000.0) == 0


def test_size_for_strategy_non_positive_price() -> None:
    """UT-EXE-017.003.M01.T04: non-positive entry price → 0 shares."""
    assert RiskManager.size_for_strategy(0.0, 25, 2_000.0) == 0


# ── can_allocate (budget basis) ───────────────────────────────────────────────

class _FakeTracker:
    def __init__(self, positions: list[Any] | None = None) -> None:
        self._positions = positions or []

    def get_all(self, user_id: int) -> list[Any]:
        return self._positions


def _rm(effective: float, positions: list[Any] | None = None) -> RiskManager:
    return RiskManager(
        config=RiskConfig(max_capital_value=effective),
        account_provider=lambda: AccountState(1, effective, effective, 0.0),
        cb_state_provider=lambda: False,
        user_id=1,
        tracker=_FakeTracker(positions),
        effective_capital_provider=lambda: effective,
    )


def test_can_allocate_room_under_budget() -> None:
    """UT-EXE-017.005.M01.T05: room under the strategy budget → ok."""
    pos = MagicMock(strategy_id="s1", average_price=100.0, quantity=3)  # $300 deployed
    rm = _rm(2_000.0, [pos])  # budget = 2000 × 25% = $500
    assert rm.can_allocate("s1", 25).ok is True


def test_can_allocate_at_budget_blocks() -> None:
    """UT-EXE-017.005.M01.T06: deployed at/over budget → blocked."""
    pos = MagicMock(strategy_id="s1", average_price=100.0, quantity=5)  # $500 deployed
    rm = _rm(2_000.0, [pos])  # budget = $500
    result = rm.can_allocate("s1", 25)
    assert result.ok is False
    assert "capital limit" in result.reason


# ── margin_available + reservation ledger ─────────────────────────────────────

def test_margin_available_nets_all_strategy_deployed() -> None:
    """UT-EXE-017.015.M10.T01: margin = budget − deployed across all strategies."""
    p1 = MagicMock(strategy_id="s1", average_price=100.0, quantity=5)   # $500
    p2 = MagicMock(strategy_id="s2", average_price=70.0, quantity=10)   # $700
    rm = _rm(2_000.0, [p1, p2])
    assert rm.margin_available() == 800.0


def test_margin_available_floors_at_zero() -> None:
    """UT-EXE-017.015.M10.T02: deployed over budget floors margin at zero."""
    p = MagicMock(strategy_id="s1", average_price=100.0, quantity=21)   # $2100
    rm = _rm(2_000.0, [p])
    assert rm.margin_available() == 0.0


def test_reservation_reduces_margin() -> None:
    """UT-EXE-017.017.M10.T03: an active reservation lowers margin."""
    rm = _rm(2_000.0, [])
    rm.reserve("s1", "AAPL", 500.0)
    assert rm.margin_available() == 1_500.0


def test_release_restores_margin_idempotent() -> None:
    """UT-EXE-017.017.M10.T04: release frees margin and is idempotent."""
    rm = _rm(2_000.0, [])
    rm.reserve("s1", "AAPL", 500.0)
    rm.release("s1", "AAPL")
    rm.release("s1", "AAPL")  # second release must not raise
    assert rm.margin_available() == 2_000.0


# ── advisory validate ─────────────────────────────────────────────────────────

def test_validate_advisory_max_position_warns_not_blocks() -> None:
    """UT-EXE-017.006.M01.T07: max-position breach warns but does not block."""
    warnings: list[RiskWarning] = []
    rm = RiskManager(
        config=RiskConfig(max_position_value=100.0),
        account_provider=lambda: AccountState(1, 10_000.0, 10_000.0, 0.0),
        cb_state_provider=lambda: False,
        user_id=1,
        warning_sink=warnings.append,
    )
    sig = TradeSignal(action=Action.ENTRY, symbol="AAPL", strategy_id="s1",
                      entry_price=50.0, qty_recommended=10)  # $500 > $100
    result = rm.validate(sig)
    assert result.ok is True
    assert result.qty == 10
    assert any(w.kind == "max_position" for w in warnings)


def test_validate_circuit_breaker_blocks() -> None:
    """UT-EXE-017.006.M01.T08: circuit breaker still blocks."""
    rm = RiskManager(
        config=RiskConfig(),
        account_provider=lambda: AccountState(1, 10_000.0, 10_000.0, 0.0),
        cb_state_provider=lambda: True,
        user_id=1,
    )
    sig = TradeSignal(action=Action.ENTRY, symbol="AAPL", strategy_id="s1",
                      entry_price=50.0, qty_recommended=1)
    result = rm.validate(sig)
    assert result.ok is False
    assert "circuit breaker" in result.reason


# ── router sizing / capital-insufficient drop ─────────────────────────────────

@dataclass
class _Cfg:
    name: str = "s1"
    mode: str = "auto"
    symbol_mode: str = "all"
    symbols_include: list[str] = field(default_factory=list)
    symbols_exclude: list[str] = field(default_factory=list)
    start_time: str = "09:30"
    end_time: str = "15:30"
    start_date: str = "2026-01-01"
    end_date: str = "2099-12-31"
    days: list[str] = field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday",
                                                     "Thursday", "Friday"])
    trade_type: str = "Intraday"
    auto_trade: bool = True
    capital_max: int = 25
    entry_condition: str = "Number(1) == Number(1)"
    exit_condition: str = "Number(1) == Number(1)"
    stoploss_enabled: bool = False
    stoploss_value: float = 1.0
    target_enabled: bool = False
    target_value: float = 2.0
    rex_count: int = 0
    run_state: str = "RUNNING"


class _FakeCycleQuery:
    def has_open_cycle(self, strategy_id: str, symbol: str) -> bool:
        return False

    def open_cycles_for_strategy(self, strategy_id: str) -> tuple[Any, ...]:
        return ()

    def open_cycles(self) -> tuple[Any, ...]:
        return ()


def _bar(close: float) -> Any:
    from us_swing.data.models import OHLCVBar
    return OHLCVBar(symbol="CVS", datetime=datetime(2026, 5, 19, 10, 0, tzinfo=_ET),
                    open=close, high=close, low=close, close=close,
                    volume=1_000, timeframe="3m")


def _candles(close: float) -> dict[str, pd.DataFrame]:
    return {"3m": pd.DataFrame({"open": [close], "high": [close], "low": [close],
                                "close": [close], "volume": [1_000]})}


def _router(effective: float) -> tuple[_Router, asyncio.Queue[TradeSignal], MagicMock,
                                       dict[str, _StrategyContext]]:
    cfg = _Cfg()
    ctx = _StrategyContext(cfg=cfg, run_state=_RS.RUNNING)  # type: ignore[arg-type]
    registry = {cfg.name: ctx}
    queue: asyncio.Queue[TradeSignal] = asyncio.Queue()
    risk = MagicMock()
    from us_swing.execution.strategy_engine._protocols import CanAllocateResult
    risk.can_allocate.return_value = CanAllocateResult(ok=True)
    risk.margin_available.return_value = effective
    bus = MagicMock()
    router = _Router(
        queue=queue, registry=registry, evaluator=ConditionEvaluator(),
        risk=risk, submitter=MagicMock(), pending=MagicMock(), bus=bus,
        cycle_query=_FakeCycleQuery(),
        clock=lambda: datetime(2026, 5, 19, 10, 0, tzinfo=_ET),
        effective_capital_provider=lambda: effective,
    )
    return router, queue, bus, registry


@pytest.mark.asyncio
async def test_router_drops_entry_when_capital_insufficient() -> None:
    """UT-EXE-017.004.M03.T01: qty<1 → dropped with capital_insufficient, no enqueue."""
    router, queue, bus, registry = _router(effective=2_000.0)  # budget $500
    ctx = list(registry.values())[0]
    await router.evaluate(ctx, "CVS", _candles(520.0), _bar(520.0))  # $520 > $500
    assert queue.empty()
    assert "CVS" not in ctx.in_flight
    dropped = [c.args[0] for c in bus.publish.call_args_list
               if isinstance(c.args[0], StrategySignalDropped)]
    assert any(d.reason == "capital_insufficient" for d in dropped)


@pytest.mark.asyncio
async def test_router_builds_sized_entry_signal() -> None:
    """UT-EXE-017.009.M03.T02: built entry signal carries the sized qty (not 1)."""
    router, queue, _bus, registry = _router(effective=2_000.0)  # budget $500
    ctx = list(registry.values())[0]
    await router.evaluate(ctx, "CVS", _candles(96.0), _bar(96.0))
    signal = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert signal.qty_recommended == 5


@pytest.mark.asyncio
async def test_router_clamps_entry_to_margin() -> None:
    """UT-EXE-017.018.M12.T01: entry qty clamped to remaining margin."""
    router, queue, _bus, registry = _router(effective=2_000.0)  # strategy slice = 5 @ $96
    router._risk.margin_available.return_value = 300.0          # only 3 shares fit
    ctx = list(registry.values())[0]
    await router.evaluate(ctx, "CVS", _candles(96.0), _bar(96.0))
    signal = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert signal.qty_recommended == 3
    router._risk.reserve.assert_called_once_with(ctx.name, "CVS", 3 * 96.0)


@pytest.mark.asyncio
async def test_router_drops_entry_when_margin_exhausted() -> None:
    """UT-EXE-017.016.M12.T02: margin below entry price → dropped margin_exhausted."""
    router, queue, bus, registry = _router(effective=2_000.0)
    router._risk.margin_available.return_value = 50.0          # < $96
    ctx = list(registry.values())[0]
    await router.evaluate(ctx, "CVS", _candles(96.0), _bar(96.0))
    assert queue.empty()
    assert "CVS" not in ctx.in_flight
    dropped = [c.args[0] for c in bus.publish.call_args_list
               if isinstance(c.args[0], StrategySignalDropped)]
    assert any(d.reason == "margin_exhausted" for d in dropped)


def test_router_releases_reservation_on_entry_fill() -> None:
    """UT-EXE-017.017.M12.T03: an entry fill releases the reservation."""
    from us_swing.execution.strategy_engine._protocols import FillEvent
    router, _queue, _bus, registry = _router(effective=2_000.0)
    sid = list(registry.keys())[0]
    fill = FillEvent(strategy_id=sid, symbol="CVS", is_entry=True,
                     fill_price=96.0, fill_qty=5, order_id=1)
    router.on_order_fill(fill)
    router._risk.release.assert_called_once_with(sid, "CVS")


# ── engine rex auto-reset on start ────────────────────────────────────────────

def _engine() -> StrategyEngine:
    return StrategyEngine(
        registry_loader=lambda: [],
        registry_saver=lambda c: None,
        candles_provider=lambda s: {"3m": pd.DataFrame()},
        bar_provider=lambda s, tf: None,
        risk=MagicMock(),
        submitter=MagicMock(),
        pending=MagicMock(),
        bus=MagicMock(),
    )


def test_rex_reset_on_start(qtbot: QtBot) -> None:
    """UT-EXE-017.010.M04.T01: STOPPED → RUNNING resets the strategy's rex counters."""
    engine = _engine()
    ctx = _StrategyContext(cfg=_Cfg(), run_state=_RS.STOPPED)  # type: ignore[arg-type]
    engine._registry = {"s1": ctx}
    engine._router = MagicMock()
    rex = MagicMock()
    rex.reset.return_value = 3
    engine._rex_counters = rex
    engine._apply_run_state("s1", _RS.RUNNING)
    rex.reset.assert_called_once_with("s1")


def test_rex_no_reset_on_stop(qtbot: QtBot) -> None:
    """UT-EXE-017.010.M04.T02: RUNNING → STOPPED does not reset counters."""
    engine = _engine()
    ctx = _StrategyContext(cfg=_Cfg(), run_state=_RS.RUNNING)  # type: ignore[arg-type]
    engine._registry = {"s1": ctx}
    engine._router = MagicMock()
    rex = MagicMock()
    engine._rex_counters = rex
    engine._apply_run_state("s1", _RS.STOPPED)
    rex.reset.assert_not_called()
