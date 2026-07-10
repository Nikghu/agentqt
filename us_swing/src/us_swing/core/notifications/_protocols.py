"""
Module: MD-INF-010.001.M02 — core/notifications/_protocols.py
Parent SRD: SRD-INF-010.002

Public Protocol surface for the notification service. Consumers type-annotate
against these, never against the concrete channel, bus, or dispatcher classes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from us_swing.core.notifications._dto import NotificationMessage


@runtime_checkable
class NotificationChannel(Protocol):
    """A delivery destination. Telegram is the first implementation; email,
    Slack, or SMS channels satisfy the same surface without any other change."""

    name: str

    async def send(self, message: NotificationMessage) -> None:
        """Deliver one rendered message. May raise on transport failure — the
        dispatcher isolates and logs it so the producer is never affected."""
        ...


@runtime_checkable
class NotificationBus(Protocol):
    """Publish/subscribe seam between event producers and the dispatcher.

    Producers depend only on this Protocol and the event DTOs, never on the
    dispatcher or any channel."""

    def subscribe(self, handler: Callable[[Any], None]) -> None:
        """Register a handler invoked for every published event."""
        ...

    def publish(self, event: Any) -> None:
        """Deliver an event to all subscribers. Never raises to the caller."""
        ...


@runtime_checkable
class CommandPort(Protocol):
    """Read-only query surface backing the inbound bot commands.

    The command router depends only on this Protocol, never on the GUI. Each
    method returns a ready, user-facing reply string. The GUI adapter implements
    it, marshalling every call onto the GUI thread."""

    def status(self) -> str:
        """Feed connection and market-session summary."""
        ...

    def pnl(self) -> str:
        """Realized and unrealized profit-and-loss summary."""
        ...

    def positions(self) -> str:
        """Currently open positions."""
        ...

    def signals(self) -> str:
        """Pending trade signals awaiting review."""
        ...

    def screener(self) -> str:
        """Latest screener results."""
        ...

    def cycles(self) -> str:
        """Open and recently closed trade cycles."""
        ...
