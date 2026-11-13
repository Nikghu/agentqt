"""Tests for MD-DSK-009.021.M31 (desk/memory_cleanup.py): the weekly memory clean-up.

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from us_swing.core import desk_memory
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_msg import Remember
from us_swing.desk.gateway import Reply
from us_swing.desk.memory_cleanup import MemoryCleanupStep
from us_swing.desk.recorder import NY

FRIDAY = datetime(2026, 11, 13, 9, 0, tzinfo=NY)
DAY = "2026-11-12"
_MOD = "tests.desk.test_memory_flow"
SKILLS = {"viewer": f"{_MOD}:ViewerSkill"}
ON = DeskAiSettings(openrouter_on=True, openrouter_model="m", memory_v2_on=True)


class Caller:
    """Answers every clean-up call with the given actions."""

    def __init__(self, actions: list[dict[str, Any]]) -> None:
        self.actions = actions
        self.calls: list[str] = []

    def __call__(self, source: str, model: str, system: str, user: str, key: str) -> Reply:
        self.calls.append(user)
        return Reply(json.dumps({"actions": self.actions}), 100, 20, 0.0)


def _team(home: Path) -> None:
    folder = home / "employees" / "emp-v"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "employee.md").write_text("""---
id: emp-v
name: Viewer
title: Test helper
level: expert
reports_to: null
skill: viewer
version: 1
trigger: after_run
models:
  primary: {source: openrouter, model: m}
  backup: {source: claude, model: default}
calls_per_day: 20
monthly_cost_usd: 3.0
kpis: [valid answers]
---
You are Viewer.
""", encoding="utf-8")


def _notes(home: Path, owner: str, texts: list[str]) -> None:
    desk_memory.write(home, owner, [Remember(kind="note", text=t) for t in texts], DAY, FRIDAY)


def _run(home: Path, caller: Caller, when: datetime = FRIDAY) -> None:
    step = MemoryCleanupStep(lambda: SKILLS, lambda: ON, lambda: "key", caller, lambda: when)
    step(StepContext(1, "manual", when, home))


def _status(home: Path) -> list[Any]:
    con = desk_memory.connect(home)
    try:
        return con.execute("SELECT id, status, text, right FROM memories ORDER BY id").fetchall()
    finally:
        con.close()


def test_weekly_cleanup(home: Path) -> None:
    """UT-DSK-009.021.M31.T01: One call; merge and retire applied; counts added."""
    _team(home)
    _notes(home, "emp-v", ["First words here", "Second other text", "Third more stuff"])
    con = desk_memory.connect(home)
    with con:
        con.execute("UPDATE memories SET right = 2 WHERE id = 1")
    con.close()
    caller = Caller([{"id": 1, "do": "merge", "into": 2, "text": "Joined"},
                     {"id": 3, "do": "retire"}])
    _run(home, caller)
    assert len(caller.calls) == 1 and "N-1 (2 right, 0 wrong, active)" in caller.calls[0]
    assert _status(home) == [(1, "retired", "First words here", 2), (2, "active", "Joined", 2),
                             (3, "retired", "Third more stuff", 0)]


def test_once_a_week(home: Path) -> None:
    """UT-DSK-009.021.M31.T02: A second run the same week makes no call."""
    _team(home)
    _notes(home, "emp-v", ["A note"])
    caller = Caller([])
    _run(home, caller)
    _run(home, caller, FRIDAY.replace(day=16))
    assert len(caller.calls) == 1


def test_bad_actions(home: Path) -> None:
    """UT-DSK-009.021.M31.T03: Another owner's note and a pinned note are left alone."""
    _team(home)
    _notes(home, "emp-v", ["Mine words", "Pinned words here"])
    _notes(home, "emp-other", ["Not mine text"])
    con = desk_memory.connect(home)
    with con:
        con.execute("UPDATE memories SET pinned = 1 WHERE id = 2")
    con.close()
    _run(home, Caller([{"id": 2, "do": "retire"}, {"id": 3, "do": "retire"}]))
    assert [s for _i, s, _t, _r in _status(home)] == ["active", "active", "active"]


def test_no_notes_no_call(home: Path) -> None:
    """UT-DSK-009.021.M31.T04: An expert without notes gets no call."""
    _team(home)
    caller = Caller([])
    _run(home, caller)
    assert caller.calls == []
