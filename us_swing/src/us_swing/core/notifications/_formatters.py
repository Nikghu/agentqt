"""
Module: MD-INF-010.001.M05 — core/notifications/_formatters.py
Parent SRD: SRD-INF-010.005

Maps an event type to the function that renders its user-facing message. A new
notification kind is added by registering a formatter — the dispatcher is never
touched.
"""
from __future__ import annotations

from typing import Callable

from us_swing.core.notifications._dto import NotificationMessage
from us_swing.core.notifications._events import (
    DayEndPnLEvent,
    NotificationEvent,
    ScreenerApprovedEvent,
    ToolStartedEvent,
)

Formatter = Callable[[NotificationEvent], NotificationMessage]


class FormatterRegistry:
    """Registry of per-event-type message formatters."""

    def __init__(self) -> None:
        self._formatters: dict[type, Formatter] = {}

    def register(self, event_type: type, formatter: Formatter) -> None:
        """Register the formatter used to render ``event_type``."""
        self._formatters[event_type] = formatter

    def render(self, event: NotificationEvent) -> NotificationMessage:
        """Render ``event`` into a channel-ready message.

        Raises:
            KeyError: if no formatter is registered for the event's type.
        """
        try:
            formatter = self._formatters[type(event)]
        except KeyError:
            raise KeyError(
                f"No notification formatter registered for {type(event).__name__}"
            ) from None
        return formatter(event)


def _fmt_tool_started(event: NotificationEvent) -> NotificationMessage:
    assert isinstance(event, ToolStartedEvent)
    version = f" (v{event.app_version})" if event.app_version else ""
    return NotificationMessage(
        text=f"USSwing started{version}",
        event_kind=ToolStartedEvent.__name__,
    )


def _fmt_screener_approved(event: NotificationEvent) -> NotificationMessage:
    assert isinstance(event, ScreenerApprovedEvent)
    names = ", ".join(event.symbols) if event.symbols else "no stocks"
    return NotificationMessage(
        text=f"Screener approved {len(event.symbols)} stock(s): {names}",
        event_kind=ScreenerApprovedEvent.__name__,
    )


def _fmt_day_end_pnl(event: NotificationEvent) -> NotificationMessage:
    assert isinstance(event, DayEndPnLEvent)
    return NotificationMessage(
        text=(
            f"Day-end P&L — realized ${event.realized:,.2f}, "
            f"unrealized ${event.unrealized:,.2f} across {event.trade_count} trade(s)"
        ),
        event_kind=DayEndPnLEvent.__name__,
    )


def default_registry() -> FormatterRegistry:
    """Build a registry pre-populated with the built-in event formatters."""
    registry = FormatterRegistry()
    registry.register(ToolStartedEvent, _fmt_tool_started)
    registry.register(ScreenerApprovedEvent, _fmt_screener_approved)
    registry.register(DayEndPnLEvent, _fmt_day_end_pnl)
    return registry
