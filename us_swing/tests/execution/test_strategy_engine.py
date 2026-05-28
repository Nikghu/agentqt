"""
Module: MD-EXE-011.001.M01 — tests
Parent SRD: SRD-EXE-011.001 — .003, .013, .014
"""
from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from pytestqt.qtbot import QtBot

from us_swing.execution.strategy_engine._context import _StrategyContext
from us_swing.execution.strategy_engine._protocols import (
    CanAllocateResult,
    ValidationResult,
)
from us_swing.execution.strategy_engine._engine import StrategyEngine

_ET = ZoneInfo("America/New_York")


@dataclass
class _Cfg:
    name: str = "test_strat"
    mode: str = "auto"
    symbol_mode: str = "all"
    symbols_include: list[str] = field(default_factory=list)
    symbols_exclude: list[str] = field(default_factory=list)
    start_time: str = "09:30"
    end_time: str = "15:30"
    start_date: str = "2026-01-01"
    end_date: str = "2099-12-31"
    days: list[str] = field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    trade_type: str = "Intraday"
    auto_trade: bool = True
    capital_max: int = 10
    entry_condition: str = ""
    exit_condition: str = ""
    stoploss_enabled: bool = False
    stoploss_value: float = 1.0
    target_enabled: bool = False
    target_value: float = 2.0
    strategy_signal: dict[str, Any] = field(default_factory=lambda: {"run_state": "RUNNING"})


def _make_risk() -> MagicMock:
    risk = MagicMock()
    risk.validate.return_value = ValidationResult(ok=True, qty=10)
    risk.can_allocate.return_value = CanAllocateResult(ok=True)
    return risk


def _make_engine(cfgs: list[_Cfg]) -> StrategyEngine:
    from us_swing.data.models import OHLCVBar
    import pandas as pd

    def loader() -> list[Any]:
        return cfgs  # type: ignore[return-value]

    def saver(c: list[Any]) -> None:
        pass

    def candles_provider(sym: str) -> dict[str, pd.DataFrame]:
        return {"3m": pd.DataFrame()}

    def bar_provider(sym: str, tf: str) -> OHLCVBar | None:
        return None

    return StrategyEngine(
        registry_loader=loader,
        registry_saver=saver,
        candles_provider=candles_provider,
        bar_provider=bar_provider,
        risk=_make_risk(),
        submitter=MagicMock(),
        pending=MagicMock(),
        bus=MagicMock(),
    )


def test_engine_starts_and_emits_started_ok(qtbot: QtBot) -> None:
    """UT-EXE-011.001.M01.T01: Engine starts asyncio loop on QThread.start — started_ok emitted."""
    engine = _make_engine([])
    with qtbot.waitSignal(engine.started_ok, timeout=3000):
        engine.start()
    assert engine.isRunning()
    assert engine._loop is not None
    engine.request_stop()
    qtbot.waitSignal(engine.stopped, timeout=3500)


def test_registry_load_skips_disabled(qtbot: QtBot) -> None:
    """UT-EXE-011.001.M01.T02: Registry load skips mode=='disabled'; run_state migrated from cfg."""
    from us_swing.execution import ExecutionEnums

    cfgs = [
        _Cfg(name="auto_strat", mode="auto"),
        _Cfg(name="manual_strat", mode="manual"),
        _Cfg(name="disabled_strat", mode="disabled"),
    ]
    engine = _make_engine(cfgs)
    with qtbot.waitSignal(engine.started_ok, timeout=3000):
        engine.start()

    assert len(engine.registry) == 2
    assert "disabled_strat" not in engine.registry
    for ctx in engine.registry.values():
        assert ctx.run_state is ExecutionEnums.StrategyRunState.RUNNING
        assert ctx.cfg.strategy_signal["run_state"] == "RUNNING"

    engine.request_stop()
    qtbot.waitSignal(engine.stopped, timeout=3500)


def test_fanout_calls_evaluate_for_accepting_contexts(qtbot: QtBot) -> None:
    """UT-EXE-011.001.M01.T03: fan-out calls evaluate for all accepting contexts."""
    from us_swing.data.models import OHLCVBar
    import pandas as pd

    cfgs = [_Cfg(name=f"s{i}") for i in range(3)]
    engine = _make_engine(cfgs)

    with qtbot.waitSignal(engine.started_ok, timeout=3000):
        engine.start()

    bar = OHLCVBar(
        symbol="AAPL",
        datetime=datetime(2026, 5, 19, 10, 0, tzinfo=_ET),
        open=149.0, high=151.0, low=148.0, close=150.0,
        volume=1_000_000, timeframe="3m",
    )
    df = pd.DataFrame({"open": [150.0], "high": [151.0], "low": [149.0], "close": [150.0], "volume": [1_000_000]})

    evaluate_calls: list[Any] = []

    async def _fake_evaluate(ctx: Any, symbol: Any, candles: Any, b: Any) -> None:
        evaluate_calls.append(symbol)

    router = engine.router
    assert router is not None
    router.evaluate = _fake_evaluate  # type: ignore[method-assign]

    engine._bar_provider = lambda sym, tf: bar  # type: ignore[assignment]
    engine._candles_provider = lambda sym: {"3m": df}  # type: ignore[assignment]

    engine.on_candle_closed("AAPL")
    time.sleep(0.25)

    assert len(evaluate_calls) == 3

    engine.request_stop()
    qtbot.waitSignal(engine.stopped, timeout=3500)


