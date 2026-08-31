"""Module: tests/broker/test_broker_contract.py
Parent SRD: SRD-INF-009.004, SRD-INF-009.006

Broker contract suite (Broker_fix.md Phase 3).  The same scenarios run against
every concrete :class:`Broker`; passing this suite is what declares two brokers
interchangeable.  Phase 4 adds ``IBKRBroker`` to ``BROKER_FACTORIES`` and the
whole suite re-runs against it unchanged.
"""
from __future__ import annotations

from collections.abc import Callable

import pytest

from us_swing.broker.broker import (
    Broker,
    OrderEvent,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
)
from us_swing.broker.ibkr import IBKRBroker, IbkrOrderUpdate
from us_swing.broker.sim import ImmediateFillModel, ScriptedFillModel, SimBroker


class _ManualScheduler:
    """Collects deferred callbacks; ``pump()`` runs them, proving fills are
    delivered only *after* ``place_order`` has returned."""

    def __init__(self) -> None:
        self._queue: list[Callable[[], None]] = []

    def __call__(self, callback: Callable[[], None]) -> None:
        self._queue.append(callback)

    def pump(self) -> None:
        while self._queue:
            self._queue.pop(0)()


def _market_buy(qty: int = 10, ref: float = 50.0) -> OrderRequest:
    return OrderRequest(
        client_ref="sig-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=qty,
        reference_price=ref,
    )


class _FakeGateway:
    """In-process OrderGateway driving scripted IBKR updates via a scheduler."""

    def __init__(
        self,
        scheduler: _ManualScheduler,
        script: list[tuple[str, int, float]],
    ) -> None:
        self._schedule = scheduler
        self._script = script
        self._callback: Callable[[IbkrOrderUpdate], None] | None = None
        self._next = 7000
        self._cancelled: set[str] = set()

    def on_status(self, callback: Callable[[IbkrOrderUpdate], None]) -> None:
        self._callback = callback

    def submit(self, symbol, side, quantity, order_type, limit_price) -> str:  # type: ignore[no-untyped-def]
        order_id = str(self._next)
        self._next += 1
        self._schedule(lambda: self._run(order_id))
        return order_id

    def cancel(self, broker_order_id: str) -> None:
        self._cancelled.add(broker_order_id)

    def _run(self, order_id: str) -> None:
        assert self._callback is not None
        if order_id in self._cancelled:
            self._callback(IbkrOrderUpdate(order_id, "Cancelled", 0, 0.0))
            return
        for status, filled, price in self._script:
            self._callback(IbkrOrderUpdate(order_id, status, filled, price))


def _sim(model: object) -> tuple[SimBroker, _ManualScheduler]:
    scheduler = _ManualScheduler()
    return SimBroker(model, scheduler=scheduler), scheduler  # type: ignore[arg-type]


def _ibkr(script: list[tuple[str, int, float]]) -> tuple[IBKRBroker, _ManualScheduler]:
    scheduler = _ManualScheduler()
    return IBKRBroker(_FakeGateway(scheduler, script)), scheduler


# Each factory builds (broker, scheduler).  The same fixture-based scenarios run
# against every concrete broker — this is the equivalence gate.
BROKER_FACTORIES: list[Callable[[], tuple[Broker, _ManualScheduler]]] = [
    lambda: _sim(ImmediateFillModel()),
    lambda: _ibkr([("Filled", 10, 50.0)]),
]


@pytest.fixture(params=BROKER_FACTORIES)
def broker_pair(request: pytest.FixtureRequest) -> tuple[Broker, _ManualScheduler]:
    return request.param()


def _collect(broker: Broker) -> list[OrderEvent]:
    events: list[OrderEvent] = []
    broker.on_event(events.append)
    return events


def test_place_order_returns_before_any_fill(broker_pair: tuple[Broker, _ManualScheduler]) -> None:
    """SRD-INF-009.004: acceptance only — no event before the scheduler runs."""
    broker, scheduler = broker_pair
    events = _collect(broker)
    order_id = broker.place_order(_market_buy())
    assert order_id
    assert events == []
    scheduler.pump()
    assert len(events) == 1


