"""
Module: MD-INF-010.001.M05 — core/notifications/_formatters.py
Parent SRD: SRD-INF-010.005
Also: MD-INF-012.003.M02 (SRD-INF-012.003, SRD-INF-012.005) — Morning brief and Day-end v2 text

Maps an event type to the function that renders its user-facing message. A new
notification kind is added by registering a formatter — the dispatcher is never
touched.
"""
from __future__ import annotations

from typing import Callable

from us_swing.core.notifications._dto import NotificationMessage
from us_swing.core.notifications._events import (
    DayEndPnLEvent,
    MarketQuote,
    MorningBriefEvent,
    NotificationEvent,
    ScreenerApprovedEvent,
    ToolStartedEvent,
    TradeLine,
)

Formatter = Callable[[NotificationEvent], NotificationMessage]

_MAX_LIST = 5
_MAX_TRADES = 10


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


def money(value: float) -> str:
    """Signed whole dollars: ``+$412``, ``−$40``."""
    sign = "−" if value < 0 else "+"
    return f"{sign}${abs(value):,.0f}"


def _pct(value: float) -> str:
    sign = "−" if value < 0 else "+"
    return f"{sign}{abs(value):.2f}%"


def _trade_line(trade: TradeLine) -> str:
    pct = f" ({_pct(trade.pnl_pct)})" if trade.pnl_pct is not None else ""
    return f"{trade.symbol} {money(trade.pnl)}{pct}"


def _quote_line(quote: MarketQuote) -> str:
    note = f" ({quote.as_of})" if quote.as_of else ""
    return f"{quote.symbol} {quote.last:,.2f}  {_pct(quote.change_pct)}{note}"


def _title(name: str, session_date: str) -> str:
    return f"USSwing · {name}" + (f" · {session_date}" if session_date else "")


def _fmt_day_end_pnl(event: NotificationEvent) -> NotificationMessage:
    assert isinstance(event, DayEndPnLEvent)
    lines = [
        _title("Day-end report", event.session_date),
        "",
        f"Realized {money(event.realized)} · Unrealized {money(event.unrealized)}",
    ]
    trades = event.trades
    if trades:
        wins = sum(1 for t in trades if t.pnl > 0)
        best = max(trades, key=lambda t: t.pnl)
        worst = min(trades, key=lambda t: t.pnl)
        lines += [
            f"Trades closed: {event.trade_count} · Win rate {wins / len(trades):.0%}",
            "",
            *(_trade_line(t) for t in trades[:_MAX_TRADES]),
            "",
            f"Best {_trade_line(best)} · Worst {_trade_line(worst)}",
        ]
    else:
        lines.append("No trades closed today")
    return NotificationMessage(text="\n".join(lines), event_kind=DayEndPnLEvent.__name__)


def _fmt_morning_brief(event: NotificationEvent) -> NotificationMessage:
    assert isinstance(event, MorningBriefEvent)
    lines = [_title("Morning brief", event.session_date), "", "Market (pre-market vs previous close)"]
    market = [*event.quotes, *([event.vix] if event.vix else [])]
    lines += [_quote_line(q) for q in market] or ["Market data not available"]
    lines.append("")
    if event.open_count:
        lines.append(
            f"Open trades: {event.open_count} · Unrealized {money(event.unrealized)}"
        )
        lines += [_trade_line(t) for t in event.open_trades[:_MAX_LIST]]
    else:
        lines.append("Open trades: none")
    signals = ", ".join(event.signals[:_MAX_LIST]) if event.signals else "none"
    more = len(event.signals) - _MAX_LIST
    lines.append(f"Waiting signals: {signals}" + (f" and {more} more" if more > 0 else ""))
    if event.screener_top:
        when = f" ({event.screener_time})" if event.screener_time else ""
        lines.append(f"Screener{when}: {', '.join(event.screener_top[:_MAX_LIST])}")
    else:
        lines.append("Screener: no recent run")
    if event.ai_comment:
        lines += ["", "AI note", event.ai_comment]
    return NotificationMessage(text="\n".join(lines), event_kind=MorningBriefEvent.__name__)


def default_registry() -> FormatterRegistry:
    """Build a registry pre-populated with the built-in event formatters."""
    registry = FormatterRegistry()
    registry.register(ToolStartedEvent, _fmt_tool_started)
    registry.register(ScreenerApprovedEvent, _fmt_screener_approved)
    registry.register(DayEndPnLEvent, _fmt_day_end_pnl)
    registry.register(MorningBriefEvent, _fmt_morning_brief)
    return registry
