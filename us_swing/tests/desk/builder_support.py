"""Shared helpers for the tool builder (AI Desk v3 M7b) tests: settings, answers, versions, a
talking context and small Backtest Data files.

Stock and employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import BaseModel

from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.core.desk_built_tools import (
    CHECKS,
    MADE_UP,
    BuiltTool,
    Check,
    ToolAnswer,
    ToolColumn,
    get_built,
    save_version,
    set_checks,
)
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_messages import Person, accept
from us_swing.core.desk_msg import Draft, Want
from us_swing.desk.sandbox import RunResult

T = TypeVar("T", bound=BaseModel)
NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 16, 9, 0, tzinfo=NY)
DAY = "2026-11-16"
SETTINGS = DeskAiSettings(claude_on=True, claude_model="c", messages_on=True, sessions_on=True,
                          task_cards_on=True, tool_builder_on=True)
NAME = "below_high_pct"
GOOD_CODE = '''"""Percent below the 52-week high."""
DAYS = 252


def high_of(bars):
    return max(b["high"] for b in bars)


def tool(symbol):
    bars = daily_bars(symbol, DAYS)
    if len(bars) < 20:
        raise ValueError("fewer than 20 daily bars")
    top = high_of(bars)
    return {"below_high": round((top - bars[-1]["close"]) / top * 100, 2)}
'''
COLUMNS = [ToolColumn(name="below_high", type="number", meaning="percent below the 52-week high")]


ASKER = "emp-a"
BUILDER = "emp-b"
ROSTER = [Person(ASKER, "Quill", "lead_chat"), Person(BUILDER, "Forge", "tool_builder")]
SOUL = "You are {name}, {title}."


def job(emp_id: str, name: str, skill: str, level: str, trigger: str) -> str:
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
  primary: {{source: claude, model: c}}
  backup: {{source: openrouter, model: m}}
calls_per_day: 20
monthly_cost_usd: 3.0
kpis: [valid answers]
"""


def team(home: Path) -> None:
    """Write a made-up chat lead and a made-up tool builder as employee folders."""
    for emp_id, name, skill, level, trigger in (
            (ASKER, "Quill", "lead_chat", "lead", "chat_question"),
            (BUILDER, "Forge", "tool_builder", "champion", "[tool_request, message]")):
        folder = home / "employees" / emp_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "job.yaml").write_text(job(emp_id, name, skill, level, trigger),
                                         encoding="utf-8")
        (folder / "soul.md").write_text(SOUL, encoding="utf-8")


def ask(home: Path, inputs: dict[str, Any] | None = None, goal: str = "Build a tool",
        text: str | None = None) -> int:
    """Store one ask from the chat lead to the builder; ``inputs`` None sends no want."""
    want = (Want(goal=goal, done_when="the tool waits for review", inputs=inputs)
            if inputs is not None else None)
    draft = Draft(type="ask", to="skill:tool_builder", subject="New tool", text=text, want=want)
    out = accept(home, [draft], ASKER, ROSTER, NOW, DAY)
    assert out[0].startswith("stored"), out
    return int(out[0].split("#")[1])


def on(home: Path, **change: Any) -> None:
    """Save the test settings, tool builder on unless changed."""
    save_settings(replace(SETTINGS, **change), home)


def answer(name: str = NAME, code: str = GOOD_CODE, columns: Sequence[ToolColumn] | None = None,
           **more: Any) -> ToolAnswer:
    """A builder answer with a title and an about."""
    return ToolAnswer(name=name, title="Below the 52-week high",
                      about="How far the last close is below the 252-day high.",
                      columns=list(COLUMNS if columns is None else columns), code=code, **more)


def ok_checks() -> list[Check]:
    """The 5 checks, all passed."""
    return [Check(check=c, ok=True) for c in CHECKS]


def version(home: Path, name: str = NAME, code: str = GOOD_CODE, ok: bool = True,
            request: int | None = None,
            columns: Sequence[ToolColumn] | None = None) -> BuiltTool:
    """Save one version with its checks: all passed, or a failed "Full row"."""
    tool = save_version(home, request, answer(name, code, columns), NOW)
    checks = ok_checks()
    if not ok:
        checks[2] = Check(check=CHECKS[2], ok=False, note="no stock got every column")
    set_checks(home, tool.id, checks, ["ZZA: below_high 3.2"])
    saved = get_built(home, tool.id)
    assert saved is not None
    return saved


