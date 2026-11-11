"""
Module: MD-DSK-008.001.M22 — core/desk_employee.py
Parent SRD: SRD-DSK-008.001
Also: SRD-DSK-008.002 (shared rules), SRD-DSK-008.003 (move old files), SRD-DSK-008.005
(save with history), SRD-DSK-008.006 (restore), SRD-DSK-008.008 (draft test),
SRD-DSK-008.009 (seat caps), SRD-DSK-004.006 (daily token budget)

An AI employee is one ``employee.md`` in ``<desk>/employees/<id>/``: a YAML block between
two ``---`` lines with the job settings, then the system prompt. The desk and the app both
read and write it through this module, so they check it with the same rules. Earlier
versions are kept in ``history/``.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from us_swing.core.desk_agents import Level
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import DB_NAME, desk_command
from us_swing.core.desk_events import EVENT_KINDS

log = logging.getLogger(__name__)

EMPLOYEE_FILE = "employee.md"
TOKENS_PER_DAY = 60_000
JOB_FILE = "job.yaml"
SOUL_FILE = "soul.md"
EMPLOYEES_DIR = "employees"
HISTORY_DIR = "history"
DEFAULT_MODEL = "default"
SEATED = ("active", "shadow")
Source = Literal["openrouter", "claude"]
Status = Literal["active", "shadow", "retired"]
_FENCE = "---"
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class ModelChoice(BaseModel):
    """One model and the source that serves it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Source
    model: str = Field(min_length=1)


class Models(BaseModel):
    """Primary model and backup model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary: ModelChoice
    backup: ModelChoice


class JobSpec(BaseModel):
    """The checked job settings; identity fields are free for the Master user."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    level: Level
    reports_to: str | None = None
    skill: str = Field(min_length=1)
    version: int = Field(ge=1)
    trigger: tuple[str, ...] = Field(min_length=1)
    models: Models
    calls_per_day: int = Field(ge=1)
    monthly_cost_usd: float = Field(gt=0)
    tokens_per_day: int = Field(default=TOKENS_PER_DAY, ge=1_000)
    kpis: list[str] = Field(min_length=1)
    status: Status = "active"
    hired_on: str | None = None

    @field_validator("name", "title")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Names and titles may not be only spaces."""
        if not value.strip():
            raise ValueError("may not be empty")
        return value.strip()

    @field_validator("hired_on", mode="before")
    @classmethod
    def _day_text(cls, value: object) -> object:
        """Accept an unquoted YAML date as its ISO text."""
        return value.isoformat() if isinstance(value, date) else value

    @field_validator("trigger", mode="before")
    @classmethod
    def _trigger_list(cls, value: object) -> object:
        """Accept one event kind or a list, and allow only known kinds."""
        kinds = [value] if isinstance(value, str) else value
        if isinstance(kinds, list | tuple):
            unknown = [k for k in kinds if k not in EVENT_KINDS]
            if unknown:
                raise ValueError(f"unknown event kind {unknown[0]}")
            return tuple(kinds)
        return value


@dataclass(frozen=True)
class EmployeeFile:
    """A checked employee file: job settings, the prompt as written, and the file text."""

    spec: JobSpec
    prompt: str
    text: str


@dataclass(frozen=True)
class Version:
    """One saved version of an employee file."""

    number: int
    saved: datetime
    path: Path
    current: bool


@dataclass(frozen=True)
class DraftResult:
    """What a draft prompt answered on the employee's last recorded run."""

    valid: bool
    answer: str
    note: str = ""


