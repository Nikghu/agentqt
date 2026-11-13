"""
Module: MD-MKT-010.003.M03 — market/lead_chat.py
Parent SRD: SRD-MKT-010.003
Also: SRD-MKT-010.004 (answer), SRD-MKT-010.005 (failed reply), SRD-MKT-010.006 (answers
only), SRD-MKT-010.008 (log lines), SRD-MKT-010.013 (session facts), SRD-MKT-010.014–.015
(session summaries and notes), SRD-MKT-010.016–.017 (one team ask and its update),
SRD-MKT-010.019 (log lines)

The lead chat skill: answers the Master's oldest open question from the day's facts, the
recent picks with their paper results and the last chat turns (of the question's session when
Chat sessions are on). It only explains: it has no tools and never approves, rejects or
trades. With sessions and agent messages on it may ask one expert per question and post the
reply as an update; it also writes the summary of each closing session.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem, Talker, talker
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_chat import (
    MAX_SUMMARY,
    ChatSession,
    ChatTurn,
    add_reply,
    add_update,
    chat_turns,
    closing_sessions,
    get_session,
    open_question,
    save_summary,
    session_turns,
    team_reply,
    team_subject,
    waiting_updates,
)
from us_swing.core.desk_msg import Remember
from us_swing.core.desk_results import results_view
from us_swing.core.econ_calendar import is_trading_day
from us_swing.data.market_calendar import ET
from us_swing.market.candles import CANDLE_DB
from us_swing.market.lead_brief import LeadBriefSkill

log = logging.getLogger(__name__)

KEY = "lead_chat"
RECENT_TURNS = 6
PICK_DAYS = 10
MAX_ANSWER = 1500
SUMMARIES_PER_WAKE = 2
SESSION_CHARS = 6000
FAILED_TEXT = "The desk could not answer this question. Please ask again later."
NO_TEAM = ("refused", "failed")
ASK_HINT = ("You may also send one message of type ask to one expert about this question. "
            "Answer the Master now with what you know; the expert's reply comes back to you "
            "and you will post it as an update.")
SUMMARY_HEAD = ("Summarise this chat session between the Master and you in at most 400 "
                "characters: the topics, what was agreed and what is still open. In remember, "
                "keep the summary as one note, and each preference the Master stated as one "
                "note that starts 'Master prefers'.")


class LeadChatAnswer(BaseModel):
    """The model's answer to one Master question, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=MAX_ANSWER,
                        description="Plain answer in short sentences, at most 1500 characters")


class LeadChatSummary(BaseModel):
    """The model's summary of a closing session, with up to 3 notes for its memory."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=MAX_SUMMARY,
                         description="The session in at most 400 characters")
    remember: list[Remember] = Field(default_factory=list, max_length=3,
                                     description="The summary as one note and each stated "
                                                 "preference of the Master as one note")


def _first_day(day: str) -> str:
    """The data day ``PICK_DAYS`` trading days before ``day``."""
    when = date.fromisoformat(day)
    count = 0
    while count < PICK_DAYS:
        when -= timedelta(days=1)
        count += is_trading_day(when)
    return when.isoformat()


def _now() -> datetime:
    return datetime.now(ET)


def _line(turn: ChatTurn) -> str:
    who = {"master": "Master", "update": "Lead (update)"}.get(turn.role, "Lead")
    return f"{who}: {turn.text}"


def _recent(home: Path, question: ChatTurn) -> list[str]:
    """The summary and last turns of the question's session, or the last chat turns."""
    if question.session is None:
        earlier = [t for t in chat_turns(home) if t.id < question.id]
        return [_line(t) for t in earlier[-RECENT_TURNS:]]
    session = get_session(home, question.session)
    head = [f"Session summary: {session.summary}"] if session and session.summary else []
    earlier = [t for t in session_turns(home, question.session) if t.id < question.id]
    return head + [_line(t) for t in earlier[-RECENT_TURNS:]]


def keep_one_ask(talk: Talker, start: int, question_id: int, on: bool) -> None:
    """Keep only the first new ask, named after the question; drop every other new draft."""
    new = talk.drafts[start:]
    first = next((d for d in new if d.type == "ask"), None) if on else None
    kept = ([first.model_copy(update={"subject": team_subject(question_id), "parent": None})]
            if first else [])
    talk.drafts[start:] = kept


def _drop_new(talk: Talker | None, start: int) -> None:
    if talk is not None:
        del talk.drafts[start:]


