"""
Module: MD-DSK-006.001.M18 — core/desk_hiring.py
Parent SRD: SRD-DSK-006.001
Also: SRD-DSK-006.002 (refused hires), SRD-DSK-006.003 (seat count), SRD-DSK-006.005 (ready
after 14 data days), SRD-DSK-006.006 (shadow report and agreement), SRD-DSK-006.007
(decisions and ``approvals``), SRD-DSK-006.010 (log lines), SRD-DSK-008.007 (a hire
writes ``employee.md``)

The hiring pipeline, shared by the GUI (which starts hires and records decisions) and
the desk. Employees are folders of data in ``<desk>/employees/<id>/``; a hire always uses
a skill the code knows, and its name, level and model are the Master user's choice.
"""
from __future__ import annotations

import importlib
import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_employee import check, read_employee, save_employee, write_new
from us_swing.core.desk_employee import seat_counts as _seats
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS

log = logging.getLogger(__name__)

SHADOW_DAYS = 14
HIRE_LEVELS = ("expert", "champion", "junior")
SOURCES = ("claude", "openrouter")
DECISIONS = ("replace", "add", "reject")
_SHORT_TEXT = 20
_APPROVALS = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY, created TEXT, kind TEXT, subject TEXT, decision TEXT, detail TEXT
);
CREATE TRIGGER IF NOT EXISTS approvals_no_update BEFORE UPDATE ON approvals
BEGIN SELECT RAISE(ABORT, 'approvals is append-only'); END;
CREATE TRIGGER IF NOT EXISTS approvals_no_delete BEFORE DELETE ON approvals
BEGIN SELECT RAISE(ABORT, 'approvals is append-only'); END;
"""


@dataclass(frozen=True)
class Employee:
    """One employee folder as the hiring pipeline sees it."""

    folder: Path
    id: str
    name: str
    level: str
    skill: str
    status: str
    model: str
    hired_on: str | None


@dataclass(frozen=True)
class HireInfo:
    """A hire made through the pipeline, with its shadow progress."""

    employee: Employee
    days: int
    ready: bool
    has_holder: bool


@dataclass(frozen=True)
class ReportRow:
    """Shadow report figures for one side (the hire or the holder) over the shadow days."""

    who: str
    days: int
    valid: float | None
    tokens: int
    cost: float


@dataclass(frozen=True)
class ShadowReport:
    """Rows for the hire and its holder, and the agreement (``None`` without a holder)."""

    rows: list[ReportRow]
    agreement: float | None


def _employee(folder: Path) -> Employee | None:
    found = read_employee(folder)
    if found is None:
        return None
    s = found.spec
    primary = s.models.primary
    return Employee(folder, s.id, s.name, s.level, s.skill, s.status,
                    f"{primary.source} / {primary.model}", s.hired_on)


def employees(home: Path) -> list[Employee]:
    """Every readable employee in ``<home>/employees``, by folder name."""
    root = home / "employees"
    folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    return [e for e in (_employee(f) for f in folders) if e is not None]


def seat_counts(home: Path) -> dict[str, int]:
    """Active and shadow employees per level."""
    return _seats(home)


def _default_folder(skill: str) -> Path | None:
    for package in DEFAULT_EMPLOYEE_PACKAGES:
        root = Path(str(importlib.import_module(package).__file__)).parent / "employees"
        for folder in sorted(root.iterdir()) if root.is_dir() else []:
            found = _employee(folder)
            if found is not None and found.skill == skill:
                return folder
    return None


def _next_id(home: Path) -> str:
    root = home / "employees"
    numbers = [int(m.group(1)) for p in (root.iterdir() if root.is_dir() else [])
               if (m := re.fullmatch(r"emp-(\d+)", p.name))]
    return f"emp-{max(numbers, default=0) + 1:03d}"


def refuse_reason(home: Path, skill: str, level: str, name: str, source: str,
                  model: str) -> str:
    """Why a hire cannot start, or an empty text when it can."""
    cap = load_settings(home).cap(level)
    if skill not in SKILL_PATHS:
        return f"unknown skill {skill}"
    if level not in HIRE_LEVELS:
        return "a hire must be an expert, champion or junior"
    if not name.strip():
        return "the name is empty"
    if source not in SOURCES or not model.strip() or model.startswith("-"):
        return "choose a source and a model"
    if any(e.name.strip().lower() == name.strip().lower() for e in employees(home)):
        return f"the name {name.strip()} is already used"
    if cap is not None and seat_counts(home).get(level, 0) >= cap:
        return f"all {cap} {level} seats are taken"
    if _default_folder(skill) is None:
        return f"no default files for skill {skill}"
    return ""


def start_hire(home: Path, skill: str, level: str, name: str, source: str, model: str,
               today: date) -> tuple[str | None, str]:
    """Create a shadow employee; return ``(id, "")`` or ``(None, reason)``."""
    reason = refuse_reason(home, skill, level, name, source, model)
    if reason:
        log.info("[Hiring] Hire not started: %s", reason)
        return None, reason
    default = _default_folder(skill)
    if default is None:
        return None, f"no default files for skill {skill}"
    template = read_employee(default)
    if template is None:
        return None, f"no default files for skill {skill}"
    job: dict[str, Any] = template.spec.model_dump(mode="json")
    new_id = _next_id(home)
    job.update({"id": new_id, "name": name.strip(), "title": level.title(), "level": level,
                "version": 1, "status": "shadow", "hired_on": today.isoformat()})
    job["models"]["primary"] = {"source": source, "model": model.strip()}
    header = (f"# Hired by the Master user on {today.isoformat()}; it runs in shadow until a "
              "decision.\n")
    write_new(home / "employees" / new_id, check(job), template.prompt, header)
    log.info("[Hiring] %s started in shadow for the %s skill", name.strip(),
             skill.replace("_", " "))
    return new_id, ""


def _connect(home: Path) -> sqlite3.Connection | None:
    path = home / DB_NAME
    if not path.exists():
        return None
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)


def _rows(home: Path, sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    con = _connect(home)
    if con is None:
        return []
    try:
        return [tuple(r) for r in con.execute(sql, params).fetchall()]
    except sqlite3.Error:
        return []
    finally:
        con.close()


def shadow_days(home: Path, employee_id: str) -> set[str]:
    """Data days on which the employee was asked in shadow."""
    return {str(r[0]) for r in _rows(
        home, "SELECT DISTINCT data_day FROM activity WHERE employee = ? AND shadow = 1",
        (employee_id,))}


def holders(home: Path, skill: str, exclude: str = "") -> list[Employee]:
    """Active employees with ``skill`` (other than ``exclude``)."""
    return [e for e in employees(home)
            if e.skill == skill and e.status == "active" and e.id != exclude]


def list_hires(home: Path) -> list[HireInfo]:
    """Hires made through the pipeline, newest first."""
    staff = employees(home)
    out: list[HireInfo] = []
    for e in staff:
        if not e.hired_on:
            continue
        days = len(shadow_days(home, e.id))
        has_holder = any(h.skill == e.skill and h.status == "active" and h.id != e.id
                         for h in staff)
        out.append(HireInfo(e, days, e.status == "shadow" and days >= SHADOW_DAYS, has_holder))
    return sorted(out, key=lambda h: (h.employee.hired_on or "", h.employee.id), reverse=True)


def _answer(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _short_values(value: Any, path: str = "") -> set[str]:
    if isinstance(value, dict):
        return {v for k, item in value.items() for v in _short_values(item, f"{path}.{k}")}
    if isinstance(value, list):
        out: set[str] = set()
        for index, item in enumerate(value):
            key = (f"{item.get('side', '')}:{item.get('symbol', '')}"
                   if isinstance(item, dict) and "symbol" in item else str(index))
            out |= _short_values(item, f"{path}[{key}]")
        return out
    if isinstance(value, bool | int | float) or (
            isinstance(value, str) and len(value) <= _SHORT_TEXT):
        return {f"{path}={value}"}
    return set()


def agreement(first: dict[str, Any], second: dict[str, Any]) -> float:
    """Share of short typed values the two answers have in common (free text left out)."""
    a, b = _short_values(first), _short_values(second)
    return 1.0 if not a | b else len(a & b) / len(a | b)


def _side(who: str, rows: list[tuple[Any, ...]], days: set[str]
          ) -> tuple[ReportRow, dict[str, dict[str, Any]]]:
    seen: set[str] = set()
    valid_days: set[str] = set()
    answers: dict[str, dict[str, Any]] = {}
    tokens, cost = 0, 0.0
    for day, valid, used, spent, text in rows:
        if str(day) not in days:
            continue
        seen.add(str(day))
        tokens += int(used or 0)
        cost += float(spent or 0.0)
        if valid:
            valid_days.add(str(day))
            parsed = _answer(str(text or ""))
            if parsed is not None:
                answers[str(day)] = parsed
    share = len(valid_days) / len(seen) if seen else None
    return ReportRow(who, len(seen), share, tokens, round(cost, 4)), answers


def shadow_report(home: Path, hire_id: str) -> ShadowReport:
    """Figures for the hire and its holder over the hire's shadow days."""
    hire = next((e for e in employees(home) if e.id == hire_id), None)
    if hire is None:
        return ShadowReport([], None)
    days = shadow_days(home, hire_id)
    select = ("SELECT data_day, valid, tokens_in + tokens_out, cost_usd, answer FROM activity "
              "WHERE employee = ? AND {} ORDER BY id")
    mine, mine_answers = _side(hire.name, _rows(home, select.format("shadow = 1"),
                                                (hire_id,)), days)
    rows = [mine]
    agree: float | None = None
    for holder in holders(home, hire.skill, hire_id):
        tries = _rows(home, select.format("COALESCE(shadow, 0) = 0 AND COALESCE(replay, 0) = 0"),
                      (holder.id,))
        row, answers = _side(holder.name, tries, days)
        rows.append(row)
        common = [d for d in answers if d in mine_answers]
        if common:
            agree = round(sum(agreement(mine_answers[d], answers[d]) for d in common)
                          / len(common), 2)
    return ShadowReport(rows, agree)


