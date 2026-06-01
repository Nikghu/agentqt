"""
Module: MD-EXE-011.001.M09 — PaperBroker
Parent SRD: SRD-EXE-011.010
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from us_swing.execution.strategy_engine._protocols import FillEvent
from us_swing.execution.strategy_engine._signals import Action, TradeSignal

log = logging.getLogger(__name__)


class PaperBroker:
    """Simulates IBKR fills synchronously; calls on_fill immediately."""

    def __init__(self, on_fill: Callable[[FillEvent], None]) -> None:
        self._on_fill = on_fill
        # Seed from epoch milliseconds so order ids stay unique across app
        # restarts.  A fixed base reset to the same value each session, so
        # ids collided with prior sessions' rows and the unique
        # entry/exit_order_id guard in trade_cycles wrongly matched an old
        # cycle — silently skipping the close.
        self._next_order_id = int(time.time() * 1000)

    def submit(self, signal: TradeSignal, qty: int) -> int | None:
        order_id = self._next_order_id
        self._next_order_id += 1
        fill = FillEvent(
            strategy_id=signal.strategy_id,
            symbol=signal.symbol,
            is_entry=(signal.action == Action.ENTRY),
            fill_price=signal.entry_price or 0.0,
            fill_qty=qty,
            order_id=order_id,
        )
        log.info(
            "[PaperBroker] Fill: %s %s ×%d @ %.2f  order_id=%d",
            signal.symbol, signal.action, qty, fill.fill_price, order_id,
        )
        self._on_fill(fill)
        return order_id
