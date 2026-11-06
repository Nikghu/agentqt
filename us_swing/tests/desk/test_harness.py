"""Tests for the P5a lean harness: registry, wake rule, gateway, budget, settings, recorder.

Employee names, titles and levels here are made up: code must never depend on them.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings, save_settings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS, STEP_PATHS, load_steps
from us_swing.desk import gateway as gw
from us_swing.desk.budget import Budget
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Gateway, Reply, json_part, parse_claude
from us_swing.desk.recorder import NY, Attempt, Recorder
from us_swing.desk.registry import (
    default_folders,
    load_employee,
    load_employees,
    record_employees,
    seed_employees,
)

NOW = datetime(2026, 11, 6, 17, 30, tzinfo=NY)
SOUL = "You are {name}, {title}. Be careful."
SKILLS = {"fake": "tests.desk.test_harness:FakeSkill"}


def job(emp_id: str = "t-1", name: str = "Tester A", level: str = "junior",
        skill: str = "fake", extra: str = "") -> str:
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
calls_per_day: 3
monthly_cost_usd: 3.0
kpis: [valid answers]
{extra}"""


ON = DeskAiSettings(openrouter_on=True, openrouter_model="or-default", claude_on=True,
                    claude_model="claude-default")


class View(BaseModel):
    """Answer schema used by the fake skill."""

    word: str


@dataclass
class FakeState:
    """What the fake skill does this test, and what it saw."""

    fresh: bool = True
    day: str = "2026-11-05"
    raises_for: set[str] = field(default_factory=set)
    seen: list[AgentContext] = field(default_factory=list)


STATE = FakeState()


class FakeSkill:
    """A skill that asks once and returns one brief with the answer."""

    key = "fake"

    def facts(self, home: Path) -> Facts:
        return Facts("facts text", STATE.day, STATE.fresh, "" if STATE.fresh else "old data")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        STATE.seen.append(ctx)
        if len(STATE.seen) in {int(x) for x in STATE.raises_for}:
            raise RuntimeError("boom")
        view = ctx.ask(facts.text, View)
        return [FeedItem("info", f"word {view.word}", facts.data_day)] if view else []


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    global STATE
    STATE = FakeState()
    yield


def employee(home: Path, folder: str = "t-1", job_text: str | None = None,
             soul: str | None = SOUL) -> Path:
    """Write one employee folder into the desk folder."""
    path = home / "employees" / folder
    path.mkdir(parents=True, exist_ok=True)
    (path / "job.yaml").write_text(job_text if job_text is not None else job(folder),
                                   encoding="utf-8")
    if soul is not None:
        (path / "soul.md").write_text(soul, encoding="utf-8")
    return path


class FakeCaller:
    """Returns queued replies (or raises queued errors) and records each request."""

    def __init__(self, *replies: Reply | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str, str, str]] = []

    def __call__(self, source: str, model: str, system: str, user: str, key: str) -> Reply:
        self.calls.append((source, model, system, user))
        item = self.replies.pop(0) if self.replies else Reply('{"word": "ok"}', 10, 5, 0.001)
        if isinstance(item, Exception):
            raise item
        return item


GOOD = Reply('Here: {"word": "calm"}', 100, 20, 0.002)
BAD = Reply("not json", 50, 5, 0.001)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "desk"


@pytest.fixture
def rec(home: Path) -> Iterator[Recorder]:
    recorder = Recorder(home)
    yield recorder
    recorder.close()


def _gateway(home: Path, rec: Recorder, caller: FakeCaller, settings: DeskAiSettings = ON,
             job_text: str | None = None, soul: str = SOUL) -> Gateway:
    hire = load_employee(employee(home, job_text=job_text, soul=soul), SKILLS)
    assert hire is not None
    return Gateway(home, hire, rec, settings, "key", 7, "2026-11-05", caller, lambda: NOW)


def _attempt(started: str = "2026-11-06T10:00:00-05:00", emp: str = "t-1",
             source: str = "openrouter", cost: float = 0.0, tokens: int = 0) -> Attempt:
    return Attempt(1, emp, "Tester A", 1, "2026-11-05", started, source, "m", 1, "p", "a", True,
                   "", tokens, 0, cost, 1.0)


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _step(caller: FakeCaller) -> EmployeesStep:
    return EmployeesStep(lambda: SKILLS, lambda: [], lambda: ON, lambda: "key", caller)


