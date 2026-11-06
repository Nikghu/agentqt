"""
Module: MD-MKT-010.003.M03 — market/lead_chat.py
Parent SRD: SRD-MKT-010.003
Also: SRD-MKT-010.004 (answer), SRD-MKT-010.005 (failed reply), SRD-MKT-010.006 (answers
only), SRD-MKT-010.008 (log lines)

The lead chat skill: answers the Master's oldest open question from the day's facts, the
recent picks with their paper results and the last chat turns. It only explains; it has no
tools and its answer is one text, so it can never approve, reject or trade.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_chat import add_reply, chat_turns, open_question
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
FAILED_TEXT = "The desk could not answer this question. Please ask again later."


class LeadChatAnswer(BaseModel):
    """The model's answer to one Master question, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=MAX_ANSWER,
                        description="Plain answer in short sentences, at most 1500 characters")


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


class LeadChatSkill:
    """Answers one Master question each time the chat employee is woken."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = LeadChatAnswer

    def __init__(self, candles: Path = CANDLE_DB, clock: Callable[[], datetime] = _now) -> None:
        """Set the candle file and the clock; both injectable for tests."""
        self._candles = candles
        self._clock = clock

    def facts(self, home: Path) -> Facts:
        """The open question, the recent chat, today's facts and the recent picks."""
        now = self._clock()
        question = open_question(home, now)
        if question is None:
            return Facts("", now.date().isoformat(), False, "no open question")
        today = LeadBriefSkill(self._candles).facts(home)
        day = today.data_day or now.date().isoformat()
        earlier = [t for t in chat_turns(home) if t.id < question.id][-RECENT_TURNS:]
        recent = [f"{'Master' if t.role == 'master' else 'Lead'}: {t.text}" for t in earlier]
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
        """Ask for the answer and save it, or save a failed reply; no feed item."""
        question = open_question(ctx.home, self._clock())
        if question is None:
            return []
        started = time.monotonic()
        reply = ctx.ask(facts.text, LeadChatAnswer)
        add_reply(ctx.home, question.id, reply.answer if reply else FAILED_TEXT,
                  reply is not None, self._clock())
        if reply is None:
            log.warning("[Chat] Question %d got no answer", question.id)
        else:
            log.info("[Chat] Question %d answered in %.1f s", question.id,
                     time.monotonic() - started)
        return []
