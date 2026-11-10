"""
Module: MD-DSK-005.005.M17 — desk/replay.py
Parent SRD: SRD-DSK-005.005
Also: SRD-DSK-005.006 (replay tries marked, nothing else written), SRD-DSK-005.007 (report),
SRD-DSK-008.008 (``--draft``: a changed prompt answers the recorded question)

``desk replay <run>``: sends the recorded prompts of one desk run again, with the recorded
model or another one, and compares the answers. A replay never calls a skill's ``act``,
so it writes no views, picks, briefs or events; its tries are recorded as replays.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from us_swing.core.desk_ai_settings import DeskAiSettings, load_key, load_settings
from us_swing.core.desk_employee import DEFAULT_MODEL, EmployeeFile, filled
from us_swing.desk.gateway import (
    Caller,
    ReplayGateway,
    call_model,
    json_part,
    system_prompt,
)
from us_swing.desk.recorder import RecordedTry, Recorder
from us_swing.desk.registry import load_employees

log = logging.getLogger(__name__)

_PROMPT_SPLIT = "\n\n---\n\n"


@dataclass(frozen=True)
class ReplayLine:
    """The result for one employee in a replay."""

    name: str
    model: str
    old_valid: bool
    new_valid: bool
    changed: tuple[str, ...]
    note: str = ""
    answer: str = ""


def _skill_paths() -> Mapping[str, str]:
    from us_swing.core.desk_steps import SKILL_PATHS  # noqa: PLC0415 — avoids a cycle

    return SKILL_PATHS


def _parse(schema: type[BaseModel], text: str) -> BaseModel | None:
    try:
        return schema.model_validate_json(json_part(text))
    except ValidationError:
        return None


def _changed(old: BaseModel | None, new: BaseModel | None) -> tuple[str, ...]:
    if old is None or new is None:
        return ()
    return tuple(f for f in type(old).model_fields if getattr(old, f) != getattr(new, f))


def replay(home: Path, run_id: int, employee: str | None = None, model: str | None = None,
           settings: DeskAiSettings | None = None, key: Callable[[], str] = load_key,
           caller: Caller = call_model,
           skills: Callable[[], Mapping[str, str]] = _skill_paths,
           draft: EmployeeFile | None = None) -> list[ReplayLine] | None:
    """Replay one desk run; ``None`` when the run has no recorded tries.

    Args:
        home: Desk folder.
        run_id: Desk run to replay.
        employee: Only this employee id, when given.
        model: Use this model instead of the recorded one, when given.
        settings: Desk AI settings (read from the desk folder when ``None``).
        key: Returns the OpenRouter key.
        caller: Model caller (injectable for tests).
        skills: Returns the skill list.
        draft: Ask with this unsaved employee file's prompt and main model instead.
    """
    recorder = Recorder(home)
    try:
        tries = [t for t in recorder.run_tries(run_id) if employee in (None, t.employee)]
        if not tries:
            return None
        by_employee: dict[str, list[RecordedTry]] = {}
        for t in tries:
            by_employee.setdefault(t.employee, []).append(t)
        hires = {h.spec.id: h for h in load_employees(home, skills())}
        chosen = settings or load_settings(home)
        lines: list[ReplayLine] = []
        for emp_id, emp_tries in by_employee.items():
            first, valid = emp_tries[0], [t for t in emp_tries if t.valid]
            old = valid[-1] if valid else emp_tries[-1]
            use_model = model or first.model
            hire = hires.get(emp_id)
            if hire is None:
                lines.append(ReplayLine(first.employee_name, use_model, old.valid, False, (),
                                        "employee not found"))
                continue
            system, _, user = first.prompt.rpartition(_PROMPT_SPLIT)
            schema = hire.skill.answer
            source = first.source
            if draft is not None:
                choice = draft.spec.models.primary
                system, source = system_prompt(filled(draft), schema), choice.source
                use_model = model or (choice.model if choice.model != DEFAULT_MODEL else (
                    chosen.openrouter_model if source == "openrouter" else chosen.claude_model))
                if not (chosen.openrouter_on if source == "openrouter" else chosen.claude_on):
                    lines.append(ReplayLine(hire.spec.name, use_model, old.valid, False, (),
                                            f"not asked: {source} is off in desk AI settings"))
                    continue
            gateway = ReplayGateway(home, hire, recorder, chosen, key(), run_id, first.data_day,
                              caller, replay=True)
            new = gateway.resend(system, user, schema, source, use_model)
            note = f"not asked: {gateway.refused}" if gateway.refused else ""
            lines.append(ReplayLine(hire.spec.name, use_model, old.valid, new is not None,
                                    _changed(_parse(schema, old.answer), new), note,
                                    new.model_dump_json(indent=2) if new is not None else ""))
        return lines
    finally:
        recorder.close()


def report(run_id: int, lines: list[ReplayLine]) -> str:
    """Plain ASCII report of a replay."""
    out = [f"Replay of desk run {run_id}"]
    for line in lines:
        old = "valid" if line.old_valid else "not valid"
        new = "valid" if line.new_valid else "not valid"
        changed = ", ".join(line.changed) if line.changed else "none"
        text = f"- {line.name} ({line.model}): recorded {old}, replay {new}; changed: {changed}"
        out.append(text + (f"; {line.note}" if line.note else ""))
    return "\n".join(out).encode("ascii", "replace").decode("ascii")
