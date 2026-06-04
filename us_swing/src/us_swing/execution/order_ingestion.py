"""Module: MD-EXE-015.001.M01 — execution/order_ingestion.py
Parent SRD: SRD-EXE-015.002, SRD-EXE-015.003, SRD-EXE-015.005

Broker-agnostic order ingestion (Broker_fix.md Phase 2).

Writes the `trades` ledger for *every* order — paper included — which ends the
historical paper bypass where fills went straight to `trade_cycles`.  The same
handler also feeds the strategy-engine fill and drives the trade-cycle
open/close.  It contains **no branch on broker type**: SimBroker and IBKRBroker
events run identical code.  Context captured at acceptance is keyed by broker
order id and recovered when the asynchronous fill events arrive.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from us_swing.broker.broker import OrderEvent, OrderSide, OrderStatus
from us_swing.data.models import TradeRecord
from us_swing.execution._enums import ExecutionEnums as E
from us_swing.execution.strategy_engine._protocols import FillEvent
from us_swing.execution.trade_cycle._protocols import TradeCycleCommand

log = logging.getLogger(__name__)


class BrokerStatusError(ValueError):
    """Raised when a broker `OrderStatus` has no matching execution order state."""


class TradeLedger(Protocol):
    """Narrow `trades`-table surface consumed by ingestion (DatabaseManager)."""

    def insert_trade(self, trade: TradeRecord) -> None: ...

    def update_trade_fill(
        self,
        trade_id: str,
        filled_quantity: int,
        order_state: str,
        exit_time: datetime | None = ...,
        exit_price: float | None = ...,
        entry_price: float | None = ...,
        entry_time: datetime | None = ...,
    ) -> None: ...


FillSink = Callable[[FillEvent], None]


class LifecycleSink(Protocol):
    """Narrow monitoring-lifecycle surface (`MonitoringCommand`) used to flip the
    `MONITORING → ENTERED → EXITED` ledger from live fills (FO-EXE-016)."""

    def mark_entered(self, symbol: str, entered_at: str, trade_id: str) -> None: ...

    def mark_exited(self, symbol: str, exited_at: str) -> None: ...


@dataclass(frozen=True, slots=True)
class OrderContext:
    """Everything ingestion needs about an order, captured at acceptance.

    Stored keyed by ``broker_order_id`` so the later asynchronous
    ``OrderEvent``s — which carry only ``client_ref`` and ``broker_order_id`` —
    can be resolved back to the originating strategy, user, and risk snapshot.
    """

    broker_order_id: str
    signal_id: str
    strategy_id: str
    user_id: int
    symbol: str
    side: OrderSide
    is_entry: bool
    quantity: int
    intended_price: float
    mode: str = "paper"
    hard_stop_loss: float = 0.0
    target_price: float | None = None
    target_type: str = "fixed"
    stoploss_type: str = "fixed"
    trailing_mode: str | None = None
    trailing_offset: float | None = None
    monitoring_session_date: str = ""
    exit_reason: str = "manual"


class OrderIngestion:
    """Persists orders and fills for any broker behind the neutral contract."""

    def __init__(
        self,
        *,
        ledger: TradeLedger,
        fill_sink: FillSink,
        cycles: TradeCycleCommand,
        lifecycle: LifecycleSink | None = None,
    ) -> None:
        self._ledger = ledger
        self._fill_sink = fill_sink
        self._cycles = cycles
        self._lifecycle = lifecycle
        self._context: dict[str, OrderContext] = {}

    def on_order_accepted(self, ctx: OrderContext) -> None:
        """Insert the `trades` row at acceptance (state NEW) — SRD-EXE-015.002."""
        self._context[ctx.broker_order_id] = ctx
        self._ledger.insert_trade(
            TradeRecord(
                trade_id=ctx.broker_order_id,
                user_id=ctx.user_id,
                symbol=ctx.symbol,
                side=ctx.side.value,
                quantity=ctx.quantity,
                entry_price=ctx.intended_price,
                mode=ctx.mode,
                strategy_id=ctx.strategy_id,
                entry_time=datetime.now(),
                order_state=self._order_state(ctx.side, OrderStatus.NEW),
                filled_quantity=0,
            )
        )
        log.info(
            "[Orders] Accepted %s %s %d share(s) — order %s",
            ctx.symbol,
            ctx.side.value,
            ctx.quantity,
            ctx.broker_order_id,
        )

    def on_order_event(self, event: OrderEvent) -> None:
        """Advance the `trades` ledger and drive the cycle — SRD-EXE-015.003."""
        ctx = self._context.get(event.broker_order_id)
        if ctx is None:
            log.warning(
                "[Orders] Received an update for an unknown order — skipping (%s)",
                event.broker_order_id,
            )
            return

        order_state = self._order_state(ctx.side, event.status)
        is_exit_fill = (not ctx.is_entry) and event.status in (
            OrderStatus.FILLED,
            OrderStatus.PARTIAL_FILLED,
        )
        is_entry_fill = ctx.is_entry and event.fill_price is not None
        now = datetime.now()
        self._ledger.update_trade_fill(
            ctx.broker_order_id,
            event.filled_quantity,
            order_state,
            exit_time=now if is_exit_fill else None,
            exit_price=event.fill_price if is_exit_fill else None,
            entry_price=event.fill_price if is_entry_fill else None,
            entry_time=now if is_entry_fill else None,
        )

        if event.status is OrderStatus.REJECTED:
            log.warning("[Orders] Order rejected — %s", event.reason or "no reason given")
            self._context.pop(event.broker_order_id, None)
            return
        if event.status is OrderStatus.CANCELLED:
            log.info(
                "[Orders] Order cancelled with %d share(s) filled",
                event.filled_quantity,
            )
            self._context.pop(event.broker_order_id, None)
            return

        self._fill_sink(
            FillEvent(
                strategy_id=ctx.strategy_id,
                symbol=ctx.symbol,
                is_entry=ctx.is_entry,
                fill_price=event.fill_price or 0.0,
                fill_qty=event.filled_quantity,
                order_id=int(event.broker_order_id),
            )
        )

        if ctx.is_entry:
            self._open_cycle(ctx, event, now)
        else:
            self._close_cycle(ctx, event, now)

        # FO-EXE-016 — a completed fill drives the monitoring-session ledger:
        # entry FILLED → ENTERED, closing exit FILLED → EXITED.  Partial fills
        # leave the ledger state unchanged.
        if self._lifecycle is not None and event.status is OrderStatus.FILLED:
            if ctx.is_entry:
                self._lifecycle.mark_entered(ctx.symbol, _iso(now), ctx.broker_order_id)
            else:
                self._lifecycle.mark_exited(ctx.symbol, _iso(now))

        if event.status is OrderStatus.FILLED:
            self._context.pop(event.broker_order_id, None)

    def _open_cycle(self, ctx: OrderContext, event: OrderEvent, now: datetime) -> None:
        buy_state = (
            E.BuyOrderState.FILLED
            if event.status is OrderStatus.FILLED
            else E.BuyOrderState.PARTIAL_FILLED
        )
        try:
            self._cycles.on_entry_fill(
                strategy_id=ctx.strategy_id,
                symbol=ctx.symbol,
                user_id=ctx.user_id,
                entry_order_id=ctx.broker_order_id,
                entry_price=event.fill_price or ctx.intended_price,
                entry_qty=event.filled_quantity,
                fill_time=_iso(now),
                hard_stop_loss=ctx.hard_stop_loss,
                target_price=ctx.target_price,
                target_type=ctx.target_type,
                stoploss_type=ctx.stoploss_type,
                trailing_mode=ctx.trailing_mode,
                trailing_offset=ctx.trailing_offset,
                monitoring_session_date=ctx.monitoring_session_date,
                order_state=buy_state,
            )
        except Exception:
            log.exception("[Orders] Could not open the trade cycle for %s", ctx.symbol)

    def _close_cycle(self, ctx: OrderContext, event: OrderEvent, now: datetime) -> None:
        sell_state = (
            E.SellOrderState.FILLED
            if event.status is OrderStatus.FILLED
            else E.SellOrderState.PARTIAL_FILLED
        )
        try:
            self._cycles.on_exit_fill(
                exit_order_id=ctx.broker_order_id,
                exit_price=event.fill_price or 0.0,
                exit_qty=event.filled_quantity,
                exit_time=_iso(now),
                exit_reason=ctx.exit_reason,
                order_state=sell_state,
            )
        except Exception:
            log.exception("[Orders] Could not close the trade cycle for %s", ctx.symbol)

    @staticmethod
    def _order_state(side: OrderSide, status: OrderStatus) -> str:
        enum = E.BuyOrderState if side is OrderSide.BUY else E.SellOrderState
        try:
            return enum(status.value).value
        except ValueError as exc:
            raise BrokerStatusError(
                f"No execution order state for broker status {status!r}"
            ) from exc


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


__all__ = [
    "BrokerStatusError",
    "FillSink",
    "OrderContext",
    "OrderIngestion",
    "TradeLedger",
]