def _set_status(folder: Path, status: str) -> None:
    current = read_employee(folder)
    if current is None:
        raise OSError(f"cannot read {folder.name}")
    reason = save_employee(folder.parent.parent, folder.name, {"status": status},
                           current.prompt)
    if reason:
        raise OSError(reason)


def decide(home: Path, hire_id: str, decision: str, now: datetime) -> str:
    """Record and apply a Master decision; return an empty text, or why it was refused."""
    hire = next((h for h in list_hires(home) if h.employee.id == hire_id), None)
    if hire is None or decision not in DECISIONS:
        return "unknown hire or decision"
    e = hire.employee
    if decision != "reject" and not hire.ready:
        return f"{e.name} is not ready: {hire.days} of {SHADOW_DAYS} shadow days"
    if decision == "add" and hire.has_holder:
        return f"the {e.skill.replace('_', ' ')} skill already has an active holder"
    old = holders(home, e.skill, e.id) if decision == "replace" else []
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    try:
        with con:
            con.executescript(_APPROVALS)
            con.execute("INSERT INTO approvals (created, kind, subject, decision, detail) "
                        "VALUES (?, 'hire', ?, ?, ?)",
                        (now.isoformat(timespec="seconds"), e.id, decision,
                         ", ".join(h.id for h in old)))
    finally:
        con.close()
    try:
        for holder in old:
            _set_status(holder.folder, "retired")
        _set_status(e.folder, "retired" if decision == "reject" else "active")
    except OSError as exc:
        log.error("[Hiring] Decision for %s was saved but the employee files could not be "
                  "changed: %s", e.name, exc)
        return "the employee files could not be changed"
    log.info("[Hiring] %s: %s (%d employee(s) retired)", e.name, decision,
             len(old) + (decision == "reject"))
    return ""
