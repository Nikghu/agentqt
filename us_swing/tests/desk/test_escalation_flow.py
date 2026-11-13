"""Tests for the AI Desk v3 M2 wake flow in MD-DSK-003.001.M10 (desk/employees_step.py): the
boss's reply-only turn, the reply as a feed note and the deputy before a refusal.

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem, Talker
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_msg import Draft, InboxReply
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.desk.recorder import NY

NOW = datetime(2026, 11, 6, 11, 20, tzinfo=NY)
DAY = "2026-11-06"
SOUL = "You are {name}, {title}."
_MOD = "tests.desk.test_escalation_flow"
SKILLS = {"flagger": f"{_MOD}:FlaggerSkill", "bosser": f"{_MOD}:BosserSkill",
          "asker": f"{_MOD}:AskerSkill", "sleeper": f"{_MOD}:SleeperSkill",
          "answerer": f"{_MOD}:AnswererSkill"}
ON = DeskAiSettings(openrouter_on=True, openrouter_model="m", claude_on=True,
                    claude_model="c", messages_on=True, escalation_on=True)


class View(BaseModel):
    """Answer of the fake skills."""

    word: str


@dataclass
class World:
    """What the fake skills saw this test."""

    woke: list[tuple[str, tuple[int, ...]]] = field(default_factory=list)


W = World()


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    global W
    W = World()
    yield


class _Base:
    key = ""
    needs: tuple[str, ...] = ()
    answer = View
    talks = True
    fresh = True

    def facts(self, home: Path) -> Facts:
        return Facts(f"facts of {self.key}", DAY, self.fresh, "" if self.fresh else "data old")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        W.woke.append((self.key, facts.inbox))
        if facts.inbox:
            ctx.ask(facts.text, InboxReply)
        else:
            ctx.ask(facts.text, View)
        return []


class FlaggerSkill(_Base):
    """Code sends one escalation to the boss, like the watch flag."""

    key = "flagger"

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        W.woke.append((self.key, facts.inbox))
        if isinstance(ctx, Talker) and not facts.inbox:
            ctx.send(Draft(type="escalate", to="boss", subject="AAPL plan broken",
                           text="AAPL touched its stop at 174.90", about=["AAPL"]))
        return []


class BosserSkill(_Base):
    """The boss; its own skill must not run for an escalation."""

    key = "bosser"


class AskerSkill(_Base):
    """Asks emp-b on its normal wake (the caller writes the ask)."""

    key = "asker"


class SleeperSkill(_Base):
    """Never has fresh data."""

    key = "sleeper"
    fresh = False


class AnswererSkill(_Base):
    """Answers its inbox."""

    key = "answerer"


class Caller:
    """Answers by prompt content; records every call."""

    def __init__(self, extra_ask: bool = False) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.extra_ask = extra_ask

    def __call__(self, source: str, model: str, system: str, user: str, key: str) -> Reply:
        who = re.search(r"You are (\w+)", system)
        name = who.group(1) if who else "?"
        self.calls.append((name, system, user))
        body: dict[str, Any]
        if "Problems raised to you" in user:
            parent = int(re.search(r"#(\d+) escalate from", user).group(1))  # type: ignore[union-attr]
            msgs: list[dict[str, Any]] = [
                {"type": "reply", "parent": parent, "text": "Take AAPL off today",
                 "verdict": {"result": "dropped", "reason": "stop hit"}}]
            if self.extra_ask:
                msgs.append({"type": "ask", "to": "emp-a", "subject": "Q", "text": "Why?"})
            body = {"messages": msgs}
        elif "INBOX" in user and "ask from" in user:
            parent = int(re.search(r"#(\d+) ask from", user).group(1))  # type: ignore[union-attr]
            body = {"messages": [{"type": "reply", "parent": parent, "text": "No news",
                                  "verdict": {"result": "done"}}]}
        elif name == "Asker" and "INBOX" not in user:
            body = {"word": "x", "messages": [{"type": "ask", "to": "emp-b", "subject": "Q",
                                               "text": "Any news for NVDA?"}]}
        else:
            body = {"word": "ok"}
        return Reply(json.dumps(body), 100, 20, 0.0)


def _job(emp_id: str, name: str, skill: str, boss: str | None, deputy: str | None) -> str:
    extra = f"deputy: {deputy}\n" if deputy else ""
    return f"""---
