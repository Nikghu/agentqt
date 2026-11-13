"""
Module: MD-DSK-003.001.M10 — desk/employees_step.py
Parent SRD: SRD-DSK-003.001
Also: SRD-DSK-003.002 (once per data day), SRD-DSK-003.003 (fresh data only),
SRD-DSK-002.005 (skills get only home and ask), SRD-DSK-002.007 (default employee files),
SRD-DSK-005.004 (run log), SRD-DSK-003.004 (posts ``after_run``),
SRD-DSK-006.004 (a shadow employee is only asked and recorded), SRD-DSK-007.005 (alert when
no employee of a run gave a valid answer), SRD-DSK-003.014 (wake result ok, slept or failed),
SRD-DSK-003.016 (a retry skips the once-per-day check), SRD-DSK-003.018 (partial plan line),
SRD-DSK-007.008 (partial plan alert), SRD-DSK-004.008 (market or plan budget part by event),
SRD-DSK-011.026, .028, .030, .031 (message wakes: inbox facts, refusals, the starter pays,
only while messages are on), SRD-DSK-011.039-.042 (boss reply-only turn, reply as a feed
note, deputy before refusal, only while escalation is on)

Desk step "AI employees": after the market steps, copies any missing default employee
files into the desk folder, posts an ``after_run`` event and lets the router handle every
waiting event. The desk loop also uses it to handle events between runs. Employees are
known only from their files.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path

from us_swing.core.desk_ai_settings import DeskAiSettings, load_key, load_settings
from us_swing.core.desk_alerts import Sender, last_error, raise_alert, run_outcome
from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.core.desk_events import Event, post_event, waiting_count
from us_swing.core.desk_agents import FeedItem
from us_swing.core.desk_messages import (
    MessageRow,
    Person,
    accept,
    hand_to_deputy,
    inbox,
    inbox_text,
    mark_seen,
    refuse_inbox,
    thread_starter,
)
from us_swing.core.desk_msg import Draft, InboxReply
from us_swing.desk.budget import Part
from us_swing.desk.gateway import Caller, Gateway, call_model
from us_swing.desk.recorder import NY, Recorder, ny_now
from us_swing.desk.registry import (
    Hire,
    default_folders,
    load_employees,
    record_employees,
    seed_employees,
)
from us_swing.desk.router import Router
from us_swing.desk.shadow import run_shadow

log = logging.getLogger(__name__)

MARKET_KINDS = ("market_checkin", "watch_flag")


def _skill_paths() -> Mapping[str, str]:
    from us_swing.core.desk_steps import SKILL_PATHS  # noqa: PLC0415 — avoids a cycle

    return SKILL_PATHS


def _default_folders() -> Sequence[Path]:
    from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES  # noqa: PLC0415

    return default_folders(DEFAULT_EMPLOYEE_PACKAGES)


class EmployeesStep:
    """Wakes the AI employees after a desk run and on other events."""

    name = "AI employees"

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
        """Set the skill list, default files, settings, key, model caller, clock and the alert
        sender (Telegram when ``None``)."""
        self._skills = skills
        self._defaults = defaults
        self._settings = settings
        self._key = key
        self._caller = caller
        self._clock = clock
        self._send = send

    def __call__(self, ctx: StepContext) -> None:
        """Post ``after_run`` and handle the events; one failing employee never fails the run."""
        home = ctx.home or desk_home()
        day = ctx.started_at.astimezone(NY).date().isoformat()
        post_event(home, "after_run", day, self._clock(), ctx.run_id)
        self.handle_events(ctx)
        self._check_run(home, ctx.run_id)

    def _check_run(self, home: Path, run_id: int) -> None:
        """Raise an alert when the run's employees made calls and none gave a valid answer."""
        calls, valid, last_error = run_outcome(home, run_id)
        if calls and not valid:
            raise_alert(home, "run_failed", "", run_id,
                        f"Run {run_id}: {calls} LLM call(s), none valid. Last error: "
                        f"{last_error or 'answers did not match the expected form'}",
                        self._clock(), self._send)

    def has_work(self, home: Path) -> bool:
        """True when a waiting event wakes at least one employee (files read only then)."""
        if not waiting_count(home, self._clock()):
            return False
        return self._router(home, -1)[0].has_work()

    def handle_events(self, ctx: StepContext) -> None:
        """Handle every waiting event with the employees loaded now."""
        home = ctx.home or desk_home()
        router, _ = self._router(home, ctx.run_id)
        router.handle()

    def _router(self, home: Path, run_id: int) -> tuple[Router, list[Hire]]:
        seed_employees(home, self._defaults())
        skills = self._skills()
        hires = load_employees(home, skills)
        if run_id >= 0:
            record_employees(home, hires)
        settings = self._settings() if self._settings else load_settings(home)

        roster = [Person(h.spec.id, h.spec.name, h.skill.key, h.spec.reports_to,
                         h.spec.deputy) for h in hires if h.spec.status == "active"]

        def wake(hire: Hire, event: Event, retry: bool, missing: tuple[str, ...]) -> str:
            if event.kind == "message":
                return self._wake_message(hire, run_id, home, settings, hires, roster)
            return self._wake(hire, event, run_id, home, settings, retry, missing, roster)

        def alert(hire: Hire, event: Event) -> None:
            error = last_error(home, hire.spec.id) or "see the desk log"
            raise_alert(home, "partial", hire.spec.id, run_id,
                        f"{hire.spec.name} failed 3 times: {error}", self._clock(), self._send)

        return Router(home, hires, wake, set(skills), self._clock, alert, roster,
                      self._send), hires

    def _wake(self, hire: Hire, event: Event, run_id: int, home: Path,
              settings: DeskAiSettings, retry: bool = False,
              missing: tuple[str, ...] = (), roster: Sequence[Person] = ()) -> str:
        """Wake one employee; return ``ok``, ``slept`` (by a rule) or ``failed``."""
        spec = hire.spec
        facts = hire.skill.facts(home)
        if not facts.fresh:
            log.info("[AI Desk] %s stays asleep: %s", spec.name, facts.why_stale)
            return "slept"
        recorder = Recorder(home)
        try:
            if spec.status == "shadow":
                gateway = Gateway(home, hire, recorder, settings, self._key(), run_id,
                                  facts.data_day, self._caller, self._clock, shadow=True,
                                  send=self._send)
                run_shadow(hire, facts, gateway, recorder)
                return "slept"
            if (not retry and event.kind == "after_run"
                    and recorder.done_on(spec.id, facts.data_day)):
                log.info("[AI Desk] %s already answered for %s", spec.name, facts.data_day)
                return "ok"
            part = Part("market" if event.kind in MARKET_KINDS else "plan", spec.id, spec.name,
                        spec.tokens_per_day)
            gateway = Gateway(home, hire, recorder, settings, self._key(), run_id,
                              facts.data_day, self._caller, self._clock, send=self._send,
                              part=part, talk=_talks(hire, settings))
            items = hire.skill.act(gateway, facts)
            accept(home, gateway.drafts, spec.id, roster, self._clock(), facts.data_day,
                   _escalates(settings), self._send)
            if missing:
                line = f"Partial plan: no view from {', '.join(missing)}."
                items = [replace(i, text=f"{line}\n{i.text}") for i in items]
            recorder.add_briefs(items, spec.id, spec.name)
        finally:
            recorder.close()
        if gateway.answered:
            a = gateway.answered
            cost = f", cost USD {a.cost_usd:.4f}" if a.cost_usd else ""
            log.info("[AI Desk] %s answered with %s in %.1f s, %d tokens%s", spec.name, a.model,
                     a.seconds, a.tokens, cost)
            return "ok"
        if gateway.refused:
            return "slept"
        if not gateway.asked:
            return "ok"  # code-only turn: the skill had nothing to ask the model
        log.warning("[AI Desk] %s gave no valid answer for %s", spec.name, facts.data_day)
        return "failed"

    def _wake_message(self, hire: Hire, run_id: int, home: Path, settings: DeskAiSettings,
                      hires: Sequence[Hire], roster: Sequence[Person]) -> str:
        """Wake one employee for its inbox; the thread's starter pays (SRD-DSK-011.030)."""
        spec, now = hire.spec, self._clock()
        rows = inbox(home, spec.id)
        if not rows:
            return "ok"
        escalates = [m for m in rows if m.type == "escalate"] if _escalates(settings) else []
        rest = [m for m in rows if m not in escalates]
        try:
            result = "ok"
            if escalates:
                result = self._answer_escalations(hire, run_id, home, settings, hires, roster,
                                                  escalates)
            if rest:
                result = self._answer_inbox(hire, run_id, home, settings, hires, roster, rest)
            return result
        except Exception:
            self._refuse(home, rows, f"{spec.name} hit an error", hire, settings, roster)
            raise
        finally:
            mark_seen(home, [m.id for m in rows], now, spec.id)

    def _refuse(self, home: Path, rows: Sequence[MessageRow], why: str, hire: Hire,
                settings: DeskAiSettings, roster: Sequence[Person]) -> None:
        """Hand open messages to the deputy first, then refuse the rest (SRD-DSK-011.041)."""
        now = self._clock()
        if _escalates(settings):
            person = next((p for p in roster if p.id == hire.spec.id), None)
            if person is not None:
                rows = hand_to_deputy(home, rows, person, roster, why, now)
        refuse_inbox(home, rows, why, now)

    def _answer_escalations(self, hire: Hire, run_id: int, home: Path,
                            settings: DeskAiSettings, hires: Sequence[Hire],
                            roster: Sequence[Person], rows: Sequence[MessageRow]) -> str:
        """A short reply-only turn for a boss; its own skill does not run (SRD-DSK-011.039)."""
        spec, day = hire.spec, rows[0].data_day
        text = _BOSS_HEAD + "\n\n" + inbox_text(rows, roster)
        starter = thread_starter(home, rows[0].thread) or spec.id
        payer = next((h.spec for h in hires if h.spec.id == starter), spec)
        part = Part("market", payer.id, payer.name, payer.tokens_per_day, message=rows[0].id)
        recorder = Recorder(home)
        try:
            gateway = Gateway(home, hire, recorder, settings, self._key(), run_id, day,
                              self._caller, self._clock, send=self._send, part=part)
            answer = gateway.ask(text, InboxReply)
            replies = [d for d in answer.messages if d.type == "reply"] if answer else []
            results = accept(home, replies, spec.id, roster, self._clock(), day, True,
                             self._send)
            subjects = {m.id: str(m.body.get("subject", "")) for m in rows}
            notes = [FeedItem("info", _note(subjects.get(d.parent or 0, ""), d), day)
                     for d, r in zip(replies, results, strict=True) if r.startswith("stored")]
            recorder.add_briefs(notes, spec.id, spec.name)  # SRD-DSK-011.040
        finally:
            recorder.close()
        if not replies:
            why = gateway.refused or f"{spec.name} gave no valid answer"
            self._refuse(home, rows, why, hire, settings, roster)
            return "slept" if gateway.refused else "failed"
        return "ok"

    def _answer_inbox(self, hire: Hire, run_id: int, home: Path, settings: DeskAiSettings,
                      hires: Sequence[Hire], roster: Sequence[Person],
                      rows: Sequence[MessageRow]) -> str:
        spec, now = hire.spec, self._clock()
        if not settings.messages_on:
            refuse_inbox(home, rows, "agent messages are off", now)
            return "slept"
        facts = hire.skill.facts(home)
        if not facts.fresh:
            self._refuse(home, rows, f"{spec.name} cannot work now: {facts.why_stale}", hire,
                         settings, roster)
            return "slept"
        facts = replace(facts, text=facts.text + "\n\n" + inbox_text(rows, roster),
                        inbox=tuple(m.id for m in rows))
        starter = thread_starter(home, rows[0].thread) or spec.id
        payer = next((h.spec for h in hires if h.spec.id == starter), spec)
        part = Part("plan", payer.id, payer.name, payer.tokens_per_day, message=rows[0].id)
        recorder = Recorder(home)
        try:
            gateway = Gateway(home, hire, recorder, settings, self._key(), run_id,
                              facts.data_day, self._caller, self._clock, send=self._send,
                              part=part, talk=_talks(hire, settings))
            items = hire.skill.act(gateway, facts)
            recorder.add_briefs(items, spec.id, spec.name)
        finally:
            recorder.close()
        accept(home, gateway.drafts, spec.id, roster, self._clock(), facts.data_day,
               _escalates(settings), self._send)
        if gateway.refused:
            self._refuse(home, rows, gateway.refused, hire, settings, roster)
            return "slept"
        if gateway.asked and not gateway.answered:
            self._refuse(home, rows, f"{spec.name} gave no valid answer", hire, settings,
                         roster)
            return "failed"
        return "ok"


_BOSS_HEAD = ("Problems raised to you by people who report to you. Reply to each one; your "
              "reply is shown to the Master user as a note. Do not plan anything else now.")


def _note(subject: str, draft: Draft) -> str:
    verdict = draft.verdict.result if draft.verdict else "done"
    return f"{subject}: {draft.text or verdict}" if subject else (draft.text or verdict)


def _talks(hire: Hire, settings: DeskAiSettings) -> bool:
    return settings.messages_on and bool(getattr(hire.skill, "talks", False))


def _escalates(settings: DeskAiSettings) -> bool:
    """Escalation and deputies run only with messages and escalation on (SRD-DSK-011.042)."""
    return settings.messages_on and settings.escalation_on
