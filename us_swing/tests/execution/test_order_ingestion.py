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
