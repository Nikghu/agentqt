"""
Module: MD-MKT-006.005.M04 — market/news_review.py
Parent SRD: SRD-MKT-006.005
Also: SRD-MKT-006.006 (typed tags), SRD-MKT-006.007 (news points), SRD-MKT-006.008 (final
score in ``news_tags``), SRD-MKT-006.009 (market note in the feed)

The news review skill: reads the day's headlines and economic events, tags each listed
idea positive, neutral or negative, and turns the tags into news points and a final
score. Event points are stored by code before any model call, so they hold without an
answer. Uses only ``core`` types; it never imports the desk harness.
Also: MD-MKT-012.005.M03 — lessons block at the end of the facts (SRD-MKT-012.005)
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.econ_calendar import events_between, next_trading_day, trading_days_after
from us_swing.core.desk_lessons import with_lessons
from us_swing.market.candles import CANDLE_DB
from us_swing.market.setup_review import ideas_day, listed_frame, rule_regime, table
from us_swing.market.store import MarketStore, NewsTagRow

log = logging.getLogger(__name__)

KEY = "news_review"
TONE_POINTS = {"positive": 10.0, "neutral": 6.0, "none": 6.0, "negative": 2.0}
EVENT_POINTS = 3.0
NO_REVIEW = "No news review yet"
HEADLINES_PER_IDEA = 5
MARKET_HEADLINES = 15
EVENT_DAYS = 5
Reason = Annotated[str, StringConstraints(min_length=5, max_length=120)]


class NewsTag(BaseModel):
    """The news tone of one listed idea, judged for the idea's side (not the company)."""

    model_config = ConfigDict(extra="forbid")

    side: Literal["long", "short"]
    symbol: str = Field(min_length=1, max_length=12)
    tone: Literal["positive", "neutral", "negative"] = Field(
        description="Tone for the idea's side: for a short idea, bad company news is positive "
                    "and good company news is negative")
    reason: Reason


