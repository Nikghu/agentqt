"""Module: tests/execution/test_order_ingestion.py
Parent SRD: SRD-EXE-015.003, SRD-EXE-015.005

Reject and cancel feedback from ingestion back to the strategy engine.

Before this, a rejected or cancelled order updated the ledger and was forgotten
without telling the engine, so the symbol stayed in ``in_flight`` with its capital
reserved for the rest of the session — the strategy could never trade it again.

Uses a real SQLite database for the ``trades`` writes (no DB mocking) and
recording stubs for the non-DB collaborators.
"""
from __future__ import annotations

import os
import tempfile

import pytest
import sqlalchemy as sa

from us_swing.broker.broker import OrderEvent, OrderSide, OrderStatus
from us_swing.db.manager import DatabaseManager
from us_swing.db.schema import create_schema, trades
from us_swing.execution.order_ingestion import OrderContext, OrderIngestion
from us_swing.execution.strategy_engine._protocols import RejectEvent


class _StubCycles:
    def __init__(self) -> None:
        self.aborted: list[tuple[str, str]] = []

    def on_entry_fill(self, **k: object) -> None:
        return None

    def on_exit_fill(self, **k: object) -> None:
        return None

    def on_entry_failed(self, *a: object, **k: object) -> None:
        return None

    def abort_entry_order(self, order_id: str, reason: str) -> None:
        self.aborted.append((order_id, reason))

    def update_risk(self, *a: object, **k: object) -> None:
        return None

    def reload(self) -> None:
        return None


def _make_db() -> DatabaseManager:
    path = os.path.join(tempfile.mkdtemp(), "ingestion.db")
    mgr = DatabaseManager("sqlite:///" + path.replace(os.sep, "/"))
    create_schema(mgr._engine)
    return mgr


def _context(is_entry: bool = True) -> OrderContext:
    return OrderContext(
        broker_order_id = "1001",
        signal_id       = "sig-1",
        strategy_id     = "SUPERTREND",
        user_id         = 1,
        symbol          = "AAPL",
        side            = OrderSide.BUY if is_entry else OrderSide.SELL,
        is_entry        = is_entry,
        quantity        = 10,
        intended_price  = 100.0,
    )


def _wire(is_entry: bool = True):
    """Build ingestion over a real DB with a registered context."""
    mgr = _make_db()
    cycles = _StubCycles()
    rejects: list[RejectEvent] = []
    fills: list[object] = []
    ingestion = OrderIngestion(
        ledger      = mgr,
        fill_sink   = fills.append,
        reject_sink = rejects.append,
        cycles      = cycles,
    )
    ingestion.register(_context(is_entry))
    return mgr, ingestion, cycles, rejects, fills


def _event(status: OrderStatus, filled: int = 0, reason: str = "") -> OrderEvent:
    return OrderEvent(
        broker_order_id = "1001",
        client_ref      = "sig-1",
        status          = status,
        filled_quantity = filled,
        reason          = reason,
    )


class TestRejectFeedback:
    def test_entry_reject_notifies_the_engine(self) -> None:
        """UT-EXE-015.005.M01.T01: a rejected entry reaches the engine as a RejectEvent."""
        _mgr, ingestion, _cycles, rejects, _fills = _wire(is_entry=True)

        ingestion.on_order_event(_event(OrderStatus.REJECTED, reason="insufficient margin"))

        assert len(rejects) == 1
        ev = rejects[0]
        assert ev.strategy_id == "SUPERTREND"
        assert ev.symbol == "AAPL"
        assert ev.is_entry is True
        assert ev.reason == "insufficient margin"

    def test_entry_reject_aborts_the_cycle(self) -> None:
        """UT-EXE-015.005.M01.T02: a rejected entry still aborts its opening cycle."""
        _mgr, ingestion, cycles, _rejects, _fills = _wire(is_entry=True)

        ingestion.on_order_event(_event(OrderStatus.REJECTED))

        assert cycles.aborted == [("1001", "broker_reject")]

    def test_exit_reject_does_not_abort_the_cycle(self) -> None:
        """UT-EXE-015.005.M01.T03: the stock is still held, so the cycle stays open."""
        _mgr, ingestion, cycles, rejects, _fills = _wire(is_entry=False)

        ingestion.on_order_event(_event(OrderStatus.REJECTED, reason="no shares"))

        assert cycles.aborted == [], "an exit reject must not abort the cycle"
        assert len(rejects) == 1
        assert rejects[0].is_entry is False

    def test_reject_with_no_reason_still_carries_one(self) -> None:
        """UT-EXE-015.005.M01.T04: a blank broker reason falls back, never empty."""
        _mgr, ingestion, _cycles, rejects, _fills = _wire()

        ingestion.on_order_event(_event(OrderStatus.REJECTED, reason=""))

        assert rejects[0].reason == "broker_reject"

    def test_reject_emits_no_fill(self) -> None:
        """UT-EXE-015.005.M01.T05: a reject must never look like a fill."""
        _mgr, ingestion, _cycles, _rejects, fills = _wire()

        ingestion.on_order_event(_event(OrderStatus.REJECTED))

        assert fills == []


