"""
Module: MD-MKT-006.001.M01 — market/news.py
Parent SRD: SRD-MKT-006.001
Also: SRD-MKT-006.002 (market headlines from fixed public RSS feeds)

Free headline sources, no API key: Yahoo Finance's per-symbol RSS feed for stocks, and a
short fixed list of market feeds. Each feed is fetched with a time limit and read with
``feedparser``; a bad feed or item is skipped, never raised.
"""
from __future__ import annotations

import calendar
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import feedparser  # type: ignore[import-untyped]
import httpx

log = logging.getLogger(__name__)

Getter = Callable[[str], str]
TIMEOUT_S = 10.0
_AGENT = "USSwing/1.0"
_YAHOO = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
_CNBC = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id={id}"
NEWS_FEEDS: dict[str, str] = {
    "CNBC top news": _CNBC.format(id="100003114"),
    "CNBC economy": _CNBC.format(id="20910258"),
    "Yahoo Finance SPY": _YAHOO.format(symbol="SPY"),
}


@dataclass(frozen=True)
class Headline:
    """One headline; ``symbol`` is empty for market headlines, ``published`` is UTC."""

    symbol: str
    source: str
    published: datetime
    title: str
    link: str


def http_get(url: str) -> str:
    """Fetch ``url`` as text within ``TIMEOUT_S``."""
    reply = httpx.get(url, timeout=TIMEOUT_S, headers={"User-Agent": _AGENT},
                      follow_redirects=True)
    reply.raise_for_status()
    return reply.text


def symbol_url(symbol: str) -> str:
    """Yahoo's per-symbol feed URL (``BRK.B`` becomes ``BRK-B``)."""
    return _YAHOO.format(symbol=symbol.replace(".", "-"))


def parse_feed(text: str, symbol: str, source: str) -> list[Headline]:
    """Read feed text; items without a title or a published time are skipped."""
    feed = feedparser.parse(text)
    out: list[Headline] = []
    for entry in feed.entries:
        title = str(entry.get("title") or "").strip()
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if not title or not stamp:
            continue
        published = datetime.fromtimestamp(calendar.timegm(stamp), UTC)
        out.append(Headline(symbol, source, published, title, str(entry.get("link") or "")))
    return out


def _fetch(url: str, symbol: str, source: str, get: Getter) -> list[Headline] | None:
    try:
        return parse_feed(get(url), symbol, source)
    except Exception as exc:  # noqa: BLE001 — a failed feed is skipped and logged
        name = f"{source} for {symbol}" if symbol else source
        log.info("[News] Could not read %s (%s)", name, _why(exc))
        return None


def _why(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timed out"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return "connection failed"


def fetch_symbol(symbol: str, get: Getter = http_get) -> list[Headline] | None:
    """Headlines for one stock, or ``None`` when the feed failed."""
    return _fetch(symbol_url(symbol), symbol, "Yahoo Finance", get)


def fetch_market(get: Getter = http_get) -> tuple[list[Headline], int]:
    """Market headlines from every feed, and the number of feeds that failed."""
    out: list[Headline] = []
    failed = 0
    for source, url in NEWS_FEEDS.items():
        items = _fetch(url, "", source, get)
        if items is None:
            failed += 1
        else:
            out.extend(items)
    return out, failed