def _reason(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = " ".join(str(p) for p in error["loc"]).replace("_", " ")
    message = str(error["msg"]).removeprefix("Value error, ")
    return f"{where}: {message[0].lower()}{message[1:]}" if where else message


def check(data: object) -> JobSpec:
    """Check job settings; raise ``ValueError`` with the first plain reason."""
    if not isinstance(data, dict):
        raise ValueError("the settings block is not a list of fields")
    try:
        return JobSpec.model_validate(data)
    except ValidationError as exc:
        raise ValueError(_reason(exc)) from None


def parse(text: str) -> EmployeeFile:
    """Read an employee file; raise ``ValueError`` with a plain reason when it is wrong."""
    lines = text.lstrip("﻿").split("\n")
    starts = [i for i, line in enumerate(lines) if line.rstrip() == _FENCE]
    if len(starts) < 2 or any(line.strip() and not line.lstrip().startswith("#")
                              for line in lines[:starts[0]]):
        raise ValueError("the file has no settings block between two --- lines at the top")
    try:
        data = yaml.safe_load("\n".join(lines[starts[0] + 1:starts[1]]))
    except yaml.YAMLError as exc:
        raise ValueError(f"the settings block is not valid YAML: {str(exc).splitlines()[0]}"
                         ) from None
    spec = check(data)
    prompt = "\n".join(lines[starts[1] + 1:]).strip("\n")
    if not prompt.strip():
        raise ValueError("the prompt is empty")
    return EmployeeFile(spec, prompt, text)


def render(spec: JobSpec, prompt: str, header: str = "") -> str:
    """Write ``spec`` and ``prompt`` as employee file text; ``header`` is YAML comment lines."""
    data = spec.model_dump(mode="json")
    block = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return f"{header}{_FENCE}\n{block}{_FENCE}\n{prompt.strip(chr(10))}\n"


def _header(text: str) -> str:
    """The comment lines above the first ``---`` of an employee file."""
    lines = text.lstrip("﻿").splitlines()
    head = lines[:lines.index(_FENCE)] if _FENCE in lines else []
    return "".join(f"{line}\n" for line in head if line.lstrip().startswith("#"))


def filled(employee: EmployeeFile) -> str:
    """The prompt with ``{name}`` and ``{title}`` filled in."""
    spec = employee.spec
    return employee.prompt.replace("{name}", spec.name).replace("{title}", spec.title)


def _legacy(folder: Path) -> EmployeeFile:
    soul = (folder / SOUL_FILE).read_text(encoding="utf-8")
    try:
        data = yaml.safe_load((folder / JOB_FILE).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"job.yaml is not valid YAML: {str(exc).splitlines()[0]}") from None
    spec = check(data)
    if not soul.strip():
        raise ValueError("the prompt is empty")
    return EmployeeFile(spec, soul.strip("\n"), render(spec, soul))


def load(folder: Path) -> EmployeeFile:
    """Read ``employee.md``, or the old ``job.yaml`` + ``soul.md`` pair; raise when wrong.

    Raises:
        ValueError: The file is missing or does not pass the rules (plain reason).
    """
    path = folder / EMPLOYEE_FILE
    try:
        if path.exists():
            return parse(path.read_text(encoding="utf-8"))
        return _legacy(folder)
    except OSError as exc:
        raise ValueError(f"the file could not be read: {exc.strerror or exc}") from None


def read_employee(folder: Path) -> EmployeeFile | None:
    """Like :func:`load`, but ``None`` when the folder holds no valid employee."""
    try:
        return load(folder)
    except ValueError:
        return None


def employee_folders(home: Path) -> list[Path]:
    """Every employee folder in ``<home>/employees``, by name."""
    root = home / EMPLOYEES_DIR
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def migrate_folder(folder: Path) -> bool:
    """Turn an old ``job.yaml`` + ``soul.md`` pair into ``employee.md`` once."""
    if (folder / EMPLOYEE_FILE).exists() or not (folder / JOB_FILE).exists():
        return False
    try:
        old = _legacy(folder)
        history = folder / HISTORY_DIR
        history.mkdir(exist_ok=True)
        for name in (JOB_FILE, SOUL_FILE):
            stem, _, ext = name.partition(".")
            shutil.copy2(folder / name, _free(history / f"v{old.spec.version}-{stem}.{ext}"))
        _write(folder / EMPLOYEE_FILE, old.text)
    except (OSError, ValueError) as exc:
        log.warning("[AI Desk] Old employee files in %s were not moved: %s", folder.name, exc)
        return False
    for name in (JOB_FILE, SOUL_FILE):
        try:
            (folder / name).unlink()
        except OSError as exc:
            log.warning("[AI Desk] Could not remove the old %s in %s: %s", name, folder.name,
                        exc)
    return True


def _free(path: Path) -> Path:
    """``path``, or the same name with -2, -3 … when it is already taken."""
    candidate, n = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}~{n}{path.suffix}")
        n += 1
    return candidate


