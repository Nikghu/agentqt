"""
Module: MD-MKT-006.001.M02 — market/news_step.py
Parent SRD: SRD-MKT-006.001
Also: SRD-MKT-006.002 (market headlines), SRD-MKT-006.003 (kept once, 30 days),
SRD-MKT-006.012 (run log)

Desk step "News", after "Ideas": keeps recent headlines for each listed idea of the
latest ideas day and recent market headlines in ``desk.db``. A failed feed is skipped and
logged; the step never fails the desk run.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.market.news import Getter, Headline, fetch_market, fetch_symbol, http_get
from us_swing.market.setup_review import listed_frame
from us_swing.market.store import MarketStore, NewsItemRow

log = logging.getLogger(__name__)

STOCK_WINDOW = timedelta(days=3)
MARKET_WINDOW = timedelta(hours=24)
KEEP_DAYS = timedelta(days=30)
PER_STOCK = 10
MARKET_MAX = 30
NEWS_BUDGET_S = 90.0


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _recent(items: list[Headline], now: datetime, window: timedelta, limit: int) -> list[Headline]:
    fresh = [h for h in items if now - window <= h.published <= now + timedelta(hours=1)]
    return sorted(fresh, key=lambda h: h.published, reverse=True)[:limit]


class NewsStep:
    """Collects stock and market headlines for the latest ideas day."""

    name = "News"

    def __init__(self, get: Getter = http_get, clock: Callable[[], datetime] = _utc_now,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        """Set the HTTP getter, clock and timer (all injectable for tests)."""
        self._get = get
        self._clock = clock
        self._monotonic = monotonic

    def __call__(self, ctx: StepContext) -> None:
        """Run the step inside a desk run; any error is logged, never raised."""
        try:
            store = MarketStore(ctx.home or desk_home())
            try:
                self._run(store)
            finally:
                store.close()
        except Exception:  # noqa: BLE001 — news must never fail the desk run
            log.exception("[News] Could not collect headlines")

    def _run(self, store: MarketStore) -> None:
        frame = store.read_frame("SELECT MAX(date) AS day FROM ideas")
        day = str(frame["day"].iloc[0]) if not frame.empty and frame["day"].iloc[0] else ""
        if not day:
            log.info("[News] No ideas yet; no headlines fetched")
            return
        now = self._clock()
        stamp = now.isoformat(timespec="seconds")
        symbols = sorted(set(listed_frame(store, day)["symbol"].astype(str)))
        rows: list[NewsItemRow] = []
        found = 0
        began = self._monotonic()
        for index, symbol in enumerate(symbols):
            if self._monotonic() - began > NEWS_BUDGET_S:
                log.warning("[News] Time limit reached; %d stock(s) not fetched",
                            len(symbols) - index)
                break
            items = fetch_symbol(symbol, self._get)
            kept = _recent(items or [], now, STOCK_WINDOW, PER_STOCK)
            found += bool(kept)
            rows.extend(_row(day, h, stamp) for h in kept)
        market, failed = fetch_market(self._get)
        market_kept = _recent(market, now, MARKET_WINDOW, MARKET_MAX)
        rows.extend(_row(day, h, stamp) for h in market_kept)
        added = store.add_news(rows)
        deleted = store.delete_news_before((now - KEEP_DAYS).isoformat(timespec="seconds"))
        log.info("[News] Headlines for %d of %d stock(s), %d market headline(s), %d new, "
                 "%d feed(s) failed, %d old row(s) deleted", found, len(symbols),
                 len(market_kept), added, failed, deleted)


def _row(day: str, h: Headline, stamp: str) -> NewsItemRow:
    return NewsItemRow(day, h.symbol, h.source, h.published.isoformat(timespec="seconds"),
                       h.title, h.link or None, stamp)
