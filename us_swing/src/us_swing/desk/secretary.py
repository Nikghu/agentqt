"""
Module: MD-DSK-006.016.M36 — desk/secretary.py
Parent SRD: SRD-DSK-006.016
Also: SRD-DSK-006.017 (picks), .018 (save and ask), .021 (no view from a code reply), .024
(off), .027 (log lines) — AI Desk v3 M7a

The desk secretary. Once a week, after the weekly report, it reads the hire needs found by code
and proposes up to 2 trial hires; each goes to its boss as one ask for a one-line view. The
evidence is written by code; the model only picks candidates, a model and a short reason. A
reply in its inbox is handled by code with no AI call. Design: DD-DSK-006.011.D01.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem, Talker, talker
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_employee import known_models
from us_swing.core.desk_hiring import HIRE_LEVELS, employees, seat_counts
from us_swing.core.desk_memory import failure_rows
from us_swing.core.desk_messages import read_message
from us_swing.core.desk_msg import AskBody, Draft, ReplyBody, Verdict, Want
from us_swing.core.desk_proposals import (
    NO_ANSWER,
    NO_VIEW,
    OFF,
    PENDING,
    Candidate,
    candidates,
    note_view,
    proposal_inputs,
    proposal_of_ask,
    save_proposal,
    waiting_proposals,
)
from us_swing.core.desk_registry import HIRE_PROPOSAL
from us_swing.core.desk_research import holder
from us_swing.desk.recorder import ny_now

log = logging.getLogger(__name__)

KEY = "hire_review"
MAX_PICKS = 2
MAX_FAILURES = 10
WEEK_DAYS = 7
ONLY_PROPOSALS = "I only propose hires, once a week"
_GOAL = "Say if you agree with this hire proposal"
_DONE_WHEN = "One reply: done if you agree, refused if not, with one short reason"
_RULES = ("Rules:\n"
          "- Pick a candidate only when its evidence shows a real problem; pick none otherwise.\n"
          "- For a failing employee pick a model you expect to do better; for a costly one, a "
          "cheaper model.\n"
          "- Write why in one or two short sentences, for the Master user.\n"
          "- Use only the candidate ids and the models listed here.\n"
          "- Send no messages: code sends each proposal to your boss.")


class HirePick(BaseModel):
    """One proposed trial hire: a candidate, the model to try and why."""

    model_config = ConfigDict(extra="forbid")

    candidate: str = Field(pattern=r"^C\d{1,2}$", description="Candidate id, like C1")
    source: Literal["claude", "openrouter"]
    model: str = Field(min_length=1, max_length=80,
                       description="A model listed for that source")
    why: str = Field(min_length=1, max_length=300, description="One or two short sentences")


class HireReviewAnswer(BaseModel):
    """The secretary's answer: at most 2 picks, or none with a note."""

    model_config = ConfigDict(extra="forbid")

    picks: list[HirePick] = Field(default_factory=list, max_length=MAX_PICKS)
    note: str = Field(default="", max_length=300,
                      description="Why you pick nothing, when you pick nothing")


def _words(skill: str) -> str:
    return skill.replace("_", " ")


def _boss(home: Path) -> tuple[str, str] | None:
    """Id and name of the secretary's active boss, from its ``reports_to``."""
    me = holder(home, KEY)
    if me is None or not me.reports_to:
        return None
    found = next((e for e in employees(home)
                  if e.id == me.reports_to and e.status == "active"), None)
    return (found.id, found.name) if found is not None else None


def _candidate_lines(found: Sequence[Candidate], names: dict[str, str],
                     models: dict[str, str]) -> list[str]:
    lines = ["Candidates:"]
    for c in found:
        n = c.need
        who = (f"holder {names.get(n.holder, n.holder)} on {models.get(n.holder, 'default')}"
               if n.holder else "no holder")
        lines.append(f"- {c.id}: {n.kind} need, skill {_words(n.skill)}, level {n.level}, {who}")
        lines += [f"  {line}" for line in n.evidence]
    return lines


def facts_text(home: Path, found: Sequence[Candidate], now: datetime) -> str:
    """Candidates, seats, the week's failure log rows and the models to pick from."""
    staff = employees(home)
    names = {e.id: e.name for e in staff}
    models = {e.id: e.model for e in staff}
    settings = load_settings(home)
    seats = seat_counts(home)
    lines = ["Hire needs found by code. Propose at most 2 trial hires, or none.", "",
             *_candidate_lines(found, names, models), "", "Seats (used of cap):"]
    lines += [f"- {level}: {seats.get(level, 0)} of {settings.cap(level)}"
              for level in HIRE_LEVELS]
    week = [m for m in failure_rows(home) if _days_ago(m.made, now) < WEEK_DAYS]
    lines += ["", "Failure log this week:"]
    lines += [f"- {m.made[:10]}: {m.text}" for m in week[:MAX_FAILURES]] or ["- none"]
    lines += ["", "Models you can pick:"]
    lines += [f"- {source}: {', '.join(listed)}" for source, listed in known_models(home).items()]
    return "\n".join([*lines, "", _RULES])


