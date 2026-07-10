"""
Module: MD-INF-010.001.M01 — core/notifications/_events.py
Parent SRD: SRD-INF-010.001

Frozen ``NotificationEvent`` variants plus an in-process publish/subscribe bus.
A new notification kind is a new frozen subclass here — nothing in the bus,
dispatcher, or channels changes (open/closed).
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Union

from us_swing.core.notifications._protocols import NotificationBus

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Event variants ───────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class NotificationEvent:
    """Base for every notification. Carries a timestamp and a schema version so
    older serialised events remain readable as the payloads evolve."""

    occurred_at: datetime = field(default_factory=_now)
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class ToolStartedEvent(NotificationEvent):
    app_version: str = ""


@dataclass(frozen=True, slots=True)
class ScreenerApprovedEvent(NotificationEvent):
    symbols: tuple[str, ...] = ()
    run_id: str = ""


@dataclass(frozen=True, slots=True)
class DayEndPnLEvent(NotificationEvent):
    realized: float = 0.0
    unrealized: float = 0.0
    trade_count: int = 0


NotificationEventType = Union[ToolStartedEvent, ScreenerApprovedEvent, DayEndPnLEvent]


# ── In-process bus ───────────────────────────────────────────────────────────

class _InProcessBus(NotificationBus):
    """Single-process synchronous bus. ``publish`` invokes handlers on the
    calling thread in registration order; a handler that raises is caught and
    logged under ``[Notify]`` and never blocks its siblings or the caller."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handlers: list[Callable[[Any], None]] = []

    def subscribe(self, handler: Callable[[Any], None]) -> None:
        with self._lock:
            self._handlers.append(handler)

    def publish(self, event: Any) -> None:
        with self._lock:
            handlers = list(self._handlers)
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                log.error(
                    "[Notify] Event handler %s failed on %s: %r",
                    getattr(handler, "__qualname__", repr(handler)),
                    type(event).__name__,
                    exc,
                )
