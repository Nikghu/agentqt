"""
Module: MD-MKT-016.001.M01 — market/post_mortem.py
Parent SRD: SRD-MKT-016.001
Also: SRD-MKT-016.002–.003 (pick step and checks), SRD-MKT-016.006–.009 (study, lessons,
follow-ups, result and gain), SRD-MKT-016.010 (default employee), SRD-MKT-016.011 (logs)

The pick post-mortem research skill. A ticket runs in three steps, one per desk tick: the
AI chooses losing and winning lead picks of the last 30 days, code gathers each pick's
stored facts and price path, then the AI says why the losers failed against the winners.
Code keeps only lessons proven by studied picks and raises follow-ups in the lead's name.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_alerts import Sender
from us_swing.core.desk_lessons import Case, add_candidate, cases, connect, lesson_rows
from us_swing.core.desk_research import StepResult, Ticket, TicketAsk, raise_follow_ups
from us_swing.data.market_calendar import ET
from us_swing.market.lesson_reflect import Candidate
from us_swing.market.post_mortem_facts import pick_records

log = logging.getLogger(__name__)

KIND = "post_mortem"
STEP_TOKENS = 6_000
DAYS = 30
SHOWN = 120
MIN_LOSERS = 2
_PICK_RULES = (
    "Rules: choose the losing picks the ticket asks about (1 to 10, R below 0) and up to 5 "
    "winning picks of the same kind (R above 0) to compare with. Use the exact keys "
    "(date|side|symbol) from the list."
)
_STUDY_RULES = (
    "Rules: write one short note per pick on why it failed or worked. Then write at most 3 "
    "lessons, each one short sentence, naming 1 to 3 tags, whether such picks do better or "
    "worse, and the studied pick keys that show it. A lesson may only make picking stricter; "
    "never suggest wider stops, more capital or skipping approval. You may ask for at most 2 "
    "follow-up research tickets (kinds: setup_tuning, stock_study, sentiment, strategy_test). "
    "End with a summary of at most 4 short sentences. Never invent a number."
)


class PickChoice(BaseModel):
    """The model's answer for the pick step."""

    model_config = ConfigDict(extra="forbid")

    losers: list[str] = Field(min_length=1, max_length=10)
    winners: list[str] = Field(default_factory=list, max_length=5)


class PickNote(BaseModel):
    """One short note on one studied pick."""

    model_config = ConfigDict(extra="forbid")

    pick: str = Field(min_length=5, max_length=40)
    note: str = Field(min_length=3, max_length=150)


class PostMortem(BaseModel):
    """The model's answer for the study step."""

    model_config = ConfigDict(extra="forbid")

    notes: list[PickNote] = Field(default_factory=list, max_length=15)
    lessons: list[Candidate] = Field(default_factory=list, max_length=3)
    follow_ups: list[TicketAsk] = Field(default_factory=list, max_length=2)
    summary: str = Field(min_length=10, max_length=600)


def _now() -> datetime:
    return datetime.now(ET)


def _closed(home: Path) -> list[Case]:
    con = connect(home)
    try:
        return cases(con)
    finally:
        con.close()


def _case_line(case: Case) -> str:
    tags = ", ".join(f"{k} {v}" for k, v in sorted(case.tags.items()))
    return f"{case.key}: {tags or 'no tags'}, {case.r:+.2f}R"


