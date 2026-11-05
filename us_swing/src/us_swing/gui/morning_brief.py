"""
Module: MD-INF-012.003.M03 — Morning Brief Builder
Parent SRD: SRD-INF-012.003

Fills a Morning brief with Yahoo pre-market quotes and, when AI notes are on, a short
AI comment (SRD-INF-012.004), then publishes it. Runs on a daemon thread so the GUI
never waits on the network or the AI.
"""
from __future__ import annotations

import dataclasses
import datetime
import logging
import threading
from collections.abc import Callable
from typing import Any

from us_swing.core.notifications import AiConfig, ask_ai
from us_swing.core.notifications._briefs import brief_facts, numbers_ok
from us_swing.core.notifications._events import MarketQuote, MorningBriefEvent
from us_swing.data.market_calendar import ET

_log = logging.getLogger(__name__)

INDEXES = ("SPY", "QQQ", "IWM")
VIX = "^VIX"
_AI_INSTRUCTION = (
    "Write a pre-market note of 2 or 3 short sentences for a swing trader, in plain text. "
    "Use only the facts given. Copy any number exactly as it is written in the facts and "
    "add no other numbers, dates or prices. Do not advise buying or selling. "
    "No markdown, no greeting, under 60 words."
)


def quote_from_bars(
    symbol: str, bars: Any, daily: Any, today: datetime.date
) -> MarketQuote | None:
    """Last extended-hours bar against the official close of the day before it.

    Args:
        symbol: Ticker shown in the brief.
        bars: Yahoo 5-minute history with extended hours (DatetimeIndex, ``Close``).
        daily: Yahoo daily history (official closes).
        today: The New York date of the brief.

    Returns:
        The quote, marked "last close" when the last bar is not from ``today``;
        None when there is no earlier close.
    """
    if bars is None or len(bars) == 0 or daily is None or len(daily) == 0:
        return None
    last_day = _et(bars.index[-1]).date()
    closes = [
        float(close) for when, close in zip(daily.index, daily["Close"], strict=True)
        if _et(when).date() < last_day
    ]
    if not closes or closes[-1] == 0:
        return None
    last = float(bars["Close"].iloc[-1])
    return MarketQuote(
        symbol=symbol, last=last, change_pct=(last / closes[-1] - 1) * 100,
        as_of="" if last_day == today else "last close",
    )


def _et(moment: Any) -> Any:
    return moment.tz_convert(ET) if moment.tzinfo else moment.tz_localize(ET)


def fetch_quotes(symbols: tuple[str, ...], today: datetime.date) -> dict[str, MarketQuote]:
    """Quotes from Yahoo 5-minute extended-hours bars; a failed symbol is left out."""
    import yfinance as yf  # type: ignore[import-untyped]

    quotes: dict[str, MarketQuote] = {}
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            bars = ticker.history(period="5d", interval="5m", prepost=True)
            daily = ticker.history(period="10d", interval="1d")
            quote = quote_from_bars(symbol.lstrip("^"), bars, daily, today)
        except Exception as exc:
            _log.warning("[Notify] Could not get the %s quote for the brief: %s", symbol, exc)
            continue
        if quote is not None:
            quotes[symbol] = quote
    return quotes


def build_brief(event: MorningBriefEvent, ai: AiConfig | None) -> MorningBriefEvent:
    """Add quotes and, when ``ai`` is given, a checked AI comment to ``event``.

    An index quote with no bar from today is left out; VIX has no pre-market
    trading, so its last close is shown and marked as such.
    """
    quotes = fetch_quotes((*INDEXES, VIX), datetime.datetime.now(ET).date())
    event = dataclasses.replace(
        event,
        quotes=tuple(quotes[s] for s in INDEXES if s in quotes and not quotes[s].as_of),
        vix=quotes.get(VIX),
    )
    if ai is None:
        return event
    facts = brief_facts(event)
    answer = ask_ai(ai, _AI_INSTRUCTION, facts)
    if answer.error:
        _log.warning("[Notify] Morning brief sent without the AI note: %s", answer.error)
        return event
    comment = " ".join(answer.text.split())
    if not numbers_ok(comment, facts):
        _log.warning("[Notify] AI note left out of the Morning brief: it used numbers not in the facts")
        return event
    return dataclasses.replace(event, ai_comment=comment)


def send_brief_async(
    event: MorningBriefEvent, ai: AiConfig | None, publish: Callable[[object], bool]
) -> threading.Thread:
    """Build the brief on a daemon thread and publish it; never raises."""

    def _job() -> None:
        try:
            brief = build_brief(event, ai)
        except Exception:
            _log.exception("[Notify] Could not finish the Morning brief; sending the basic one")
            brief = event
        if publish(brief):
            _log.info("[Notify] Morning brief sent")
        else:
            _log.warning("[Notify] Morning brief not sent: Telegram service not ready, will retry")

    thread = threading.Thread(target=_job, name="morning-brief", daemon=True)
    thread.start()
    return thread
