"""
Module: MD-DSK-003.001.M10 — desk/employees_step.py
Parent SRD: SRD-DSK-003.001
Also: SRD-DSK-003.002 (once per data day), SRD-DSK-003.003 (fresh data only),
SRD-DSK-002.005 (employees get only home and ask), SRD-DSK-005.004 (run log)

Desk step "AI employees": after the market steps, wakes each employee whose trigger is
``after_run``, at most once per data day and only on fresh data.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from us_swing.core.desk_ai_settings import DeskAiSettings, load_key, load_settings
from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.desk.gateway import Caller, Gateway, call_model
from us_swing.desk.recorder import Recorder
from us_swing.desk.registry import Hire, load_employee, load_employees, record_employees

log = logging.getLogger(__name__)


def _employee_paths() -> tuple[str, ...]:
    from us_swing.core.desk_steps import EMPLOYEE_PATHS  # noqa: PLC0415 — avoids a cycle

    return EMPLOYEE_PATHS


class EmployeesStep:
    """Wakes the AI employees after a desk run."""

    name = "AI employees"

    def __init__(
        self,
        paths: Callable[[], Sequence[str]] = _employee_paths,
        settings: Callable[[], DeskAiSettings] | None = None,
        key: Callable[[], str] = load_key,
        caller: Caller = call_model,
    ) -> None:
        """Set the employee list, settings, key and model caller; all injectable for tests."""
        self._paths = paths
        self._settings = settings
        self._key = key
        self._caller = caller

    def __call__(self, ctx: StepContext) -> None:
        """Run the step inside a desk run; one failing employee never fails the run."""
        home = ctx.home or desk_home()
        hires = [h for e in load_employees(self._paths()) if (h := load_employee(e))]
        recorder = Recorder(home)
        try:
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
        name = hire.spec.name
        emp = hire.employee
        facts = emp.facts(home)
        if not facts.fresh:
            log.info("[AI Desk] %s stays asleep: %s", name, facts.why_stale)
            return
        if recorder.done_on(name, facts.data_day):
            log.info("[AI Desk] %s already answered for %s", name, facts.data_day)
            return
        gateway = Gateway(home, hire, recorder, settings, self._key(), run_id,
                          facts.data_day, self._caller)
        items = emp.act(gateway, facts)
        recorder.add_briefs(items)
        if gateway.answered:
            a = gateway.answered
            cost = f", cost USD {a.cost_usd:.4f}" if a.cost_usd else ""
            log.info("[AI Desk] %s answered with %s in %.1f s, %d tokens%s", name, a.model,
                     a.seconds, a.tokens, cost)
        elif not gateway.refused:
            log.warning("[AI Desk] %s gave no valid answer for %s", name, facts.data_day)