def _days_ago(day: str, now: datetime) -> int:
    """Whole days from ``day`` (``YYYY-MM-DD…``) to ``now``; a bad day counts as long ago."""
    try:
        return (now.date() - date.fromisoformat(day[:10])).days
    except ValueError:
        return WEEK_DAYS


def _ask(pid: int, c: Candidate, pick: HirePick, boss: str, holder_name: str) -> Draft:
    text = "\n".join([*c.need.evidence, f"Why: {pick.why}",
                      f"Model: {pick.source}/{pick.model}"])[:600]
    inputs = proposal_inputs(pid, c.need, holder_name, pick.why, pick.source, pick.model)
    return Draft(type="ask", to=boss, subject=f"Hire proposal: {_words(c.need.skill)}"[:80],
                 text=text, want=Want(goal=_GOAL, done_when=_DONE_WHEN, inputs=inputs,
                                      schema=HIRE_PROPOSAL.id))


class HireReviewSkill:
    """Proposes trial hires once a week from the needs found by code (SRD-DSK-006.016)."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = HireReviewAnswer
    talks = True

    def __init__(self, clock: Callable[[], datetime] = ny_now) -> None:
        """Use ``clock`` (New York time); injectable for tests."""
        self._clock = clock

    def facts(self, home: Path) -> Facts:
        """The needs to pick from; not fresh while hire proposals or messages are off."""
        now = self._clock()
        day = now.date().isoformat()
        settings = load_settings(home)
        if not (settings.hire_proposals_on and settings.messages_on):
            return Facts("Hire review", day, False, OFF)
        return Facts(facts_text(home, candidates(home, now), now), day, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Answer the inbox by code, or pick and send up to 2 proposals with one AI call."""
        talk = talker(ctx)
        if facts.inbox:
            self._inbox(ctx.home, facts.inbox, talk)
            return []
        now = self._clock()
        self._no_answer(ctx.home, now)
        found = candidates(ctx.home, now)
        if not found:
            log.info("[Hiring] No hire need found for the week")
            return []
        answer = ctx.ask(facts.text, HireReviewAnswer)
        if talk is not None:
            talk.drafts.clear()  # the model sends nothing itself; code sends each proposal
        if answer is None:
            return []
        if not answer.picks:
            log.info("[Hiring] The secretary proposed no hire: %s", answer.note or "no reason")
        self._send(ctx.home, found, answer.picks, talk, now)
        return []

    def _send(self, home: Path, found: Sequence[Candidate], picks: Sequence[HirePick],
              talk: Talker | None, now: datetime) -> None:
        by_id = {c.id: c for c in found}
        known = known_models(home)
        names = {e.id: e.name for e in employees(home)}
        me = holder(home, KEY)
        boss = _boss(home) if talk is not None else None
        taken: set[str] = set()
        for pick in picks:
            c = by_id.get(pick.candidate)
            if (c is None or pick.model not in known.get(pick.source, [])
                    or pick.candidate in taken or c.need.skill in taken):
                log.debug("[Hiring] Pick %s was dropped", pick.candidate)
                continue
            taken.update({pick.candidate, c.need.skill})
            pid = save_proposal(home, me.id if me else "", c.need, pick.why, pick.source,
                                pick.model, boss[0] if boss else None, now)
            if boss is None or talk is None:
                log.info("[Hiring] Proposal #%d waits for you: trial for %s, %s", pid,
                         _words(c.need.skill), "no boss to ask")
                continue
            talk.send(_ask(pid, c, pick, boss[0], names.get(c.need.holder, "")))
            log.info("[Hiring] Proposal #%d sent to %s: trial for %s", pid, boss[1],
                     _words(c.need.skill))

    @staticmethod
    def _no_answer(home: Path, now: datetime) -> None:
        """A view still pending after a day gets none: its ask was never answered or stored."""
        for p in waiting_proposals(home):
            if p.view == PENDING and _days_ago(p.made, now) >= 1:
                note_view(home, p.id, NO_VIEW, p.view_by, NO_ANSWER, now)

    def _inbox(self, home: Path, inbox: Sequence[int], talk: Talker | None) -> None:
        """A reply written by code gives its proposal no view; any ask gets a refused reply."""
        now = self._clock()
        for message_id in inbox:
            msg = read_message(home, message_id)
            if msg is None:
                continue
            if isinstance(msg.body, AskBody):
                if talk is not None:
                    talk.send(Draft(type="reply", parent=msg.id,
                                    verdict=Verdict(result="refused", reason=ONLY_PROPOSALS)))
                continue
            if not isinstance(msg.body, ReplyBody) or msg.parent is None:
                continue
            parent = read_message(home, msg.parent)
            want = parent.body.want if parent and isinstance(parent.body, AskBody) else None
            pid = proposal_of_ask(want.schema_id, want.inputs) if want else None
            if pid is not None:
                reason = msg.body.verdict.reason or msg.body.text or "no reason given"
                note_view(home, pid, NO_VIEW, msg.sender, reason, now)