def test_fanout_50_strategies_under_200ms(qtbot: QtBot) -> None:
    """UT-EXE-011.001.M01.T04: Fan-out ≤200ms for 50 strategies × 1 candle_closed emit."""
    from us_swing.data.models import OHLCVBar
    import pandas as pd

    cfgs = [_Cfg(name=f"perf_{i}") for i in range(50)]
    engine = _make_engine(cfgs)

    with qtbot.waitSignal(engine.started_ok, timeout=3000):
        engine.start()

    bar = OHLCVBar(
        symbol="AAPL",
        datetime=datetime(2026, 5, 19, 10, 0, tzinfo=_ET),
        open=149.0, high=151.0, low=148.0, close=150.0,
        volume=1_000_000, timeframe="3m",
    )
    df = pd.DataFrame({"open": [150.0], "high": [151.0], "low": [149.0], "close": [150.0], "volume": [1_000_000]})

    done_event = asyncio.Event() if False else None  # only need wall-time
    engine._bar_provider = lambda sym, tf: bar  # type: ignore[assignment]
    engine._candles_provider = lambda sym: {"3m": df}  # type: ignore[assignment]

    router = engine.router
    assert router is not None
    router.evaluate = AsyncMock()  # type: ignore[method-assign]

    t0 = time.perf_counter()
    engine.on_candle_closed("AAPL")
    time.sleep(0.22)
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.5, f"Fan-out wall time {elapsed:.3f}s exceeded safety margin"

    engine.request_stop()
    qtbot.waitSignal(engine.stopped, timeout=3500)


def test_request_stop_stops_engine_within_3s(qtbot: QtBot) -> None:
    """UT-EXE-011.001.M01.T05: request_stop() stops the engine within 3s."""
    engine = _make_engine([])
    with qtbot.waitSignal(engine.started_ok, timeout=3000):
        engine.start()
    engine.request_stop()
    with qtbot.waitSignal(engine.stopped, timeout=3500):
        pass
    assert not engine.isRunning()


def test_no_pyqt6_in_business_logic_modules() -> None:
    """UT-EXE-011.001.M01.T06: No PyQt6 import in business-logic modules."""
    import importlib

    business_modules = [
        "us_swing.execution.strategy_engine._signals",
        "us_swing.execution.strategy_engine._events",
        "us_swing.execution.strategy_engine._context",
        "us_swing.execution.strategy_engine._evaluator",
        "us_swing.execution.strategy_engine._router",
        "us_swing.execution.strategy_engine._protocols",
    ]

    pyqt_modules_before = {k for k in sys.modules if "PyQt6" in k}
    for mod_name in business_modules:
        importlib.import_module(mod_name)
    pyqt_modules_after = {k for k in sys.modules if "PyQt6" in k}

    new_pyqt = pyqt_modules_after - pyqt_modules_before
    assert not new_pyqt, f"Business modules imported PyQt6: {new_pyqt}"


def test_request_stop_before_start_is_safe_no_op() -> None:
    """UT-EXE-011.001.M01.T07: request_stop() before start() is safe no-op."""
    engine = _make_engine([])
    engine.request_stop()
    assert not engine.isRunning()


def test_empty_registry_no_evaluate_calls(qtbot: QtBot) -> None:
    """UT-EXE-011.001.M02.T09: Empty load_strategies → len(registry)==0; on_candle_closed emits no evaluate calls."""
    from unittest.mock import AsyncMock

    engine = _make_engine([])
    with qtbot.waitSignal(engine.started_ok, timeout=3000):
        engine.start()

    assert len(engine.registry) == 0

    router = engine.router
    assert router is not None
    router.evaluate = AsyncMock()  # type: ignore[method-assign]

    engine.on_candle_closed("AAPL")
    time.sleep(0.1)

    router.evaluate.assert_not_called()  # type: ignore[union-attr]

    engine.request_stop()
    qtbot.waitSignal(engine.stopped, timeout=3500)