class TestCancelFeedback:
    def test_cancel_notifies_the_engine(self) -> None:
        """UT-EXE-015.005.M01.T06: a cancelled order releases the symbol too."""
        _mgr, ingestion, _cycles, rejects, _fills = _wire()

        ingestion.on_order_event(_event(OrderStatus.CANCELLED))

        assert len(rejects) == 1
        assert rejects[0].reason == "cancelled"
        assert rejects[0].symbol == "AAPL"

    def test_cancel_preserves_the_partial_fill_in_the_ledger(self) -> None:
        """UT-EXE-015.005.M01.T07: shares already filled stay recorded."""
        mgr, ingestion, _cycles, _rejects, _fills = _wire()

        ingestion.on_order_event(_event(OrderStatus.CANCELLED, filled=4))

        with mgr._engine.connect() as conn:
            filled = conn.execute(
                sa.select(trades.c.filled_quantity).where(trades.c.trade_id == "1001")
            ).scalar_one()
        assert filled == 4

    def test_cancel_does_not_abort_the_cycle(self) -> None:
        """UT-EXE-015.005.M01.T08: a cancel is not a reject — no abort."""
        _mgr, ingestion, cycles, _rejects, _fills = _wire(is_entry=True)

        ingestion.on_order_event(_event(OrderStatus.CANCELLED))

        assert cycles.aborted == []

    def test_fill_after_a_cancel_is_not_lost(self) -> None:
        """UT-EXE-015.005.M01.T11: TWS can cancel an order and fill it moments later.

        The cancel used to forget the order, so the fill that followed arrived
        for an unknown order and was discarded — the stock was held with nothing
        in the app to show for it.
        """
        mgr, ingestion, _cycles, rejects, fills = _wire(is_entry=True)

        ingestion.on_order_event(_event(OrderStatus.CANCELLED))
        ingestion.on_order_event(_event(OrderStatus.FILLED, filled=16))

        assert len(rejects) == 1, "the cancel must still release the symbol"
        assert len(fills) == 1, "the late fill was dropped"

        with mgr._engine.connect() as conn:
            filled = conn.execute(
                sa.select(trades.c.filled_quantity).where(trades.c.trade_id == "1001")
            ).scalar_one()
        assert filled == 16
        assert ingestion._context == {}, "the fill must release the context"



class TestSinkFailureIsContained:
    def test_a_raising_sink_does_not_break_ingestion(self) -> None:
        """UT-EXE-015.005.M01.T09: a sink failing on shutdown must not propagate."""
        mgr = _make_db()

        def _boom(_ev: RejectEvent) -> None:
            raise RuntimeError("event loop is closed")

        ingestion = OrderIngestion(
            ledger      = mgr,
            fill_sink   = lambda _f: None,
            reject_sink = _boom,
            cycles      = _StubCycles(),
        )
        ingestion.register(_context())

        ingestion.on_order_event(_event(OrderStatus.REJECTED))  # must not raise

    def test_context_is_released_even_when_the_sink_raises(self) -> None:
        """UT-EXE-015.005.M01.T10: the order context is forgotten before notifying."""
        mgr = _make_db()

        def _boom(_ev: RejectEvent) -> None:
            raise RuntimeError("event loop is closed")

        ingestion = OrderIngestion(
            ledger      = mgr,
            fill_sink   = lambda _f: None,
            reject_sink = _boom,
            cycles      = _StubCycles(),
        )
        ingestion.register(_context())

        ingestion.on_order_event(_event(OrderStatus.REJECTED))

        assert ingestion._context == {}


# ── FO-EXE-018 — order state by entry/exit & short reject ─────────────────────


