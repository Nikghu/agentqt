"""
Module: MD-EXE-011.001.M04 — tests
Parent SRD: SRD-EXE-011.008 — SRD-EXE-011.013, SRD-EXE-013.001 — .008
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from us_swing.data.models import OHLCVBar
from us_swing.execution import ExecutionEnums
from us_swing.execution.strategy_engine._context import _StrategyContext
from us_swing.execution.strategy_engine._evaluator import ConditionEvaluator
from us_swing.execution.strategy_engine._events import (
    StrategySignalDropped,
    StrategySquaredOff,
)
from us_swing.execution.strategy_engine._protocols import (
    CanAllocateResult,
    FillEvent,
    RejectEvent,
    ValidationResult,
)
from us_swing.execution.strategy_engine._rex_counter import RexCounterRepository
from us_swing.execution.strategy_engine._router import _Router
from us_swing.execution.strategy_engine._signals import Action, TradeSignal

_ET = ZoneInfo("America/New_York")
_RUNNING = ExecutionEnums.StrategyRunState.RUNNING


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
    run_state: str = "RUNNING"


class _FakeCycleQuery:
    """In-memory TradeCycleQuery double for router tests."""

    def __init__(self) -> None:
        self.open_pairs: set[tuple[str, str]] = set()

    def has_open_cycle(self, strategy_id: str, symbol: str) -> bool:
        return (strategy_id, symbol) in self.open_pairs

    def open_cycles_for_strategy(self, strategy_id: str) -> tuple[Any, ...]:
        snaps: list[Any] = []
        for sid, sym in self.open_pairs:
            if sid == strategy_id:
                snap = MagicMock()
                snap.symbol = sym
                snap.strategy_id = sid
                snaps.append(snap)
        return tuple(snaps)

    def open_cycles(self) -> tuple[Any, ...]:
        return self.open_cycles_for_strategy("")

    def cycle(self, _cycle_id: int) -> Any:
        return None

    def history(self, **_kwargs: Any) -> tuple[Any, ...]:
        return ()


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
    cycle_query: _FakeCycleQuery | None = None,
) -> tuple[_Router, asyncio.Queue[TradeSignal], MagicMock, MagicMock, MagicMock, MagicMock, dict[str, _StrategyContext], _FakeCycleQuery]:
    c = cfg or _Cfg()
    ctx = _StrategyContext(cfg=c, run_state=_RUNNING)  # type: ignore[arg-type]
    registry: dict[str, _StrategyContext] = {c.name: ctx}

    queue: asyncio.Queue[TradeSignal] = asyncio.Queue()
    risk = MagicMock()
    risk.validate.return_value = ValidationResult(ok=risk_ok, qty=10, reason="risk_reject" if not risk_ok else "")
    risk.can_allocate.return_value = CanAllocateResult(ok=can_allocate_ok, reason="cap" if not can_allocate_ok else "")
    submitter = MagicMock()
    submitter.submit.return_value = 42
    pending = MagicMock()
    bus = MagicMock()

    cq = cycle_query or _FakeCycleQuery()

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
        cycle_query=cq,
    )
    return router, queue, risk, submitter, pending, bus, registry, cq


def _scheduled_clock() -> datetime:
    return datetime(2026, 5, 19, 10, 0, tzinfo=_ET)


@pytest.mark.asyncio
async def test_auto_auto_trade_entry_calls_risk_and_submitter() -> None:
    """UT-EXE-011.001.M04.T01: auto+auto_trade=True ENTRY → risk.validate called; submitter.submit called."""
    router, queue, risk, submitter, pending, bus, registry, _cq = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    bar = _make_bar()
    import pandas as pd
    candles: dict[str, pd.DataFrame] = {
        "3m": pd.DataFrame({"open": [150.0], "high": [151.0], "low": [149.0], "close": [150.0], "volume": [1_000_000]})
    }

    await router.evaluate(ctx, "AAPL", candles, bar)
    signal = await asyncio.wait_for(queue.get(), timeout=1.0)
    await router._dispatch(signal)

    risk.validate.assert_called_once()
    submitter.submit.assert_called_once()


@pytest.mark.asyncio
async def test_manual_mode_entry_goes_to_pending_not_submitter() -> None:
    """UT-EXE-011.001.M04.T02: manual mode ENTRY → pending.add called; submitter NOT called."""
    cfg = _Cfg(mode="manual")
    router, queue, _risk, submitter, pending, _bus, registry, _cq = _make_router(cfg=cfg, clock=_scheduled_clock)
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
    router, queue, _risk, submitter, pending, _bus, registry, _cq = _make_router(cfg=cfg, clock=_scheduled_clock)
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
async def test_duplicate_entry_in_flight_suppresses_signal(caplog: Any) -> None:
    """UT-EXE-011.001.M04.T04: Duplicate ENTRY when symbol already in_flight → no new signal; DEBUG log."""
    import logging
    router, queue, _risk, _sub, _pend, _bus, registry, _cq = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    ctx.in_flight.add("AAPL")
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
    router, queue, _risk, _sub, _pend, bus, registry, _cq = _make_router(
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
async def test_end_time_sweep_force_exits_intraday_open_cycle() -> None:
    """UT-EXE-011.001.M04.T06: Intraday past end_time → _force_exit fires for symbol with open cycle."""
    past_end = datetime(2026, 5, 19, 16, 0, tzinfo=_ET)
    router, queue, _risk, _sub, _pend, bus, registry, cq = _make_router(clock=lambda: past_end)
    ctx = list(registry.values())[0]
    cq.open_pairs.add((ctx.name, "AAPL"))

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
    router, queue, _risk, _sub, _pend, bus, registry, cq = _make_router(cfg=cfg, clock=lambda: past_end)
    ctx = list(registry.values())[0]
    cq.open_pairs.add((ctx.name, "AAPL"))

    await router._sweep_end_times()

    assert queue.empty()
    bus.publish.assert_not_called()


@pytest.mark.asyncio
async def test_emergency_stop_enqueues_exit_for_all_open_cycles() -> None:
    """UT-EXE-011.001.M04.T08: emergency_stop() enqueues EXIT for every open cycle across strategies."""
    router, queue, _risk, _sub, _pend, _bus, registry, cq = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    cq.open_pairs.add((ctx.name, "AAPL"))
    cq.open_pairs.add((ctx.name, "MSFT"))

    async def _drain() -> None:
        exits_seen = 0
        while exits_seen < 2:
            sig = await asyncio.wait_for(queue.get(), timeout=1.0)
            cq.open_pairs.discard((sig.strategy_id, sig.symbol))
            ctx.in_flight.discard(sig.symbol)
            queue.task_done()
            exits_seen += 1
        router._maybe_signal_quiesced()

    done, _ = await asyncio.wait(
        [asyncio.create_task(router.emergency_stop()), asyncio.create_task(_drain())],
        timeout=3.0,
        return_when=asyncio.ALL_COMPLETED,
    )
    assert len(done) == 2, "emergency_stop or drain task did not complete"
    assert not cq.open_pairs


def test_on_order_fill_clears_in_flight() -> None:
    """UT-EXE-011.001.M04.T09: on_order_fill clears in_flight flag for the symbol."""
    router, _q, _r, _s, _p, _b, registry, _cq = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    ctx.in_flight.add("AAPL")

    fill = FillEvent(
        strategy_id="test_strat",
        symbol="AAPL",
        is_entry=True,
        fill_price=150.0,
        fill_qty=10,
        order_id=1,
    )
    router.on_order_fill(fill)

    assert "AAPL" not in ctx.in_flight


def test_on_order_reject_clears_in_flight() -> None:
    """UT-EXE-011.001.M04.T10: on_order_reject clears in_flight flag for the symbol."""
    router, _q, _r, _s, _p, _b, registry, _cq = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    ctx.in_flight.add("AAPL")

    reject = RejectEvent(
        strategy_id="test_strat",
        symbol="AAPL",
        is_entry=True,
        reason="broker_reject",
    )
    router.on_order_reject(reject)

    assert "AAPL" not in ctx.in_flight


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
    cfg = _Cfg(rex_count=5)
    repo.decrement(cfg.name, "AAPL", init_value=0)  # forces remaining=-1
    router, queue, _r, _s, _p, bus, registry, _cq = _make_router(
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
    cfg = _Cfg(rex_count=5)
    router, queue, _r, _s, _p, _b, registry, _cq = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    ctx = list(registry.values())[0]
    bar = _make_bar()

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    assert not queue.empty()
    assert "AAPL" in ctx.in_flight


@pytest.mark.asyncio
async def test_rex_gate_allows_entry_when_counter_zero() -> None:
    """UT-EXE-011.001.M04.T13: gate allows entry when remaining == 0 (final allowed entry)."""
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=5)
    repo.decrement(cfg.name, "AAPL", init_value=1)  # remaining=0
    router, queue, _r, _s, _p, _b, registry, _cq = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    ctx = list(registry.values())[0]
    bar = _make_bar()

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    assert not queue.empty()
    assert "AAPL" in ctx.in_flight


def test_on_order_fill_entry_decrements_counter() -> None:
    """UT-EXE-011.001.M04.T14: on_order_fill(entry) calls decrement with cfg.rex_count."""
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=5)
    router, _q, _r, _s, _p, _b, _registry, _cq = _make_router(
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
async def test_rex_blocked_drop_does_not_change_in_flight() -> None:
    """UT-EXE-011.001.M04.T15: rex-blocked entry leaves in_flight set empty."""
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=5)
    repo.decrement(cfg.name, "AAPL", init_value=0)  # remaining=-1
    router, queue, _r, _s, _p, _b, registry, _cq = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    ctx = list(registry.values())[0]
    bar = _make_bar()
    assert "AAPL" not in ctx.in_flight

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    assert "AAPL" not in ctx.in_flight
    assert queue.empty()


def test_rex_count_zero_allows_first_blocks_second() -> None:
    """UT-EXE-011.001.M04.T16: rex_count=0 → first entry allowed, second blocked."""
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=0)
    router, _q, _r, _s, _p, _b, _registry, _cq = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    assert repo.get(cfg.name, "AAPL") is None
    fill = FillEvent(
        strategy_id=cfg.name,
        symbol="AAPL",
        is_entry=True,
        fill_price=150.0,
        fill_qty=10,
        order_id="ord-1",
    )
    router.on_order_fill(fill)
    assert repo.get(cfg.name, "AAPL") == -1


@pytest.mark.asyncio
async def test_rex_full_lifecycle_with_reset() -> None:
    """UT-EXE-011.001.M04.T17: end-to-end — rex_count=2 yields 3 entries, blocks the 4th, reset re-enables."""
    repo = _fresh_rex_repo()
    cfg = _Cfg(rex_count=2)
    router, queue, _r, _s, _p, bus, registry, _cq = _make_router(
        cfg=cfg, clock=_scheduled_clock, rex_counters=repo,
    )
    ctx = list(registry.values())[0]
    bar = _make_bar()

    async def _simulate_one_entry(order_id: str) -> bool:
        bus.reset_mock()
        ctx.in_flight.discard("AAPL")
        await router.evaluate(ctx, "AAPL", _candles_3m(), bar)
        if queue.empty():
            return False
        await queue.get()
        fill = FillEvent(
            strategy_id=cfg.name, symbol="AAPL", is_entry=True,
            fill_price=150.0, fill_qty=10, order_id=order_id,
        )
        router.on_order_fill(fill)
        return True

    assert await _simulate_one_entry("ord-1") is True
    assert repo.get(cfg.name, "AAPL") == 1
    assert await _simulate_one_entry("ord-2") is True
    assert repo.get(cfg.name, "AAPL") == 0
    assert await _simulate_one_entry("ord-3") is True
    assert repo.get(cfg.name, "AAPL") == -1

    assert await _simulate_one_entry("ord-4") is False
    assert any(
        getattr(arg[0][0], "reason", None) == "rex_limit"
        for arg in [c for c in bus.publish.call_args_list]
    )

    deleted = repo.reset(cfg.name)
    assert deleted == 1
    assert repo.get(cfg.name, "AAPL") is None
    assert await _simulate_one_entry("ord-5") is True
    assert repo.get(cfg.name, "AAPL") == 1


# ── user_id + qty propagation (SRD-EXE-011.020) ──────────────────────────────


def _make_router_with_uid(uid: int) -> tuple[_Router, asyncio.Queue[TradeSignal], dict[str, _StrategyContext], _FakeCycleQuery]:
    c = _Cfg()
    ctx = _StrategyContext(cfg=c, run_state=_RUNNING)  # type: ignore[arg-type]
    registry: dict[str, _StrategyContext] = {c.name: ctx}
    queue: asyncio.Queue[TradeSignal] = asyncio.Queue()
    risk = MagicMock()
    risk.validate.return_value = ValidationResult(ok=True, qty=10, reason="")
    risk.can_allocate.return_value = CanAllocateResult(ok=True, reason="")
    cq = _FakeCycleQuery()
    router = _Router(
        queue=queue,
        registry=registry,
        evaluator=ConditionEvaluator(),
        risk=risk,
        submitter=MagicMock(),
        pending=MagicMock(),
        bus=MagicMock(),
        clock=_scheduled_clock,
        user_id_provider=lambda: uid,
        cycle_query=cq,
    )
    return router, queue, registry, cq


@pytest.mark.asyncio
async def test_entry_signal_propagates_user_id_from_provider() -> None:
    """UT-EXE-011.001.M04.T18: SRD-EXE-011.020 — entry signal carries user_id from provider."""
    router, queue, registry, _cq = _make_router_with_uid(uid=7)
    ctx = list(registry.values())[0]
    bar = _make_bar()

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    signal = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert signal.action == Action.ENTRY
    assert signal.user_id == 7


@pytest.mark.asyncio
async def test_entry_signal_default_qty_is_one() -> None:
    """UT-EXE-011.001.M04.T19: SRD-EXE-011.020 — entry signal qty_recommended defaults to 1."""
    router, queue, registry, _cq = _make_router_with_uid(uid=1)
    ctx = list(registry.values())[0]
    bar = _make_bar()

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    signal = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert signal.qty_recommended == 1


@pytest.mark.asyncio
async def test_forced_exit_signal_carries_user_id() -> None:
    """UT-EXE-011.001.M04.T20: SRD-EXE-011.020 — forced EXIT (end-time sweep) carries user_id."""
    past_end = datetime(2026, 5, 19, 16, 0, tzinfo=_ET)
    c = _Cfg()
    ctx = _StrategyContext(cfg=c, run_state=_RUNNING)  # type: ignore[arg-type]
    registry: dict[str, _StrategyContext] = {c.name: ctx}
    queue: asyncio.Queue[TradeSignal] = asyncio.Queue()
    cq = _FakeCycleQuery()
    cq.open_pairs.add((c.name, "AAPL"))
    router = _Router(
        queue=queue,
        registry=registry,
        evaluator=ConditionEvaluator(),
        risk=MagicMock(),
        submitter=MagicMock(),
        pending=MagicMock(),
        bus=MagicMock(),
        clock=lambda: past_end,
        user_id_provider=lambda: 3,
        cycle_query=cq,
    )

    await router._sweep_end_times()

    signal = queue.get_nowait()
    assert signal.action == Action.EXIT
    assert signal.user_id == 3


# ── FO-EXE-013 run_state gating ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stopped_run_state_blocks_evaluation() -> None:
    """UT-EXE-011.001.M04.T21: SRD-EXE-013.004 — STOPPED run_state emits no signal."""
    router, queue, _r, _s, _p, _b, registry, _cq = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    ctx.run_state = ExecutionEnums.StrategyRunState.STOPPED
    bar = _make_bar()

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    assert queue.empty()


@pytest.mark.asyncio
async def test_squaring_off_run_state_blocks_router_evaluation() -> None:
    """UT-EXE-011.001.M04.T22: SRD-EXE-013.007 — SQUARING_OFF emits no ENTRY through router.evaluate."""
    router, queue, _r, _s, _p, _b, registry, _cq = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    ctx.run_state = ExecutionEnums.StrategyRunState.SQUARING_OFF
    bar = _make_bar()

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    assert queue.empty()


@pytest.mark.asyncio
async def test_running_no_open_cycle_emits_entry() -> None:
    """UT-EXE-011.001.M04.T23: SRD-EXE-013.005 — RUNNING + no open cycle evaluates entry."""
    router, queue, _r, _s, _p, _b, registry, _cq = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    ctx.run_state = ExecutionEnums.StrategyRunState.RUNNING
    bar = _make_bar()

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    sig = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert sig.action == Action.ENTRY


@pytest.mark.asyncio
async def test_running_with_open_cycle_evaluates_exit_only() -> None:
    """UT-EXE-011.001.M04.T24: SRD-EXE-013.006 — RUNNING + open cycle evaluates exit."""
    router, queue, _r, _s, _p, _b, registry, cq = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    cq.open_pairs.add((ctx.name, "AAPL"))
    bar = _make_bar()

    await router.evaluate(ctx, "AAPL", _candles_3m(), bar)

    sig = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert sig.action == Action.EXIT


@pytest.mark.asyncio
async def test_squaring_off_exit_enqueues_forced_exit_per_open_cycle() -> None:
    """UT-EXE-011.001.M04.T25: SRD-EXE-013.003 — squaring_off_exit emits forced EXIT per open cycle."""
    router, queue, _r, _s, _p, _b, registry, cq = _make_router(clock=_scheduled_clock)
    ctx = list(registry.values())[0]
    cq.open_pairs.add((ctx.name, "AAPL"))
    cq.open_pairs.add((ctx.name, "MSFT"))

    count = await router.squaring_off_exit(ctx)

    assert count == 2
    sigs = []
    while not queue.empty():
        sigs.append(queue.get_nowait())
    assert {s.symbol for s in sigs} == {"AAPL", "MSFT"}
    assert all(s.action == Action.EXIT for s in sigs)
    assert all(s.reason == "squaring_off" for s in sigs)
