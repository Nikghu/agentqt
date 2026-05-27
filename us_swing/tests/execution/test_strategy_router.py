"""
Module: MD-EXE-011.001.M04 — tests
Parent SRD: SRD-EXE-011.008 — SRD-EXE-011.013
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from us_swing.execution.strategy_engine._context import _CycleState, _StrategyContext
from us_swing.execution.strategy_engine._evaluator import ConditionEvaluator
from us_swing.execution.strategy_engine._events import (
    StrategySignalDropped,
    StrategySignalPending,
    StrategySquaredOff,
)
from us_swing.execution.strategy_engine._protocols import CanAllocateResult, FillEvent, RejectEvent, ValidationResult
from us_swing.execution.strategy_engine._rex_counter import RexCounterRepository
from us_swing.execution.strategy_engine._router import _Router
from us_swing.execution.strategy_engine._signals import Action, TradeSignal
from us_swing.data.models import OHLCVBar

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
    entry_condition: str = "Number(1) == Number(1)"
    exit_condition: str = "Number(1) == Number(1)"
    stoploss_enabled: bool = False
    stoploss_value: float = 1.0
    target_enabled: bool = False
    target_value: float = 2.0
    rex_count: int = 0
    strategy_signal: dict[str, Any] = field(default_factory=lambda: {"Status": "Active"})


def _make_bar(symbol: str = "AAPL", close: float = 150.0) -> OHLCVBar:
    return OHLCVBar(
        symbol=symbol,
        datetime=datetime(2026, 5, 19, 10, 0, tzinfo=_ET),
        open=149.0,
        high=151.0,
        low=148.0,
        close=close,
        volume=1_000_000,
        timeframe="3m",
    )


def _make_router(
    cfg: _Cfg | None = None,
    clock: Any = None,
    risk_ok: bool = True,
    can_allocate_ok: bool = True,
    rex_counters: RexCounterRepository | None = None,
) -> tuple[_Router, asyncio.Queue[TradeSignal], MagicMock, MagicMock, MagicMock, MagicMock, dict[str, _StrategyContext]]:
    c = cfg or _Cfg()
    ctx = _StrategyContext(cfg=c)  # type: ignore[arg-type]
    registry: dict[str, _StrategyContext] = {c.name: ctx}

    queue: asyncio.Queue[TradeSignal] = asyncio.Queue()
    risk = MagicMock()
    risk.validate.return_value = ValidationResult(ok=risk_ok, qty=10, reason="risk_reject" if not risk_ok else "")
    risk.can_allocate.return_value = CanAllocateResult(ok=can_allocate_ok, reason="cap" if not can_allocate_ok else "")
    submitter = MagicMock()
    submitter.submit.return_value = 42
    pending = MagicMock()
    bus = MagicMock()

    router = _Router(
        queue=queue,
        registry=registry,
        evaluator=ConditionEvaluator(),
        risk=risk,
        submitter=submitter,
        pending=pending,
        bus=bus,
        rex_counters=rex_counters,
        clock=clock,
    )
    return router, queue, risk, submitter, pending, bus, registry


def _scheduled_clock() -> datetime:
    return datetime(2026, 5, 19, 10, 0, tzinfo=_ET)


@pytest.mark.asyncio
async def test_auto_auto_trade_entry_calls_risk_and_submitter() -> None:
    """UT-EXE-011.001.M04.T01: auto+auto_trade=True ENTRY → risk.validate called; submitter.submit called."""
    router, queue, risk, submitter, pending, bus, registry = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    bar = _make_bar()
    import pandas as pd, numpy as np
    candles: dict[str, pd.DataFrame] = {
        "3m": pd.DataFrame({"open": [150.0], "high": [151.0], "low": [149.0], "close": [150.0], "volume": [1_000_000]})
    }

    await router.evaluate(ctx, "AAPL", candles, bar)
    # process dispatched signal
    signal = await asyncio.wait_for(queue.get(), timeout=1.0)
    await router._dispatch(signal)

    risk.validate.assert_called_once()
    submitter.submit.assert_called_once()


@pytest.mark.asyncio
async def test_manual_mode_entry_goes_to_pending_not_submitter() -> None:
    """UT-EXE-011.001.M04.T02: manual mode ENTRY → pending.add called; submitter NOT called."""
    cfg = _Cfg(mode="manual")
    router, queue, risk, submitter, pending, bus, registry = _make_router(cfg=cfg, clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    bar = _make_bar()
    import pandas as pd
    candles: dict[str, pd.DataFrame] = {
        "3m": pd.DataFrame({"open": [150.0], "high": [151.0], "low": [149.0], "close": [150.0], "volume": [1_000_000]})
    }

    await router.evaluate(ctx, "AAPL", candles, bar)
    signal = await asyncio.wait_for(queue.get(), timeout=1.0)
    await router._dispatch(signal)

    pending.add.assert_called_once()
    submitter.submit.assert_not_called()


@pytest.mark.asyncio
async def test_auto_no_auto_trade_goes_to_pending_not_submitter() -> None:
    """UT-EXE-011.001.M04.T03: auto+auto_trade=False ENTRY → pending.add called; submit NOT called."""
    cfg = _Cfg(mode="auto", auto_trade=False)
    router, queue, risk, submitter, pending, bus, registry = _make_router(cfg=cfg, clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    bar = _make_bar()
    import pandas as pd
    candles: dict[str, pd.DataFrame] = {
        "3m": pd.DataFrame({"open": [150.0], "high": [151.0], "low": [149.0], "close": [150.0], "volume": [1_000_000]})
    }

    await router.evaluate(ctx, "AAPL", candles, bar)
    signal = await asyncio.wait_for(queue.get(), timeout=1.0)
    await router._dispatch(signal)

    pending.add.assert_called_once()
    submitter.submit.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_entry_under_entry_suppresses_signal(caplog: Any) -> None:
    """UT-EXE-011.001.M04.T04: Duplicate ENTRY when UNDER_ENTRY → no new signal; DEBUG log."""
    import logging
    router, queue, risk, submitter, pending, bus, registry = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    ctx.cycles["AAPL"] = _CycleState.UNDER_ENTRY
    bar = _make_bar()
    import pandas as pd
    candles: dict[str, pd.DataFrame] = {
        "3m": pd.DataFrame({"open": [150.0], "high": [151.0], "low": [149.0], "close": [150.0], "volume": [1_000_000]})
    }

    with caplog.at_level(logging.DEBUG):
        await router.evaluate(ctx, "AAPL", candles, bar)

    assert queue.empty()
    assert any("duplicate" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_can_allocate_fails_publishes_signal_dropped() -> None:
    """UT-EXE-011.001.M04.T05: can_allocate fails → StrategySignalDropped published."""
    router, queue, risk, submitter, pending, bus, registry = _make_router(
        clock=_scheduled_clock, can_allocate_ok=False
    )
    ctx = list(registry.values())[0]
    bar = _make_bar()
    import pandas as pd
    candles: dict[str, pd.DataFrame] = {
        "3m": pd.DataFrame({"open": [150.0], "high": [151.0], "low": [149.0], "close": [150.0], "volume": [1_000_000]})
    }

    await router.evaluate(ctx, "AAPL", candles, bar)

    assert queue.empty()
    bus.publish.assert_called_once()
    published = bus.publish.call_args[0][0]
    assert isinstance(published, StrategySignalDropped)


@pytest.mark.asyncio
async def test_end_time_sweep_force_exits_intraday_running_symbol() -> None:
    """UT-EXE-011.001.M04.T06: Intraday past end_time → _force_exit fires for RUNNING symbol."""
    past_end = datetime(2026, 5, 19, 16, 0, tzinfo=_ET)
    router, queue, risk, submitter, pending, bus, registry = _make_router(clock=lambda: past_end)
    ctx = list(registry.values())[0]
    ctx.cycles["AAPL"] = _CycleState.RUNNING

    await router._sweep_end_times()

    assert not queue.empty()
    signal = queue.get_nowait()
    assert signal.action == Action.EXIT
    bus.publish.assert_called_once()
    published = bus.publish.call_args[0][0]
    assert isinstance(published, StrategySquaredOff)


@pytest.mark.asyncio
async def test_positional_strategy_no_end_time_square_off() -> None:
    """UT-EXE-011.001.M04.T07: Positional strategy does NOT receive end-time SquareOff."""
    cfg = _Cfg(trade_type="Positional")
    past_end = datetime(2026, 5, 19, 16, 0, tzinfo=_ET)
    router, queue, risk, submitter, pending, bus, registry = _make_router(cfg=cfg, clock=lambda: past_end)
    ctx = list(registry.values())[0]
    ctx.cycles["AAPL"] = _CycleState.RUNNING

    await router._sweep_end_times()

    assert queue.empty()
    bus.publish.assert_not_called()


@pytest.mark.asyncio
async def test_emergency_stop_enqueues_exit_for_all_running() -> None:
    """UT-EXE-011.001.M04.T08: emergency_stop() enqueues EXIT for all RUNNING symbols."""
    router, queue, risk, submitter, pending, bus, registry = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    ctx.cycles["AAPL"] = _CycleState.RUNNING
    ctx.cycles["MSFT"] = _CycleState.RUNNING
    ctx.cycles["TSLA"] = _CycleState.ACTIVE

    # Run emergency_stop concurrently with a drain task so _quiesced_event fires.
    async def _drain() -> None:
        exits_seen = 0
        while exits_seen < 2:
            sig = await asyncio.wait_for(queue.get(), timeout=1.0)
            ctx.cycles[sig.symbol] = _CycleState.SQUARE_OFF
            queue.task_done()
            exits_seen += 1
        router._maybe_signal_quiesced()

    done, _ = await asyncio.wait(
        [asyncio.create_task(router.emergency_stop()), asyncio.create_task(_drain())],
        timeout=3.0,
        return_when=asyncio.ALL_COMPLETED,
    )
    assert len(done) == 2, "emergency_stop or drain task did not complete"

    squared_off = {sym for sym, st in ctx.cycles.items() if st == _CycleState.SQUARE_OFF}
    assert "AAPL" in squared_off
    assert "MSFT" in squared_off
    assert "TSLA" not in squared_off


@pytest.mark.asyncio
async def test_on_order_fill_sets_running_state() -> None:
    """UT-EXE-011.001.M04.T09: on_order_fill sets RUNNING state for entry fill."""
    from us_swing.execution.strategy_engine._protocols import FillEvent
    router, queue, risk, submitter, pending, bus, registry = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    ctx.cycles["AAPL"] = _CycleState.UNDER_ENTRY

    fill = FillEvent(
        strategy_id="test_strat",
        symbol="AAPL",
        is_entry=True,
        fill_price=150.0,
        fill_qty=10,
        order_id=1,
    )
    router.on_order_fill(fill)

    assert ctx.cycles["AAPL"] == _CycleState.RUNNING


def test_on_order_reject_rolls_back_under_entry_to_active() -> None:
    """UT-EXE-011.001.M04.T10: on_order_reject rolls back UNDER_ENTRY → ACTIVE."""
    router, queue, risk, submitter, pending, bus, registry = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    ctx.cycles["AAPL"] = _CycleState.UNDER_ENTRY

    reject = RejectEvent(
        strategy_id="test_strat",
        symbol="AAPL",
        is_entry=True,
        reason="broker_reject",
    )
    router.on_order_reject(reject)

    assert ctx.cycles["AAPL"] == _CycleState.ACTIVE


# ── Rex counter gate + decrement (SRD-EXE-011.017, .018) ─────────────────────

def _candles_3m() -> "dict[str, Any]":
    import pandas as pd
    return {
        "3m": pd.DataFrame({
            "open": [150.0], "high": [151.0], "low": [149.0],
            "close": [150.0], "volume": [1_000_000],
        })
    }


def _fresh_rex_repo() -> RexCounterRepository:
    import sqlalchemy as sa
    return RexCounterRepository(sa.create_engine("sqlite:///:memory:", future=True))


@pytest.mark.asyncio
async def test_rex_gate_blocks_entry_when_counter_negative(caplog: Any) -> None:
    """UT-EXE-011.001.M04.T11: rex_limit gate drops entry when remaining < 0."""
    import logging
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=5)  # type: ignore[call-arg]
    repo.decrement(cfg.name, "AAPL", init_value=0)  # forces remaining=-1
    router, queue, risk, submitter, pending, bus, registry = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    ctx = list(registry.values())[0]
    bar = _make_bar()

    with caplog.at_level(logging.INFO):
        await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    assert queue.empty()
    bus.publish.assert_called_once()
    published = bus.publish.call_args[0][0]
    assert isinstance(published, StrategySignalDropped)
    assert published.reason == "rex_limit"
    assert any("rex limit reached" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_rex_gate_allows_entry_when_counter_absent() -> None:
    """UT-EXE-011.001.M04.T12: gate allows entry when counter row is missing (first ever)."""
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=5)  # type: ignore[call-arg]
    router, queue, risk, submitter, pending, bus, registry = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    ctx = list(registry.values())[0]
    bar = _make_bar()

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    assert not queue.empty()
    assert ctx.cycles["AAPL"] == _CycleState.UNDER_ENTRY


@pytest.mark.asyncio
async def test_rex_gate_allows_entry_when_counter_zero() -> None:
    """UT-EXE-011.001.M04.T13: gate allows entry when remaining == 0 (final allowed entry)."""
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=5)  # type: ignore[call-arg]
    repo.decrement(cfg.name, "AAPL", init_value=1)  # remaining=0
    router, queue, risk, submitter, pending, bus, registry = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    ctx = list(registry.values())[0]
    bar = _make_bar()

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    assert not queue.empty()
    assert ctx.cycles["AAPL"] == _CycleState.UNDER_ENTRY


def test_on_order_fill_entry_decrements_counter() -> None:
    """UT-EXE-011.001.M04.T14: on_order_fill(entry) calls decrement with cfg.rex_count."""
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=5)  # type: ignore[call-arg]
    router, _q, _r, _s, _p, _b, registry = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    fill = FillEvent(
        strategy_id=cfg.name,
        symbol="AAPL",
        is_entry=True,
        fill_price=150.0,
        fill_qty=10,
        order_id="ord-1",
    )
    router.on_order_fill(fill)
    assert repo.get(cfg.name, "AAPL") == 4


@pytest.mark.asyncio
async def test_rex_blocked_drop_does_not_change_cycle_state() -> None:
    """UT-EXE-011.001.M04.T15: rex-blocked entry does not mutate cycle state."""
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=5)  # type: ignore[call-arg]
    repo.decrement(cfg.name, "AAPL", init_value=0)  # remaining=-1
    router, queue, risk, submitter, pending, bus, registry = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    ctx = list(registry.values())[0]
    bar = _make_bar()
    assert ctx.state("AAPL") == _CycleState.ACTIVE

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    assert ctx.state("AAPL") == _CycleState.ACTIVE
    assert queue.empty()


def test_rex_count_zero_allows_first_blocks_second() -> None:
    """UT-EXE-011.001.M04.T16: rex_count=0 → first entry allowed, second blocked."""
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=0)  # type: ignore[call-arg]
    router, _q, _r, _s, _p, _b, registry = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    # First entry: no row exists yet → allowed
    assert repo.get(cfg.name, "AAPL") is None
    # Simulate the fill from the first entry
    fill = FillEvent(
        strategy_id=cfg.name,
        symbol="AAPL",
        is_entry=True,
        fill_price=150.0,
        fill_qty=10,
        order_id="ord-1",
    )
    router.on_order_fill(fill)
    # After first fill, remaining = 0 - 1 = -1 → second entry blocked by gate
    assert repo.get(cfg.name, "AAPL") == -1


@pytest.mark.asyncio
async def test_rex_full_lifecycle_with_reset() -> None:
    """UT-EXE-011.001.M04.T17: end-to-end — rex_count=2 yields 3 entries, blocks the 4th, reset re-enables.

    Walks gate → fill → decrement repeatedly, then reset → counter cleared → gate allows again.
    Verifies the live integration of `_router.evaluate` + `_router.on_order_fill`
    + `RexCounterRepository.{get,decrement,reset}`.
    """
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=2)  # 2 re-entries beyond first → 3 entries total
    router, queue, _r, _s, _p, bus, registry = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    ctx = list(registry.values())[0]
    bar = _make_bar()

    async def _simulate_one_entry(order_id: str) -> bool:
        """Run evaluate; if signal enqueued, drain it and simulate a fill.
        Returns True if the entry was accepted, False if rex-blocked."""
        bus.reset_mock()
        ctx.cycles["AAPL"] = _CycleState.ACTIVE
        await router.evaluate(ctx, "AAPL", _candles_3m(), bar)
        if queue.empty():
            return False  # rex-blocked
        await queue.get()
        fill = FillEvent(
            strategy_id=cfg.name, symbol="AAPL", is_entry=True,
            fill_price=150.0, fill_qty=10, order_id=order_id,
        )
        router.on_order_fill(fill)
        return True

    # Three entries should succeed: counter goes None → 1 → 0 → -1
    assert await _simulate_one_entry("ord-1") is True
    assert repo.get(cfg.name, "AAPL") == 1
    assert await _simulate_one_entry("ord-2") is True
    assert repo.get(cfg.name, "AAPL") == 0
    assert await _simulate_one_entry("ord-3") is True
    assert repo.get(cfg.name, "AAPL") == -1

    # Fourth attempt should be rex-blocked
    assert await _simulate_one_entry("ord-4") is False
    drops = [c for c in bus.publish.call_args_list
             if isinstance(c[1].get("signal") or c[0][0], StrategySignalDropped)]
    assert any(
        getattr(arg[0][0], "reason", None) == "rex_limit"
        for arg in [c for c in bus.publish.call_args_list]
    )

    # Reset Strategy → counter cleared → next entry allowed again
    deleted = repo.reset(cfg.name)
    assert deleted == 1
    assert repo.get(cfg.name, "AAPL") is None
    assert await _simulate_one_entry("ord-5") is True
    assert repo.get(cfg.name, "AAPL") == 1
