"""
Module: MD-MKT-005.014.M08 — market/lead_brief.py
Parent SRD: SRD-MKT-005.014
Also: SRD-MKT-005.015 (picks and morning brief), SRD-MKT-005.016 (``lead_picks``, feed kind
``morning``), SRD-MKT-006.010 (news view and final scores in the facts)

The lead brief skill: reads the day's views and picks the final ideas, only from ideas
that passed the risk check, then writes the morning brief for the Floor. The hard limits
are applied again here, so a vetoed idea is never offered even without a risk check.
Uses only ``core`` types; it never imports the desk harness.
Also: MD-MKT-012.005.M03 — lessons block at the end of the facts (SRD-MKT-012.005)
Also: MD-MKT-014.001.M01 — tickets in the answer, research block, tickets to the queue
Also: SRD-MKT-017.007 — sentiment cards block after the ideas table
Also: SRD-MKT-018.010 — books block (uploaded books, topic form, chapters read)
Also: SRD-MKT-019.011 — untested strategy cards block after the books block
(SRD-MKT-014.001, .004, .005)
Also: MD-MKT-020.004.M03 — company day (SRD-MKT-020.004 stand-up first, .006 huddle call and
wait, .010 huddle block, .011 day call, .024 log lines); DD-MKT-020.001.D01 §2, §3, §6
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Annotated, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem, talker
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_day import (
    CHECK_DAYS,
    MARKETS,
    can_huddle,
    clash,
    huddle_block,
    huddle_called,
    huddle_open,
    mark_huddle,
    save_call,
    save_standup,
    standup_text,
    views,
)
from us_swing.core.desk_memory import add_trading_days
from us_swing.core.desk_msg import Draft
from us_swing.core.desk_cards import untested_block
from us_swing.core.desk_lessons import with_lessons
from us_swing.core.desk_research import TicketAsk, raise_tickets, with_research
from us_swing.market.book_cards import books_block
from us_swing.market.candles import CANDLE_DB
from us_swing.market.risk_check import views_text
from us_swing.market.risk_limits import code_vetoes
from us_swing.market.sentiment_cards import cards_block
from us_swing.market.setup_review import (
    ideas_day,
    listed_frame,
    listed_ideas,
    reasons_text,
    rule_regime,
    table,
)
from us_swing.market.store import LeadPickRow, MarketStore

log = logging.getLogger(__name__)

KEY = "lead_brief"
PICKS_PER_SIDE = 5
Reason = Annotated[str, StringConstraints(min_length=5, max_length=120)]


class LeadPick(BaseModel):
    """One final idea picked by the lead."""

    model_config = ConfigDict(extra="forbid")

    side: Literal["long", "short"]
    symbol: str = Field(min_length=1, max_length=12)
    reason: Reason


class LeadBrief(BaseModel):
    """The model's answer for the lead brief skill, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    picks: list[LeadPick] = Field(default_factory=list, max_length=10)
    morning: str = Field(min_length=40, max_length=1200)
    tickets: list[TicketAsk] = Field(default_factory=list, max_length=3)


class DayCall(BaseModel):
    """The lead's call for the day: market view and sectors to favour (SRD-MKT-020.011)."""

    model_config = ConfigDict(extra="forbid")

    market: Literal["Uptrend", "Choppy", "Downtrend"]
    favour: list[Annotated[str, StringConstraints(max_length=40)]] = Field(min_length=1,
                                                                            max_length=3)
    note: str = Field(default="", max_length=200)


class LeadBriefWithCall(LeadBrief):
    """The lead answer while the company day is on."""

    call: DayCall


HUDDLE_SUBJECT = "Huddle: views clash"
HUDDLE_TO = "skill:regime_view,skill:sector_flow_view"


def _now() -> datetime:
    return datetime.now(ZoneInfo("America/New_York"))


def passed_frame(store: MarketStore, day: str) -> pd.DataFrame:
    """Listed ideas of ``day`` that break no hard limit and were not vetoed in ``risk_check``."""
    listed = listed_frame(store, day)
    if listed.empty:
        return listed
    vetoed = set(code_vetoes(listed_ideas(listed), rule_regime(store, day)))
    risk = store.read_frame("SELECT side, symbol FROM risk_check WHERE date = ? AND "
                            "verdict = 'veto'", (day,))
    vetoed |= {(str(s), str(y)) for s, y in risk.itertuples(index=False)}
    keep = [(str(s), str(y)) not in vetoed for s, y in
            zip(listed["side"], listed["symbol"], strict=True)]
    return listed[keep].reset_index(drop=True)


