"""Tests for AI Desk v3 M5 day-end: MD-MKT-020.019.M07, .020.M08, .023.M09, .018.M10."""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from tests.market.p5b_support import FakeCtx
from us_swing.core import desk_memory
from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.core.desk_day import (
    connect,
    day_end_day,
    has_handover,
    plan_day,
    save_call,
    save_day_end,
    save_standup,
)
from us_swing.core.desk_events import EVENT_RULES
from us_swing.core.desk_steps import SKILL_PATHS, STEP_PATHS, load_steps
from us_swing.core.desk_team import _EVENT_NAMES
from us_swing.core.desk_watch import SCHEMA as WATCH_SCHEMA
from us_swing.desk import employees_step
from us_swing.desk.process import DeskProcess
from us_swing.desk.registry import default_folders, seed_employees
from us_swing.market.day_end import DayEnd, DayEndSkill
from us_swing.market.store import MarketStore

NY = ZoneInfo("America/New_York")
PLAN = "2026-11-12"
TRADED = "2026-11-13"
AFTER_CLOSE = datetime(2026, 11, 13, 16, 30, tzinfo=NY)


def _sql(home: Path, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        with con:
            return con.execute(sql, params).fetchall()
    finally:
        con.close()


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "desk"
    path.mkdir()
    MarketStore(path).close()
    con = sqlite3.connect(path / "desk.db")
    con.executescript(WATCH_SCHEMA)
    con.execute("CREATE TABLE IF NOT EXISTS roster (id TEXT PRIMARY KEY, name TEXT, title TEXT, "
                "level TEXT, reports_to TEXT, skill TEXT, version INTEGER, hash TEXT, "
                "loaded_at TEXT)")
    con.execute("INSERT INTO roster (id, name, skill) VALUES ('emp-x', 'Xi', 'setup_review')")
    con.commit()
    con.close()
    save_standup(path, PLAN, "Stand-up", datetime(2026, 11, 13, 8, tzinfo=NY))
    return path


def _day(home: Path) -> None:
    _sql(home, "INSERT INTO regime_view (date, regime) VALUES (?, 'Uptrend')", (PLAN,))
    save_call(home, PLAN, "Uptrend", ["Energy"], "Lean long", "2026-11-19", AFTER_CLOSE)
    _sql(home, "INSERT INTO lead_picks VALUES (?, 'long', 'NVDA', 1, 'r')", (PLAN,))
    _sql(home, "INSERT INTO lead_picks VALUES (?, 'long', 'AMD', 2, 'r')", (PLAN,))
    _sql(home, "INSERT INTO pick_results (date, side, symbol, status) VALUES "
         "(?, 'long', 'NVDA', 'open')", (PLAN,))
    _sql(home, "INSERT INTO watch_flags (day, hour, kind, symbol, verdict) VALUES "
         "(?, 10, 'trigger_hit', 'NVDA', 'holds')", (TRADED,))
    _sql(home, "INSERT INTO briefs (created, data_day, author, kind, text) VALUES "
         "('2026-11-13T12:30:00-05:00', ?, 'W', 'info', 'Check-in 12:30: plan holds')", (PLAN,))
    _sql(home, "INSERT INTO open_trades (symbol) VALUES ('NVDA')")


def _skill() -> DayEndSkill:
    return DayEndSkill(clock=lambda: AFTER_CLOSE)


def _answer(lines: list[str] | None = None, feedback: list[dict[str, str]] | None = None
            ) -> DayEnd:
    return DayEnd.model_validate({"handover": lines or ["NVDA in trade, stop 136",
                                                         "AMD did not trigger"],
                                  "feedback": feedback or []})


# ── M07: day_end event ───────────────────────────────────────────────────────


def test_day_end_day() -> None:
    """UT-MKT-020.019.M07.T01: After 16:00 today; before it or on a weekend the day before."""
    assert day_end_day(datetime(2026, 11, 13, 16, 5, tzinfo=NY)) == "2026-11-13"
    assert day_end_day(datetime(2026, 11, 16, 15, 0, tzinfo=NY)) == "2026-11-13"
    assert day_end_day(datetime(2026, 11, 14, 10, 0, tzinfo=NY)) == "2026-11-13"


def test_event_kind() -> None:
    """UT-MKT-020.019.M07.T02: day_end has priority 2, a 12-hour expiry and a label."""
    rule = EVENT_RULES["day_end"]
    assert (rule.priority, rule.expiry.total_seconds()) == (2, 12 * 3600)
    assert _EVENT_NAMES["day_end"] == "Day-end"


@dataclass
class _Tick:
    """Just enough of a desk process to run its day-end tick."""

    _home: Path
    _posted: set[tuple[str, str, int]]


def _tick(home: Path, posted: set[tuple[str, str, int]]) -> None:
    DeskProcess._day_end_tick(_Tick(home, posted), AFTER_CLOSE)  # type: ignore[arg-type]


def _events(home: Path) -> list[Any]:
    return _sql(home, "SELECT kind, data_day FROM events WHERE kind = 'day_end'")


def test_posted_once(home: Path) -> None:
    """UT-MKT-020.019.M07.T03: With the day on and no handover, one event over two ticks."""
    save_settings(DeskAiSettings(company_day_on=True), home)
    posted: set[tuple[str, str, int]] = set()
    _tick(home, posted)
    _tick(home, posted)
    assert _events(home) == [("day_end", TRADED)]
    assert plan_day(home, TRADED) == PLAN


def test_not_posted(home: Path) -> None:
    """UT-MKT-020.019.M07.T04: Not posted with a handover, nor with the day off."""
    save_settings(DeskAiSettings(company_day_on=True), home)
    save_day_end(home, PLAN, ["done"], [], "s", AFTER_CLOSE)
    _tick(home, set())
    save_settings(DeskAiSettings(company_day_on=False), home)
    _sql(home, "UPDATE day_brief SET handover = ''")
    _tick(home, set())
    assert _sql(home, "SELECT name FROM sqlite_master WHERE name = 'events'") == [] or \
        _events(home) == []


# ── M08: day-end skill ───────────────────────────────────────────────────────


def test_day_end_facts(home: Path) -> None:
    """UT-MKT-020.020.M08.T01: Facts hold the call, picks, flags, check-ins and trades."""
    _day(home)
    facts = _skill().facts(home)
    assert facts.fresh and facts.data_day == PLAN
    for part in ("Day call: Uptrend, favour Energy. Lean long", "No huddle.",
                 "long NVDA: open", "long AMD: no result yet", "trigger_hit NVDA: holds",
                 "Check-in 12:30: plan holds", "Open trades: 1", "setup_review"):
        assert part in facts.text, part


def test_empty_day(home: Path) -> None:
    """UT-MKT-020.020.M08.T02: With nothing kept the facts say so."""
    facts = _skill().facts(home)
    assert "No day call today." in facts.text and "(no picks)" in facts.text


def test_answer_limits() -> None:
    """UT-MKT-020.021.M08.T01: Six lines, a long line or long feedback are refused."""
    with pytest.raises(ValidationError):
        _answer(["line one"] * 6)
    with pytest.raises(ValidationError):
        _answer(["x" * 121])
    with pytest.raises(ValidationError):
        _answer(feedback=[{"skill": "risk_check", "text": "y" * 151}])


def test_answer_at_limits() -> None:
    """UT-MKT-020.021.M08.T02: Five 120-character lines and 150-character feedback pass."""
    answer = _answer(["x" * 120] * 5, [{"skill": "risk_check", "text": "y" * 150}])
    assert len(answer.handover) == 5


def test_day_end_stored(home: Path) -> None:
    """UT-MKT-020.022.M08.T01: Handover, feedback and summary are kept; one feed item."""
    _day(home)
    skill = _skill()
    items = skill.act(FakeCtx(home, _answer(feedback=[
        {"skill": "setup_review", "text": "AMD grade B was right to doubt"}])),
        skill.facts(home))
    assert [i.text for i in items] == ["Handover: NVDA in trade, stop 136 / AMD did not trigger"]
    assert has_handover(home, PLAN)
    feedback, summary = _sql(home, "SELECT feedback, summary FROM day_brief WHERE day = ?",
                             (PLAN,))[0]
    assert json.loads(feedback) == [["setup_review", "AMD grade B was right to doubt"]]
    assert summary == "2 picks: 1 triggered, 0 stopped; 1 flags; huddle no; call Uptrend"
    assert not skill.facts(home).fresh


def _notes(home: Path) -> list[Any]:
    con = desk_memory.connect(home)
    try:
        return con.execute("SELECT owner, text FROM memories WHERE kind = 'note'").fetchall()
    finally:
        con.close()


def test_feedback_to_memory(home: Path) -> None:
    """UT-MKT-020.022.M08.T02: With Memory v2 on the feedback is a note of the expert."""
    save_settings(DeskAiSettings(memory_v2_on=True), home)
    _day(home)
    skill = _skill()
    skill.act(FakeCtx(home, _answer(feedback=[
        {"skill": "setup_review", "text": "AMD grade B was right to doubt"}])),
        skill.facts(home))
    assert _notes(home) == [("emp-x", f"Day-end feedback {PLAN}: AMD grade B was right to "
                                      "doubt")]


def test_feedback_not_kept(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-020.022.M08.T03: Unknown skills drop; Memory v2 off writes no note."""
    _day(home)
    skill = _skill()
    with caplog.at_level(logging.INFO):
        skill.act(FakeCtx(home, _answer(feedback=[
            {"skill": "crystal_ball", "text": "Nice guess"},
            {"skill": "setup_review", "text": "Good grades today"}])), skill.facts(home))
    assert json.loads(_sql(home, "SELECT feedback FROM day_brief WHERE day = ?",
                           (PLAN,))[0][0]) == [["setup_review", "Good grades today"]]
    assert not (home / "memory.db").exists() or _notes(home) == []
    assert has_handover(home, PLAN)


def test_no_answer(home: Path) -> None:
    """UT-MKT-020.022.M08.T04: Without an answer nothing is kept."""
    _day(home)
    skill = _skill()
    assert skill.act(FakeCtx(home, None), skill.facts(home)) == []
    assert not has_handover(home, PLAN)


def test_log_line(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-020.024.M08.T01: The day-end logs one company day line."""
    _day(home)
    skill = _skill()
    with caplog.at_level(logging.INFO):
        skill.act(FakeCtx(home, _answer()), skill.facts(home))
    lines = [r.getMessage() for r in caplog.records if "Day-end written" in r.getMessage()]
    assert lines == [f"[Company day] Day-end written for {TRADED}: 2 handover line(s), 0 "
                     "feedback line(s)"]


# ── M09: default employee ────────────────────────────────────────────────────


def test_default_employee(tmp_path: Path) -> None:
    """UT-MKT-020.023.M09.T01: emp-018 is a lead doing day_end on day_end; paths load."""
    seed_employees(tmp_path, default_folders(("us_swing.market",)))
    text = (tmp_path / "employees" / "emp-018" / "employee.md").read_text(encoding="utf-8")
    for part in ("level: lead", "skill: day_end", "- day_end", "calls_per_day: 2"):
        assert part in text
    assert SKILL_PATHS["day_end"] == "us_swing.market.day_end:DayEndSkill"
    assert "us_swing.market.decision_check:DecisionCheckStep" in STEP_PATHS
    assert any(s.name == "Decision check" for s in load_steps())


def test_user_copy_kept(tmp_path: Path) -> None:
    """UT-MKT-020.023.M09.T02: A changed copy in the desk folder is not overwritten."""
    seed_employees(tmp_path, default_folders(("us_swing.market",)))
    path = tmp_path / "employees" / "emp-018" / "employee.md"
    path.write_text(path.read_text(encoding="utf-8").replace("Lead 3", "Closer"),
                    encoding="utf-8")
    seed_employees(tmp_path, default_folders(("us_swing.market",)))
    assert "name: Closer" in path.read_text(encoding="utf-8")


# ── M10: day-call line in the wake ───────────────────────────────────────────


@dataclass
class _Skill:
    key: str


@dataclass
class _Hire:
    skill: _Skill
    spec: Any = None


def _checked_vote(home: Path) -> None:
    connect(home).close()
    _sql(home, "INSERT INTO decision_votes VALUES ('2026-11-02', 'regime_view', 'market', "
         "'agreed', 'right')")


def test_line_after_memory(home: Path) -> None:
    """UT-MKT-020.018.M10.T01: With checked votes the wake facts end with the line."""
    _checked_vote(home)
    text = employees_step._with_day_calls("facts", home, _Hire(_Skill("regime_view")))  # type: ignore[arg-type]
    assert text == "facts\nDay calls you voted on: 1 checked, 1 right, 0 wrong."


def test_no_line_when_memory_off(home: Path) -> None:
    """UT-MKT-020.018.M10.T02: Memory off: the line is only added on the memory path."""
    _checked_vote(home)
    hire: Any = _Hire(_Skill("regime_view"))
    assert not employees_step._remembers(hire, DeskAiSettings(memory_v2_on=False))
    assert employees_step._with_day_calls("facts", home, _Hire(_Skill("setup_review"))) == (  # type: ignore[arg-type]
        "facts")
