"""
Module: MD-DSK-002.002.M09 — desk/registry.py
Parent SRD: SRD-DSK-002.002
Also: SRD-DSK-002.001 (skills by key), SRD-DSK-002.003 (job file wins),
SRD-DSK-002.004 (``employees`` table), SRD-DSK-002.006 (employee identity is data),
SRD-DSK-002.007 (employee files in the desk folder), SRD-DSK-002.009 (trigger list),
SRD-DSK-006.008 (status: retired employees are not loaded)

Employees are folders of data in ``<desk>/employees/<id>/``: ``soul.md`` (the prompt) and
``job.yaml`` (identity, level, reporting line, skill and rules). Defaults shipped with
the app are copied there only when missing, so the Master user's edits are never
overwritten. Code knows skills by key only, never employee names or titles.
"""
from __future__ import annotations

import hashlib
import importlib
import logging
import shutil
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from us_swing.core.desk_agents import Level, Skill
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_events import EVENT_KINDS
from us_swing.desk.recorder import ny_now

log = logging.getLogger(__name__)

SOUL_FILE = "soul.md"
JOB_FILE = "job.yaml"
EMPLOYEES_DIR = "employees"
Source = Literal["openrouter", "claude"]
Status = Literal["active", "shadow", "retired"]


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
    """The checked contents of ``job.yaml``; identity fields are free for the Master user."""

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
    kpis: list[str] = Field(min_length=1)
    status: Status = "active"
    hired_on: str | None = None

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
class Hire:
    """An employee: checked job spec, soul text (names filled in), its skill and file hash."""

    spec: JobSpec
    soul: str
    skill: Skill
    hash: str


def default_folders(packages: Sequence[str]) -> list[Path]:
    """Return the shipped default employee folders of ``packages`` (``<pkg>/employees/*``)."""
    out: list[Path] = []
    for name in packages:
        try:
            module = importlib.import_module(name)
        except ImportError as exc:
            log.warning("[AI Desk] Could not read default employees of %s: %s", name, exc)
            continue
        root = Path(str(module.__file__)).parent / EMPLOYEES_DIR
        out.extend(sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else [])
    return out


def seed_employees(home: Path, defaults: Sequence[Path]) -> int:
    """Copy each default employee folder into ``<home>/employees`` when it is missing."""
    target = home / EMPLOYEES_DIR
    target.mkdir(parents=True, exist_ok=True)
    added = 0
    for folder in defaults:
        if not (target / folder.name).exists():
            shutil.copytree(folder, target / folder.name)
            added += 1
    if added:
        log.info("[AI Desk] %d default employee(s) added to the desk folder", added)
    return added


def load_skill(key: str, paths: Mapping[str, str]) -> Skill | None:
    """Build the skill named ``key`` from its import path; ``None`` when unknown or broken."""
    path = paths.get(key)
    if path is None:
        return None
    module_name, _, class_name = path.partition(":")
    try:
        skill: Skill = getattr(importlib.import_module(module_name), class_name)()
    except Exception as exc:  # noqa: BLE001 — a broken skill only keeps its employees asleep
        log.warning("[AI Desk] Could not load skill %s: %s", key, exc)
        return None
    return skill


def load_employee(folder: Path, skills: Mapping[str, str]) -> Hire | None:
    """Read and check one employee folder; ``None`` (and a warning) when it is not valid."""
    try:
        soul_text = (folder / SOUL_FILE).read_text(encoding="utf-8")
        job_text = (folder / JOB_FILE).read_text(encoding="utf-8")
        spec = JobSpec.model_validate(yaml.safe_load(job_text))
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        reason = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        log.warning("[AI Desk] Employee files in %s are not valid, it stays asleep: %s",
                    folder.name, reason)
        return None
    skill = load_skill(spec.skill, skills)
    if skill is None:
        log.warning("[AI Desk] %s uses unknown skill %s and stays asleep", spec.name,
                    spec.skill)
        return None
    soul = soul_text.replace("{name}", spec.name).replace("{title}", spec.title)
    digest = hashlib.sha256(f"{soul_text}\0{job_text}".encode()).hexdigest()
    return Hire(spec, soul, skill, digest)


def load_employees(home: Path, skills: Mapping[str, str]) -> list[Hire]:
    """Load every valid employee in ``<home>/employees``; ids must be unique."""
    root = home / EMPLOYEES_DIR
    hires: list[Hire] = []
    seen: set[str] = set()
    for folder in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        hire = load_employee(folder, skills)
        if hire is None or hire.spec.status == "retired":
            continue
        if hire.spec.id in seen:
            log.warning("[AI Desk] Employee id %s is used twice; %s stays asleep",
                        hire.spec.id, folder.name)
            continue
        seen.add(hire.spec.id)
        hires.append(hire)
    return hires


def record_employees(home: Path, hires: Sequence[Hire]) -> None:
    """Keep id, name, title, level, reporting line, skill, version and hash in ``employees``."""
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    try:
        with con:
            con.execute("CREATE TABLE IF NOT EXISTS roster (id TEXT PRIMARY KEY, name TEXT, "
                        "title TEXT, level TEXT, reports_to TEXT, skill TEXT, version INTEGER, "
                        "hash TEXT, loaded_at TEXT)")
            for hire in hires:
                s = hire.spec
                old = con.execute("SELECT version, hash FROM roster WHERE id = ?",
                                  (s.id,)).fetchone()
                if old and old[0] == s.version and old[1] != hire.hash:
                    log.warning("[AI Desk] %s files changed but version is still %d", s.name,
                                s.version)
                con.execute(
                    "INSERT OR REPLACE INTO roster VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (s.id, s.name, s.title, s.level, s.reports_to, s.skill, s.version,
                     hire.hash, ny_now().isoformat(timespec="seconds")))
    finally:
        con.close()
