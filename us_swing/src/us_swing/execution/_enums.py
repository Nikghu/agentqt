"""
Module: MD-EXE-013.001.M01 — execution/_enums.py
Parent SRD: SRD-EXE-013.001

Single source of truth for every execution-related state machine.
Import as: from us_swing.execution import ExecutionEnums as E
"""
from __future__ import annotations

from enum import StrEnum


class ExecutionEnums:
    """Container for every execution-domain state enum.

    Access pattern:
        from us_swing.execution import ExecutionEnums as E
        if cycle.state == E.TradeCycleState.OPEN: ...
    """

    class StrategyRunState(StrEnum):
        """Per-strategy lifecycle, persisted in strategy registry."""

        STOPPED = "STOPPED"
        RUNNING = "RUNNING"
        SQUARING_OFF = "SQUARING_OFF"

    class TradeCycleState(StrEnum):
        """Per Entry to Exit pair, persisted in trade_cycles.state."""

        OPENING = "OPENING"
        OPEN = "OPEN"
        CLOSING = "CLOSING"
        CLOSED = "CLOSED"
        ABORTED = "ABORTED"

        def is_terminal(self) -> bool:
            return self.value in ("CLOSED", "ABORTED")

        def is_non_terminal(self) -> bool:
            return not self.is_terminal()

    class BuyOrderState(StrEnum):
        """Per entry order to broker, persisted in trades.order_state (SRD-EXE-018.006).

        A long entry is a BUY and a short entry a SELL; the state set is chosen by
        entry/exit, never by the order side.
        """

        NEW = "NEW"
        PARTIAL_FILLED = "PARTIAL_FILLED"
        FILLED = "FILLED"
        REJECTED = "REJECTED"
        CANCELLED = "CANCELLED"

    class SellOrderState(StrEnum):
        """Per exit order to broker, persisted in trades.order_state (SRD-EXE-018.006).

        A long exit is a SELL and a short exit a BUY.
        """

        NEW = "NEW"
        PARTIAL_FILLED = "PARTIAL_FILLED"
        FILLED = "FILLED"
        REJECTED = "REJECTED"
        CANCELLED = "CANCELLED"

    class LifecycleState(StrEnum):
        """Per (session_date, symbol) audit row. Internal — not shown in UI."""

        MONITORING = "MONITORING"
        ENTERED = "ENTERED"
        SKIPPED = "SKIPPED"
        EVICTED = "EVICTED"
        EXITED = "EXITED"

    class Action(StrEnum):
        """Direction of a TradeSignal emitted by the engine."""

        ENTRY = "entry"
        EXIT = "exit"

    class TradeDirection(StrEnum):
        """Long or short, fixed per strategy and per trade cycle (SRD-EXE-018.001)."""

        LONG = "LONG"
        SHORT = "SHORT"


__all__ = ["ExecutionEnums"]