id: {emp_id}
name: {name}
title: Test helper
level: expert
reports_to: {boss or "null"}
{extra}skill: {skill}
version: 1
trigger: after_run
models:
  primary: {{source: openrouter, model: m}}
  backup: {{source: claude, model: default}}
calls_per_day: 20
monthly_cost_usd: 3.0
kpis: [valid answers]
---
{SOUL}
"""


def _team(home: Path, people: list[tuple[str, str, str, str | None, str | None]]) -> None:
    for emp_id, name, skill, boss, deputy in people:
        folder = home / "employees" / emp_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "employee.md").write_text(_job(emp_id, name, skill, boss, deputy),
                                            encoding="utf-8")


def _run(home: Path, caller: Caller, settings: DeskAiSettings = ON) -> None:
    step = EmployeesStep(lambda: SKILLS, lambda: [], lambda: settings, lambda: "key", caller,
                         lambda: NOW, send=lambda text: True)
    step(StepContext(1, "manual", NOW, home))


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "desk"


BOSS_TEAM = [("emp-a", "Flagger", "flagger", "emp-b", None),
             ("emp-b", "Bosser", "bosser", None, None)]
DEPUTY_TEAM = [("emp-a", "Asker", "asker", None, None),
               ("emp-b", "Sleeper", "sleeper", None, "emp-c"),
               ("emp-c", "Answerer", "answerer", None, None)]


def test_reply_only_turn(home: Path) -> None:
    """UT-DSK-011.039.M10.T01: Reply-only turn."""
    _team(home, BOSS_TEAM)
    caller = Caller()
    _run(home, caller)
    assert not [box for key, box in W.woke if key == "bosser" and box]  # own skill not run
    boss_calls = [c for c in caller.calls if "Problems raised to you" in c[2]]
    assert len(boss_calls) == 1 and boss_calls[0][0] == "Bosser"
    assert '"messages"' in boss_calls[0][1]  # the InboxReply schema
    assert _rows(home, "SELECT type, sender, receiver, state FROM messages ORDER BY id") == [
        ("escalate", "emp-a", "emp-b", "failed"), ("reply", "emp-b", "emp-a", "completed")]


def test_only_replies_kept(home: Path) -> None:
    """UT-DSK-011.039.M10.T02: Only replies kept."""
    _team(home, BOSS_TEAM)
    _run(home, Caller(extra_ask=True))
    assert [r[0] for r in _rows(home, "SELECT type FROM messages ORDER BY id")] == [
        "escalate", "reply"]


def test_reply_as_feed_note(home: Path) -> None:
    """UT-DSK-011.040.M10.T01: Reply as feed note."""
    _team(home, BOSS_TEAM)
    _run(home, Caller())
    assert ("emp-b", "AAPL plan broken: Take AAPL off today") in _rows(
        home, "SELECT employee_id, text FROM briefs")
    assert not [box for key, box in W.woke if key == "flagger" and box]  # sender not woken


def test_sleeping_receiver_to_deputy(home: Path) -> None:
    """UT-DSK-011.041.M10.T01: Sleeping receiver to deputy."""
    _team(home, DEPUTY_TEAM)
    _run(home, Caller())
    assert [box for key, box in W.woke if key == "answerer" and box] == [(1,)]
    assert _rows(home, "SELECT type, sender, receiver, state, handed FROM messages "
                       "ORDER BY id") == [
        ("ask", "emp-a", "emp-c", "completed", "emp-b"),
        ("reply", "emp-c", "emp-a", "completed", None)]


def test_off_keeps_m1_refusal(home: Path) -> None:
    """UT-DSK-011.042.M10.T01: Off keeps M1 refusal."""
    _team(home, DEPUTY_TEAM)
    _run(home, Caller(), replace(ON, escalation_on=False))
    assert not [box for key, box in W.woke if key == "answerer" and box]
    assert _rows(home, "SELECT type, receiver, state, handed FROM messages ORDER BY id") == [
        ("ask", "emp-b", "refused", None), ("reply", "emp-a", "completed", None)]
