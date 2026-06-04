"""Module: MD-INF-009.001.M01 — broker/broker.py
Parent SRD: SRD-INF-009.001, SRD-INF-009.002, SRD-INF-009.003

Universal broker contract.  Phase 1 of the Broker_fix plan.

The broker layer is a pluggable INF component: it can be swapped (Sim, IBKR,
or any future broker) without the execution core changing.  To keep it a
self-contained plugin, this contract imports **nothing** from the execution
layer — it speaks only neutral broker types: ``OrderRequest`` in, ``OrderEvent``
out.  Communication still flows both ways (orders down, fills up), but the
broker reports fills through callbacks it does not own; the import dependency
points one way only (execution → broker).

Concrete brokers (``broker/sim.py``, ``broker/ibkr.py``) subclass ``Broker``.
Translation between the execution layer's ``TradeSignal`` / ``FillEvent`` and
these neutral types is done by an adapter on the execution side, never here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class OrderSide(StrEnum):
    """Direction of a broker order."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """Supported broker order types."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(StrEnum):
    """Broker-native order lifecycle.

    Member values mirror the execution layer's ``BuyOrderState`` /
    ``SellOrderState`` exactly, so the execution-side adapter maps them 1:1
    onto ``trades.order_state`` with no lookup table.
    """

    NEW = "NEW"
    PARTIAL_FILLED = "PARTIAL_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """A neutral order instruction handed to a broker.

    Attributes:
        client_ref: Caller's correlation id (e.g. the engine signal id).
            Echoed back unchanged on every resulting ``OrderEvent`` so the
            adapter can match fills to the originating order.
        symbol: Ticker symbol.
        side: Buy or sell.
        quantity: Number of shares to transact.
        order_type: Market or limit. Defaults to market.
        limit_price: Required when ``order_type`` is ``LIMIT``; otherwise None.
        reference_price: Advisory price the caller observed for this order (e.g.
            the strategy signal price).  Simulated brokers fill market orders at
            this price; live brokers ignore it and fill at the actual market.
    """

    client_ref: str
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    reference_price: float | None = None


@dataclass(frozen=True, slots=True)
class OrderEvent:
    """An asynchronous order-lifecycle update emitted by a broker.

    Attributes:
        broker_order_id: The broker's identifier for the order.
        client_ref: The ``client_ref`` of the originating ``OrderRequest``.
        status: New order status.
        filled_quantity: Cumulative shares filled so far.
        fill_price: Average fill price for the filled quantity, if any.
        reason: Human-readable detail for ``REJECTED`` / ``CANCELLED``.
        schema_version: DTO version for forward compatibility.
    """

    broker_order_id: str
    client_ref: str
    status: OrderStatus
    filled_quantity: int = 0
    fill_price: float | None = None
    reason: str | None = None
    schema_version: int = 1


OrderEventCallback = Callable[[OrderEvent], None]


class Broker(ABC):
    """Universal broker contract subclassed by every concrete broker.

    Submission only *accepts* an order and returns a broker order id; fills
    and rejections arrive asynchronously through subscribed callbacks, exactly
    as a real broker behaves.  Subclasses implement ``place_order`` and
    ``cancel_order`` and report progress via :meth:`_emit`.
    """

    def __init__(self) -> None:
        self._event_callbacks: list[OrderEventCallback] = []

    def on_event(self, callback: OrderEventCallback) -> None:
        """Register a listener for asynchronous order-lifecycle events."""
        self._event_callbacks.append(callback)

    def _emit(self, event: OrderEvent) -> None:
        """Dispatch an order event to every registered listener."""
        for callback in self._event_callbacks:
            callback(event)

    @abstractmethod
    def place_order(self, request: OrderRequest) -> str:
        """Submit an order for execution and return its broker order id.

        Acceptance only — the returned id confirms the broker received the
        order, not that it filled.  Fills are delivered later as
        ``OrderEvent``s through registered :meth:`on_event` callbacks.
        """

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> None:
        """Request cancellation of a working order by its broker order id."""


__all__ = [
    "Broker",
    "OrderEvent",
    "OrderEventCallback",
    "OrderRequest",
    "OrderSide",
    "OrderStatus",
    "OrderType",
]