class LeadBriefSkill:
    """The lead brief skill (a ``Skill``)."""

    key = KEY
    needs: tuple[str, ...] = ("regime_view", "sector_flow_view", "setup_review", "news_review",
                              "risk_check")
    answer = LeadBrief

    def __init__(self, candles: Path = CANDLE_DB,
                 clock: Callable[[], datetime] = _now) -> None:
        """Use ``candles`` to check that the ideas are up to date; ``clock`` is New York time."""
        self._candles = candles
        self._clock = clock

    def facts(self, home: Path) -> Facts:
        """Build the facts: every view of the day and the ideas that passed."""
        facts = self._facts(home)
        if not facts.fresh or not load_settings(home).company_day_on:
            return facts
        day = facts.data_day
        head = [standup_text(home, day)]
        block = huddle_block(home, day)
        if block:
            head.append(block)
        head.append(_call_ask(home, day))
        return Facts("\n\n".join([*head, facts.text]), day, True)

    def _facts(self, home: Path) -> Facts:
        store = MarketStore(home)
        try:
            day, why = ideas_day(store, self._candles)
            if why:
                return Facts("", day, False, why)
            passed = passed_frame(store, day)
            grades = store.read_frame("SELECT side, symbol, grade FROM setup_review "
                                      "WHERE date = ?", (day,))
            grade = {(str(s), str(y)): str(g) for s, y, g in grades.itertuples(index=False)}
            tags = store.read_frame("SELECT side, symbol, final_score FROM news_tags "
                                    "WHERE date = ?", (day,))
            final = {(str(s), str(y)): f"{float(v):.1f}" for s, y, v in
                     tags.itertuples(index=False)}
            reasons = reasons_text(store, day)
            keys = list(zip(passed["side"].astype(str), passed["symbol"].astype(str),
                            strict=True))
            shown = passed[["side", "symbol", "score", "sector", "setup", "trigger", "stop"]]
            shown = shown.assign(final=[final.get(k, "-") for k in keys],
                                 grade=[grade.get(k, "-") for k in keys],
                                 reasons=[reasons.get(k, "") for k in keys])
            text = "\n\n".join([
                f"Data day: {day}",
                f"Regime by the rules: {rule_regime(store, day) or 'unknown'}",
                views_text(store, day, self.needs),
                f"Ideas you may pick (they passed the risk check), at most {PICKS_PER_SIDE} "
                f"per side:\n{table(shown)}",
            ])
            cards = cards_block(home, keys, day)
            text = f"{text}\n\n{cards}" if cards else text
            books = books_block(home, home / "books")
            text = f"{text}\n\n{books}" if books else text
            untested = untested_block(home)
            text = f"{text}\n\n{untested}" if untested else text
            text = with_lessons(text, home, KEY, day)
            return Facts(with_research(text, home, KEY, self._clock()), day, True)
        finally:
            store.close()

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Ask for the picks and the morning brief; keep only picks that passed."""
        day_on = load_settings(ctx.home).company_day_on
        if day_on and self._huddle(ctx, facts):
            return []
        brief = ctx.ask(facts.text, LeadBriefWithCall if day_on else LeadBrief)
        if brief is None:
            return []
        if isinstance(brief, LeadBriefWithCall):
            self._keep_day(ctx.home, facts.data_day, brief.call)
        if brief.tickets:
            raise_tickets(ctx.home, KEY, brief.tickets, self._clock())
        store = MarketStore(ctx.home)
        try:
            day = facts.data_day
            allowed = {(str(s), str(y)) for s, y in
                       passed_frame(store, day)[["side", "symbol"]].itertuples(index=False)}
            rows: dict[tuple[str, str], LeadPickRow] = {}
            per_side = {"long": 0, "short": 0}
            dropped = 0
            for pick in brief.picks:
                idea = (pick.side, pick.symbol.upper())
                if idea not in allowed or idea in rows or per_side[pick.side] >= PICKS_PER_SIDE:
                    dropped += 1
                    continue
                per_side[pick.side] += 1
                rows[idea] = LeadPickRow(day, idea[0], idea[1], per_side[pick.side],
                                         pick.reason)
            if dropped:
                log.info("[AI Desk] Lead brief named %d pick(s) that were not allowed",
                         dropped)
            store.replace_day("lead_picks", day, list(rows.values()))
        finally:
            store.close()
        return [FeedItem("morning", brief.morning, day)]

    def _huddle(self, ctx: AgentContext, facts: Facts) -> bool:
        """Call the day's huddle on a clash, or wait while it is open; ``True`` to stop now."""
        home, day = ctx.home, facts.data_day
        talk = talker(ctx)
        if talk is None:
            return False
        if not facts.inbox and not huddle_called(home, day) and can_huddle(home):
            why = clash(*views(home, day))
            if why:
                talk.send(Draft(type="meeting", to=HUDDLE_TO, subject=HUDDLE_SUBJECT,
                                text=f"{why} Reply in one or two lines: what do you see, "
                                     "and should we lean your way today?"))
                mark_huddle(home, day, why, self._clock())
                log.info("[Company day] Huddle called for %s: %s", day, why)
                return True
        return huddle_open(home, day)

    def _keep_day(self, home: Path, day: str, call: DayCall) -> None:
        """Save the stand-up and the day call with the experts' votes."""
        now = self._clock()
        save_standup(home, day, standup_text(home, day), now)
        known = set(_sector_names(home, day))
        favour = [s for s in call.favour if s in known]
        if len(favour) < len(call.favour):
            log.info("[Company day] Day call named %d sector(s) that are not in the list",
                     len(call.favour) - len(favour))
        if not favour:
            return
        votes = save_call(home, day, call.market, favour, call.note,
                          add_trading_days(day, CHECK_DAYS), now)
        agreed = sum(1 for v in votes if v.stance == "agreed")
        log.info("[Company day] Day call for %s: %s, favour %s; %d of %d expert(s) agreed",
                 day, call.market, ", ".join(favour), agreed, len(votes))


def _sector_names(home: Path, day: str) -> list[str]:
    store = MarketStore(home)
    try:
        frame = store.read_frame("SELECT sector FROM sector_daily WHERE date = (SELECT "
                                 "MAX(date) FROM sector_daily WHERE date <= ?) ORDER BY rank",
                                 (day,))
    finally:
        store.close()
    return [str(s) for s in frame["sector"]]


def _call_ask(home: Path, day: str) -> str:
    names = ", ".join(_sector_names(home, day)) or "none saved"
    return (f"Day call: also give the market for today ({', '.join(MARKETS)}), 1 to 3 "
            f"sectors to favour from: {names}, and a short note. The call is checked "
            f"{CHECK_DAYS} trading days from now.")
