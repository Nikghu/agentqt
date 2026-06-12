"""Module: MD-INF-009.004.M01 — broker/sim.py
Parent SRD: SRD-INF-009.004, SRD-INF-009.007

Simulated broker — a mock exchange that behaves like a real broker behind the
universal :class:`Broker` contract (Broker_fix.md Phase 3).

Unlike the old ``PaperBroker`` (which filled synchronously inside ``submit``),
``SimBroker`` only *accepts* an order in ``place_order`` and emits the resulting
fills **asynchronously** via a scheduler, so ``place_order`` always returns
before any ``OrderEvent`` is delivered — exactly as a real broker behaves.

The fill behaviour is delegated to an injectable :class:`FillModel`, which
decides price, partial splits, and terminal status.  A scripted model can force
``REJECTED`` / ``PARTIAL_FILLED`` / ``CANCELLED`` sequences for functionality
testing.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol

from us_swing.broker.broker import (
    Broker,
    OrderEvent,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
)

# Resolves the current live market price for a symbol, or None if unknown.
PriceProvider = Callable[[str], "float | None"]

# A scheduler defers a callback so it runs after ``place_order`` has returned.
Scheduler = Callable[[Callable[[], None]], None]


def _loop_soon(callback: Callable[[], None]) -> None:
    """Default scheduler — run the callback on the next iteration of the
    currently running asyncio event loop."""
    asyncio.get_running_loop().call_soon(callback)


class FillModel(Protocol):
    """Decides the ``OrderEvent`` sequence a single order produces."""

    def plan(self, request: OrderRequest, broker_order_id: str) -> list[OrderEvent]: ...


def _fill_price(request: OrderRequest, slippage: float) -> float:
    base = request.limit_price if request.limit_price is not None else request.reference_price
    if base is None:
        base = 0.0
    sign = 1.0 if request.side is OrderSide.BUY else -1.0
    return base * (1.0 + sign * slippage)


@dataclass(frozen=True, slots=True)
class ImmediateFillModel:
    """Fills the whole order at the reference (or limit) price in one event.

    ``slippage`` is a fraction applied against the order side: a buy fills
    slightly higher, a sell slightly lower.
    """

    slippage: float = 0.0

    def plan(self, request: OrderRequest, broker_order_id: str) -> list[OrderEvent]:
        return [
            OrderEvent(
                broker_order_id=broker_order_id,
                client_ref=request.client_ref,
                status=OrderStatus.FILLED,
                filled_quantity=request.quantity,
                fill_price=_fill_price(request, self.slippage),
            )
        ]


@dataclass(frozen=True, slots=True)
class ScriptedFillModel:
    """Emits a fixed script of ``(status, cumulative_filled_quantity)`` steps.

    Used to exercise partial fills, rejections, and cancellations.  Fill price
    defaults to the request's reference (or limit) price unless ``price`` is set.
    """

    steps: tuple[tuple[OrderStatus, int], ...]
    price: float | None = None

    def plan(self, request: OrderRequest, broker_order_id: str) -> list[OrderEvent]:
        fill_price = self.price if self.price is not None else _fill_price(request, 0.0)
        events: list[OrderEvent] = []
        for status, filled in self.steps:
            is_fill = status in (OrderStatus.FILLED, OrderStatus.PARTIAL_FILLED)
            events.append(
                OrderEvent(
                    broker_order_id=broker_order_id,
                    client_ref=request.client_ref,
                    status=status,
                    filled_quantity=filled,
                    fill_price=fill_price if is_fill else None,
                    reason=None if is_fill else "scripted",
                )
            )
        return events


@dataclass
class _PendingOrder:
    request: OrderRequest
    plan: list[OrderEvent]


class SimBroker(Broker):
    """In-memory mock exchange implementing the universal :class:`Broker`."""

    def __init__(
        self,
        fill_model: FillModel | None = None,
        *,
        scheduler: Scheduler | None = None,
        price_provider: PriceProvider | None = None,
    ) -> None:
        super().__init__()
        self._fill_model = fill_model or ImmediateFillModel()
        self._schedule = scheduler or _loop_soon
        self._price_provider = price_provider
        # Seed from epoch milliseconds so order ids stay unique across restarts.
        self._next_id = int(time.time() * 1000)
        self._open: dict[str, _PendingOrder] = {}
        self._cancelled: set[str] = set()

    def place_order(self, request: OrderRequest) -> str:
        broker_order_id = str(self._next_id)
        self._next_id += 1
        priced = self._with_market_price(request)
        plan = self._fill_model.plan(priced, broker_order_id)
        self._open[broker_order_id] = _PendingOrder(request=priced, plan=plan)
        self._schedule(lambda: self._resolve(broker_order_id))
        return broker_order_id

    def _with_market_price(self, request: OrderRequest) -> OrderRequest:
        """Fill a MARKET order at the live market price like a real broker.

        Resolves the current price from the injected provider and overrides the
        caller's advisory ``reference_price`` with it (SRD-INF-009.007). Falls
        back to the original ``reference_price`` when there is no provider or it
        reports no positive price; LIMIT orders are returned unchanged.
        """
        if self._price_provider is None or request.order_type is not OrderType.MARKET:
            return request
        live = self._price_provider(request.symbol)
        if live is None or live <= 0:
            return request
        return replace(request, reference_price=live)

    def cancel_order(self, broker_order_id: str) -> None:
        if broker_order_id in self._open:
            self._cancelled.add(broker_order_id)

    def _resolve(self, broker_order_id: str) -> None:
        pending = self._open.get(broker_order_id)
        if pending is None:
            return
        if broker_order_id in self._cancelled:
            self._emit(
                OrderEvent(
                    broker_order_id=broker_order_id,
                    client_ref=pending.request.client_ref,
                    status=OrderStatus.CANCELLED,
                    filled_quantity=0,
                    reason="cancelled before fill",
                )
            )
            self._finish(broker_order_id)
            return
        for event in pending.plan:
            self._emit(event)
        self._finish(broker_order_id)

    def _finish(self, broker_order_id: str) -> None:
        self._open.pop(broker_order_id, None)
        self._cancelled.discard(broker_order_id)


__all__ = [
    "FillModel",
    "ImmediateFillModel",
    "PriceProvider",
    "ScriptedFillModel",
    "Scheduler",
    "SimBroker",
]
