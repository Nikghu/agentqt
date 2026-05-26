"""
Module: MD-EXE-004.001.M01 — PaperEngine
Parent SRD: SRD-EXE-004.001, SRD-EXE-004.002, SRD-EXE-004.003, SRD-EXE-004.004
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from us_swing.data.models import OpenPosition, PositionState, TradeRecord
from us_swing.db.manager import DatabaseManager
from us_swing.execution.strategy_engine._protocols import FillEvent
from us_swing.execution.strategy_engine._signals import TradeSignal

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PaperFill:
    order_id: int
    fill_price: float
    fill_qty: int
    symbol: str
    strategy_id: str
    is_entry: bool
    mode: str = "paper"
    schema_version: int = 1


class PaperEngine:
    """Simulates broker fills without IBKR; writes paper trades to DB."""

    def __init__(
        self,
        db: DatabaseManager,
        price_provider: Callable[[str], float | None],
        on_fill: Callable[[FillEvent], None],
        user_id: int,
    ) -> None:
        self._db = db
        self._price_provider = price_provider
        self._on_fill = on_fill
        self._user_id = user_id
        self._next_id = -1

    # ── Public API ────────────────────────────────────────────────────────────

    def simulate_fill(
        self,
        signal: TradeSignal,
        quantity: int,
        order_type: str = "MKT",
    ) -> PaperFill | None:
        """Simulate an entry fill; returns None if limit condition not met."""
        market_price = self._price_provider(signal.symbol)
        entry_limit = signal.entry_price or 0.0

        if order_type == "MKT":
            fill_price = market_price if market_price is not None else entry_limit
        else:
            # LMT BUY: only fills when market_price <= limit
            if market_price is None or market_price > entry_limit:
                return None
            fill_price = entry_limit

        if fill_price <= 0:
            return None

        order_id = self._next_id
        self._next_id -= 1
        now = datetime.now(tz=timezone.utc)

        trade = TradeRecord(
            trade_id=str(order_id),
            user_id=self._user_id,
            symbol=signal.symbol,
            side="BUY",
            quantity=quantity,
            entry_price=fill_price,
            mode="paper",
            strategy_id=signal.strategy_id,
            entry_time=now,
            status="FILLED",
        )
        self._db.insert_trade(trade)

        pos = OpenPosition(
            symbol=signal.symbol,
            user_id=self._user_id,
            quantity=quantity,
            average_price=fill_price,
            stop_loss=signal.stop_loss or 0.0,
            target_price=signal.target or 0.0,
            mode="paper",
            state=PositionState.OPEN.value,
            strategy_id=signal.strategy_id,
            trade_id=str(order_id),
            entry_time=now,
        )
        self._db.upsert_position(pos)

        fill = PaperFill(
            order_id=order_id,
            fill_price=fill_price,
            fill_qty=quantity,
            symbol=signal.symbol,
            strategy_id=signal.strategy_id,
            is_entry=True,
        )
        self._on_fill(
            FillEvent(
                strategy_id=signal.strategy_id,
                symbol=signal.symbol,
                is_entry=True,
                fill_price=fill_price,
                fill_qty=quantity,
                order_id=order_id,
            )
        )
        return fill

    def simulate_exit(
        self,
        symbol: str,
        quantity: int,
        strategy_id: str,
        entry_trade_id: str,
        entry_price: float = 0.0,
    ) -> PaperFill:
        """Simulate an exit fill at current market price; updates trade PnL in DB."""
        market_price = self._price_provider(symbol)
        fill_price = market_price if market_price is not None else 0.0

        order_id = self._next_id
        self._next_id -= 1
        now = datetime.now(tz=timezone.utc)

        pnl = (fill_price - entry_price) * quantity

        self._db.update_trade_exit(
            trade_id=entry_trade_id,
            exit_time=now,
            exit_price=fill_price,
            pnl=pnl,
        )

        fill = PaperFill(
            order_id=order_id,
            fill_price=fill_price,
            fill_qty=quantity,
            symbol=symbol,
            strategy_id=strategy_id,
            is_entry=False,
        )
        self._on_fill(
            FillEvent(
                strategy_id=strategy_id,
                symbol=symbol,
                is_entry=False,
                fill_price=fill_price,
                fill_qty=quantity,
                order_id=order_id,
            )
        )
        return fill

    def submit(self, signal: TradeSignal, qty: int) -> int | None:
        """ExecutionSubmitter protocol: simulate MKT fill synchronously."""
        fill = self.simulate_fill(signal, qty, "MKT")
        return fill.order_id if fill is not None else None
