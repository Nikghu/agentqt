"""
Module: MD-EXE-012.002.M02 — TradeCycleService tests
Parent SRD: SRD-EXE-012.002, .003, .004, .005, .006, .007, .008, .009, .011, .013
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from us_swing.db.schema import create_schema
from us_swing.execution._enums import ExecutionEnums
from us_swing.execution.trade_cycle._dto import (
    InvariantViolation,
    TradeCycleState,
)
from us_swing.execution.trade_cycle._events import (
    CycleAborted,
    CycleClosed,
    CycleOpened,
    CycleUpdated,
    ExitTrigger,
    RiskUpdated,
)
from us_swing.execution.trade_cycle._repository import TradeCycleRepository
from us_swing.execution.trade_cycle._service import TradeCycleService


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mem_engine() -> sa.Engine:
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_schema(eng)
    return eng


@pytest.fixture
def bus() -> MagicMock:
    return MagicMock()


@pytest.fixture
def svc(mem_engine: sa.Engine, bus: MagicMock):  # type: ignore[return]
    repo = TradeCycleRepository(mem_engine)
    service = TradeCycleService(repo=repo, bus=bus)
    service.start()
    yield service
    service.stop()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _entry_kwargs(**overrides: Any) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "strategy_id":             "boss_ema",
        "symbol":                  "AAPL",
        "user_id":                 1,
        "entry_order_id":          "ord-001",
        "entry_price":             182.5,
        "entry_qty":               25,
        "fill_time":               "2026-05-25T09:35:00",
        "hard_stop_loss":          179.0,
        "target_price":            190.0,
        "target_type":             "fixed",
        "stoploss_type":           "fixed",
        "trailing_mode":           None,
        "trailing_offset":         None,
        "monitoring_session_date": "2026-05-25",
    }
    kw.update(overrides)
    return kw


def _tick_and_flush(
    svc: TradeCycleService,
    cycle_id: int,
    symbol: str,
    price: float,
    timeout: float = 2.0,
) -> None:
    """Send one tick then force-flush its accumulator synchronously."""
    loop = svc._loop
    assert loop is not None and loop.is_running()

    async def _do() -> None:
        await svc._handle_tick(symbol, price)
        acc = svc._accs.get(cycle_id)
        if acc is not None and acc.dirty:
            await svc._flush(acc)

    asyncio.run_coroutine_threadsafe(_do(), loop).result(timeout=timeout)


def _published_of(bus: MagicMock, event_type: type) -> list[Any]:
    return [c[0][0] for c in bus.publish.call_args_list if isinstance(c[0][0], event_type)]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_on_entry_fill_opens_cycle_publishes_cycle_opened(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T01: on_entry_fill opens cycle and publishes exactly one CycleOpened."""
    snap = svc.on_entry_fill(**_entry_kwargs())
    assert snap.state == "OPEN"
    events = _published_of(bus, CycleOpened)
    assert len(events) == 1
    assert events[0].symbol == "AAPL"
    assert events[0].cycle_id == snap.cycle_id