def test_full_fill(broker_pair: tuple[Broker, _ManualScheduler]) -> None:
    """SRD-INF-009.006: a market order fills fully in one FILLED event."""
    broker, scheduler = broker_pair
    events = _collect(broker)
    broker.place_order(_market_buy(qty=10))
    scheduler.pump()
    assert [e.status for e in events] == [OrderStatus.FILLED]
    assert events[0].filled_quantity == 10
    assert events[0].fill_price == 50.0


def test_client_ref_is_echoed(broker_pair: tuple[Broker, _ManualScheduler]) -> None:
    broker, scheduler = broker_pair
    events = _collect(broker)
    broker.place_order(_market_buy())
    scheduler.pump()
    assert events[0].client_ref == "sig-1"


def test_order_ids_unique(broker_pair: tuple[Broker, _ManualScheduler]) -> None:
    broker, _ = broker_pair
    first = broker.place_order(_market_buy())
    second = broker.place_order(_market_buy())
    assert first != second


def test_partial_then_fill() -> None:
    """SRD-INF-009.004: scripted partial fill emits PARTIAL_FILLED then FILLED."""
    scheduler = _ManualScheduler()
    model = ScriptedFillModel(
        steps=((OrderStatus.PARTIAL_FILLED, 4), (OrderStatus.FILLED, 10)),
        price=50.0,
    )
    broker = SimBroker(model, scheduler=scheduler)
    events = _collect(broker)
    broker.place_order(_market_buy(qty=10))
    scheduler.pump()
    assert [(e.status, e.filled_quantity) for e in events] == [
        (OrderStatus.PARTIAL_FILLED, 4),
        (OrderStatus.FILLED, 10),
    ]


def test_rejected() -> None:
    """SRD-INF-009.004: a rejection emits one REJECTED with zero fill."""
    scheduler = _ManualScheduler()
    broker = SimBroker(
        ScriptedFillModel(steps=((OrderStatus.REJECTED, 0),)),
        scheduler=scheduler,
    )
    events = _collect(broker)
    broker.place_order(_market_buy())
    scheduler.pump()
    assert len(events) == 1
    assert events[0].status is OrderStatus.REJECTED
    assert events[0].filled_quantity == 0
    assert events[0].reason


def test_cancel_before_fill() -> None:
    """SRD-INF-009.004: cancelling an accepted order yields a CANCELLED event."""
    scheduler = _ManualScheduler()
    broker = SimBroker(ImmediateFillModel(), scheduler=scheduler)
    events = _collect(broker)
    order_id = broker.place_order(_market_buy())
    broker.cancel_order(order_id)
    scheduler.pump()
    assert [e.status for e in events] == [OrderStatus.CANCELLED]
    assert events[0].filled_quantity == 0


def test_sell_side_slippage() -> None:
    """A sell fills below the reference price when slippage is configured."""
    scheduler = _ManualScheduler()
    broker = SimBroker(ImmediateFillModel(slippage=0.01), scheduler=scheduler)
    events = _collect(broker)
    broker.place_order(
        OrderRequest(
            client_ref="sig-2",
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=5,
            reference_price=100.0,
        )
    )
    scheduler.pump()
    assert events[0].fill_price == pytest.approx(99.0)


# ── Live-price provider (SRD-INF-009.007) ─────────────────────────────────────

def _sim_with_provider(
    provider: Callable[[str], float | None],
) -> tuple[SimBroker, _ManualScheduler]:
    scheduler = _ManualScheduler()
    return SimBroker(ImmediateFillModel(), scheduler=scheduler, price_provider=provider), scheduler


def test_market_order_fills_at_provider_price() -> None:
    """UT-INF-009.004.M01.T01: a market order fills at the provider's live price, not the reference."""
    broker, scheduler = _sim_with_provider(lambda _s: 191.3)
    events = _collect(broker)
    broker.place_order(_market_buy(qty=10, ref=50.0))
    scheduler.pump()
    assert events[0].fill_price == pytest.approx(191.3)


def test_market_order_falls_back_to_reference_when_no_live_price() -> None:
    """UT-INF-009.004.M01.T02: with no live price, the fill uses the reference price."""
    broker, scheduler = _sim_with_provider(lambda _s: None)
    events = _collect(broker)
    broker.place_order(_market_buy(qty=10, ref=50.0))
    scheduler.pump()
    assert events[0].fill_price == pytest.approx(50.0)


