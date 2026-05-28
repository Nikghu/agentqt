"""
Module: MD-EXE-001.001.M02 — ExecutionEngine
Parent SRD: SRD-EXE-001.003, SRD-EXE-001.004, SRD-EXE-001.005,
            SRD-EXE-002.002, SRD-EXE-002.003, SRD-EXE-005.005
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from us_swing.broker.client import IBKRClient
from us_swing.data.models import (
    AccountState,
    IBKRFill,
    OpenPosition,
    TradeRecord,
)
from us_swing.db.manager import DatabaseManager
from us_swing.exceptions import OrderSubmissionError
from us_swing.execution._enums import ExecutionEnums
from us_swing.execution.position_tracker import PositionTracker
from us_swing.execution.risk_manager import RiskManager
from us_swing.execution.strategy_engine._protocols import FillEvent
from us_swing.execution.strategy_engine._signals import TradeSignal

log = logging.getLogger(__name__)


class ExecutionEngine:
    """Live-broker order submission with risk gating and fill handling."""

    def __init__(
        self,
        ibkr: IBKRClient,
        risk: RiskManager,
        tracker: PositionTracker,
        db: DatabaseManager,
        on_fill: Callable[[FillEvent], None],
        user_id: int,
        loop: asyncio.AbstractEventLoop | None = None,
        timeout: float = 2.0,
    ) -> None:
        self._ibkr = ibkr
        self._risk = risk
        self._tracker = tracker
        self._db = db
        self._on_fill = on_fill
        self._user_id = user_id
        self._loop = loop
        self._timeout = timeout
        self._cb_active = False
        self._queued = 0
        # Maps order_id → trade_id for fill routing
        self._pending: dict[int, str] = {}

    # ── Primary async API ─────────────────────────────────────────────────────

    async def submit_signal(
        self,
        signal: TradeSignal,
        account_state: AccountState,
        quantity_override: int | None = None,
    ) -> int | None:
        """Validate, size, and submit a single signal to IBKR."""
        if quantity_override is not None and quantity_override <= 0:
            raise ValueError(
                f"quantity_override must be > 0, got {quantity_override}"
            )

        result = self._risk.validate_signal(signal, account_state, self._cb_active)
        if not result.ok:
            log.warning("[Execution] Signal REJECTED for %s: %s", signal.symbol, result.reason)
            return None

        qty = quantity_override if quantity_override is not None else self._risk.calculate_position_size(signal, account_state)
        if qty <= 0:
            log.warning("[Execution] Signal REJECTED for %s: position size is zero", signal.symbol)
            return None

        try:
            from ib_insync import MarketOrder, Stock
        except ImportError as exc:
            raise OrderSubmissionError("ib_insync not installed") from exc

        contract: Any = Stock(signal.symbol, "SMART", "USD")
        order: Any = MarketOrder("BUY", qty)

        try:
            order_id: int = await asyncio.wait_for(
                self._ibkr.place_order(contract, order),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as exc:
            raise OrderSubmissionError(
                f"IBKR order timeout for {signal.symbol} after {self._timeout}s"
            ) from exc

        now = datetime.now(tz=timezone.utc)
        trade = TradeRecord(
            trade_id=str(order_id),
            user_id=self._user_id,
            symbol=signal.symbol,
            side="BUY",
            quantity=qty,
            entry_price=signal.entry_price or 0.0,
            mode="live",
            strategy_id=signal.strategy_id,
            entry_time=now,
            order_state=ExecutionEnums.BuyOrderState.NEW.value,
            filled_quantity=0,
        )
        self._db.insert_trade(trade)
        self._pending[order_id] = str(order_id)

        return order_id

    # ── ExecutionSubmitter protocol (sync fire-and-forget) ────────────────────

    def submit(self, signal: TradeSignal, qty: int) -> int | None:
        """Synchronous protocol wrapper: schedules async submit, returns sentinel."""
        self._queued += 1
        sentinel = self._queued
        loop = self._loop or asyncio.get_event_loop()
        asyncio.ensure_future(self._submit_async(signal, qty), loop=loop)
        return sentinel

    async def _submit_async(self, signal: TradeSignal, qty: int) -> None:
        try:
            from ib_insync import MarketOrder, Stock
            contract: Any = Stock(signal.symbol, "SMART", "USD")
            order: Any = MarketOrder("BUY", qty)
            order_id: int = await asyncio.wait_for(
                self._ibkr.place_order(contract, order),
                timeout=self._timeout,
            )
            now = datetime.now(tz=timezone.utc)
            trade = TradeRecord(
                trade_id=str(order_id),
                user_id=self._user_id,
                symbol=signal.symbol,
                side="BUY",
                quantity=qty,
                entry_price=signal.entry_price or 0.0,
                mode="live",
                strategy_id=signal.strategy_id,
                entry_time=now,
                order_state=ExecutionEnums.BuyOrderState.NEW.value,
                filled_quantity=0,
            )
            self._db.insert_trade(trade)
            self._pending[order_id] = str(order_id)
        except Exception:
            log.exception("[Execution] Async submit failed for %s", signal.symbol)

    # ── Fill handling ─────────────────────────────────────────────────────────

    def handle_order_fill(self, fill: IBKRFill) -> None:
        """Process an IBKR fill callback (SRD-EXE-014.004).

        For an entry fill: register the position and advance the BUY
        `trades.order_state` to FILLED / PARTIAL_FILLED.  For an exit fill:
        decrement the position and advance the SELL `trades.order_state`.
        """
        trade_id = self._pending.get(fill.order_id, str(fill.order_id))
        is_entry = not self._tracker.has_open(self._user_id, fill.symbol)

        if is_entry:
            pos = OpenPosition(
                symbol=fill.symbol,
                user_id=self._user_id,
                quantity=fill.filled_quantity,
                average_price=fill.fill_price,
                stop_loss=0.0,
                target_price=0.0,
                mode="live",
                trade_id=trade_id,
            )
            self._tracker.open(pos)
            self._db.update_trade_fill(
                trade_id=trade_id,
                filled_quantity=fill.filled_quantity,
                order_state=ExecutionEnums.BuyOrderState.FILLED.value,
            )
        else:
            closed = self._tracker.close(self._user_id, fill.symbol)
            self._db.update_trade_fill(
                trade_id=closed.trade_id or trade_id,
                filled_quantity=fill.filled_quantity,
                order_state=ExecutionEnums.SellOrderState.FILLED.value,
                exit_time=fill.fill_time,
                exit_price=fill.fill_price,
            )

        self._on_fill(
            FillEvent(
                strategy_id="",
                symbol=fill.symbol,
                is_entry=is_entry,
                fill_price=fill.fill_price,
                fill_qty=fill.filled_quantity,
                order_id=fill.order_id,
            )
        )

    # ── Exit ──────────────────────────────────────────────────────────────────

    def exit_position(self, symbol: str) -> int | None:
        """Submit a market SELL for the full open quantity of a symbol."""
        if not self._tracker.has_open(self._user_id, symbol):
            return None
        positions = self._tracker.get_all(self._user_id)
        pos = next((p for p in positions if p.symbol == symbol), None)
        if pos is None:
            return None

        from ib_insync import MarketOrder, Stock
        contract: Any = Stock(symbol, "SMART", "USD")
        order: Any = MarketOrder("SELL", pos.quantity)
        loop = self._loop or asyncio.get_event_loop()
        sentinel = self._queued + 1
        self._queued = sentinel
        asyncio.ensure_future(
            self._ibkr.place_order(contract, order),
            loop=loop,
        )
        return sentinel

    # ── Circuit breaker ───────────────────────────────────────────────────────

    def set_circuit_breaker(self, active: bool) -> None:
        self._cb_active = active
