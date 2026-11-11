"""
Module: MD-MKT-017.004.M02 — market/sentiment_news.py
Parent SRD: SRD-MKT-017.004

Headlines for a sentiment ticket: the desk's stored headlines of the last 7 days first,
and a fresh Yahoo feed only for stocks with no stored headline in the last 3 days, within
a 90-second budget. Fetched headlines are stored, so the next ticket reads them for free.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from us_swing.data.market_calendar import ET
from us_swing.market.news import Getter, fetch_symbol, http_get
from us_swing.market.store import MarketStore, NewsItemRow

log = logging.getLogger(__name__)

STORED_DAYS = 7
FRESH_DAYS = 3
PER_STOCK = 5
BUDGET_S = 90.0
TITLE_CUT = 110


@dataclass(frozen=True)
class Gathered:
    """Record lines per stock key, headline counts and how many stocks were fetched."""

    records: list[str]
    counts: dict[str, int]
    fetched: int


def _stored(store: MarketStore, symbol: str, since: datetime) -> list[tuple[str, str]]:
    frame = store.read_frame(
        "SELECT published, title FROM news_items WHERE symbol = ? AND published >= ? "
        f"ORDER BY published DESC LIMIT {PER_STOCK}",
        (symbol, since.isoformat(timespec="seconds")))
    return [(str(p), str(t)) for p, t in frame.itertuples(index=False)]


def _fetch(store: MarketStore, symbol: str, now: datetime, get: Getter) -> bool:
    found = fetch_symbol(symbol, get)
    if not found:
        return False
    day = now.astimezone(ET).date().isoformat()
    stamp = now.isoformat(timespec="seconds")
    store.add_news([NewsItemRow(day, h.symbol, h.source, h.published.isoformat(timespec="seconds"),
                                h.title, h.link or None, stamp) for h in found])
    return True


def gather_news(home: Path, stocks: Sequence[str], labels: dict[str, str],
                now: datetime | None = None, get: Getter = http_get,
                monotonic: Callable[[], float] = time.monotonic) -> Gathered:
    """Headline records for each ``side|symbol`` key, fetching only the gaps."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    started = monotonic()
    store = MarketStore(home)
    try:
        records: list[str] = []
        counts: dict[str, int] = {}
        fetched = 0
        for key in stocks:
            symbol = key.split("|", 1)[-1]
            if (not _stored(store, symbol, now - timedelta(days=FRESH_DAYS))
                    and monotonic() - started < BUDGET_S):
                fetched += int(_fetch(store, symbol, now, get))
            items = _stored(store, symbol, now - timedelta(days=STORED_DAYS))
            counts[key] = len(items)
            head = f"{key} ({labels.get(key, 'stock')})"
            if not items:
                records.append(f"{head}: no news")
                continue
            parts = [f"{p[:10]} {t.strip()[:TITLE_CUT]}" for p, t in items]
            records.append(f"{head}: " + "; ".join(parts))
        return Gathered(records, counts, fetched)
    finally:
        store.close()