class PostMortemSkill:
    """Works pick post-mortem tickets: choose picks, gather facts, study them."""

    key = KIND
    needs: tuple[str, ...] = ()
    answer = PickChoice
    kinds: tuple[str, ...] = (KIND,)
    step_tokens = STEP_TOKENS

    def __init__(
        self,
        clock: Callable[[], datetime] = _now,
        records: Callable[[Path, Sequence[str]], list[str]] = pick_records,
        send: Sender | None = None,
    ) -> None:
        """Set the clock, the record builder and the alert sender; injectable for tests."""
        self._clock = clock
        self._records = records
        self._send = send

    def facts(self, home: Path) -> Facts:
        """This employee works research tickets only, so events never wake it."""
        return Facts("", self._clock().date().isoformat(), False,
                     "works research tickets only")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Nothing to do outside a research ticket."""
        return []

    def step(self, ctx: AgentContext, ticket: Ticket) -> StepResult | None:
        """Do the next step of ``ticket``: pick, gather or study."""
        state: dict[str, Any] = json.loads(ticket.state or "{}")
        phase = state.get("phase", "pick")
        if phase == "pick":
            return self._pick(ctx, ticket)
        if phase == "gather":
            return self._gather(ctx.home, ticket, state)
        return self._study(ctx, ticket, state)

    # ── pick ──────────────────────────────────────────────────────────────

    def _recent(self, home: Path) -> list[Case]:
        first = (self._clock().date() - timedelta(days=DAYS)).isoformat()
        recent = [c for c in _closed(home) if c.day >= first]
        return sorted(recent, key=lambda c: c.day, reverse=True)[:SHOWN]

    def _pick(self, ctx: AgentContext, ticket: Ticket) -> StepResult:
        recent = self._recent(ctx.home)
        if not recent:
            return StepResult("No closed lead picks in the last 30 days to study", "pick",
                              "failed")
        text = "\n".join([f"Ticket {ticket.id}: {ticket.topic}", f"Goal: {ticket.goal}",
                          f"Done when: {ticket.done_test}", "",
                          "Closed lead picks of the last 30 days (key: tags, R):",
                          *(_case_line(c) for c in recent), "", _PICK_RULES])
        reply = ctx.ask(text, PickChoice)
        if reply is None:
            return StepResult("", "pick", "go")
        by_key = {c.key: c for c in recent}
        losers = list(dict.fromkeys(k for k in reply.losers if k in by_key and by_key[k].r < 0))
        winners = list(dict.fromkeys(k for k in reply.winners
                                     if k in by_key and by_key[k].r > 0))
        if len(losers) < MIN_LOSERS:
            return StepResult(f"Only {len(losers)} valid losing pick(s) chosen; at least "
                              f"{MIN_LOSERS} are needed", "pick", "failed")
        log.info("[Research] Ticket %d will study %d loser(s) and %d winner(s)", ticket.id,
                 len(losers), len(winners))
        return StepResult(f"Chose {len(losers)} loser(s) and {len(winners)} winner(s)", "pick",
                          "go", state={"phase": "gather", "losers": losers,
                                       "winners": winners})

    # ── gather ────────────────────────────────────────────────────────────

    def _gather(self, home: Path, ticket: Ticket, state: dict[str, Any]) -> StepResult:
        keys = [*state["losers"], *state["winners"]]
        records = self._records(home, keys)
        no_bars = sum(1 for r in records if "path: no bars" in r)
        log.info("[Research] Ticket %d gathered %d pick(s)", ticket.id, len(records))
        return StepResult(f"Gathered {len(records)} pick(s), {no_bars} with no bars", "gather",
                          "go", state={**state, "phase": "study", "records": records})

    # ── study ─────────────────────────────────────────────────────────────

    def _study(self, ctx: AgentContext, ticket: Ticket, state: dict[str, Any]) -> StepResult:
        losers, winners = set(state["losers"]), set(state["winners"])
        records: list[str] = state["records"]
        active = lesson_rows(ctx.home, "active")
        text = "\n".join([
            f"Ticket {ticket.id}: {ticket.topic}", f"Goal: {ticket.goal}",
            f"Done when: {ticket.done_test}", "", "Losing picks:",
            *(r for r in records if r.split(":", 1)[0] in losers), "", "Winning picks:",
            *([r for r in records if r.split(":", 1)[0] in winners] or ["(none)"]), "",
            "Active lessons:", *([f"L-{x.id}: {x.text}" for x in active] or ["(none)"]), "",
            _STUDY_RULES])
        reply = ctx.ask(text, PostMortem)
        if reply is None:
            return StepResult("", "study", "go")
        studied = losers | winners
        notes = [f"{n.pick}: {n.note.strip()}" for n in reply.notes if n.pick in studied]
        kept = self._lessons(ctx.home, reply.lessons, studied)
        asks = [a for a in reply.follow_ups if a.kind != KIND]
        raised = raise_follow_ups(ctx.home, ticket.raised_by, asks, self._clock(), self._send)
        log.info("[Research] Ticket %d kept %d lesson(s), raised %d follow-up ticket(s)",
                 ticket.id, kept, sum(1 for r in raised if r.startswith("ticket ")))
        lines = [f"Summary: {reply.summary.strip()}", *notes, f"Lessons kept: {kept}",
                 *(f"Follow-up: {r}" for r in raised)]
        return StepResult("\n".join(lines), "study", "done", gain=kept > 0)

    def _lessons(self, home: Path, lessons: Sequence[Candidate], studied: set[str]) -> int:
        kept = 0
        for cand in lessons:
            if not set(cand.picks) <= studied:
                continue
            try:
                add_candidate(home, cand.text, {str(k): v for k, v in cand.tags.items()},
                              cand.claim, cand.picks, self._clock())
            except ValueError:
                continue
            kept += 1
        return kept
