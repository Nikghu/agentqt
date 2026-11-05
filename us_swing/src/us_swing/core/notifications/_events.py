"""
Module: MD-INF-010.001.M01 — core/notifications/_events.py
Parent SRD: SRD-INF-010.001
Also: MD-INF-012.003.M02 (SRD-INF-012.003) — MorningBriefEvent, DayEndPnLEvent v2

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
class MarketQuote:
    """Last price and move against the previous close (MD-INF-012.003.M02)."""

    symbol: str
    last: float
    change_pct: float
    as_of: str = ""


@dataclass(frozen=True, slots=True)
class TradeLine:
    """One trade line: P&L in dollars and percent."""

    symbol: str
    pnl: float
    pnl_pct: float | None = None


@dataclass(frozen=True, slots=True)
class DayEndPnLEvent(NotificationEvent):
    realized: float = 0.0
    unrealized: float = 0.0
    trade_count: int = 0
    session_date: str = ""
    trades: tuple[TradeLine, ...] = ()


@dataclass(frozen=True, slots=True)
class MorningBriefEvent(NotificationEvent):
    """Pre-market brief (SRD-INF-012.003); empty parts mean no data."""

    session_date: str = ""
    quotes: tuple[MarketQuote, ...] = ()
    vix: MarketQuote | None = None
    open_trades: tuple[TradeLine, ...] = ()
    open_count: int = 0
    unrealized: float = 0.0
    signals: tuple[str, ...] = ()
    screener_time: str = ""
    screener_top: tuple[str, ...] = ()
    ai_comment: str = ""


NotificationEventType = Union[
    ToolStartedEvent, ScreenerApprovedEvent, DayEndPnLEvent, MorningBriefEvent
]


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
