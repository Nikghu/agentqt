"""Shared helpers for the hire proposal (AI Desk v3 M7a) tests: a small desk with made-up
employees, tries in ``activity`` and a talking context that returns a set answer.

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from tests.desk import test_harness as th
from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.core.desk_msg import Draft
from us_swing.core.desk_proposals import FAILING, Need
from us_swing.desk.recorder import Attempt, Recorder
from us_swing.desk.secretary import HireReviewSkill

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 13, 9, 0, tzinfo=NY)  # a Friday
DAY = "2026-11-13"
BOSS, SEC, FAIL = "emp-b", "emp-s", "emp-f"
SETTINGS = DeskAiSettings(openrouter_on=True, openrouter_model="m", claude_on=True,
                          claude_model="c", messages_on=True, hire_proposals_on=True)
SOUL = "You are {name}, {title}."


def job(emp_id: str, name: str, skill: str, level: str = "expert", trigger: str = "after_run",
        reports_to: str | None = None, status: str = "active") -> str:
    """Job text of one made-up employee."""
    return f"""id: {emp_id}
name: {name}
title: Test helper
level: {level}
reports_to: {reports_to or 'null'}
skill: {skill}
version: 1
trigger: {trigger}
models:
  primary: {{source: openrouter, model: m}}
  backup: {{source: claude, model: default}}
calls_per_day: 20
monthly_cost_usd: 3.0
kpis: [valid answers]
status: {status}
"""


def hire(home: Path, emp_id: str, name: str, skill: str, level: str = "expert",
         trigger: str = "after_run", reports_to: str | None = None,
         status: str = "active") -> None:
    """Write one made-up employee folder."""
    th.employee(home, emp_id, job(emp_id, name, skill, level, trigger, reports_to, status),
                SOUL)


def team(home: Path, boss: bool = True) -> None:
    """A boss, the secretary (reporting to the boss) and a setup reviewer; settings on."""
    if boss:
        hire(home, BOSS, "Helm", "boss_desk", level="lead")
    hire(home, SEC, "Ledger", "hire_review", trigger="weekly_report",
         reports_to=BOSS if boss else None)
    hire(home, FAIL, "Quill", "setup_review")
    save_settings(SETTINGS, home)


def days(n: int, last: str = DAY) -> list[str]:
    """``n`` data days ending on ``last``, oldest first."""
    end = date.fromisoformat(last)
    return [(end - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


def tries(home: Path, emp: str, day: str, count: int, valid: int, cost: float = 0.0,
          shadow: int = 0, replay: int = 0) -> None:
    """Record ``count`` tries of ``emp`` on ``day``; the first ``valid`` are valid; each try
    costs ``cost`` USD."""
    rec = Recorder(home)
    try:
        for n in range(count):
            ok = n < valid
            rec.add(Attempt(1, emp, emp, 1, day, f"{day}T09:00:00-05:00", "openrouter", "m", 1,
                            "p", '{"ok": 1}' if ok else "bad", ok, "", 10, 10, cost, 1.0,
                            replay, shadow))
    finally:
        rec.close()


def failing(home: Path, emp: str = FAIL, valid: int = 9, total: int = 15) -> None:
    """``valid`` of ``total`` tries over 5 data days, spread evenly."""
    per_day = total // 5
    left = valid
    for day in days(5):
        good = min(per_day, left)
        tries(home, emp, day, per_day, good)
        left -= good


def need(skill: str = "setup_review", holder: str = FAIL, kind: str = FAILING) -> Need:
    """A need as the rules would find it."""
    return Need(kind, skill, "expert", holder, (f"Quill ({skill.replace('_', ' ')}): 9 valid "
                                                "answers in 15 tries over the last 5 data days "
                                                "(60%).",))


class Ctx:
    """A talking context: every model ask returns ``reply``; drafts and facts are kept."""

    talk = True

    def __init__(self, home: Path, reply: BaseModel | None = None) -> None:
        self.home = home
        self.reply = reply
        self.drafts: list[Draft] = []
        self.facts: list[str] = []

    @property
    def asked(self) -> int:
        """How often the model was asked."""
        return len(self.facts)

    def send(self, draft: Draft) -> None:
        self.drafts.append(draft)

    def ask(self, facts: str, schema: type) -> Any:
        self.facts.append(facts)
        return self.reply


def secretary() -> HireReviewSkill:
    """The secretary skill with the test clock."""
    return HireReviewSkill(clock=lambda: NOW)