class _EntryCaptureCycles(_StubCycles):
    def __init__(self) -> None:
        super().__init__()
        self.entry_calls: list[dict[str, object]] = []
        self.exit_calls: list[dict[str, object]] = []

    def on_entry_fill(self, **k: object) -> None:
        self.entry_calls.append(k)

    def on_exit_fill(self, **k: object) -> None:
        self.exit_calls.append(k)


def _short_wire(is_entry: bool):  # type: ignore[no-untyped-def]
    mgr = _make_db()
    cycles = _EntryCaptureCycles()
    ingestion = OrderIngestion(
        ledger      = mgr,
        fill_sink   = lambda _f: None,
        reject_sink = lambda _r: None,
        cycles      = cycles,
    )
    ingestion.register(OrderContext(
        broker_order_id = "1001",
        signal_id       = "sig-1",
        strategy_id     = "FADE",
        user_id         = 1,
        symbol          = "AAPL",
        side            = OrderSide.SELL if is_entry else OrderSide.BUY,
        is_entry        = is_entry,
        quantity        = 10,
        intended_price  = 100.0,
        direction       = "SHORT",
    ))
    return mgr, ingestion, cycles


def _order_state(mgr: DatabaseManager) -> str:
    with mgr._engine.connect() as conn:
        return str(conn.execute(
            sa.select(trades.c.order_state).where(trades.c.trade_id == "1001")
        ).scalar_one())


def _filled(status: OrderStatus, qty: int) -> OrderEvent:
    return OrderEvent(
        broker_order_id = "1001",
        client_ref      = "sig-1",
        status          = status,
        filled_quantity = qty,
        fill_price      = 100.0,
    )


class TestShortDirection:
    def test_short_entry_uses_entry_order_states(self) -> None:
        """UT-EXE-018.006.M07.T01: a SHORT entry (SELL) records entry order states and opens a SHORT cycle."""
        from us_swing.execution import ExecutionEnums as E

        mgr, ingestion, cycles = _short_wire(is_entry=True)

        ingestion.on_order_event(_filled(OrderStatus.PARTIAL_FILLED, 4))
        assert _order_state(mgr) == E.BuyOrderState.PARTIAL_FILLED.value
        ingestion.on_order_event(_filled(OrderStatus.FILLED, 10))
        assert _order_state(mgr) == E.BuyOrderState.FILLED.value

        assert [c["direction"] for c in cycles.entry_calls] == ["SHORT", "SHORT"]
        assert cycles.entry_calls[0]["order_state"] is E.BuyOrderState.PARTIAL_FILLED
        assert cycles.entry_calls[1]["order_state"] is E.BuyOrderState.FILLED

    def test_short_exit_uses_exit_order_states(self) -> None:
        """UT-EXE-018.006.M07.T02: a SHORT exit (BUY) passes the exit FILLED state that closes the cycle."""
        from us_swing.execution import ExecutionEnums as E

        mgr, ingestion, cycles = _short_wire(is_entry=False)

        ingestion.on_order_event(_filled(OrderStatus.FILLED, 10))

        assert _order_state(mgr) == E.SellOrderState.FILLED.value
        assert cycles.exit_calls[0]["order_state"] is E.SellOrderState.FILLED

    def test_rejected_short_entry_aborts_with_message(self, caplog: pytest.LogCaptureFixture) -> None:
        """UT-EXE-018.015.M07.T03: a rejected SHORT entry aborts the cycle and names the short sale."""
        _mgr, ingestion, cycles = _short_wire(is_entry=True)

        with caplog.at_level("WARNING"):
            ingestion.on_order_event(_event(OrderStatus.REJECTED, reason="not shortable"))

        assert cycles.aborted == [("1001", "broker_reject")]
        assert any(
            r.getMessage() == "[Orders] Short sale for AAPL was rejected by the broker"
            for r in caplog.records
        )

    def test_rejected_long_entry_has_no_short_message(self, caplog: pytest.LogCaptureFixture) -> None:
        """UT-EXE-018.015.M07.T04: a rejected LONG entry aborts without the short-sale message."""
        _mgr, ingestion, cycles, _rejects, _fills = _wire(is_entry=True)

        with caplog.at_level("WARNING"):
            ingestion.on_order_event(_event(OrderStatus.REJECTED, reason="no funds"))

        assert cycles.aborted == [("1001", "broker_reject")]
        assert not any("Short sale" in r.getMessage() for r in caplog.records)