def migrate_all(home: Path) -> int:
    """Move every old employee folder to ``employee.md``; return how many moved."""
    moved = sum(migrate_folder(f) for f in employee_folders(home))
    if moved:
        log.info("[AI Desk] Moved %d employee(s) to employee.md", moved)
    return moved


def seat_counts(home: Path) -> dict[str, int]:
    """Active and shadow employees per level."""
    counts: dict[str, int] = {}
    for folder in employee_folders(home):
        employee = read_employee(folder)
        if employee is not None and employee.spec.status in SEATED:
            counts[employee.spec.level] = counts.get(employee.spec.level, 0) + 1
    return counts


def _write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_new(folder: Path, spec: JobSpec, prompt: str, header: str = "") -> None:
    """Write a brand-new employee file (a hire); the folder is made when missing."""
    folder.mkdir(parents=True, exist_ok=True)
    _write(folder / EMPLOYEE_FILE, render(spec, prompt, header))


def _seat_refusal(home: Path, old: JobSpec, new: JobSpec) -> str:
    if new.status not in SEATED or (new.level == old.level and old.status in SEATED):
        return ""
    cap = load_settings(home).cap(new.level)
    if cap is not None and seat_counts(home).get(new.level, 0) >= cap:
        return f"all {cap} {new.level} seats are taken"
    return ""


def save_employee(home: Path, emp_id: str, fields: Mapping[str, Any], prompt: str) -> str:
    """Check and save a changed employee as the next version; return ``""`` or why not.

    Args:
        home: Desk folder.
        emp_id: Employee id (folder name).
        fields: Job fields to change; ``id``, ``skill`` and ``version`` are ignored.
        prompt: The new system prompt.
    """
    folder = home / EMPLOYEES_DIR / emp_id
    migrate_folder(folder)
    try:
        current = load(folder)
    except ValueError as exc:
        return str(exc)
    old = current.spec
    data = old.model_dump(mode="json") | dict(fields)
    data.update(id=old.id, skill=old.skill, version=old.version + 1)
    try:
        spec = check(data)
    except ValueError as exc:
        return str(exc)
    if not prompt.strip():
        return "the prompt is empty"
    refusal = _seat_refusal(home, old, spec)
    if refusal:
        return refusal
    history = folder / HISTORY_DIR
    try:
        history.mkdir(exist_ok=True)
        keep = history / f"v{old.version}.md"
        if keep.exists() and keep.read_text(encoding="utf-8") != current.text:
            keep = _free(keep)
        if not keep.exists():
            shutil.copy2(folder / EMPLOYEE_FILE, keep)
        _write(folder / EMPLOYEE_FILE, render(spec, prompt, _header(current.text)))
    except OSError as exc:
        return f"the file could not be saved: {exc.strerror or exc}"
    log.info("[Team setup] Saved %s as version %d", spec.name, spec.version)
    return ""


def versions(folder: Path) -> list[Version]:
    """Saved versions, newest first; the current file is marked."""
    out: list[Version] = []
    current = read_employee(folder)
    for path in (folder / HISTORY_DIR).glob("v*.md") if (folder / HISTORY_DIR).is_dir() else []:
        match = re.fullmatch(r"v(\d+)\.md", path.name)
        if match and (current is None or int(match.group(1)) != current.spec.version):
            out.append(Version(int(match.group(1)),
                               datetime.fromtimestamp(path.stat().st_mtime), path, False))
    if current is not None:
        path = folder / EMPLOYEE_FILE
        saved = datetime.fromtimestamp(path.stat().st_mtime) if path.exists() else datetime.now()
        out.append(Version(current.spec.version, saved, path, True))
    return sorted(out, key=lambda v: v.number, reverse=True)