def test_market_order_rejects_non_positive_provider_price() -> None:
    """UT-INF-009.004.M01.T03: a non-positive provider price falls back to the reference price."""
    broker, scheduler = _sim_with_provider(lambda _s: 0.0)
    events = _collect(broker)
    broker.place_order(_market_buy(qty=10, ref=50.0))
    scheduler.pump()
    assert events[0].fill_price == pytest.approx(50.0)


def test_limit_order_ignores_provider() -> None:
    """UT-INF-009.004.M01.T04: a limit order fills at its limit price, ignoring the provider."""
    broker, scheduler = _sim_with_provider(lambda _s: 191.3)
    events = _collect(broker)
    broker.place_order(
        OrderRequest(
            client_ref="sig-lmt",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            limit_price=48.0,
        )
    )
    scheduler.pump()
    assert events[0].fill_price == pytest.approx(48.0)


# ── IBKR status mapping (SRD-INF-009.005) ─────────────────────────────────────


def test_ibkr_partial_then_fill() -> None:
    """A `Submitted` update with a partial fill maps to PARTIAL_FILLED; the
    final `Filled` maps to FILLED — identical to SimBroker's sequence."""
    broker, scheduler = _ibkr([("Submitted", 4, 50.0), ("Filled", 10, 50.0)])
    events = _collect(broker)
    broker.place_order(_market_buy(qty=10))
    scheduler.pump()
    assert [(e.status, e.filled_quantity) for e in events] == [
        (OrderStatus.PARTIAL_FILLED, 4),
        (OrderStatus.FILLED, 10),
    ]


def test_ibkr_acknowledgement_emits_nothing() -> None:
    """A `Submitted` update with zero fill is an acknowledgement — no event."""
    broker, scheduler = _ibkr([("Submitted", 0, 0.0), ("Filled", 10, 50.0)])
    events = _collect(broker)
    broker.place_order(_market_buy(qty=10))
    scheduler.pump()
    assert [e.status for e in events] == [OrderStatus.FILLED]


def test_ibkr_inactive_maps_to_rejected() -> None:
    broker, scheduler = _ibkr([("Inactive", 0, 0.0)])
    events = _collect(broker)
    broker.place_order(_market_buy())
    scheduler.pump()
    assert [e.status for e in events] == [OrderStatus.REJECTED]


def test_ibkr_cancel() -> None:
    broker, scheduler = _ibkr([("Filled", 10, 50.0)])
    events = _collect(broker)
    order_id = broker.place_order(_market_buy())
    broker.cancel_order(order_id)
    scheduler.pump()
    assert [e.status for e in events] == [OrderStatus.CANCELLED]


# ── Sim ≡ IBKR reject feedback (SRD-EXE-015.005) ─────────────────────────────
#
# The equivalence gate for Phase 1: a reject or cancel from either broker must
# reach the strategy engine as the same RejectEvent, so the symbol is released
# whichever broker is behind the adapter.

def _ingestion_over(broker: Broker):
    """Wire a real-DB OrderIngestion behind *broker*; returns the reject list."""
    import os
    import tempfile

    from us_swing.db.manager import DatabaseManager
    from us_swing.db.schema import create_schema
    from us_swing.execution.order_ingestion import OrderContext, OrderIngestion
    from us_swing.execution.strategy_engine._protocols import RejectEvent

    path = os.path.join(tempfile.mkdtemp(), "contract.db")
    mgr = DatabaseManager("sqlite:///" + path.replace(os.sep, "/"))
    create_schema(mgr._engine)

    class _Cycles:
        def on_entry_fill(self, **k: object) -> None: ...
        def on_exit_fill(self, **k: object) -> None: ...
        def on_entry_failed(self, *a: object, **k: object) -> None: ...
        def abort_entry_order(self, *a: object, **k: object) -> None: ...
        def update_risk(self, *a: object, **k: object) -> None: ...
        def reload(self) -> None: ...

    rejects: list[RejectEvent] = []
    ingestion = OrderIngestion(
        ledger=mgr, fill_sink=lambda _f: None, reject_sink=rejects.append, cycles=_Cycles(),
    )
    ingestion.register(OrderContext(
        broker_order_id="", signal_id="sig-1", strategy_id="SUPERTREND", user_id=1,
        symbol="AAPL", side=OrderSide.BUY, is_entry=True, quantity=10, intended_price=50.0,
    ))
    broker.on_event(ingestion.on_order_event)
    return rejects


