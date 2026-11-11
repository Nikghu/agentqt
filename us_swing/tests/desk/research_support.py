"""Shared helpers for the research queue tests (Autonomous desk step E)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_employee import migrate_all
from us_swing.core.desk_research import StepResult, Ticket, TicketAsk
from us_swing.desk.recorder import NY, Attempt, Recorder

NOW = datetime(2026, 11, 6, 11, 0, tzinfo=NY)  # Friday
DAY = "2026-11-06"
ON = DeskAiSettings(openrouter_on=True, openrouter_model="or-default", claude_on=True,
                    claude_model="claude-default", monthly_budget_usd=100.0)
SKILLS = {"fake_lead": "tests.desk.test_harness:FakeSkill",
          "fake_research": "tests.desk.research_support:FakeResearchSkill"}


def job(emp_id: str, name: str, level: str, skill: str, calls: int = 40,
        extra: str = "") -> str:
    return f"""id: {emp_id}
name: {name}
title: Test helper
level: {level}
reports_to: null
skill: {skill}
version: 1
trigger: after_run
models:
  primary: {{source: openrouter, model: or-model}}
  backup: {{source: claude, model: default}}
calls_per_day: {calls}
monthly_cost_usd: 50.0
kpis: [valid answers]
{extra}"""


def employee(home: Path, emp_id: str, name: str, level: str, skill: str,
             extra: str = "") -> None:
    """Write one employee as job.yaml + soul.md and turn it into employee.md."""
    path = home / "employees" / emp_id
    path.mkdir(parents=True, exist_ok=True)
    (path / "job.yaml").write_text(job(emp_id, name, level, skill, extra=extra),
                                   encoding="utf-8")
    (path / "soul.md").write_text("You are {name}.", encoding="utf-8")
    migrate_all(home)


def team(home: Path, lead_level: str = "lead") -> None:
    """A lead (skill fake_lead) and a research doer (skill fake_research)."""
    employee(home, "l-1", "Lead A", lead_level, "fake_lead")
    employee(home, "r-1", "Expert R", "expert", "fake_research")


def ask(kind: str = "setup_tuning", topic: str = "pullback", goal: str = "Test RSI limits 35 40 45",
        cap: int = 8_000) -> TicketAsk:
    return TicketAsk(kind=kind, topic=topic, goal=goal,
                     done_test="Any variant beats the base by 0.05R", token_cap=cap)


def add_try(home: Path, emp: str, tokens: int, part: str | None = "plan", payer: str = "",
            ticket: int | None = None, seconds: float = 1.0, started: str = f"{DAY}T10:00:00-05:00"
            ) -> None:
    rec = Recorder(home)
    try:
        rec.add(Attempt(1, emp, emp, 1, DAY, started, "openrouter", "m", 1, "p", "a", True, "",
                        tokens, 0, 0.0, seconds, 0, 0, part or "plan", payer, ticket))
    finally:
        rec.close()


def rows(home: Path, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def execute(home: Path, sql: str, params: tuple[Any, ...] = ()) -> None:
    con = sqlite3.connect(home / "desk.db")
    try:
        with con:
            con.execute(sql, params)
    finally:
        con.close()


class View(BaseModel):
    word: str


@dataclass
class ResearchState:
    """What the fake research skill returns this test, and what it saw."""

    step_tokens: int = 1_000
    results: list[StepResult | None] = field(default_factory=list)
    seen: list[int] = field(default_factory=list)


STATE = ResearchState()


def reset() -> None:
    global STATE
    STATE = ResearchState()


class FakeResearchSkill:
    """Works setup tuning tickets: one ask per step, then the queued result."""

    key = "fake_research"
    needs: tuple[str, ...] = ()
    answer = View
    kinds: tuple[str, ...] = ("setup_tuning",)

    @property
    def step_tokens(self) -> int:
        return STATE.step_tokens

    def facts(self, home: Path) -> Facts:
        return Facts("", DAY, False, "research only")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        return []

    def step(self, ctx: AgentContext, ticket: Ticket) -> StepResult | None:
        STATE.seen.append(ticket.id)
        view = ctx.ask(f"Work ticket {ticket.id}: {ticket.goal}", View)
        if view is None:
            return None
        if STATE.results:
            return STATE.results.pop(0)
        return StepResult(f"found {len(STATE.seen)}", f"call {len(STATE.seen)}", "go")
