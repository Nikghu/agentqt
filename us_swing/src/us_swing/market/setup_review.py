"""
Module: MD-MKT-005.009.M05 — market/setup_review.py
Parent SRD: SRD-MKT-005.009
Also: SRD-MKT-005.010 (grades kept in ``setup_review``)

The setup review skill: grades each listed idea of the day A, B or C with a short note.
Also holds the readers for the day's listed ideas that the risk check and the lead use.
Uses only ``core`` types; it never imports the desk harness.
Also: MD-MKT-012.005.M03 — lessons block at the end of the facts (SRD-MKT-012.005)
Also: SRD-MKT-005.019 (asks the news review, at most 3 ideas held), .021 (replies to a
send-back with a fix), .023 (fixed levels in the listed ideas), .024 (price facts for a
sent-back idea) — AI Desk v3 M1
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem, Talker, talker
from us_swing.core.desk_lessons import with_lessons
from us_swing.core.desk_messages import read_message
from us_swing.market.candles import CANDLE_DB, CandleReader
from us_swing.market.regime_view import latest_spy_day
from us_swing.market.risk_limits import ListedIdea
from us_swing.market.store import (
    FIXED_JOIN,
    FIXED_STOP,
    FIXED_TRIGGER,
    MarketStore,
    SetupReviewRow,
)

log = logging.getLogger(__name__)

KEY = "setup_review"
PER_SIDE = 10
MAX_HELD = 3
Side = Literal["long", "short"]
Note = Annotated[str, StringConstraints(min_length=5, max_length=120)]


class SetupGrade(BaseModel):
    """The grade of one listed idea."""

    model_config = ConfigDict(extra="forbid")

    side: Side
    symbol: str = Field(min_length=1, max_length=12)
    grade: Literal["A", "B", "C"]
    note: Note


class SetupReview(BaseModel):
    """The model's answer for the setup review skill, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    grades: list[SetupGrade] = Field(min_length=1, max_length=20)


def ideas_day(store: MarketStore, candles: Path) -> tuple[str, str]:
    """Return ``(day, why_stale)`` for the latest ideas day; ``why_stale`` is empty when fresh."""
    frame = store.read_frame("SELECT MAX(date) AS day FROM ideas")
    day = str(frame["day"].iloc[0]) if not frame.empty and frame["day"].iloc[0] else ""
    if not day:
        return "", "no ideas yet"
    spy_day = latest_spy_day(candles, store)
    if spy_day != day:
        return day, f"ideas are for {day} but the latest SPY candle is {spy_day}"
    return day, ""


def rule_regime(store: MarketStore, day: str) -> str:
    """The rule regime of ``day``, or an empty text when there is none."""
    frame = store.read_frame("SELECT regime FROM regime_snapshot WHERE date = ?", (day,))
    return str(frame["regime"].iloc[0]) if not frame.empty else ""


def listed_frame(store: MarketStore, day: str) -> pd.DataFrame:
    """The day's listed ideas, best 10 per side, with score parts (one row per idea)."""
    frame = store.read_frame(
        f"SELECT i.side, i.symbol, i.rank, i.score, i.sector, i.setup, "
        f"{FIXED_TRIGGER} AS \"trigger\", {FIXED_STOP} AS stop, "
        "s.rs_part, s.flow_part, s.setup_part, s.sector_part, s.regime_part, s.penalty "
        "FROM ideas i LEFT JOIN stock_score s ON s.date = i.date AND s.symbol = i.symbol "
        f"AND s.side = i.side {FIXED_JOIN} WHERE i.date = ? AND i.status = 'list' "
        "ORDER BY i.side, i.rank",
        (day,))
    return frame.groupby("side", group_keys=False).head(PER_SIDE).reset_index(drop=True)


def listed_ideas(frame: pd.DataFrame) -> list[ListedIdea]:
    """Turn a listed-ideas frame into ``ListedIdea`` values for the risk limits."""
    def num(value: Any) -> float | None:
        return None if value is None or pd.isna(value) else float(value)

    rows = frame.to_dict("records")
    return [ListedIdea(str(r["side"]), str(r["symbol"]), int(r["rank"]), str(r["sector"] or ""),
                       num(r["trigger"]), num(r["stop"])) for r in rows]


def reasons_text(store: MarketStore, day: str) -> dict[tuple[str, str], str]:
    """The day's idea reasons joined into one line per ``(side, symbol)``."""
    frame = store.read_frame(
        "SELECT side, symbol, reason FROM idea_reasons WHERE date = ? ORDER BY side, symbol, "
        "seq", (day,))
    out: dict[tuple[str, str], list[str]] = {}
    for r in frame.itertuples(index=False):
        out.setdefault((str(r.side), str(r.symbol)), []).append(str(r.reason))
    return {k: "; ".join(v) for k, v in out.items()}


def table(frame: pd.DataFrame) -> str:
    """A frame as plain text, or ``(none)``."""
    return frame.to_string(index=False) if not frame.empty else "(none)"


