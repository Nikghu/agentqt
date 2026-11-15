"""Shared helpers for the task card (AI Desk v3 M6) tests: fake table tools and a small desk.

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from us_swing.core import desk_steps
from us_swing.core.desk_agents import Facts
from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.core.desk_messages import Person, accept
from us_swing.core.desk_msg import Draft, Want
from us_swing.core.desk_registry import ToolResult, fill_registry
from us_swing.core.desk_tasks import fill_plans
from us_swing.desk.planner import TaskPlannerSkill

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 13, 9, 0, tzinfo=NY)
DAY = "2026-11-13"
ASKER = "emp-a"
PLANNER = "emp-p"
FORMAT = "setup_table.v1"
SIX = ["AVGO", "MU", "AMAT", "LRCX", "KLAC", "NVDA"]
ROSTER = [Person(ASKER, "Quill", "asker"), Person(PLANNER, "Maker", "task_planner")]
SETTINGS = DeskAiSettings(openrouter_on=True, openrouter_model="m", claude_on=True,
                          claude_model="c", messages_on=True, sessions_on=True,
                          task_cards_on=True)
SOUL = "You are {name}, {title}."
TIMED_OUT = "connection timed out"


@dataclass
class World:
    """What the fake tools do and saw in one test."""

    known: set[str] = field(default_factory=lambda: set(SIX))
    raises: dict[str, int] = field(default_factory=dict)
    error: dict[str, str] = field(default_factory=dict)
    wrong: set[str] = field(default_factory=set)
    no_earnings: set[str] = field(default_factory=set)
    near: dict[str, int] = field(default_factory=dict)
    calls: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def called(self, tool: str) -> list[tuple[str, ...]]:
        """The symbol lists ``tool`` was called with, in order."""
        return [symbols for name, symbols in self.calls if name == tool]


W = World()


def _enter(tool: str, symbols: Sequence[str]) -> ToolResult | None:
    with W.lock:
        W.calls.append((tool, tuple(symbols)))
        left = W.raises.get(tool, 0)
        if left:
            W.raises[tool] = left - 1
    if left:
        raise RuntimeError(TIMED_OUT)
    if tool in W.error:
        return ToolResult(isError=True, error=W.error[tool])
    return None


def fake_close(home: Path, symbols: Sequence[str]) -> ToolResult:
    """Fake last close."""
    early = _enter("data.daily_close", symbols)
    if early is not None:
        return early
    return ToolResult(
        rows=[{"symbol": s, "close": 100.0 + n} for n, s in enumerate(symbols) if s in W.known],
        missing={s: "no daily bars" for s in symbols if s not in W.known})


def fake_rs(home: Path, symbols: Sequence[str]) -> ToolResult:
    """Fake RS rank."""
    early = _enter("technical.rs_rank", symbols)
    if early is not None:
        return early
    bad = "technical.rs_rank" in W.wrong
    return ToolResult(rows=[{"symbol": s, "rs_rank": "high" if bad else 80 + n}
                            for n, s in enumerate(symbols)])


def fake_atr(home: Path, symbols: Sequence[str]) -> ToolResult:
    """Fake ATR percent."""
    early = _enter("technical.atr_pct", symbols)
    if early is not None:
        return early
    return ToolResult(rows=[{"symbol": s, "atr_pct": 2.5} for s in symbols])


def fake_setup(home: Path, symbols: Sequence[str]) -> ToolResult:
    """Fake setup."""
    early = _enter("technical.setup", symbols)
    if early is not None:
        return early
    return ToolResult(rows=[{"symbol": s, "side": "long", "setup": "flag", "trigger": 10.0,
                             "stop": 9.0} for s in symbols])


def fake_earn(home: Path, symbols: Sequence[str]) -> ToolResult:
    """Fake earnings days."""
    early = _enter("calendar.earnings", symbols)
    if early is not None:
        return early
    dated = [s for s in symbols if s not in W.no_earnings]
    return ToolResult(
        rows=[{"symbol": s, "earn_days": W.near.get(s, 12)} for s in dated],
        missing={s: "no earnings date found" for s in symbols if s in W.no_earnings},
        flags={s: f"earnings in {W.near[s]} trading days" for s in dated if s in W.near})


_HERE = "tests.desk.task_support"
PATHS: dict[str, tuple[str, int]] = {
    "data.daily_close": (f"{_HERE}:fake_close", 20),
    "technical.rs_rank": (f"{_HERE}:fake_rs", 10),
    "technical.atr_pct": (f"{_HERE}:fake_atr", 20),
    "technical.setup": (f"{_HERE}:fake_setup", 10),
    "calendar.earnings": (f"{_HERE}:fake_earn", 30),
}


def job(emp_id: str, name: str, skill: str, level: str = "expert",
        trigger: str = "after_run") -> str:
    """Job text of one made-up employee."""
    return f"""id: {emp_id}