def rows(home: Path, sql: str, args: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
    """Rows of a query on the desk database; a write is committed."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME)
    try:
        with con:
            return con.execute(sql, args).fetchall()
    finally:
        con.close()


def daily_file(root: Path, symbol: str, days: int = 60) -> None:
    """Write ``days`` rising daily bars for ``symbol`` under ``root/1d``."""
    start = datetime(2026, 1, 1)
    frame = pd.DataFrame({"ts": [start + timedelta(days=i) for i in range(days)],
                          "open": [100.0 + i for i in range(days)],
                          "high": [101.0 + i for i in range(days)],
                          "low": [99.0 + i for i in range(days)],
                          "close": [100.5 + i for i in range(days)],
                          "volume": [1e6] * days})
    (root / "1d").mkdir(parents=True, exist_ok=True)
    frame.to_parquet(root / "1d" / f"{symbol}.parquet")


def stocks(home: Path, symbols: Sequence[str] = ("ZZA", "ZZB")) -> None:
    """A latest ``stock_rs`` day holding ``symbols``, so a request without stocks has samples."""
    rows(home, "CREATE TABLE IF NOT EXISTS stock_rs (date TEXT, symbol TEXT, rs_rating INTEGER)")
    for n, symbol in enumerate(symbols):
        rows(home, "INSERT INTO stock_rs VALUES (?, ?, ?)", (DAY, symbol, 90 - n))


class Runs:
    """A stand-in for the sandbox: every stock gets 1.5 in each column and the made-up stock a
    ValueError reason, unless the code holds a marker that asks for a problem."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def __call__(self, home: Path, code: str, columns: Sequence[ToolColumn],
                 symbols: Sequence[str], backtest: Path | None = None) -> RunResult:
        self.calls.append((code, tuple(symbols)))
        real = [s for s in symbols if s != MADE_UP]
        if "# crash" in code:
            return RunResult(rows=tuple({"symbol": s, **{c.name: 1.5 for c in columns}}
                                        for s in real),
                             missing={MADE_UP: "error: IndexError: list index out of range"},
                             crashed=(MADE_UP,))
        if "# wrong" in code:
            first = f"{real[0]}.{columns[0].name}"
            return RunResult(missing={first: "wrong value", MADE_UP: "no data"}, wrong=(first,))
        if "# hang" in code:
            return RunResult(error="took longer than 60 s")
        if "# slow" in code:
            first, rest = real[:1], [*real[1:], MADE_UP]
            return RunResult(rows=tuple({"symbol": s, **{c.name: 1.5 for c in columns}}
                                        for s in first),
                             missing=dict.fromkeys(rest, "not run: the time limit was reached"),
                             cut=tuple(rest))
        return RunResult(rows=tuple({"symbol": s, **{c.name: 1.5 for c in columns}}
                                    for s in real),
                         missing={MADE_UP: "fewer than 20 daily bars"})


class Ctx:
    """A talking context: hands out the queued answers in order and keeps what it was asked."""

    talk = True

    def __init__(self, home: Path, answers: Sequence[ToolAnswer | None] = (),
                 drafts_per_ask: Sequence[Draft] = ()) -> None:
        self.home = home
        self.drafts: list[Draft] = []
        self.answers = list(answers)
        self.texts: list[str] = []
        self._extra = list(drafts_per_ask)

    @property
    def asked(self) -> int:
        """How often the model was asked."""
        return len(self.texts)

    def ask(self, facts: str, schema: type[T]) -> T | None:
        """The next queued answer; like the gateway, a talking answer may add drafts."""
        self.texts.append(facts)
        self.drafts.extend(self._extra)
        found = self.answers.pop(0) if self.answers else None
        return found if found is None or isinstance(found, schema) else None

    def send(self, draft: Draft) -> None:
        """Keep one draft to send."""
        self.drafts.append(draft)


# ── test children for the sandbox (SRD-DSK-013.010): module level, so spawn can load them ──


def child_big(conn: Connection, job: bytes) -> None:
    """Send 2 MB."""
    conn.send_bytes(b"x" * 2_000_000)
    conn.close()


def child_silent(conn: Connection, job: bytes) -> None:
    """End without sending."""
    conn.close()


def child_pickle(conn: Connection, job: bytes) -> None:
    """Send a pickled object instead of JSON."""
    conn.send({"rows": []})
    conn.close()