class LeadChatSkill:
    """Answers one Master question each time the chat employee is woken."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = LeadChatAnswer
    talks = True

    def __init__(self, candles: Path = CANDLE_DB, clock: Callable[[], datetime] = _now) -> None:
        """Set the candle file and the clock; both injectable for tests."""
        self._candles = candles
        self._clock = clock

    def facts(self, home: Path) -> Facts:
        """The open question, its recent chat, today's facts and the recent picks."""
        now = self._clock()
        question = open_question(home, now)
        if question is None:
            if load_settings(home).sessions_on and (waiting_updates(home, now)
                                                    or closing_sessions(home)):
                return Facts("Chat follow-ups", now.date().isoformat(), True)
            return Facts("", now.date().isoformat(), False, "no open question")
        today = LeadBriefSkill(self._candles).facts(home)
        day = today.data_day or now.date().isoformat()
        recent = _recent(home, question)
        view = results_view(home, now, _first_day(day))
        picks = [f"{p.day} {p.side} {p.symbol}: {p.decision}, paper {p.status or 'not worked out'}"
                 f", R {'-' if p.r is None else p.r}, real P&L "
                 f"{'-' if p.real_pnl is None else round(p.real_pnl, 2)}" for p in view.picks]
        text = "\n".join([
            f"Question #{question.id}: {question.text}", "",
            "Recent chat:", *(recent or ["(none)"]), "",
            f"Today ({day}):", today.text or f"(no fresh facts: {today.why_stale})", "",
            f"Picks of the last {PICK_DAYS} trading days:", *(picks or ["(none)"]),
        ])
        return Facts(text, day, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Answer the open question, post team updates and summarise closing sessions."""
        on = load_settings(ctx.home).sessions_on
        talk = talker(ctx)
        question = open_question(ctx.home, self._clock())
        if question is not None:
            self._answer(ctx, facts, question, talk, on)
        if not on:
            return []
        for asked in waiting_updates(ctx.home, self._clock()):
            self._update(ctx, asked, talk)
        for session in closing_sessions(ctx.home)[:SUMMARIES_PER_WAKE]:
            self._summarise(ctx, session, talk)
        return []

    def _answer(self, ctx: AgentContext, facts: Facts, question: ChatTurn,
                talk: Talker | None, on: bool) -> None:
        started = time.monotonic()
        start = len(talk.drafts) if talk else 0
        text = f"{facts.text}\n\n{ASK_HINT}" if talk is not None and on else facts.text
        reply = ctx.ask(text, LeadChatAnswer)
        if talk is not None:
            keep_one_ask(talk, start, question.id, on)
        add_reply(ctx.home, question.id, reply.answer if reply else FAILED_TEXT,
                  reply is not None, self._clock())
        if reply is None:
            log.warning("[Chat] Question %d got no answer", question.id)
        else:
            log.info("[Chat] Question %d answered in %.1f s", question.id,
                     time.monotonic() - started)

    def _update(self, ctx: AgentContext, asked: ChatTurn, talk: Talker | None) -> None:
        team = team_reply(ctx.home, asked.id)
        if team is None:
            return
        if team.result in NO_TEAM:
            text = f"The team could not answer: {team.text or team.result}"[:MAX_ANSWER]
        else:
            first = next((t.text for t in chat_turns(ctx.home, 200)
                          if t.role == "lead" and t.reply_to == asked.id), "")
            start = len(talk.drafts) if talk else 0
            reply = ctx.ask("\n".join([
                f"Master question #{asked.id}: {asked.text}", f"Your answer: {first}",
                f"The team's reply: {team.text}", "",
                "Write a short update for the Master from the team's reply."]), LeadChatAnswer)
            _drop_new(talk, start)
            if reply is None:
                return
            text = reply.answer
        if add_update(ctx.home, asked.id, text, self._clock()):
            log.info("[Chat] Update for question %d saved", asked.id)

    def _summarise(self, ctx: AgentContext, session: ChatSession, talk: Talker | None) -> None:
        turns = "\n".join(_line(t) for t in session_turns(ctx.home, session.id, 200))
        if not turns:
            save_summary(ctx.home, session.id, "")
            return
        start = len(talk.drafts) if talk else 0
        reply = ctx.ask(f"{SUMMARY_HEAD}\n\nSession: {session.title}\n{turns[-SESSION_CHARS:]}",
                        LeadChatSummary)
        _drop_new(talk, start)
        if reply is None:
            log.warning("[Chat] Session %d summary failed; tried again at the next wake",
                        session.id)
            return
        save_summary(ctx.home, session.id, reply.summary)
        log.info("[Chat] Session %d summary saved", session.id)