name: {name}
title: Test helper
level: {level}
reports_to: null
skill: {skill}
version: 1
trigger: {trigger}
models:
  primary: {{source: openrouter, model: m}}
  backup: {{source: claude, model: default}}
calls_per_day: 20
monthly_cost_usd: 3.0
kpis: [valid answers]
"""


def team(home: Path) -> None:
    """Write the asker and the planner as employee folders."""
    for emp_id, name, skill, level, trigger in (
            (ASKER, "Quill", "asker", "expert", "after_run"),
            (PLANNER, "Maker", "task_planner", "champion", "message")):
        folder = home / "employees" / emp_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "job.yaml").write_text(job(emp_id, name, skill, level, trigger),
                                         encoding="utf-8")
        (folder / "soul.md").write_text(SOUL, encoding="utf-8")


def prepare(home: Path, monkeypatch: pytest.MonkeyPatch, on: bool = True,
            paths: dict[str, tuple[str, int]] | None = None) -> None:
    """A desk folder with the fake tools in the registry, the plans, settings and a team."""
    global W
    W = World()
    monkeypatch.setattr(desk_steps, "TOOL_PATHS", dict(paths or PATHS))
    fill_registry(home, NOW)
    fill_plans(home, NOW)
    save_settings(SETTINGS if on else DeskAiSettings(messages_on=True), home)
    team(home)


def ask(home: Path, symbols: Any = None, schema: str | None = FORMAT,
        cols: list[str] | None = None, want: bool = True) -> int:
    """Store one ask from the asker to the planner and return its message id."""
    wanted = Want(goal="table", done_when="table sent",
                  inputs={"symbols": SIX if symbols is None else symbols}, schema=schema,
                  cols=cols) if want else None
    draft = Draft(type="ask", to="skill:task_planner", subject="Table please", want=wanted,
                  text=None if want else "Any table?")
    out = accept(home, [draft], ASKER, ROSTER, NOW, DAY)
    assert out[0].startswith("stored"), out
    return int(out[0].split("#")[1])


class Ctx:
    """A talking context for the planner; it counts how often the model is asked."""

    talk = True

    def __init__(self, home: Path) -> None:
        self.home = home
        self.drafts: list[Draft] = []
        self.asked = 0

    def send(self, draft: Draft) -> None:
        self.drafts.append(draft)

    def ask(self, facts: str, schema: type) -> None:
        self.asked += 1


def planner(sent: list[str] | None = None,
            clock: Callable[[], datetime] = lambda: NOW) -> TaskPlannerSkill:
    """The planner skill with a fixed clock and an alert sender that only records."""
    box = sent if sent is not None else []

    def send(text: str) -> bool:
        box.append(text)
        return True

    return TaskPlannerSkill(clock=clock, send=send)


def act(home: Path, *message_ids: int, sent: list[str] | None = None) -> Ctx:
    """Wake the planner for ``message_ids`` and return its context with the reply drafts."""
    ctx = Ctx(home)
    planner(sent).act(ctx, Facts("", DAY, True, inbox=tuple(message_ids)))
    return ctx


def answer(home: Path, sent: list[str] | None = None, **kwargs: Any) -> Draft:
    """Store one ask, wake the planner and return its single reply draft."""
    ctx = act(home, ask(home, **kwargs), sent=sent)
    assert len(ctx.drafts) == 1
    return ctx.drafts[0]

