"""Tests for the AI Desk v3 M3 wake flow in MD-DSK-003.001.M10 (desk/employees_step.py): the
remember field for lead and expert employees, core block and recall in the facts, notes kept
after the answer, and nothing while Memory v2 is off.

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from us_swing.core import desk_memory
from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_msg import Remember
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.desk.recorder import NY

NOW = datetime(2026, 11, 6, 9, 20, tzinfo=NY)
DAY = "2026-11-06"
_MOD = "tests.desk.test_memory_flow"
SKILLS = {"viewer": f"{_MOD}:ViewerSkill"}
ON = DeskAiSettings(openrouter_on=True, openrouter_model="m", memory_v2_on=True)
OFF = DeskAiSettings(openrouter_on=True, openrouter_model="m")


class View(BaseModel):
    """Answer of the fake skill."""

    word: str


class ViewerSkill:
    """Names NVDA in its facts and asks once."""

    key = "viewer"
    needs: tuple[str, ...] = ()
    answer = View

    def facts(self, home: Path) -> Facts:
        return Facts("Ideas today: NVDA long at 140", DAY, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        ctx.ask(facts.text, View)
        return []


class Caller:
    """Answers with one view when the schema allows it; records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, source: str, model: str, system: str, user: str, key: str) -> Reply:
        self.calls.append((system, user))
        body: dict[str, Any] = {"word": "ok"}
        if '"remember"' in system:
            body["remember"] = [{"kind": "view", "text": "Semis strong", "symbol": "NVDA",
                                 "direction": "up"}]
        return Reply(json.dumps(body), 100, 20, 0.0)


def _team(home: Path, level: str, status: str = "active") -> None:
    folder = home / "employees" / "emp-v"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "employee.md").write_text(f"""---
id: emp-v
name: Viewer
title: Test helper
level: {level}
status: {status}
reports_to: null
skill: viewer
version: 1
trigger: after_run
models:
  primary: {{source: openrouter, model: m}}
  backup: {{source: claude, model: default}}
calls_per_day: 20
monthly_cost_usd: 3.0
kpis: [valid answers]
---
You are Viewer.
""", encoding="utf-8")


def _run(home: Path, caller: Caller, settings: DeskAiSettings) -> None:
    step = EmployeesStep(lambda: SKILLS, lambda: [], lambda: settings, lambda: "key", caller,
                         lambda: NOW, send=lambda text: True)
    step(StepContext(1, "manual", NOW, home))


def _kept(home: Path) -> list[Any]:
    if not (home / "memory.db").exists():
        return []
    con = desk_memory.connect(home)
    try:
        return con.execute("SELECT owner, kind, symbol, direction FROM memories").fetchall()
    finally:
        con.close()


def test_lead_or_expert_only(home: Path) -> None:
    """UT-DSK-009.013.M10.T01: An expert's schema has remember; a champion's has not."""
    _team(home, "expert")
    caller = Caller()
    _run(home, caller, ON)
    assert '"remember"' in caller.calls[0][0]
    assert _kept(home) == [("emp-v", "view", "NVDA", "up")]
    other = home.parent / "other"
    _team(other, "champion")
    caller = Caller()
    _run(other, caller, ON)
    assert '"remember"' not in caller.calls[0][0] and _kept(other) == []


def test_blocks_in_wake(home: Path) -> None:
    """UT-DSK-009.017.M10.T01: The facts sent to the model hold core block and recall."""
    _team(home, "lead")
    desk_memory.write(home, "emp-v", [
        Remember(kind="note", text="Semis lead the tape", symbol="NVDA"),
        Remember(kind="view", text="old call", symbol="AMD", direction="down")],
        "2026-11-05", NOW)
    caller = Caller()
    _run(home, caller, ON)
    user = caller.calls[0][1]
    assert desk_memory.CORE_HEADER in user and "AMD down" in user
    assert desk_memory.RECALL_HEADER in user and "Semis lead the tape" in user


def test_shadow_wake(home: Path) -> None:
    """UT-DSK-009.017.M10.T02: A shadow wake gets no blocks and writes nothing."""
    _team(home, "expert", "shadow")
    desk_memory.write(home, "emp-v", [Remember(kind="note", text="Semis lead", symbol="NVDA")],
                      "2026-11-05", NOW)
    caller = Caller()
    _run(home, caller, ON)
    assert all(desk_memory.CORE_HEADER not in u and desk_memory.RECALL_HEADER not in u
               for _s, u in caller.calls)
    assert [k[1] for k in _kept(home)] == ["note"]


def test_off_means_m2(home: Path) -> None:
    """UT-DSK-009.023.M10.T01: With Memory v2 off facts and schema are as before."""
    _team(home, "expert")
    desk_memory.write(home, "emp-v", [Remember(kind="note", text="Semis lead", symbol="NVDA")],
                      "2026-11-05", NOW)
    caller = Caller()
    _run(home, caller, OFF)
    system, user = caller.calls[0]
    assert '"remember"' not in system and re.sub(r"\s+", " ", user).strip().startswith(
        "Ideas today: NVDA long at 140")
    assert desk_memory.CORE_HEADER not in user
    assert [k[1] for k in _kept(home)] == ["note"]
