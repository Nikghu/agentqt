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

import asyncio
import concurrent.futures
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from us_swing.exceptions import BrokerConnectionError
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

# Order-scoped IBKR error codes that decide an order's fate, mapped onto the raw
# ib_insync status strings ``_map_status`` already understands.  Anything absent
# here is a warning (399 order message, 2104/2106/2158 data-farm notices) and
# must never reject a live order.
_ERROR_STATUS: dict[int, str] = {
    103: "Inactive",    # duplicate order id
    201: "Inactive",    # order rejected — errorString carries the reason
    202: "Cancelled",   # order cancelled
}


def _error_to_update(order_id: str, code: int, message: str) -> IbkrOrderUpdate | None:
    """Map an order-scoped IBKR error onto an order update, or None to ignore.

    ``trade.statusEvent`` never fires for a margin or risk rejection — TWS
    reports those only through ``errorEvent`` — so without this the order sits
    in flight forever.
    """
    status = _ERROR_STATUS.get(code)
    if status is None:
        return None
    return IbkrOrderUpdate(
        broker_order_id=order_id,
        status=status,
        filled=0,
        avg_fill_price=0.0,
        reason=message,
    )


def _reason_from_trade(trade: Any) -> str:
    """Best available human reason for a trade's current status.

    ib_insync appends a ``TradeLogEntry`` per transition; the newest message is
    the one that explains a rejection.  Falls back to the empty string.
    """
    entries = getattr(trade, "log", None) or []
    if not entries:
        return ""
    return str(getattr(entries[-1], "message", "") or "")

# Longest a caller thread waits for TWS to accept a placement or cancellation.
_ORDER_TIMEOUT_S = 10.0

_T = TypeVar("_T")


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
        # "PendingCancel" is deliberately absent: it is a request in progress,
        # not an outcome.  Treating it as terminal drops the client_ref, so a
        # cancel that loses the race and fills anyway arrives unattributable and
        # is discarded by ingestion.  Held as ack-only until a true terminal.
        if status in ("Cancelled", "ApiCancelled"):
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
        # Order ids this gateway placed.  errorEvent is account-wide, so an
        # error for someone else's order — or a non-order error, which carries
        # reqId -1 — must never be attributed to one of ours.
        self._order_ids: set[str] = set()
        self._error_hooked = False

    def on_status(self, callback: Callable[[IbkrOrderUpdate], None]) -> None:
        self._callbacks.append(callback)

    def _hook_errors(self) -> None:  # pragma: no cover - requires a live connection
        """Subscribe to ``errorEvent`` once, on the first placement.

        Deferred rather than done in ``__init__`` so constructing a gateway never
        requires a connected client.  ``build_broker`` runs inside a try/except
        that falls back to the simulated broker, so a constructor reaching into a
        half-built client would silently downgrade live routing to paper.
        """
        if self._error_hooked:
            return
        self._client.ib.errorEvent += self._on_error
        self._error_hooked = True

    def _on_error(  # pragma: no cover - requires a live IBKR connection
        self, req_id: int, code: int, message: str, *_: Any
    ) -> None:
        """Turn an order-scoped IBKR error into an order update."""
        order_id = str(req_id)
        if order_id not in self._order_ids:
            return
        update = _error_to_update(order_id, code, message)
        if update is not None:
            self._dispatch(update)

    def _require_live(self) -> None:
        """Refuse to touch the socket when the order connection is down.

        Raising lets the router's rollback clear the symbol and release its
        capital reservation.  Placing into a dead socket instead would leave the
        signal in flight with no broker event ever coming back to free it.
        """
        if not self._client.is_connected():
            raise BrokerConnectionError(
                "IBKR order connection is not live — the order was not sent"
            )

    def submit(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        limit_price: float | None,
    ) -> str:
        self._require_live()
        return self._on_client_loop(  # pragma: no cover - needs a live connection
            lambda: self._place(symbol, side, quantity, order_type, limit_price)
        )

    def cancel(self, broker_order_id: str) -> None:
        self._require_live()
        self._on_client_loop(  # pragma: no cover - needs a live connection
            lambda: self._cancel(broker_order_id)
        )

    # ── ib_insync calls — always run on the client's own loop ─────────────────

    def _place(  # pragma: no cover
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        limit_price: float | None,
    ) -> str:
        from ib_insync import LimitOrder, MarketOrder, Stock

        self._hook_errors()
        contract = Stock(symbol, "SMART", "USD")
        order: Any = (
            LimitOrder(side, quantity, limit_price if limit_price is not None else 0.0)
            if order_type == "LIMIT"
            else MarketOrder(side, quantity)
        )
        trade = self._client.ib.placeOrder(contract, order)
        broker_order_id = str(trade.order.orderId)
        self._order_ids.add(broker_order_id)
        trade.statusEvent += self._make_handler(broker_order_id)
        return broker_order_id

    def _cancel(self, broker_order_id: str) -> None:  # pragma: no cover
        for trade in self._client.ib.trades():
            if str(trade.order.orderId) == broker_order_id:
                self._client.ib.cancelOrder(trade.order)
                return

    def _on_client_loop(self, fn: Callable[[], _T]) -> _T:  # pragma: no cover
        """Run ``fn`` on the loop owning the ib_insync connection and wait.

        Orders are submitted from the GUI thread (manual execute) and from the
        engine thread (strategy signals), but ib_insync may only be touched on
        its own loop.  Already on that loop, call straight through.
        """
        loop = self._client.loop
        if loop is None:
            return fn()
        try:
            if asyncio.get_running_loop() is loop:
                return fn()
        except RuntimeError:
            pass
        future: concurrent.futures.Future[_T] = concurrent.futures.Future()

        def _run() -> None:
            try:
                future.set_result(fn())
            except BaseException as exc:  # noqa: BLE001 - relayed to the caller
                future.set_exception(exc)

        loop.call_soon_threadsafe(_run)
        return future.result(timeout=_ORDER_TIMEOUT_S)

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
                    reason=_reason_from_trade(trade),
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