@pytest.mark.parametrize("factory", [
    pytest.param(lambda: _sim(ScriptedFillModel(steps=((OrderStatus.REJECTED, 0),))), id="sim"),
    pytest.param(lambda: _ibkr([("Inactive", 0, 0.0)]), id="ibkr"),
])
def test_reject_reaches_the_engine_identically(factory) -> None:  # type: ignore[no-untyped-def]
    """UT-EXE-015.005.M01.T14: Sim and IBKR rejects yield the same RejectEvent."""
    broker, scheduler = factory()
    rejects = _ingestion_over(broker)

    broker.place_order(_market_buy())
    scheduler.pump()

    assert len(rejects) == 1
    ev = rejects[0]
    assert (ev.strategy_id, ev.symbol, ev.is_entry) == ("SUPERTREND", "AAPL", True)
    assert ev.reason


def test_cancel_reaches_the_engine() -> None:
    """UT-EXE-015.005.M01.T15: a cancel releases the symbol the same way."""
    broker, scheduler = _sim(ImmediateFillModel())
    rejects = _ingestion_over(broker)

    order_id = broker.place_order(_market_buy())
    broker.cancel_order(order_id)
    scheduler.pump()

    assert [r.reason for r in rejects] == ["cancelled"]


# ── IBKR status-mapping correctness (SRD-INF-009.005, Phase 3) ───────────────

def test_pending_cancel_is_not_terminal() -> None:
    """UT-INF-009.005.M01.T10: a cancel that loses the race still fills correctly.

    ``PendingCancel`` is a request in progress, not an outcome.  Treating it as
    terminal dropped the client_ref, so the real ``Filled`` that followed arrived
    with no reference and was discarded by ingestion.
    """
    broker, scheduler = _ibkr([("PendingCancel", 0, 0.0), ("Filled", 10, 50.0)])
    events = _collect(broker)

    broker.place_order(_market_buy())
    scheduler.pump()

    assert [e.status for e in events] == [OrderStatus.FILLED]
    assert events[0].client_ref == "sig-1", "client_ref was dropped before the fill"
    assert events[0].filled_quantity == 10


def test_cancelled_then_filled_keeps_the_client_ref() -> None:
    """UT-INF-009.005.M01.T19: a fill arriving after a cancel is still attributable.

    TWS cancelled a live order (error 10349, an order preset rewriting the TIF)
    and filled it two seconds later.  The reference was dropped on the cancel, so
    the fill arrived unattributable and was discarded — the stock was held with
    nothing in the app to show for it.
    """
    broker, scheduler = _ibkr([("Cancelled", 0, 0.0), ("Filled", 16, 30.95)])
    events = _collect(broker)

    broker.place_order(_market_buy())
    scheduler.pump()

    assert [e.status for e in events] == [OrderStatus.CANCELLED, OrderStatus.FILLED]
    assert events[1].client_ref == "sig-1", "client_ref was dropped on the cancel"
    assert events[1].filled_quantity == 16


def test_pending_cancel_then_cancelled_still_cancels() -> None:
    """UT-INF-009.005.M01.T11: the normal cancel sequence is unaffected."""
    broker, scheduler = _ibkr([("PendingCancel", 0, 0.0), ("Cancelled", 0, 0.0)])
    events = _collect(broker)

    broker.place_order(_market_buy())
    scheduler.pump()

    assert [e.status for e in events] == [OrderStatus.CANCELLED]


def test_inactive_carries_the_reason() -> None:
    """UT-INF-009.005.M01.T12: a rejection reports why, not an empty string."""
    scheduler = _ManualScheduler()
    gateway = _FakeGateway(scheduler, [])
    broker = IBKRBroker(gateway)
    events = _collect(broker)

    broker.place_order(_market_buy())
    gateway._callback(  # type: ignore[misc]
        IbkrOrderUpdate("7000", "Inactive", 0, 0.0, reason="margin exceeded")
    )

    assert [e.status for e in events] == [OrderStatus.REJECTED]
    assert events[0].reason == "margin exceeded"


