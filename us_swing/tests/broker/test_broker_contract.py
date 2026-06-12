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