def _run(step: EmployeesStep, home: Path, run_id: int = 1) -> None:
    step(StepContext(run_id, "manual", NOW, home))


# ---------------- registry ----------------

def test_job_file_loads(home: Path) -> None:
    """UT-DSK-002.002.M09.T01: Valid files give a Hire; the soul gets the name and title."""
    hire = load_employee(employee(home), SKILLS)
    assert hire is not None
    assert (hire.spec.id, hire.spec.name, hire.spec.level, hire.spec.skill) == (
        "t-1", "Tester A", "junior", "fake")
    assert hire.soul == "You are Tester A, Test helper. Be careful."
    assert hire.skill.key == "fake" and len(hire.hash) == 64


@pytest.mark.parametrize("text", [
    job().replace("models:", "modelz:"),
    job(extra="extra: 1\n"),
    job().replace("after_run", "every_minute"),
    job(level="captain"),
    job().replace("id: t-1\n", ""),
])
def test_bad_job_file(home: Path, text: str, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-002.002.M09.T02: Missing models or id, unknown key, bad trigger or level: asleep."""
    with caplog.at_level(logging.WARNING):
        assert load_employee(employee(home, job_text=text), SKILLS) is None
    assert "not valid, it stays asleep" in caplog.text


def test_missing_soul(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-002.002.M09.T03: Without soul.md the employee stays asleep."""
    with caplog.at_level(logging.WARNING):
        assert load_employee(employee(home, soul=None), SKILLS) is None
    assert "not valid" in caplog.text


def test_roster_table(home: Path) -> None:
    """UT-DSK-002.004.M09.T01: Loading twice keeps one roster row with identity and hash."""
    employee(home)
    Recorder(home).close()
    hires = load_employees(home, SKILLS)
    record_employees(home, hires)
    record_employees(home, hires)
    assert _rows(home, "SELECT id, name, title, level, reports_to, skill, version, hash "
                       "FROM roster") == [("t-1", "Tester A", "Test helper", "junior", None,
                                           "fake", 1, hires[0].hash)]


def test_changed_file_same_version(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-002.004.M09.T02: A changed soul with the same version is stored and warned."""
    Recorder(home).close()
    employee(home)
    record_employees(home, load_employees(home, SKILLS))
    employee(home, soul="Changed soul")
    second = load_employees(home, SKILLS)
    with caplog.at_level(logging.WARNING):
        record_employees(home, second)
    assert _rows(home, "SELECT hash FROM roster") == [(second[0].hash,)]
    assert "changed but version is still 1" in caplog.text


def test_bad_file_not_stored(home: Path) -> None:
    """UT-DSK-002.004.M09.T03: An invalid job file adds no roster row."""
    employee(home, job_text="name: only")
    _run(_step(FakeCaller()), home)
    assert _rows(home, "SELECT COUNT(*) FROM roster") == [(0,)]


def test_unknown_skill(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-002.001.M09.T01: An unknown skill keeps that employee asleep; others load."""
    employee(home, "t-1", job("t-1", skill="no_such_skill"))
    employee(home, "t-2", job("t-2", name="Tester B"))
    with caplog.at_level(logging.WARNING):
        hires = load_employees(home, SKILLS)
    assert [h.spec.name for h in hires] == ["Tester B"]
    assert "unknown skill no_such_skill" in caplog.text


def test_default_employees_seeded(home: Path) -> None:
    """UT-DSK-002.001.M09.T02: Shipped defaults are copied once and use known skills."""
    defaults = default_folders(DEFAULT_EMPLOYEE_PACKAGES)
    assert defaults
    assert seed_employees(home, defaults) == len(defaults)
    hires = load_employees(home, SKILL_PATHS)
    assert len(hires) == len(defaults)
    assert all(h.spec.skill in SKILL_PATHS for h in hires)


def test_seed_never_overwrites(home: Path) -> None:
    """UT-DSK-002.007.M09.T01: A user's edited copy is kept when defaults are seeded again."""
    defaults = default_folders(DEFAULT_EMPLOYEE_PACKAGES)
    seed_employees(home, defaults)
    copy = home / "employees" / defaults[0].name / "job.yaml"
    edited = copy.read_text(encoding="utf-8").replace("name:", "name: Renamed #", 1)
    copy.write_text(edited, encoding="utf-8")
    assert seed_employees(home, defaults) == 0
    assert copy.read_text(encoding="utf-8") == edited


def test_rename_and_restructure(home: Path) -> None:
    """UT-DSK-002.006.M09.T01: Name, title, level and reports_to change only in the files."""
    employee(home, "t-1", job("t-1", name="Tester A", level="junior"))
    employee(home, "t-2", job("t-2", name="Tester B", level="lead"))
    text = job("t-1", name="Someone Else", level="expert").replace(
        "reports_to: null", "reports_to: t-2")
    employee(home, "t-1", text)
    hires = {h.spec.id: h.spec for h in load_employees(home, SKILLS)}
    assert (hires["t-1"].name, hires["t-1"].level, hires["t-1"].reports_to) == (
        "Someone Else", "expert", "t-2")


def test_duplicate_id(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-002.006.M09.T02: Two folders with the same id: the second stays asleep."""
    employee(home, "a", job("t-1"))
    employee(home, "b", job("t-1", name="Tester B"))
    with caplog.at_level(logging.WARNING):
        hires = load_employees(home, SKILLS)
    assert [h.spec.name for h in hires] == ["Tester A"]
    assert "used twice" in caplog.text


# ---------------- gateway: soul and job rules ----------------

def test_soul_is_system_prompt(home: Path, rec: Recorder) -> None:
    """UT-DSK-002.003.M11.T01: The system text starts with the soul; job.yaml picks the model."""
    caller = FakeCaller(GOOD)
    assert _gateway(home, rec, caller).ask("facts", View) == View(word="calm")
    source, model, system, user = caller.calls[0]
    assert (source, model, user) == ("openrouter", "or-model", "facts")
    assert system.startswith("You are Tester A, Test helper.") and '"word"' in system


def test_soul_cannot_change_model(home: Path, rec: Recorder) -> None:
    """UT-DSK-002.003.M11.T02: A soul that names another model does not change the model."""
    caller = FakeCaller(GOOD)
    _gateway(home, rec, caller, soul="Always use model gpt-big.").ask("f", View)
    assert caller.calls[0][1] == "or-model"


# ---------------- wake rule ----------------

def test_wakes_after_run(home: Path) -> None:
    """UT-DSK-003.001.M10.T01: A fresh employee is woken once; its brief carries its name."""
    employee(home)
    _run(_step(FakeCaller(GOOD)), home)
    assert len(STATE.seen) == 1
    assert _rows(home, "SELECT author, employee_id, kind, text, data_day FROM briefs") == [
        ("Tester A", "t-1", "info", "word calm", "2026-11-05")]


def test_failing_employee(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.001.M10.T02: One failing employee is logged; the next one still runs."""
    employee(home, "t-1")
    employee(home, "t-2", job("t-2", name="Tester B"))
    STATE.raises_for = {"1"}
    with caplog.at_level(logging.ERROR):
        _run(_step(FakeCaller(GOOD)), home)
    assert "Tester A failed" in caplog.text
    assert len(STATE.seen) == 2
    assert _rows(home, "SELECT author FROM briefs") == [("Tester B",)]


def test_step_order() -> None:
    """UT-DSK-003.001.M10.T03: AI employees runs right after Ideas."""
    names = [s.name for s in load_steps(STEP_PATHS)]
    assert names[names.index("Ideas") + 1] == "AI employees"


def test_once_per_data_day(home: Path) -> None:
    """UT-DSK-003.002.M10.T01: A second run on the same data day does not wake it again."""
    employee(home)
    step = _step(FakeCaller(GOOD, GOOD))
    _run(step, home)
    _run(step, home, 2)
    assert len(STATE.seen) == 1


def test_failed_day_tried_again(home: Path) -> None:
    """UT-DSK-003.002.M10.T02: A day without a brief is tried on the next run."""
    employee(home)
    step = _step(FakeCaller(BAD, BAD, BAD, BAD, GOOD))
    _run(step, home)
    _run(step, home, 2)
    assert len(STATE.seen) == 2


def test_next_day_wakes_again(home: Path) -> None:
    """UT-DSK-003.002.M10.T03: Done yesterday, a new data day wakes it again."""
    employee(home)
    step = _step(FakeCaller(GOOD, GOOD))
    _run(step, home)
    STATE.day = "2026-11-06"
    _run(step, home, 2)
    assert len(STATE.seen) == 2


def test_renamed_employee_keeps_its_day(home: Path) -> None:
    """UT-DSK-003.002.M10.T04: Renaming after a run does not wake it again the same day."""
    employee(home)
    step = _step(FakeCaller(GOOD, GOOD))
    _run(step, home)
    employee(home, job_text=job(name="New Name"))
    _run(step, home, 2)
    assert len(STATE.seen) == 1


def test_stale_data(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.003.M10.T01: Stale facts keep the employee asleep; the reason is logged."""
    employee(home)
    STATE.fresh = False
    caller = FakeCaller()
    with caplog.at_level(logging.INFO):
        _run(_step(caller), home)
    assert STATE.seen == [] and caller.calls == []
    assert "Tester A stays asleep: old data" in caplog.text


def test_fresh_data_wakes(home: Path) -> None:
    """UT-DSK-003.003.M10.T02: Fresh facts wake the employee."""
    employee(home)
    _run(_step(FakeCaller(GOOD)), home)
    assert len(STATE.seen) == 1


def test_context_is_ask_only(home: Path) -> None:
    """UT-DSK-002.005.M10.T01: The skill sees only its home and ask."""
    employee(home)
    _run(_step(FakeCaller(GOOD)), home)
    ctx = STATE.seen[0]
    assert {n for n in dir(ctx) if not n.startswith("_")} == {"home", "ask", "answered",
                                                               "refused"}
    assert ctx.home == home


def test_job_files_untouched(home: Path) -> None:
    """UT-DSK-002.005.M10.T02: A full run leaves the employee files as they were."""
    folder = employee(home)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    _run(_step(FakeCaller(GOOD)), home)
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


# ---------------- gateway sources ----------------

class _Response:
    def __init__(self, status: int, body: dict[str, Any]) -> None:
        self.status_code = status
        self._body = body

    def json(self) -> dict[str, Any]:
        return self._body


def test_openrouter_reply_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-004.001.M11.T01: The OpenRouter reply gives text, tokens and cost."""
    sent: list[dict[str, Any]] = []

    def post(url: str, **kw: Any) -> _Response:
        sent.append(kw)
        return _Response(200, {"choices": [{"message": {"content": "hi"}}],
                               "usage": {"prompt_tokens": 120, "completion_tokens": 30,
                                         "cost": 0.0042}})

    monkeypatch.setattr(gw.httpx, "post", post)
    assert gw.call_model("openrouter", "m", "sys", "user", "key") == Reply("hi", 120, 30, 0.0042)
    assert sent[0]["json"]["usage"] == {"include": True}
    monkeypatch.setattr(gw.httpx, "post", lambda url, **kw: _Response(
        200, {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 1}}))
    with pytest.raises(RuntimeError, match="no cost"):
        gw.call_model("openrouter", "m", "sys", "user", "key")


def test_claude_reply_read() -> None:
    """UT-DSK-004.001.M11.T02: The CLI reply gives text and tokens; its cost is ignored."""
    out = json.dumps({"result": " answer ", "total_cost_usd": 0.31,
                      "usage": {"input_tokens": 10, "cache_creation_input_tokens": 200,
                                "cache_read_input_tokens": 1000, "output_tokens": 40}})
    assert parse_claude(out, "", 0) == Reply("answer", 1210, 40, 0.0)
    with pytest.raises(RuntimeError):
        parse_claude(json.dumps({"is_error": True, "result": "limit"}), "", 1)


def test_source_switched_off(home: Path, rec: Recorder) -> None:
    """UT-DSK-004.001.M11.T03: With OpenRouter off, the backup (Claude, default model) is used."""
    caller = FakeCaller(GOOD)
    settings = DeskAiSettings(claude_on=True, claude_model="claude-default")
    assert _gateway(home, rec, caller, settings).ask("f", View) is not None
    assert [(c[0], c[1]) for c in caller.calls] == [("claude", "claude-default")]


# ---------------- gateway checks ----------------

def test_valid_answer(home: Path, rec: Recorder) -> None:
    """UT-DSK-004.002.M11.T01: JSON inside other words is accepted; one valid try recorded."""
    assert json_part('Sure! {"word": "x"} thanks') == '{"word": "x"}'
    assert _gateway(home, rec, FakeCaller(GOOD)).ask("f", View) == View(word="calm")
    assert _rows(home, "SELECT valid, attempt, employee, employee_name FROM activity") == [
        (1, 1, "t-1", "Tester A")]


def test_retry_then_backup(home: Path, rec: Recorder) -> None:
    """UT-DSK-004.002.M11.T02: Primary bad twice, backup good: 3 tries, 2 invalid with errors."""
    caller = FakeCaller(BAD, Reply('{"other": 1}', 5, 1, 0.0), GOOD)
    assert _gateway(home, rec, caller).ask("f", View) == View(word="calm")
    rows = _rows(home, "SELECT source, valid, error FROM activity ORDER BY id")
    assert [(s, v) for s, v, _ in rows] == [("openrouter", 0), ("openrouter", 0), ("claude", 1)]
    assert all(e for _, v, e in rows if not v)
    assert "not valid" in caller.calls[1][3]


def test_all_tries_bad(home: Path, rec: Recorder) -> None:
    """UT-DSK-004.002.M11.T03: All answers bad or errors: None and 4 tries recorded."""
    caller = FakeCaller(BAD, RuntimeError("HTTP 500"), BAD, BAD)
    assert _gateway(home, rec, caller).ask("f", View) is None
    assert _rows(home, "SELECT COUNT(*), SUM(valid) FROM activity") == [(4, 0)]


# ---------------- budget ----------------

def _budget(rec: Recorder, settings: DeskAiSettings = ON) -> Budget:
    return Budget(rec, settings, lambda: NOW)


def _refusal(rec: Recorder, source: str = "openrouter") -> str | None:
    return _budget(rec).refusal("t-1", "Tester A", 3.0, 3, source)


def test_budget_used_up(home: Path, rec: Recorder, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-004.003.M12.T01: With USD 10.00 spent no API call is made; Claude CLI still can."""
    rec.add(_attempt(emp="t-9", cost=10.0))
    assert _refusal(rec) == "monthly budget USD 10.00 used up"
    caller = FakeCaller(GOOD)
    with caplog.at_level(logging.WARNING):
        assert _gateway(home, rec, caller, DeskAiSettings(openrouter_on=True)).ask(
            "f", View) is None
    assert caller.calls == [] and "monthly budget" in caplog.text
    assert _refusal(rec, "claude") is None


def test_employee_cap_used_up(rec: Recorder) -> None:
    """UT-DSK-004.003.M12.T02: The employee's own monthly cap refuses, by its id."""
    rec.add(_attempt(cost=3.0))
    assert "Tester A monthly cap" in (_refusal(rec) or "")


def test_last_month_not_counted(rec: Recorder) -> None:
    """UT-DSK-004.003.M12.T03: Spend from last month does not count."""
    rec.add(_attempt(started="2026-10-30T10:00:00-04:00", cost=9.99))
    assert _refusal(rec) is None


def test_claude_token_cap(rec: Recorder) -> None:
    """UT-DSK-004.004.M12.T01: 200,000 CLI tokens today refuses Claude but not OpenRouter."""
    rec.add(_attempt(emp="t-9", source="claude", tokens=200_000))
    assert "200,000 tokens" in (_refusal(rec, "claude") or "")
    assert _refusal(rec) is None


def test_calls_per_day(rec: Recorder) -> None:
    """UT-DSK-004.004.M12.T02: calls_per_day 3 allows 12 tries a day (4 per call), then refuses."""
    for _ in range(12):
        rec.add(_attempt())
    assert "3 call(s) for today" in (_refusal(rec) or "")


def test_under_the_caps(rec: Recorder) -> None:
    """UT-DSK-004.004.M12.T03: 150,000 CLI tokens with a 200,000 cap is allowed."""
    rec.add(_attempt(source="claude", tokens=150_000))
    assert _refusal(rec, "claude") is None


# ---------------- settings ----------------

def test_settings_round_trip(tmp_path: Path) -> None:
    """UT-DSK-004.005.M13.T01: Saved settings load back the same."""
    settings = DeskAiSettings(True, "or/m", True, "claude-haiku-5-5", 7.5, 150_000)
    save_settings(settings, tmp_path)
    assert load_settings(tmp_path) == settings


def test_settings_defaults(tmp_path: Path) -> None:
    """UT-DSK-004.005.M13.T02: A missing or broken file gives the defaults (both sources off)."""
    assert load_settings(tmp_path) == DeskAiSettings()
    (tmp_path / "desk_ai.json").write_text("{bad", encoding="utf-8")
    loaded = load_settings(tmp_path)
    assert (loaded.openrouter_on, loaded.claude_on) == (False, False)
    assert (loaded.monthly_budget_usd, loaded.claude_tokens_per_day) == (10.0, 200_000)
    (tmp_path / "desk_ai.json").write_text('{"monthly_budget_usd": -1}', encoding="utf-8")
    assert load_settings(tmp_path) == DeskAiSettings()


# ---------------- recorder ----------------

def test_try_recorded(home: Path, rec: Recorder) -> None:
    """UT-DSK-005.001.M14.T01: One try is stored with every field."""
    attempt = _attempt(cost=0.5, tokens=99)
    rec.add(attempt)
    names = ", ".join(vars(attempt))
    row = _rows(home, f"SELECT {names} FROM activity")[0]  # noqa: S608
    assert row == tuple(int(v) if isinstance(v, bool) else v for v in vars(attempt).values())


def test_call_error_recorded(home: Path, rec: Recorder) -> None:
    """UT-DSK-005.001.M14.T02: A source error is stored as an invalid try with the error text."""
    caller = FakeCaller(RuntimeError("HTTP 401 no key"))
    _gateway(home, rec, caller, DeskAiSettings(openrouter_on=True, openrouter_model="m")).ask(
        "f", View)
    assert _rows(home, "SELECT valid, answer, error FROM activity")[0] == (
        0, "", "HTTP 401 no key")


def test_old_tables_get_new_columns(home: Path) -> None:
    """UT-DSK-005.001.M14.T03: Tables made before the id columns get them on open."""
    home.mkdir(parents=True)
    con = sqlite3.connect(home / "desk.db")
    con.execute("CREATE TABLE briefs (id INTEGER PRIMARY KEY, created TEXT, data_day TEXT, "
                "author TEXT, kind TEXT, text TEXT)")
    con.commit()
    con.close()
    Recorder(home).close()
    cols = {r[1] for r in _rows(home, "PRAGMA table_info(briefs)")}
    assert "employee_id" in cols


def test_append_only(home: Path, rec: Recorder) -> None:
    """UT-DSK-005.002.M14.T01: Updates and deletes on activity and briefs are refused."""
    rec.add(_attempt())
    rec.add_briefs([FeedItem("info", "hello", "2026-11-05")], "t-1", "Tester A")
    con = sqlite3.connect(home / "desk.db")
    try:
        for sql in ("UPDATE activity SET cost_usd = 0", "DELETE FROM activity",
                    "UPDATE briefs SET text = 'x'", "DELETE FROM briefs"):
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                con.execute(sql)
    finally:
        con.close()
    assert _rows(home, "SELECT COUNT(*) FROM activity") == [(1,)]


def test_inserts_still_work(home: Path, rec: Recorder) -> None:
    """UT-DSK-005.002.M14.T02: After a refused update new tries are still added."""
    rec.add(_attempt())
    con = sqlite3.connect(home / "desk.db")
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("UPDATE activity SET valid = 0")
    con.close()
    rec.add(_attempt())
    assert _rows(home, "SELECT COUNT(*) FROM activity") == [(2,)]


def test_brief_stored(home: Path, rec: Recorder) -> None:
    """UT-DSK-005.003.M14.T01: A brief is stored with time, data day, name and id."""
    rec.add_briefs([FeedItem("info", "Calm market.", "2026-11-05")], "t-1", "Tester A", NOW)
    assert _rows(home, "SELECT created, data_day, author, employee_id, kind, text "
                       "FROM briefs") == [("2026-11-06T17:30:00-05:00", "2026-11-05",
                                           "Tester A", "t-1", "info", "Calm market.")]


def test_empty_brief(home: Path, rec: Recorder) -> None:
    """UT-DSK-005.003.M14.T02: An empty brief is refused before anything is stored."""
    with pytest.raises(ValueError):
        rec.add_briefs([FeedItem("info", "  ", "2026-11-05")], "t-1", "Tester A")
    assert _rows(home, "SELECT COUNT(*) FROM briefs") == [(0,)]