def test_on_entry_fill_idempotent_on_entry_order_id(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T02: Duplicate on_entry_fill with same entry_order_id returns same snapshot."""
    snap1 = svc.on_entry_fill(**_entry_kwargs())
    snap2 = svc.on_entry_fill(**_entry_kwargs())
    assert snap1.cycle_id == snap2.cycle_id
    assert len(_published_of(bus, CycleOpened)) == 1


def test_on_entry_fill_filled_opens_cycle(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-014.007.M01.T01: A FILLED entry fill opens the cycle directly in OPEN."""
    snap = svc.on_entry_fill(
        **_entry_kwargs(order_state=ExecutionEnums.BuyOrderState.FILLED)
    )
    assert snap.state == TradeCycleState.OPEN


def test_on_entry_fill_partial_holds_opening(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-014.007.M01.T02: A PARTIAL_FILLED entry fill holds the cycle in OPENING."""
    snap = svc.on_entry_fill(
        **_entry_kwargs(order_state=ExecutionEnums.BuyOrderState.PARTIAL_FILLED)
    )
    assert snap.state == TradeCycleState.OPENING
    assert len(_published_of(bus, CycleOpened)) == 1
    assert len(_published_of(bus, CycleUpdated)) == 0


def test_on_entry_fill_partial_then_filled_transitions_to_open(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-014.007.M01.T03: The FILLED fill completing a held partial advances OPENING -> OPEN."""
    held = svc.on_entry_fill(
        **_entry_kwargs(order_state=ExecutionEnums.BuyOrderState.PARTIAL_FILLED)
    )
    assert held.state == TradeCycleState.OPENING

    opened = svc.on_entry_fill(
        **_entry_kwargs(order_state=ExecutionEnums.BuyOrderState.FILLED)
    )
    assert opened.cycle_id == held.cycle_id
    assert opened.state == TradeCycleState.OPEN
    updates = _published_of(bus, CycleUpdated)
    assert len(updates) == 1
    assert updates[0].cycle_id == held.cycle_id


def test_tick_updates_trailing_stop_only_upward(svc: TradeCycleService) -> None:
    """UT-EXE-012.002.M02.T03: Trailing stop advances on new high; stays put on pullback."""
    snap = svc.on_entry_fill(**_entry_kwargs(
        trailing_mode="$",
        trailing_offset=2.5,
        target_price=None,
    ))

    _tick_and_flush(svc, snap.cycle_id, "AAPL", 185.0)
    assert svc.cycle(snap.cycle_id).trailing_stop_level == pytest.approx(182.5)  # type: ignore[union-attr]

    _tick_and_flush(svc, snap.cycle_id, "AAPL", 188.0)
    assert svc.cycle(snap.cycle_id).trailing_stop_level == pytest.approx(185.5)  # type: ignore[union-attr]

    _tick_and_flush(svc, snap.cycle_id, "AAPL", 187.4)
    assert svc.cycle(snap.cycle_id).trailing_stop_level == pytest.approx(185.5)  # type: ignore[union-attr]


def test_effective_stop_equals_max_hard_sl_and_trailing(svc: TradeCycleService) -> None:
    """UT-EXE-012.002.M02.T04: effective_stop = max(hard_sl=179, trailing=185.5) = 185.5."""
    snap = svc.on_entry_fill(**_entry_kwargs(
        hard_stop_loss=179.0,
        trailing_mode="$",
        trailing_offset=2.5,
        target_price=None,
    ))
    _tick_and_flush(svc, snap.cycle_id, "AAPL", 188.0)
    fresh = svc.cycle(snap.cycle_id)
    assert fresh is not None
    assert fresh.effective_stop == pytest.approx(185.5)


def test_tick_at_effective_stop_publishes_exit_trigger_trailing_sl(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T05: price ≤ effective_stop with trailing floor → ExitTrigger(trailing_sl)."""
    snap = svc.on_entry_fill(**_entry_kwargs(
        hard_stop_loss=179.0,
        trailing_mode="$",
        trailing_offset=2.5,
        target_price=None,
    ))
    _tick_and_flush(svc, snap.cycle_id, "AAPL", 188.0)   # raise trailing to 185.5
    bus.reset_mock()

    _tick_and_flush(svc, snap.cycle_id, "AAPL", 185.4)   # triggers trailing_sl

    triggers = _published_of(bus, ExitTrigger)
    assert len(triggers) == 1
    assert triggers[0].reason == "trailing_sl"
    assert triggers[0].trigger_price == pytest.approx(185.4)


def test_tick_at_target_publishes_exit_trigger_target(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T06: price ≥ target_price → ExitTrigger(reason='target')."""
    snap = svc.on_entry_fill(**_entry_kwargs(target_price=190.0))
    bus.reset_mock()

    _tick_and_flush(svc, snap.cycle_id, "AAPL", 192.0)

    triggers = _published_of(bus, ExitTrigger)
    assert len(triggers) == 1
    assert triggers[0].reason == "target"


def test_both_target_and_stop_hit_target_takes_precedence(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T07: When price simultaneously hits target and stop, reason='target'."""
    snap = svc.on_entry_fill(**_entry_kwargs(
        entry_price=182.5,
        hard_stop_loss=185.0,
        target_price=185.0,
        trailing_mode=None,
        trailing_offset=None,
    ))
    bus.reset_mock()

    _tick_and_flush(svc, snap.cycle_id, "AAPL", 185.0)

    triggers = _published_of(bus, ExitTrigger)
    assert len(triggers) == 1
    assert triggers[0].reason == "target"


def test_second_tick_after_closing_emits_no_second_exit_trigger(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T08: After cycle enters CLOSING, subsequent ticks emit no ExitTrigger."""
    snap = svc.on_entry_fill(**_entry_kwargs(target_price=190.0))
    bus.reset_mock()

    _tick_and_flush(svc, snap.cycle_id, "AAPL", 192.0)    # triggers target, state→CLOSING
    assert len(_published_of(bus, ExitTrigger)) == 1
    bus.reset_mock()

    _tick_and_flush(svc, snap.cycle_id, "AAPL", 193.0)    # should be a no-op
    assert len(_published_of(bus, ExitTrigger)) == 0


def test_tick_throttle_limits_update_live_calls(svc: TradeCycleService) -> None:
    """UT-EXE-012.002.M02.T09: 100 rapid ticks → update_live called ≤ 3 times; last price reflected."""
    snap = svc.on_entry_fill(**_entry_kwargs(target_price=None))
    loop = svc._loop
    assert loop is not None

    call_count: list[int] = [0]
    original_update = svc._repo.update_live

    def _counting_update(cid: int, *, fields: dict) -> None:  # type: ignore[type-arg]
        call_count[0] += 1
        original_update(cid, fields=fields)

    svc._repo.update_live = _counting_update  # type: ignore[method-assign]

    async def _send_ticks() -> None:
        acc = svc._accs.get(snap.cycle_id)
        assert acc is not None
        acc.last_persist_at = asyncio.get_running_loop().time()  # reset throttle clock
        for i in range(100):
            await svc._handle_tick("AAPL", 183.0 + i * 0.01)
        await asyncio.sleep(0.65)   # wait for scheduled flush to fire

    asyncio.run_coroutine_threadsafe(_send_ticks(), loop).result(timeout=3.0)

    assert call_count[0] <= 3, f"Expected ≤ 3 update_live calls, got {call_count[0]}"
    fresh = svc.cycle(snap.cycle_id)
    assert fresh is not None and fresh.current_price is not None
    assert fresh.current_price > 183.0


def test_update_risk_valid_hard_sl_publishes_risk_updated(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T10: update_risk(hard_sl=valid) updates DB and publishes RiskUpdated."""
    snap = svc.on_entry_fill(**_entry_kwargs(entry_price=185.4, hard_stop_loss=181.0))
    bus.reset_mock()

    updated = svc.update_risk(snap.cycle_id, hard_sl=184.5)

    assert updated.hard_stop_loss == pytest.approx(184.5)
    risk_events = _published_of(bus, RiskUpdated)
    assert len(risk_events) == 1


def test_update_risk_hard_sl_above_current_price_raises(svc: TradeCycleService) -> None:
    """UT-EXE-012.002.M02.T11: update_risk(hard_sl > current_price) raises InvariantViolation."""
    snap = svc.on_entry_fill(**_entry_kwargs(entry_price=182.5))
    with pytest.raises(InvariantViolation):
        svc.update_risk(snap.cycle_id, hard_sl=200.0)


def test_update_risk_target_below_current_price_raises(svc: TradeCycleService) -> None:
    """UT-EXE-012.002.M02.T12: update_risk(target < current_price) raises InvariantViolation."""
    snap = svc.on_entry_fill(**_entry_kwargs(entry_price=185.4))
    with pytest.raises(InvariantViolation):
        svc.update_risk(snap.cycle_id, target=180.0)


def test_on_exit_fill_closes_cycle_and_publishes_cycle_closed(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T13: close_cycle_by_id freezes PnL, removes accumulator, publishes CycleClosed."""
    snap = svc.on_entry_fill(**_entry_kwargs())
    svc._repo.update_state(snap.cycle_id, "CLOSING")
    bus.reset_mock()

    closed = svc.close_cycle_by_id(
        snap.cycle_id,
        exit_order_id="exit-001",
        exit_price=187.8,
        exit_qty=25,
        exit_time="2026-05-25T10:00:00",
        exit_reason="target",
    )

    assert closed.state == "CLOSED"
    assert closed.realized_pnl_usd == pytest.approx(132.5, abs=0.01)
    assert snap.cycle_id not in svc._accs

    closed_events = _published_of(bus, CycleClosed)
    assert len(closed_events) == 1


def _exit_kwargs(**overrides: Any) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "exit_order_id": "exit-100",
        "exit_price":    187.8,
        "exit_qty":      25,
        "exit_time":     "2026-05-25T10:00:00",
        "exit_reason":   "target",
    }
    kw.update(overrides)
    return kw


def test_exit_fill_filled_finalises_closed(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-014.007.M02.T01: A FILLED sell finalises the cycle CLOSED."""
    snap = svc.on_entry_fill(**_entry_kwargs())
    closed = svc.close_cycle_by_id(
        snap.cycle_id,
        **_exit_kwargs(order_state=ExecutionEnums.SellOrderState.FILLED),
    )
    assert closed.state == TradeCycleState.CLOSED
    assert snap.cycle_id not in svc._accs


def test_exit_fill_partial_holds_closing(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-014.007.M02.T02: A PARTIAL_FILLED sell holds the cycle in CLOSING (not CLOSED)."""
    snap = svc.on_entry_fill(**_entry_kwargs())
    held = svc.close_cycle_by_id(
        snap.cycle_id,
        **_exit_kwargs(order_state=ExecutionEnums.SellOrderState.PARTIAL_FILLED),
    )
    assert held.state == TradeCycleState.CLOSING
    assert len(_published_of(bus, CycleClosed)) == 0


def test_exit_fill_partial_then_filled_finalises_closed(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-014.007.M02.T03: The FILLED sell completing a held partial advances CLOSING -> CLOSED."""
    snap = svc.on_entry_fill(**_entry_kwargs())

    held = svc.close_cycle_by_id(
        snap.cycle_id,
        **_exit_kwargs(order_state=ExecutionEnums.SellOrderState.PARTIAL_FILLED),
    )
    assert held.state == TradeCycleState.CLOSING

    closed = svc.close_cycle_by_id(
        snap.cycle_id,
        **_exit_kwargs(order_state=ExecutionEnums.SellOrderState.FILLED),
    )
    assert closed.cycle_id == snap.cycle_id
    assert closed.state == TradeCycleState.CLOSED
    assert len(_published_of(bus, CycleClosed)) == 1


def test_reload_reattaches_open_cycles_after_restart(
    mem_engine: sa.Engine, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T14: reload() attaches accumulators for all OPEN rows on a fresh service."""
    repo = TradeCycleRepository(mem_engine)
    snap1 = repo.insert_open(row={
        "strategy_id": "s1", "symbol": "AAPL", "user_id": 1,
        "monitoring_session_date": "2026-05-25",
        "entry_time": "2026-05-25T09:30:00", "entry_price": 182.5,
        "entry_qty": 25, "entry_order_id": "ord-r1",
        "hard_stop_loss": 179.0, "target_type": "fixed",
        "stoploss_type": "fixed", "state": "OPEN",
    })
    snap2 = repo.insert_open(row={
        "strategy_id": "s2", "symbol": "MSFT", "user_id": 1,
        "monitoring_session_date": "2026-05-25",
        "entry_time": "2026-05-25T09:30:00", "entry_price": 420.0,
        "entry_qty": 10, "entry_order_id": "ord-r2",
        "hard_stop_loss": 415.0, "target_type": "fixed",
        "stoploss_type": "fixed", "state": "OPEN",
    })

    new_svc = TradeCycleService(repo=repo, bus=bus)
    new_svc.start()
    try:
        new_svc.reload()
        assert snap1.cycle_id in new_svc._accs
        assert snap2.cycle_id in new_svc._accs
        assert "AAPL" in new_svc._accs_by_sym
        assert "MSFT" in new_svc._accs_by_sym
    finally:
        new_svc.stop()


def test_abort_entry_order_aborts_opening_cycle(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T16: abort_entry_order aborts a partial-filled OPENING cycle on reject."""
    held = svc.on_entry_fill(
        **_entry_kwargs(order_state=ExecutionEnums.BuyOrderState.PARTIAL_FILLED)
    )
    assert held.state == TradeCycleState.OPENING

    snap = svc.abort_entry_order("ord-001", "broker_reject")

    assert snap is not None
    assert snap.state == TradeCycleState.ABORTED
    aborted = _published_of(bus, CycleAborted)
    assert len(aborted) == 1
    assert aborted[0].cycle_id == held.cycle_id
    assert aborted[0].reason == "broker_reject"


def test_abort_entry_order_no_cycle_is_noop(
    svc: TradeCycleService, bus: MagicMock
) -> None:
    """UT-EXE-012.002.M02.T17: abort_entry_order is a no-op when no cycle was opened."""
    snap = svc.abort_entry_order("never-filled", "broker_reject")

    assert snap is None
    assert _published_of(bus, CycleAborted) == []


def test_no_pyqt6_import_under_trade_cycle() -> None:
    """UT-EXE-012.002.M02.T15: No module under trade_cycle/ imports PyQt6."""
    import importlib

    modules = [
        "us_swing.execution.trade_cycle._dto",
        "us_swing.execution.trade_cycle._schema",
        "us_swing.execution.trade_cycle._events",
        "us_swing.execution.trade_cycle._protocols",
        "us_swing.execution.trade_cycle._repository",
        "us_swing.execution.trade_cycle._service",
    ]

    pyqt_before = {k for k in sys.modules if "PyQt6" in k}
    for mod in modules:
        importlib.import_module(mod)
    pyqt_after = {k for k in sys.modules if "PyQt6" in k}

    new_pyqt = pyqt_after - pyqt_before
    assert not new_pyqt, f"trade_cycle modules imported PyQt6: {new_pyqt}"
