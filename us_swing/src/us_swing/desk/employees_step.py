"""
Module: MD-DSK-003.001.M10 — desk/employees_step.py
Parent SRD: SRD-DSK-003.001
Also: SRD-DSK-003.002 (once per data day), SRD-DSK-003.003 (fresh data only),
SRD-DSK-002.005 (skills get only home and ask), SRD-DSK-002.007 (default employee files),
SRD-DSK-005.004 (run log), SRD-DSK-003.004 (posts ``after_run``),
SRD-DSK-006.004 (a shadow employee is only asked and recorded), SRD-DSK-007.005 (alert when
no employee of a run gave a valid answer), SRD-DSK-003.014 (wake result ok, slept or failed),
SRD-DSK-003.016 (a retry skips the once-per-day check), SRD-DSK-003.018 (partial plan line),
SRD-DSK-007.008 (partial plan alert), SRD-DSK-004.008 (market or plan budget part by event)

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

        def wake(hire: Hire, event: Event, retry: bool, missing: tuple[str, ...]) -> str:
            return self._wake(hire, event, run_id, home, settings, retry, missing)

        def alert(hire: Hire, event: Event) -> None:
            error = last_error(home, hire.spec.id) or "see the desk log"
            raise_alert(home, "partial", hire.spec.id, run_id,
                        f"{hire.spec.name} failed 3 times: {error}", self._clock(), self._send)

        return Router(home, hires, wake, set(skills), self._clock, alert), hires

    def _wake(self, hire: Hire, event: Event, run_id: int, home: Path,
              settings: DeskAiSettings, retry: bool = False,
              missing: tuple[str, ...] = ()) -> str:
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
                              part=part)
            items = hire.skill.act(gateway, facts)
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
        log.warning("[AI Desk] %s gave no valid answer for %s", spec.name, facts.data_day)
        return "failed"
