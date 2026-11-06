"""
Module: MD-DSK-002.002.M09 — desk/registry.py
Parent SRD: SRD-DSK-002.002
Also: SRD-DSK-002.001 (employees by import path), SRD-DSK-002.003 (job file wins),
SRD-DSK-002.004 (``employees`` table)

Loads AI employees by import path and checks their ``job.yaml`` against a fixed schema.
``soul.md`` is only the system prompt; everything enforced comes from ``job.yaml``.
"""
from __future__ import annotations

import hashlib
import importlib
import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from us_swing.core.desk_agents import Employee
from us_swing.core.desk_contract import DB_NAME
from us_swing.desk.recorder import ny_now

log = logging.getLogger(__name__)

SOUL_FILE = "soul.md"
JOB_FILE = "job.yaml"
Source = Literal["openrouter", "claude"]


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
    """The checked contents of ``job.yaml``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    version: int = Field(ge=1)
    trigger: Literal["after_run"]
    output: str = Field(min_length=1)
    models: Models
    calls_per_day: int = Field(ge=1)
    monthly_cost_usd: float = Field(gt=0)
    kpis: list[str] = Field(min_length=1)


@dataclass(frozen=True)
class Hire:
    """An employee with its checked job spec, its soul text and the files' hash."""

    employee: Employee
    spec: JobSpec
    soul: str
    hash: str


def load_employees(paths: Sequence[str]) -> list[Employee]:
    """Import and build each employee in ``paths`` (``"module:Class"``); bad ones are left out."""
    out: list[Employee] = []
    for path in paths:
        module_name, _, class_name = path.partition(":")
        try:
            out.append(getattr(importlib.import_module(module_name), class_name)())
        except Exception as exc:  # noqa: BLE001 — one bad employee never stops the others
            log.warning("[AI Desk] Could not load AI employee %s: %s", path, exc)
    return out


def load_employee(employee: Employee) -> Hire | None:
    """Read and check the employee's ``soul.md`` and ``job.yaml``; ``None`` when not valid."""
    try:
        soul = (employee.folder / SOUL_FILE).read_text(encoding="utf-8")
        job_text = (employee.folder / JOB_FILE).read_text(encoding="utf-8")
        spec = JobSpec.model_validate(yaml.safe_load(job_text))
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        reason = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        log.warning("[AI Desk] %s job file is not valid, it stays asleep: %s",
                    employee.name, reason)
        return None
    digest = hashlib.sha256(f"{soul}\0{job_text}".encode()).hexdigest()
    return Hire(employee, spec, soul, digest)


def record_employees(home: Path, hires: Sequence[Hire]) -> None:
    """Keep the name, title, version and hash of each loaded employee in ``employees``."""
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    try:
        with con:
            con.execute("CREATE TABLE IF NOT EXISTS employees (name TEXT PRIMARY KEY, "
                        "title TEXT, version INTEGER, hash TEXT, loaded_at TEXT)")
            for hire in hires:
                old = con.execute("SELECT version, hash FROM employees WHERE name = ?",
                                  (hire.spec.name,)).fetchone()
                if old and old[0] == hire.spec.version and old[1] != hire.hash:
                    log.warning("[AI Desk] %s files changed but version is still %d",
                                hire.spec.name, hire.spec.version)
                con.execute(
                    "INSERT OR REPLACE INTO employees VALUES (?, ?, ?, ?, ?)",
                    (hire.spec.name, hire.spec.title, hire.spec.version, hire.hash,
                     ny_now().isoformat(timespec="seconds")))
    finally:
        con.close()
