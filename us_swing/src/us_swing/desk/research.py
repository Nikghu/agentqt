"""
Module: MD-DSK-010.008.M26 — desk/research.py
Parent SRD: SRD-DSK-010.008
Also: SRD-DSK-010.009 (doer by kind), SRD-DSK-010.010 (done test and hard caps),
SRD-DSK-010.011 (stall), SRD-DSK-010.012 (pause for market work or a used-up research part),
SRD-DSK-010.013 (``research_done`` event), SRD-DSK-010.014 (logs)

Works approved research tickets in quiet time, one AI step per desk tick, so market work
always comes first. The doer is the active employee whose research skill handles the
ticket's kind; the raising lead's research part pays. No research skill ships with step E.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path

from us_swing.core.desk_ai_settings import DeskAiSettings, load_key, load_settings
from us_swing.core.desk_alerts import Sender
from us_swing.core.desk_contract import DB_NAME, StepContext, desk_home
from us_swing.core.desk_employee import TOKENS_PER_DAY
from us_swing.core.desk_events import post_event, waiting_count
from us_swing.core.desk_research import (
    ResearchSkill,
    StepResult,
    Ticket,
    connect,
    pause_running,
    runnable,
    save_step,
)
from us_swing.core.desk_watch import flags_since
from us_swing.desk.budget import Part, part_cap
from us_swing.desk.employees_step import _default_folders, _skill_paths
from us_swing.desk.gateway import Caller, Gateway, call_model
from us_swing.desk.recorder import NY, Recorder, ny_now
from us_swing.desk.registry import Hire, load_employees, seed_employees

log = logging.getLogger(__name__)

QUIET = timedelta(minutes=20)
IDLE = timedelta(minutes=1)
BACK_OFF = timedelta(minutes=15)
RESULT_CHARS = 4_000


def _stamp(now: datetime) -> str:
    return now.astimezone(NY).isoformat(timespec="seconds")


def quiet(home: Path, now: datetime) -> bool:
    """True when no event waits and no watcher flag came in the last 20 minutes."""
    return waiting_count(home) == 0 and not flags_since(home, now - QUIET)


def _is_research(skill: object) -> bool:
    return hasattr(skill, "kinds") and hasattr(skill, "step") and hasattr(skill, "step_tokens")


class ResearchRunner:
    """The desk's research step: one step of the next ticket that can run."""

    name = "Research"

    def __init__(
        self,
        skills: Callable[[], Mapping[str, str]] = _skill_paths,
        defaults: Callable[[], Sequence[Path]] = _default_folders,
        settings: Callable[[], DeskAiSettings] | None = None,
        key: Callable[[], str] = load_key,
        caller: Caller = call_model,
        clock: Callable[[], datetime] = ny_now,
        send: Sender | None = None,
    ) -> None:
        """Set the skill list, default files, settings, key, model caller, clock and sender."""
        self._skills = skills
        self._defaults = defaults
        self._settings = settings
        self._key = key
        self._caller = caller
        self._clock = clock
        self._send = send
        self._idle_until: datetime | None = None
        self._told: set[tuple[str, str]] = set()

    # ── when to run ────────────────────────────────────────────────────────

    def has_work(self, home: Path) -> bool:
        """True when it is quiet and a ticket can take a step now."""
        if not (home / DB_NAME).exists():
            return False
        now = self._clock()
        if not quiet(home, now):
            pause_running(home, "market work", now)
            return False
        if self._idle_until is not None and now < self._idle_until:
            return False
        con = connect(home)
        try:
            tickets = runnable(con)
        finally:
            con.close()
        if tickets and self._pick(home, self._hires(home), tickets, now) is not None:
            return True
        self._idle_until = now + IDLE
        return False

    def __call__(self, ctx: StepContext) -> None:
        """Take one step of the next ticket that can run."""
        home = ctx.home or desk_home()
        now = self._clock()
        try:
            con = connect(home)
            try:
                pick = self._pick(home, self._hires(home), runnable(con), now)
            finally:
                con.close()
            if pick is not None:
                self._step(home, ctx.run_id, *pick, now)
        except Exception:  # noqa: BLE001 — a research problem must never put the desk in error
            log.exception("[Research] The research step failed; trying again in 15 minutes")
            self._idle_until = now + BACK_OFF

    def _hires(self, home: Path) -> list[Hire]:
        seed_employees(home, self._defaults())
        return load_employees(home, self._skills())

    def _pick(self, home: Path, hires: Sequence[Hire], tickets: Sequence[Ticket],
              now: datetime) -> tuple[Ticket, Hire, Part] | None:
        """The first ticket with a doer whose payer still has research tokens today."""
        recorder = Recorder(home)
        try:
            for ticket in tickets:
                doer = self._doer(hires, ticket.kind, now)
                if doer is None:
                    continue
                part = self._part(hires, ticket)
                day = now.astimezone(NY).date().isoformat()
                if recorder.part_tokens(day, part.payer, "research") >= part_cap(part):
                    if ticket.status == "running":
                        pause_running(home, "research tokens used up for today", now,
                                      ticket.id)
                    continue
                return ticket, doer, part
        finally:
            recorder.close()
        return None

    def _doer(self, hires: Sequence[Hire], kind: str, now: datetime) -> Hire | None:
        for hire in hires:
            if (hire.spec.status == "active" and _is_research(hire.skill)
                    and kind in getattr(hire.skill, "kinds", ())):
                return hire
        day = now.astimezone(NY).date().isoformat()
        if (day, kind) not in self._told:
            self._told.add((day, kind))
            log.info("[Research] No employee can work %s tickets yet; they wait",
                     kind.replace("_", " "))
        return None

    @staticmethod
    def _part(hires: Sequence[Hire], ticket: Ticket) -> Part:
        raiser = next((h.spec for h in hires if h.spec.id == ticket.raised_by), None)
        tokens = raiser.tokens_per_day if raiser else TOKENS_PER_DAY
        return Part("research", ticket.raised_by, ticket.raised_by_name, tokens, ticket.id,
                    ticket.token_cap)

    # ── one step ───────────────────────────────────────────────────────────

    def _step(self, home: Path, run_id: int, ticket: Ticket, doer: Hire, part: Part,
              now: datetime) -> None:
        skill: ResearchSkill = doer.skill  # type: ignore[assignment]
        con = connect(home)
        recorder = Recorder(home)
        try:
            spent = recorder.ticket_tokens(ticket.id)
            cap_reason = self._cap_reason(recorder, ticket, spent,
                                          max(skill.step_tokens, ticket.biggest))
            if cap_reason:
                self._end(con, home, ticket, "done", cap_reason, None, now)
                return
            if ticket.status != "running":
                save_step(con, ticket, status="running", started=ticket.started or _stamp(now),
                          end_reason="", updated=_stamp(now))
                log.info("[Research] Ticket %d %s by %s", ticket.id,
                         "resumed" if ticket.started else "started", doer.spec.name)
            settings = self._settings() if self._settings else load_settings(home)
            gateway = Gateway(home, doer, recorder, settings, self._key(), run_id,
                              now.astimezone(NY).date().isoformat(), self._caller, self._clock,
                              send=self._send, part=part)
            try:
                result = skill.step(gateway, ticket)
            except Exception:  # noqa: BLE001 — a failing step counts as a step with no result
                log.exception("[Research] Ticket %d step failed", ticket.id)
                result = None
            if gateway.refused and gateway.answered is None:
                self._refused(con, home, ticket, gateway.refused, now)
                return
            self._after(con, home, ticket, result, recorder.ticket_tokens(ticket.id), spent,
                        now)
        finally:
            recorder.close()
            con.close()

    @staticmethod
    def _cap_reason(recorder: Recorder, ticket: Ticket, spent: int, need: int) -> str:
        if ticket.token_cap - spent < need:
            return "token cap"
        if ticket.steps >= ticket.step_cap:
            return "step cap"
        if recorder.ticket_seconds(ticket.id) >= ticket.time_cap_min * 60:
            return "time cap"
        return ""

    def _refused(self, con: sqlite3.Connection, home: Path, ticket: Ticket, why: str,
                 now: datetime) -> None:
        if why.startswith(f"ticket {ticket.id} "):
            self._end(con, home, ticket, "done", "token cap", None, now)
            return
        save_step(con, ticket, status="paused", end_reason=why,
                  updated=_stamp(now))
        self._idle_until = now + BACK_OFF
        log.info("[Research] Ticket %d paused: %s; next try in 15 minutes", ticket.id, why)

    def _after(self, con: sqlite3.Connection, home: Path, ticket: Ticket, result: StepResult | None,
               tokens: int, spent: int, now: datetime) -> None:
        note = result.note.strip() if result else ""
        call = result.call.strip() if result else ""
        text = f"{ticket.result}\n{note}".strip() if note else ticket.result
        quiet_steps = 0 if note else ticket.quiet_steps + 1
        state = result.state if result and result.state else json.loads(ticket.state or "{}")
        save_step(con, ticket, tokens=tokens, steps=ticket.steps + 1,
                  biggest=max(ticket.biggest, tokens - spent), quiet_steps=quiet_steps,
                  last_call=call, state=state, result=text[-RESULT_CHARS:],
                  updated=_stamp(now))
        if result is not None and result.outcome in ("done", "failed"):
            reason = "done test met" if result.outcome == "done" else "done test failed"
            self._end(con, home, ticket, result.outcome, reason, result.gain,
                      now)
        elif quiet_steps >= 2:
            self._end(con, home, ticket, "stuck", "no new result in 2 steps", False,
                      now)
        elif call and call == ticket.last_call:
            self._end(con, home, ticket, "stuck", "same call twice in a row", False,
                      now)

    def _end(self, con: sqlite3.Connection, home: Path, ticket: Ticket, status: str, reason: str,
             gain: bool | None, now: datetime) -> None:
        recorder = Recorder(home)
        try:
            tokens = recorder.ticket_tokens(ticket.id)
        finally:
            recorder.close()
        save_step(con, ticket, status=status, ended=_stamp(now),
                  end_reason=reason, gain=None if gain is None else int(gain), tokens=tokens,
                  updated=_stamp(now))
        post_event(home, "research_done", now.astimezone(NY).date().isoformat(), now,
                   ticket.id)
        log.info("[Research] Ticket %d ended %s: %s, %s tokens", ticket.id, status, reason,
                 f"{tokens:,}")