class TestErrorEventMapping:
    """The reqId filter and code map — the correctness point of Phase 3."""

    def test_margin_reject_maps_to_inactive(self) -> None:
        """UT-INF-009.005.M01.T13: error 201 becomes a rejection carrying its text."""
        from us_swing.broker.ibkr import _error_to_update

        update = _error_to_update("7000", 201, "Order rejected - insufficient margin")

        assert update is not None
        assert update.status == "Inactive"
        assert update.reason == "Order rejected - insufficient margin"
        assert IBKRBroker._map_status(update) is OrderStatus.REJECTED

    def test_duplicate_order_id_maps_to_inactive(self) -> None:
        """UT-INF-009.005.M01.T14: error 103 is a rejection, not a warning."""
        from us_swing.broker.ibkr import _error_to_update

        update = _error_to_update("7000", 103, "Duplicate order id")

        assert update is not None
        assert IBKRBroker._map_status(update) is OrderStatus.REJECTED

    def test_cancel_confirmation_maps_to_cancelled(self) -> None:
        """UT-INF-009.005.M01.T15: error 202 is the cancel confirmation."""
        from us_swing.broker.ibkr import _error_to_update

        update = _error_to_update("7000", 202, "Order cancelled")

        assert update is not None
        assert IBKRBroker._map_status(update) is OrderStatus.CANCELLED

    def test_noise_codes_are_ignored(self) -> None:
        """UT-INF-009.005.M01.T16: warnings must never reject a live order."""
        from us_swing.broker.ibkr import _error_to_update

        for code in (399, 2104, 2106, 2158, 2109):
            assert _error_to_update("7000", code, "notice") is None, f"code {code} rejected"


class TestReasonFromTrade:
    def test_takes_the_newest_log_message(self) -> None:
        """UT-INF-009.005.M01.T17: the latest transition explains the status."""
        from types import SimpleNamespace

        from us_swing.broker.ibkr import _reason_from_trade

        trade = SimpleNamespace(log=[
            SimpleNamespace(message="Submitted"),
            SimpleNamespace(message="Order rejected - insufficient margin"),
        ])

        assert _reason_from_trade(trade) == "Order rejected - insufficient margin"

    def test_empty_log_is_the_empty_string(self) -> None:
        """UT-INF-009.005.M01.T18: no log entries means no reason, not a crash."""
        from types import SimpleNamespace

        from us_swing.broker.ibkr import _reason_from_trade

        assert _reason_from_trade(SimpleNamespace(log=[])) == ""
        assert _reason_from_trade(SimpleNamespace()) == ""


# ── Liveness gate (SRD-EXE-015.004, Phase 4) ─────────────────────────────────

class TestLivenessGate:
    """A placement into a dead socket leaves the signal in flight forever.

    Raising instead lets the router's rollback clear the symbol and release its
    capital (Phase 1).
    """

    @staticmethod
    def _gateway(connected: bool):  # type: ignore[no-untyped-def]
        from types import SimpleNamespace

        from us_swing.broker.ibkr import IBKRClientGateway

        client = SimpleNamespace(is_connected=lambda: connected)
        return IBKRClientGateway(client)  # type: ignore[arg-type]

    def test_submit_refuses_when_the_connection_is_down(self) -> None:
        """UT-EXE-015.004.M01.T29: a dead socket raises instead of silently dropping."""
        from us_swing.exceptions import BrokerConnectionError

        gateway = self._gateway(connected=False)

        with pytest.raises(BrokerConnectionError, match="not live"):
            gateway.submit("AAPL", "BUY", 10, "MARKET", None)

    def test_cancel_refuses_when_the_connection_is_down(self) -> None:
        """UT-EXE-015.004.M01.T30: cancelling into a dead socket also raises."""
        from us_swing.exceptions import BrokerConnectionError

        gateway = self._gateway(connected=False)

        with pytest.raises(BrokerConnectionError):
            gateway.cancel("7000")

    def test_constructing_a_gateway_needs_no_connection(self) -> None:
        """UT-EXE-015.004.M01.T31: construction stays inert — see the __init__ note."""
        self._gateway(connected=False)  # must not raise