# ── Catch-up of fills from an earlier session (SRD-EXE-015.011, ISS-EXE-0018) ──

class _ExitCaptureCycles(_StubCycles):
    def __init__(self) -> None:
        super().__init__()
        self.exits: list[dict[str, object]] = []

    def on_exit_fill(self, **k: object) -> None:
        self.exits.append(k)


class _CycleQuery:
    def __init__(self, cycles: list[object]) -> None:
        self._cycles = tuple(cycles)

    def open_cycles(self) -> tuple[object, ...]:
        return self._cycles


def _closing_hrl() -> object:
    from types import SimpleNamespace

    from us_swing.execution.trade_cycle._dto import TradeCycleState

    return SimpleNamespace(
        strategy_id="Chart plan - HRL", symbol="HRL", direction="LONG",
        exit_order_id=None, state=TradeCycleState.CLOSING,
    )


def _wire_catch_up(side: str, cycles_open: list[object]):  # type: ignore[no-untyped-def]
    from datetime import datetime

    from us_swing.data.models import TradeRecord

    mgr = _make_db()
    mgr.insert_trade(TradeRecord(
        trade_id="1764000000000", user_id=1, symbol="HRL", side=side, quantity=5,
        entry_price=21.41, mode="live", strategy_id="Chart plan - HRL",
        entry_time=datetime(2026, 11, 24, 13, 50, 22),
    ))
    cycles = _ExitCaptureCycles()
    fills: list[object] = []
    ingestion = OrderIngestion(
        ledger=mgr, fill_sink=fills.append, reject_sink=lambda _r: None,
        cycles=cycles, cycle_query=_CycleQuery(cycles_open),  # type: ignore[arg-type]
    )
    return mgr, ingestion, cycles, fills


def _caught_up(order_id: str = "1764000000000") -> OrderEvent:
    return OrderEvent(
        broker_order_id=order_id, client_ref="", status=OrderStatus.PARTIAL_FILLED,
        filled_quantity=5, fill_price=23.10,
    )


class TestCatchUp:
    def test_exit_fill_saves_row_and_closes_trade(self) -> None:
        """UT-EXE-015.011.M02.T01: a caught-up exit fill saves the row and closes the trade."""
        mgr, ingestion, cycles, fills = _wire_catch_up("SELL", [_closing_hrl()])

        ingestion.on_order_event(_caught_up())

        row = mgr.trade_by_id("1764000000000")
        assert row is not None
        assert (row.order_state, row.filled_quantity, row.exit_price) == ("FILLED", 5, 23.10)
        assert len(cycles.exits) == 1
        exit_call = cycles.exits[0]
        assert (exit_call["exit_order_id"], exit_call["exit_qty"], exit_call["exit_price"]) == (
            "1764000000000", 5, 23.10
        )
        assert exit_call["strategy_id"] == "Chart plan - HRL"
        assert fills == []

    def test_unknown_order_is_skipped(self) -> None:
        """UT-EXE-015.011.M02.T02: a fill for an order the app never saved is skipped."""
        mgr, ingestion, cycles, _fills = _wire_catch_up("SELL", [_closing_hrl()])

        ingestion.on_order_event(_caught_up("999"))

        assert mgr.trade_by_id("999") is None
        assert cycles.exits == []

    def test_repeat_closes_once(self) -> None:
        """UT-EXE-015.011.M02.T03: the same caught-up fill twice closes the trade once."""
        _mgr, ingestion, cycles, _fills = _wire_catch_up("SELL", [_closing_hrl()])

        ingestion.on_order_event(_caught_up())
        ingestion.on_order_event(_caught_up())

        assert len(cycles.exits) == 1

    def test_entry_fill_asks_user_to_check(self, caplog: pytest.LogCaptureFixture) -> None:
        """UT-EXE-015.011.M02.T04: a caught-up entry fill saves the row, closes nothing, warns."""
        mgr, ingestion, cycles, _fills = _wire_catch_up("BUY", [])

        with caplog.at_level("WARNING"):
            ingestion.on_order_event(_caught_up())

        row = mgr.trade_by_id("1764000000000")
        assert row is not None and (row.order_state, row.filled_quantity) == ("FILLED", 5)
        assert cycles.exits == []
        assert any(
            r.getMessage() == "[Orders] HRL BUY 5 share(s) filled while the app was away "
            "— check this trade in TWS"
            for r in caplog.records
        )
