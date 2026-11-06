"""
Module: MD-DSK-003.001.M10 — desk/employees_step.py
Parent SRD: SRD-DSK-003.001
Also: SRD-DSK-003.002 (once per data day), SRD-DSK-003.003 (fresh data only),
SRD-DSK-002.005 (skills get only home and ask), SRD-DSK-002.007 (default employee files),
SRD-DSK-005.004 (run log)

Desk step "AI employees": after the market steps, copies any missing default employee
files into the desk folder, then wakes each employee whose trigger is ``after_run``, at
most once per data day and only on fresh data. Employees are known only from their files.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from us_swing.core.desk_ai_settings import DeskAiSettings, load_key, load_settings
from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.desk.gateway import Caller, Gateway, call_model
from us_swing.desk.recorder import Recorder
from us_swing.desk.registry import (
    Hire,
    default_folders,
    load_employees,
    record_employees,
    seed_employees,
)

log = logging.getLogger(__name__)


def _skill_paths() -> Mapping[str, str]:
    from us_swing.core.desk_steps import SKILL_PATHS  # noqa: PLC0415 — avoids a cycle

    return SKILL_PATHS


def _default_folders() -> Sequence[Path]:
    from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES  # noqa: PLC0415

    return default_folders(DEFAULT_EMPLOYEE_PACKAGES)


class EmployeesStep:
    """Wakes the AI employees after a desk run."""

    name = "AI employees"

    def __init__(
        self,
        skills: Callable[[], Mapping[str, str]] = _skill_paths,
        defaults: Callable[[], Sequence[Path]] = _default_folders,
        settings: Callable[[], DeskAiSettings] | None = None,
        key: Callable[[], str] = load_key,
        caller: Caller = call_model,
    ) -> None:
        """Set the skill list, default files, settings, key and model caller (all injectable)."""
        self._skills = skills
        self._defaults = defaults
        self._settings = settings
        self._key = key
        self._caller = caller

    def __call__(self, ctx: StepContext) -> None:
        """Run the step inside a desk run; one failing employee never fails the run."""
        home = ctx.home or desk_home()
        recorder = Recorder(home)
        try:
            seed_employees(home, self._defaults())
            hires = load_employees(home, self._skills())
            record_employees(home, hires)
            settings = self._settings() if self._settings else load_settings(home)
            for hire in hires:
                if hire.spec.trigger != "after_run":
                    continue
                try:
                    self._wake(hire, ctx.run_id, home, recorder, settings)
                except Exception:  # noqa: BLE001 — logged; the next employee still runs
                    log.exception("[AI Desk] %s failed", hire.spec.name)
        finally:
            recorder.close()

    def _wake(self, hire: Hire, run_id: int, home: Path, recorder: Recorder,
              settings: DeskAiSettings) -> None:
        spec = hire.spec
        facts = hire.skill.facts(home)
        if not facts.fresh:
            log.info("[AI Desk] %s stays asleep: %s", spec.name, facts.why_stale)
            return
        if recorder.done_on(spec.id, facts.data_day):
            log.info("[AI Desk] %s already answered for %s", spec.name, facts.data_day)
            return
        gateway = Gateway(home, hire, recorder, settings, self._key(), run_id,
                          facts.data_day, self._caller)
        items = hire.skill.act(gateway, facts)
        recorder.add_briefs(items, spec.id, spec.name)
        if gateway.answered:
            a = gateway.answered
            cost = f", cost USD {a.cost_usd:.4f}" if a.cost_usd else ""
            log.info("[AI Desk] %s answered with %s in %.1f s, %d tokens%s", spec.name, a.model,
                     a.seconds, a.tokens, cost)
        elif not gateway.refused:
            log.warning("[AI Desk] %s gave no valid answer for %s", spec.name, facts.data_day)
