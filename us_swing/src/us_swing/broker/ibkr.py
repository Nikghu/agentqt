"""Module: MD-INF-009.005.M01 — broker/ibkr.py
Parent SRD: SRD-INF-009.005

IBKR broker — implements the universal :class:`Broker` over Interactive
Brokers (Broker_fix.md Phase 4).

``IBKRBroker`` holds no ib_insync logic itself.  It depends on a narrow
:class:`OrderGateway` seam that delivers IBKR-native order updates
(``IbkrOrderUpdate``); the broker's job is to translate an ``OrderRequest`` into
a submission and to **map IBKR order statuses onto the neutral
``OrderStatus``** — the one piece of genuine IBKR logic, fully unit-tested.

The production seam ``IBKRClientGateway`` wraps :class:`IBKRClient` and builds
ib_insync orders; it is exercised only against a live TWS (``# pragma: no
cover``).  The contract suite drives ``IBKRBroker`` with an in-process fake, so
the mapping and event emission are proven identical to ``SimBroker``.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from us_swing.broker.broker import (
    Broker,
    OrderEvent,
    OrderRequest,
    OrderStatus,
)

if TYPE_CHECKING:
    from us_swing.broker.client import IBKRClient


@dataclass(frozen=True, slots=True)
class IbkrOrderUpdate:
    """An IBKR-native order-status update delivered by the gateway."""

    broker_order_id: str
    status: str            # raw ib_insync order status, e.g. "Filled"
    filled: int            # cumulative filled quantity
    avg_fill_price: float
    reason: str = ""


class OrderGateway(Protocol):
    """Broker-native order transport ``IBKRBroker`` depends on.

    The production implementation wraps ``IBKRClient`` + ib_insync; tests supply
    an in-process fake that drives ``IbkrOrderUpdate``s.
    """

    def submit(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        limit_price: float | None,
    ) -> str: ...

    def cancel(self, broker_order_id: str) -> None: ...

    def on_status(self, callback: Callable[[IbkrOrderUpdate], None]) -> None: ...


# IBKR statuses that finish an order — context is dropped once one arrives.
_TERMINAL = (OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED)


class IBKRBroker(Broker):
    """Universal :class:`Broker` backed by an Interactive Brokers gateway."""

    def __init__(self, gateway: OrderGateway) -> None:
        super().__init__()
        self._gateway = gateway
        self._client_ref: dict[str, str] = {}
        gateway.on_status(self._on_update)

    def place_order(self, request: OrderRequest) -> str:
        broker_order_id = self._gateway.submit(
            request.symbol,
            request.side.value,
            request.quantity,
            request.order_type.value,
            request.limit_price,
        )
        self._client_ref[broker_order_id] = request.client_ref
        return broker_order_id

    def cancel_order(self, broker_order_id: str) -> None:
        self._gateway.cancel(broker_order_id)

    def _on_update(self, update: IbkrOrderUpdate) -> None:
        status = self._map_status(update)
        if status is None:
            return  # acknowledgement-only transition (e.g. Submitted, no fill)
        is_fill = status in (OrderStatus.FILLED, OrderStatus.PARTIAL_FILLED)
        self._emit(
            OrderEvent(
                broker_order_id=update.broker_order_id,
                client_ref=self._client_ref.get(update.broker_order_id, ""),
                status=status,
                filled_quantity=update.filled,
                fill_price=update.avg_fill_price if is_fill else None,
                reason=(update.reason or None) if not is_fill else None,
            )
        )
        if status in _TERMINAL:
            self._client_ref.pop(update.broker_order_id, None)

    @staticmethod
    def _map_status(update: IbkrOrderUpdate) -> OrderStatus | None:
        status = update.status
        if status == "Filled":
            return OrderStatus.FILLED
        if status in ("Cancelled", "ApiCancelled", "PendingCancel"):
            return OrderStatus.CANCELLED
        if status == "Inactive":
            return OrderStatus.REJECTED
        if status in ("Submitted", "PreSubmitted") and update.filled > 0:
            return OrderStatus.PARTIAL_FILLED
        return None


class IBKRClientGateway:
    """Production :class:`OrderGateway` wrapping :class:`IBKRClient` + ib_insync.

    Only runs against a live TWS/Gateway, so it carries no unit coverage; the
    broker logic above is covered by the contract suite via a fake gateway.
    """

    def __init__(self, client: IBKRClient) -> None:
        self._client = client
        self._callbacks: list[Callable[[IbkrOrderUpdate], None]] = []

    def on_status(self, callback: Callable[[IbkrOrderUpdate], None]) -> None:
        self._callbacks.append(callback)

    def submit(  # pragma: no cover - requires a live IBKR connection
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        limit_price: float | None,
    ) -> str:
        from ib_insync import LimitOrder, MarketOrder, Stock

        contract = Stock(symbol, "SMART", "USD")
        order: Any = (
            LimitOrder(side, quantity, limit_price if limit_price is not None else 0.0)
            if order_type == "LIMIT"
            else MarketOrder(side, quantity)
        )
        trade = self._client.ib.placeOrder(contract, order)
        broker_order_id = str(trade.order.orderId)
        trade.statusEvent += self._make_handler(broker_order_id)
        return broker_order_id

    def cancel(self, broker_order_id: str) -> None:  # pragma: no cover
        for trade in self._client.ib.trades():
            if str(trade.order.orderId) == broker_order_id:
                self._client.ib.cancelOrder(trade.order)
                return

    def _make_handler(  # pragma: no cover
        self, broker_order_id: str
    ) -> Callable[[object], None]:
        def _handle(trade: object) -> None:
            status = trade.orderStatus  # type: ignore[attr-defined]
            self._dispatch(
                IbkrOrderUpdate(
                    broker_order_id=broker_order_id,
                    status=str(status.status),
                    filled=int(trade.filled()),  # type: ignore[attr-defined]
                    avg_fill_price=float(status.avgFillPrice or 0.0),
                )
            )

        return _handle

    def _dispatch(self, update: IbkrOrderUpdate) -> None:  # pragma: no cover
        for callback in self._callbacks:
            callback(update)


__all__ = [
    "IBKRBroker",
    "IBKRClientGateway",
    "IbkrOrderUpdate",
    "OrderGateway",
]