class SetupReviewSkill:
    """The setup review skill (a ``Skill``)."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = SetupReview
    talks = True

    def __init__(self, candles: Path = CANDLE_DB) -> None:
        """Use ``candles`` to check that the ideas are up to date."""
        self._candles = candles

    def facts(self, home: Path) -> Facts:
        """Build the facts from the day's listed ideas; stale when the ideas lag SPY."""
        store = MarketStore(home)
        try:
            day, why = ideas_day(store, self._candles)
            if why:
                return Facts("", day, False, why)
            listed = listed_frame(store, day)
            if listed.empty:
                return Facts("", day, False, f"no listed ideas for {day}")
            reasons = reasons_text(store, day)
            listed = listed.assign(reasons=[reasons.get((str(s), str(y)), "") for s, y in
                                            zip(listed["side"], listed["symbol"], strict=True)])
            text = "\n\n".join([
                f"Data day: {day}",
                f"Regime by the rules: {rule_regime(store, day) or 'unknown'}",
                f"Listed ideas (score parts out of 20, 15 for sector and regime):\n"
                f"{table(listed)}",
            ])
            return Facts(with_lessons(text, home, KEY, day), day, True)
        finally:
            store.close()

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Ask for the grades, keep the ones for today's listed ideas and post a count.

        The count brief also marks the day as done, so the employee is not asked again.
        """
        text = facts.text
        if facts.inbox:
            text += _price_facts(self._candles, ctx.home, facts)
        review = ctx.ask(text, SetupReview)
        if review is None:
            return []
        talk = talker(ctx)
        if talk is not None:
            _trim_asks(talk)
        store = MarketStore(ctx.home)
        try:
            known = {(str(s), str(y)) for s, y in
                     listed_frame(store, facts.data_day)[["side", "symbol"]].itertuples(
                         index=False)}
            rows: dict[tuple[str, str], SetupReviewRow] = {}
            dropped = 0
            for g in review.grades:
                idea = (g.side, g.symbol.upper())
                if idea not in known or idea in rows:
                    dropped += 1
                    continue
                rows[idea] = SetupReviewRow(facts.data_day, g.side, idea[1], g.grade, g.note)
            if dropped:
                log.info("[AI Desk] Setup review named %d stock(s) not in today's ideas or "
                         "twice", dropped)
            if facts.inbox:
                store.put_rows("setup_review", facts.data_day, list(rows.values()))
            else:
                store.replace_day("setup_review", facts.data_day, list(rows.values()))
        finally:
            store.close()
        if not rows or facts.inbox:
            return []
        counts = {g: sum(1 for r in rows.values() if r.grade == g) for g in "ABC"}
        text = (f"Setup review: {len(rows)} idea(s) graded - A {counts['A']}, B {counts['B']}, "
                f"C {counts['C']}")
        return [FeedItem("info", text, facts.data_day)]


def _trim_asks(talk: Talker) -> None:
    """Keep asks until they name 3 ideas in all; drop and log the rest (SRD-MKT-005.019).

    The model leaves out the grade of an idea it asks about, so that idea is graded on the
    wake that brings the reply (or its refusal or expiry).
    """
    held: set[str] = set()
    kept = []
    for draft in talk.drafts:
        if draft.type == "ask":
            named = {s.upper() for s in draft.about or []}
            if len(held | named) > MAX_HELD:
                log.info("[AI Desk] Setup review asked about more than %d ideas; extra "
                         "question not sent", MAX_HELD)
                continue
            held |= named
        kept.append(draft)
    talk.drafts[:] = kept


def idea_of(text: str) -> tuple[str, str] | None:
    """``(side, SYMBOL)`` from a send-back text that starts ``<side> <SYMBOL>:``."""
    head = text.split(":", 1)[0].split()
    if len(head) != 2 or head[0] not in ("long", "short"):
        return None
    return head[0], head[1].upper()


def _price_facts(candles: Path, home: Path, facts: Facts) -> str:
    """Price facts for each idea sent back in the inbox, to choose new levels (SRD-MKT-005.024)."""
    ideas = []
    for mid in facts.inbox:
        msg = read_message(home, mid)
        if msg is not None and msg.type == "send_back":
            idea = idea_of(getattr(msg.body, "text", None) or "")
            if idea is not None:
                ideas.append(idea)
    if not ideas:
        return ""
    try:
        bars = CandleReader(candles, topup=home).read({s for _side, s in ideas})
    except FileNotFoundError:
        return ""
    lines = ["", "", "Price facts for the ideas sent back (daily bars up to the data day):"]
    for side, symbol in ideas:
        lines.append(_price_line(bars.closes, bars.highs, bars.lows, side, symbol,
                                 facts.data_day))
    return "\n".join(lines)


def _price_line(closes: pd.DataFrame, highs: pd.DataFrame, lows: pd.DataFrame, side: str,
                symbol: str, day: str) -> str:
    if symbol not in closes.columns:
        return f"  {side} {symbol}: no daily bars"
    end = pd.Timestamp(day)
    c, h, lo = (f[symbol].loc[:end].dropna() for f in (closes, highs, lows))
    if len(c) < 21:
        return f"  {side} {symbol}: fewer than 21 daily bars"
    prev = c.shift(1)
    true_range = pd.concat([h - lo, (h - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)
    atr = float(true_range.iloc[-14:].mean())
    return (f"  {side} {symbol}: last close {c.iloc[-1]:.2f}, ATR(14) {atr:.2f}, "
            f"10-day low {lo.iloc[-10:].min():.2f}, 10-day high {h.iloc[-10:].max():.2f}, "
            f"20-day low {lo.iloc[-20:].min():.2f}, 20-day high {h.iloc[-20:].max():.2f}")