def restore(home: Path, emp_id: str, number: int) -> str:
    """Save version ``number`` again as the next version; return ``""`` or why not."""
    folder = home / EMPLOYEES_DIR / emp_id
    found = next((v for v in versions(folder) if v.number == number), None)
    if found is None:
        return f"version {number} is not kept"
    try:
        old = parse(found.path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"version {number} cannot be read: {exc}"
    fields = old.spec.model_dump(mode="json")
    for key in ("id", "skill", "version", "status"):
        fields.pop(key)
    return save_employee(home, emp_id, fields, old.prompt)


def _activity(home: Path, sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    path = home / DB_NAME
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return []
    try:
        return list(con.execute(sql, params))
    except sqlite3.Error:
        return []
    finally:
        con.close()


def known_models(home: Path) -> dict[str, list[str]]:
    """Models to offer per source: default, the desk settings model, and models used before."""
    settings = load_settings(home)
    out = {"claude": [DEFAULT_MODEL, settings.claude_model],
           "openrouter": [DEFAULT_MODEL, settings.openrouter_model]}
    for source, model in _activity(home, "SELECT DISTINCT source, model FROM activity", ()):
        if source in out and model:
            out[str(source)].append(str(model))
    return {s: list(dict.fromkeys(m for m in models if m)) for s, models in out.items()}


def last_run(home: Path, emp_id: str) -> int | None:
    """The newest desk run with a recorded live try by ``emp_id``."""
    rows = _activity(home, "SELECT MAX(run_id) FROM activity WHERE employee = ? AND "
                     "COALESCE(replay, 0) = 0", (emp_id,))
    return int(rows[0][0]) if rows and rows[0][0] is not None else None


def try_draft(home: Path, emp_id: str, text: str, timeout: float = 180.0) -> DraftResult:
    """Ask the desk to answer the employee's last recorded question with a draft file.

    One real model call is made (recorded as a replay). Nothing is saved to the employee.
    """
    try:
        parse(text)
    except ValueError as exc:
        return DraftResult(False, "", str(exc))
    run_id = last_run(home, emp_id)
    if run_id is None:
        return DraftResult(False, "", "no recorded run for this employee yet")
    with tempfile.TemporaryDirectory() as tmp:
        draft, out = Path(tmp) / EMPLOYEE_FILE, Path(tmp) / "result.json"
        draft.write_text(text, encoding="utf-8")
        command = desk_command()
        console = Path(command[0]).with_name("python.exe")
        if command[0].lower().endswith("pythonw.exe") and console.exists():
            command[0] = str(console)
        done: subprocess.CompletedProcess[bytes] | None = None
        try:
            done = subprocess.run(  # noqa: S603 — fixed command built from our own executable
                [*command, "replay", str(run_id), "--employee", emp_id, "--draft", str(draft),
                 "--out", str(out)],
                capture_output=True, timeout=timeout, creationflags=_NO_WINDOW, check=False)
            result = json.loads(out.read_text(encoding="utf-8"))
            if not isinstance(result, dict):
                raise ValueError("the test result is not readable")
        except subprocess.TimeoutExpired:
            return DraftResult(False, "", "the test took too long")
        except (OSError, ValueError):
            err = done.stderr if done is not None else b""
            tail = err.decode(errors="replace").strip().splitlines()[-1:]
            log.warning("[Team setup] The prompt test did not finish%s",
                        f": {tail[0]}" if tail else "")
            return DraftResult(False, "", "the test did not finish")
    return DraftResult(bool(result.get("valid")), str(result.get("answer") or ""),
                       str(result.get("note") or ""))
