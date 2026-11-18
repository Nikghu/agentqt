"""
Module: MD-SCR-019.002.M38 — core/stock_context/_news.py
Parent SRD: SRD-SCR-019.002

Recent headlines per stock from Yahoo Finance: the newest 8 from the last 5 days,
kept in a daily cache. Sync and network-bound: run off the GUI thread.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from us_swing.core.stock_context._cache import DailyCache

_log = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path.home() / ".usswing" / "news_cache.json"
NEWS_DAYS = 5
NEWS_MAX = 8
_ISO = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True, slots=True)
class Headline:
    """One news headline; ``published`` is ISO UTC (``YYYY-MM-DDTHH:MM:SSZ``)."""

    title: str
    source: str
    published: str
    url: str = ""


Fetch = Callable[[str], list[Headline]]


def _parse_yahoo_item(item: Any) -> Headline | None:
    """One Yahoo news item in the current (``content``) or older flat format."""
    if not isinstance(item, dict):
        return None
    content = item.get("content")
    if isinstance(content, dict):
        title = content.get("title") or ""
        published = str(content.get("pubDate") or "")
        provider = content.get("provider") or {}
        link = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        source = provider.get("displayName", "") if isinstance(provider, dict) else ""
        url = link.get("url", "") if isinstance(link, dict) else ""
    else:
        title = item.get("title") or ""
        stamp = item.get("providerPublishTime")
        published = (datetime.fromtimestamp(stamp, timezone.utc).strftime(_ISO)
                     if isinstance(stamp, (int, float)) else "")
        source, url = str(item.get("publisher") or ""), str(item.get("link") or "")
    if not title or not published:
        return None
    return Headline(str(title), str(source), published, str(url))


def _yahoo_headlines(symbol: str) -> list[Headline]:
    import yfinance as yf  # type: ignore[import-untyped]

    items: Any = yf.Ticker(symbol).news
    parsed = (_parse_yahoo_item(item) for item in items or [])
    return [headline for headline in parsed if headline is not None]


def _when(headline: Headline) -> datetime | None:
    try:
        return datetime.strptime(headline.published, _ISO).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class NewsLookup:
    """Recent headlines per stock, fetched once per stock per day (SRD-SCR-019.002)."""

    def __init__(self, cache_path: Path | None = None, fetch: Fetch | None = None) -> None:
        self._path = cache_path or DEFAULT_CACHE_PATH
        self._fetch = fetch or _yahoo_headlines

    def headlines(self, symbols: Iterable[str], now: datetime) -> dict[str, list[Headline]]:
        """Return the newest ``NEWS_MAX`` headlines from the last ``NEWS_DAYS`` days.

        Args:
            symbols: Stocks to look up.
            now: Run time (UTC); the 5-day window ends here.

        Returns:
            Symbol → headlines, newest first. A failed lookup gives an empty list
            and is retried next call.
        """
        cache = DailyCache(self._path)
        day = now.date().isoformat()
        since = now - timedelta(days=NEWS_DAYS)
        result: dict[str, list[Headline]] = {}
        failed = 0
        for symbol in symbols:
            hit, saved = cache.get(symbol, day)
            if hit and isinstance(saved, list):
                result[symbol] = [Headline(**h) for h in saved if isinstance(h, dict)]
                continue
            try:
                fetched = self._fetch(symbol)
            except Exception:  # noqa: BLE001 — any data-source error only drops this stock
                failed += 1
                result[symbol] = []
                continue
            dated = [(when, h) for h in fetched if (when := _when(h)) and since <= when <= now]
            dated.sort(key=lambda pair: pair[0], reverse=True)
            result[symbol] = [h for _when_, h in dated[:NEWS_MAX]]
            cache.put(symbol, day, [asdict(h) for h in result[symbol]])
        if failed:
            _log.warning("[Screener] Headline lookup failed for %d stock(s)", failed)
        cache.save()
        return result