class NewsReview(BaseModel):
    """The model's answer for the news review skill, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    tags: list[NewsTag] = Field(min_length=1, max_length=20)
    market: str = Field(min_length=20, max_length=400)


def event_tomorrow(day: date) -> bool:
    """True when a high-importance event falls on the next trading day after ``day``."""
    nxt = next_trading_day(day)
    return any(e.importance == "high" for e in events_between(nxt, nxt))


def news_points(tone: str, day: date) -> float:
    """News points 0–10: by tone, minus the event points before a high-importance event."""
    points = TONE_POINTS[tone] - (EVENT_POINTS if event_tomorrow(day) else 0.0)
    return max(points, 0.0)


def _final(score: float, points: float) -> float:
    return round(0.9 * score + points, 1)


def _earlier_tags(store: MarketStore, day: str) -> dict[tuple[str, str], NewsTagRow]:
    """Real tags already stored for ``day``, so a failed later ask keeps them."""
    frame = store.read_frame("SELECT side, symbol, tone, reason, points, final_score FROM "
                             "news_tags WHERE date = ? AND tone <> 'none'", (day,))
    return {(str(s), str(y)): NewsTagRow(day, str(s), str(y), str(t), str(r), float(p),
                                         float(f))
            for s, y, t, r, p, f in frame.itertuples(index=False)}


def _news_day(store: MarketStore) -> str:
    frame = store.read_frame("SELECT MAX(date) AS day FROM news_items")
    return str(frame["day"].iloc[0]) if not frame.empty and frame["day"].iloc[0] else ""


class NewsReviewSkill:
    """The news review skill (a ``Skill``)."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = NewsReview

    def __init__(self, candles: Path = CANDLE_DB) -> None:
        """Use ``candles`` to check that the ideas are up to date."""
        self._candles = candles

    def facts(self, home: Path) -> Facts:
        """Build the facts; stale unless the news, ideas and SPY candles share one day."""
        store = MarketStore(home)
        try:
            day, why = ideas_day(store, self._candles)
            if why:
                return Facts("", day, False, why)
            news_day = _news_day(store)
            if news_day != day:
                return Facts("", day, False,
                             f"news is for {news_day or 'no day'} but the ideas are for {day}")
            listed = listed_frame(store, day)
            if listed.empty:
                return Facts("", day, False, f"no listed ideas for {day}")
            return Facts(with_lessons(self._text(store, day, listed), home, KEY, day), day,
                         True)
        finally:
            store.close()

    def _text(self, store: MarketStore, day: str, listed: pd.DataFrame) -> str:
        first = date.fromisoformat(day)
        events = pd.DataFrame(
            [(e.day.isoformat(), e.time.strftime("%H:%M"), e.name, e.importance)
             for e in events_between(next_trading_day(first),
                                     trading_days_after(first, EVENT_DAYS))],
            columns=["date", "time_ny", "event", "importance"])
        heads = store.read_frame(
            "SELECT symbol, substr(published, 1, 10) AS day, title FROM news_items "
            "WHERE date = ? ORDER BY published DESC", (day,))
        lines: list[str] = []
        for symbol in listed["symbol"].astype(str):
            mine = heads[heads["symbol"] == symbol].head(HEADLINES_PER_IDEA)
            lines.append(f"{symbol}:")
            lines.extend(f"  {d} | {t}" for d, t in zip(mine["day"], mine["title"], strict=True))
            if mine.empty:
                lines.append("  (no headlines)")
        market = heads[heads["symbol"] == ""].head(MARKET_HEADLINES)
        stock_count = int((heads["symbol"] != "").sum())
        return "\n\n".join([
            f"Data day: {day}",
            f"Regime by the rules: {rule_regime(store, day) or 'unknown'}",
            f"Economic events in the next {EVENT_DAYS} trading days:\n{table(events)}",
            f"Listed ideas:\n{table(listed[['side', 'symbol', 'sector', 'score']])}",
            "Headlines per idea (newest first):\n" + "\n".join(lines)
            + ("" if stock_count else "\n(no headlines for any idea today)"),
            "Market headlines (newest first):\n"
            + ("\n".join(f"  {d} | {t}" for d, t in zip(market["day"], market["title"],
                                                         strict=True)) or "  (none)"),
        ])

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Store code rows first, then ask for tags and store those with their points.

        Without a valid answer the code rows (event points) stay and no brief is posted,
        so a later run on the same data day asks again.
        """
        day = facts.data_day
        first = date.fromisoformat(day)
        store = MarketStore(ctx.home)
        try:
            listed = listed_frame(store, day)
            scores = {(str(s), str(y)): float(v) for s, y, v in
                      listed[["side", "symbol", "score"]].itertuples(index=False)}
            if not scores:
                return []
            none_points = news_points("none", first)
            earlier = _earlier_tags(store, day)
            rows = {k: earlier.get(k) or NewsTagRow(day, k[0], k[1], "none", NO_REVIEW,
                                                    none_points, _final(v, none_points))
                    for k, v in scores.items()}
            store.replace_day("news_tags", day, list(rows.values()))
            review = ctx.ask(facts.text, NewsReview)
            if review is None:
                return []
            done: set[tuple[str, str]] = set()
            dropped = 0
            for tag in review.tags:
                idea = (tag.side, tag.symbol.upper())
                if idea not in scores or idea in done:
                    dropped += 1
                    continue
                done.add(idea)
                points = news_points(tag.tone, first)
                rows[idea] = NewsTagRow(day, idea[0], idea[1], tag.tone, tag.reason, points,
                                        _final(scores[idea], points))
            if dropped:
                log.info("[AI Desk] News review named %d stock(s) that are not in today's "
                         "ideas or were named more than once", dropped)
            store.replace_day("news_tags", day, list(rows.values()))
        finally:
            store.close()
        return [FeedItem("info", review.market, day)]
