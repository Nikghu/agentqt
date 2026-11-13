"""
Module: MD-DSK-009.021.M31 — desk/memory_cleanup.py
Parent SRD: SRD-DSK-009.021
Also: SRD-DSK-009.023 (only while Memory v2 is on), SRD-DSK-009.024 (log lines)

Desk step "Memory clean-up" (AI Desk v3 M3): once a week, on or after Friday, each active
lead and expert with notes gets one call to keep, merge or retire its own notes. Code checks
every action: only the employee's own unpinned notes change.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_ai_settings import DeskAiSettings, load_key, load_settings
from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.core.desk_memory import (
    CleanupAction,
    Memory,
    apply_cleanup,
    cleanup_notes,
    connect,
    get_state,
    is_top,
    set_state,
)
from us_swing.desk.budget import Part
from us_swing.desk.gateway import Caller, Gateway, call_model
from us_swing.desk.recorder import NY, Recorder, ny_now
from us_swing.desk.registry import Hire, load_employees
from us_swing.desk.weekly_report import report_friday

log = logging.getLogger(__name__)

WEEK_KEY = "cleanup_week"
HEAD = ("Weekly clean-up of your own notes. For each note you may keep it, merge it into "
        "another note (give into and, if you like, a new short text) or retire it when it "
        "no longer helps. Leave out notes you keep. Notes:")


class Action(BaseModel):
    """One clean-up step for one note."""

    model_config = ConfigDict(extra="forbid")

    id: int
    do: Literal["keep", "merge", "retire"]
    into: int | None = None
    text: str | None = Field(default=None, max_length=200)


class Cleanup(BaseModel):
    """Answer of a weekly memory clean-up."""

    model_config = ConfigDict(extra="forbid")

    actions: list[Action] = Field(default_factory=list, max_length=30)


def _skill_paths() -> Mapping[str, str]:
    from us_swing.core.desk_steps import SKILL_PATHS  # noqa: PLC0415 — avoids a cycle

    return SKILL_PATHS


def cleanup_text(notes: Sequence[Memory]) -> str:
    """The facts of one clean-up call: the notes with their checks."""
    lines = [HEAD]
    lines.extend(f"N-{m.id} ({m.right} right, {m.wrong} wrong, {m.status}): {m.text}"
                 for m in notes)
    return "\n".join(lines)


class MemoryCleanupStep:
    """Asks each lead and expert once a week to tidy its notes."""

    name = "Memory clean-up"

    def __init__(
        self,
        skills: Callable[[], Mapping[str, str]] = _skill_paths,
        settings: Callable[[], DeskAiSettings] | None = None,
        key: Callable[[], str] = load_key,
        caller: Caller = call_model,
        clock: Callable[[], datetime] = ny_now,
    ) -> None:
        """Set the skill list, settings, key, model caller and clock; injectable for tests."""
        self._skills = skills
        self._settings = settings
        self._key = key
        self._caller = caller
        self._clock = clock

    def __call__(self, ctx: StepContext) -> None:
        """Run the clean-up once per week while Memory v2 is on."""
        home = ctx.home or desk_home()
        settings = self._settings() if self._settings else load_settings(home)
        if not settings.memory_v2_on:
            return
        now = self._clock()
        week = report_friday(now.astimezone(NY).date()).isoformat()
        con = connect(home)
        try:
            if get_state(con, WEEK_KEY) == week:
                return
        finally:
            con.close()
        day = now.astimezone(NY).date().isoformat()
        for hire in load_employees(home, self._skills()):
            if hire.spec.status == "active" and is_top(hire.spec.level):
                try:
                    self._clean(hire, home, settings, ctx.run_id, day)
                except Exception:  # noqa: BLE001 — one employee never stops the others
                    log.exception("[Memory] Clean-up failed for %s", hire.spec.name)
        con = connect(home)
        try:
            set_state(con, WEEK_KEY, week)
        finally:
            con.close()

    def _clean(self, hire: Hire, home: Path, settings: DeskAiSettings, run_id: int,
               day: str) -> None:
        spec = hire.spec
        notes = cleanup_notes(home, spec.id)
        if not notes:
            return
        recorder = Recorder(home)
        try:
            gateway = Gateway(home, hire, recorder, settings, self._key(), run_id, day,
                              self._caller, self._clock,
                              part=Part("plan", spec.id, spec.name, spec.tokens_per_day))
            answer = gateway.ask(cleanup_text(notes), Cleanup)
        finally:
            recorder.close()
        if answer is None:
            log.info("[Memory] %s gave no clean-up answer; notes stay as they are", spec.name)
            return
        actions = [CleanupAction(a.id, a.do, a.into, a.text) for a in answer.actions]
        apply_cleanup(home, spec.id, actions, self._clock())
