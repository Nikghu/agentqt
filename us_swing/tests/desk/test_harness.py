"""Tests for the P5a lean harness: registry, wake rule, gateway, budget, settings, recorder."""
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
from us_swing.core.desk_steps import EMPLOYEE_PATHS, STEP_PATHS, load_steps
from us_swing.desk import gateway as gw
from us_swing.desk.budget import Budget
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Gateway, Reply, json_part, parse_claude
from us_swing.desk.recorder import NY, Attempt, Recorder
from us_swing.desk.registry import load_employee, load_employees, record_employees

NOW = datetime(2026, 11, 6, 17, 30, tzinfo=NY)
SOUL = "You are TEST, a careful helper."
JOB = """name: TEST
title: Test expert
version: 1
trigger: after_run
output: View
models:
  primary: {source: openrouter, model: or-model}
  backup: {source: claude, model: default}
calls_per_day: 3
monthly_cost_usd: 3.0
kpis: [valid answers]
"""
ON = DeskAiSettings(openrouter_on=True, openrouter_model="or-default", claude_on=True,
                    claude_model="claude-default")


class View(BaseModel):
    """Answer schema used by the fake employee."""

    word: str


def _folder(tmp_path: Path, job: str = JOB, soul: str | None = SOUL) -> Path:
    folder = tmp_path / "emp"
    folder.mkdir(exist_ok=True)
    (folder / "job.yaml").write_text(job, encoding="utf-8")
    if soul is not None:
        (folder / "soul.md").write_text(soul, encoding="utf-8")
    return folder


@dataclass
class FakeEmployee:
    """An employee that asks once and returns one brief with the answer."""

    folder: Path
    fresh: bool = True
    day: str = "2026-11-05"
    name: str = "TEST"
    seen_ctx: list[AgentContext] = field(default_factory=list)
    raises: bool = False

    def facts(self, home: Path) -> Facts:
        return Facts("facts text", self.day, self.fresh, "" if self.fresh else "old data")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        self.seen_ctx.append(ctx)
        if self.raises:
            raise RuntimeError("boom")
        view = ctx.ask(facts.text, View)
        return [FeedItem(self.name, "info", f"word {view.word}", facts.data_day)] if view else []


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
def rec(tmp_path: Path) -> Iterator[Recorder]:
    recorder = Recorder(tmp_path / "desk")
    yield recorder
    recorder.close()


def _gateway(tmp_path: Path, rec: Recorder, caller: FakeCaller,
             settings: DeskAiSettings = ON, job: str = JOB) -> Gateway:
    hire = load_employee(FakeEmployee(_folder(tmp_path, job)))
    assert hire is not None
    return Gateway(tmp_path / "desk", hire, rec, settings, "key", 7, "2026-11-05", caller,
                   lambda: NOW)


def _attempt(started: str = "2026-11-06T10:00:00-05:00", employee: str = "TEST",
             source: str = "openrouter", cost: float = 0.0, tokens: int = 0,
             valid: bool = True, day: str = "2026-11-05") -> Attempt:
    return Attempt(1, employee, 1, day, started, source, "m", 1, "p", "a", valid, "", tokens, 0,
                   cost, 1.0)


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


# ---------------- registry ----------------

def test_job_file_loads(tmp_path: Path) -> None:
    """UT-DSK-002.002.M09.T01: A valid soul.md and job.yaml give a Hire."""
    hire = load_employee(FakeEmployee(_folder(tmp_path)))
    assert hire is not None
    assert (hire.spec.name, hire.spec.version, hire.spec.calls_per_day) == ("TEST", 1, 3)
    assert hire.soul == SOUL and len(hire.hash) == 64


@pytest.mark.parametrize("job", [
    JOB.replace("models:", "modelz:"),
    JOB + "extra: 1\n",
    JOB.replace("after_run", "every_minute"),
])
def test_bad_job_file(tmp_path: Path, job: str, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-002.002.M09.T02: Missing models, an unknown key or a bad trigger: asleep."""
    with caplog.at_level(logging.WARNING):
        assert load_employee(FakeEmployee(_folder(tmp_path, job))) is None
    assert "TEST job file is not valid" in caplog.text


def test_missing_soul(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-002.002.M09.T03: Without soul.md the employee stays asleep."""
    with caplog.at_level(logging.WARNING):
        assert load_employee(FakeEmployee(_folder(tmp_path, soul=None))) is None
    assert "not valid" in caplog.text


def test_employees_table(tmp_path: Path) -> None:
    """UT-DSK-002.004.M09.T01: Loading twice keeps one row with name, title, version, hash."""
    home = tmp_path / "desk"
    hire = load_employee(FakeEmployee(_folder(tmp_path)))
    assert hire is not None
    Recorder(home).close()
    record_employees(home, [hire])
    record_employees(home, [hire])
    assert _rows(home, "SELECT name, title, version, hash FROM employees") == [
        ("TEST", "Test expert", 1, hire.hash)]


def test_changed_file_same_version(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-002.004.M09.T02: A changed soul.md with the same version is stored and warned."""
    home = tmp_path / "desk"
    Recorder(home).close()
    first = load_employee(FakeEmployee(_folder(tmp_path)))
    assert first is not None
    record_employees(home, [first])
    second = load_employee(FakeEmployee(_folder(tmp_path, soul="Changed soul")))
    assert second is not None
    with caplog.at_level(logging.WARNING):
        record_employees(home, [second])
    assert _rows(home, "SELECT hash FROM employees") == [(second.hash,)]
    assert "changed but version is still 1" in caplog.text


def test_bad_file_not_stored(tmp_path: Path) -> None:
    """UT-DSK-002.004.M09.T03: An invalid job file adds no employees row."""
    home = tmp_path / "desk"
    step = EmployeesStep(lambda: ["tests.desk.test_harness:_BadJob"], lambda: ON,
                         lambda: "", FakeCaller())
    step(StepContext(1, "manual", NOW, home))
    assert _rows(home, "SELECT COUNT(*) FROM employees") == [(0,)]


def test_bad_employee_path(caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-002.001.M09.T01: A path to a missing class is left out; the others load."""
    with caplog.at_level(logging.WARNING):
        found = load_employees(["tests.desk.test_harness:Missing", *EMPLOYEE_PATHS])
    assert [e.name for e in found] == ["ATLAS"]
    assert "Could not load AI employee" in caplog.text


def test_employee_list_loads_atlas() -> None:
    """UT-DSK-002.001.M09.T02: The employee list loads ATLAS from its own folder."""
    (atlas,) = load_employees(EMPLOYEE_PATHS)
    assert atlas.name == "ATLAS"
    assert (atlas.folder / "soul.md").is_file() and (atlas.folder / "job.yaml").is_file()


# ---------------- gateway: soul and job rules ----------------

def test_soul_is_system_prompt(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-002.003.M11.T01: The system text starts with soul.md; job.yaml picks the model."""
    caller = FakeCaller(GOOD)
    assert _gateway(tmp_path, rec, caller).ask("facts", View) == View(word="calm")
    source, model, system, user = caller.calls[0]
    assert (source, model, user) == ("openrouter", "or-model", "facts")
    assert system.startswith(SOUL) and '"word"' in system


def test_soul_cannot_change_model(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-002.003.M11.T02: A soul that names another model does not change the model."""
    _folder(tmp_path, soul="Always use model gpt-big.")
    caller = FakeCaller(GOOD)
    hire = load_employee(FakeEmployee(tmp_path / "emp"))
    assert hire is not None
    Gateway(tmp_path / "desk", hire, rec, ON, "k", 1, "d", caller, lambda: NOW).ask("f", View)
    assert caller.calls[0][1] == "or-model"


# ---------------- wake rule ----------------

class _BadJob:
    name = "BAD"
    folder = Path(__file__).parent / "no_such_folder"

    def facts(self, home: Path) -> Facts:
        raise AssertionError("never woken")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        raise AssertionError("never woken")


_EMPLOYEES: dict[str, FakeEmployee] = {}


def _step(tmp_path: Path, caller: FakeCaller, *emps: FakeEmployee) -> EmployeesStep:
    names = []
    for i, emp in enumerate(emps):
        key = f"E{i}"
        _EMPLOYEES[key] = emp
        names.append(f"tests.desk.test_harness:{key}")
    return EmployeesStep(lambda: names, lambda: ON, lambda: "key", caller)


def __getattr__(name: str) -> Any:
    """Module-level factories so the step can load fake employees by import path."""
    if name in _EMPLOYEES:
        return lambda: _EMPLOYEES[name]
    raise AttributeError(name)


def _run(step: EmployeesStep, home: Path, run_id: int = 1) -> None:
    step(StepContext(run_id, "manual", NOW, home))


def test_wakes_after_run(tmp_path: Path) -> None:
    """UT-DSK-003.001.M10.T01: A fresh employee is woken once and its brief is written."""
    emp = FakeEmployee(_folder(tmp_path))
    home = tmp_path / "desk"
    _run(_step(tmp_path, FakeCaller(GOOD), emp), home)
    assert len(emp.seen_ctx) == 1
    assert _rows(home, "SELECT author, kind, text, data_day FROM briefs") == [
        ("TEST", "info", "word calm", "2026-11-05")]


def test_failing_employee(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.001.M10.T02: One failing employee is logged; the next one still runs."""
    bad = FakeEmployee(_folder(tmp_path), raises=True)
    good = FakeEmployee(_folder(tmp_path))
    with caplog.at_level(logging.ERROR):
        _run(_step(tmp_path, FakeCaller(GOOD), bad, good), tmp_path / "desk")
    assert "TEST failed" in caplog.text
    assert len(good.seen_ctx) == 1


def test_step_order() -> None:
    """UT-DSK-003.001.M10.T03: AI employees runs right after Ideas."""
    names = [s.name for s in load_steps(STEP_PATHS)]
    assert names[names.index("Ideas") + 1] == "AI employees"


def test_once_per_data_day(tmp_path: Path) -> None:
    """UT-DSK-003.002.M10.T01: A second run on the same data day does not wake it again."""
    emp = FakeEmployee(_folder(tmp_path))
    step = _step(tmp_path, FakeCaller(GOOD, GOOD), emp)
    _run(step, tmp_path / "desk")
    _run(step, tmp_path / "desk", 2)
    assert len(emp.seen_ctx) == 1


def test_failed_day_tried_again(tmp_path: Path) -> None:
    """UT-DSK-003.002.M10.T02: A day without a valid answer is tried on the next run."""
    emp = FakeEmployee(_folder(tmp_path))
    step = _step(tmp_path, FakeCaller(BAD, BAD, BAD, BAD, GOOD), emp)
    _run(step, tmp_path / "desk")
    _run(step, tmp_path / "desk", 2)
    assert len(emp.seen_ctx) == 2


def test_next_day_wakes_again(tmp_path: Path) -> None:
    """UT-DSK-003.002.M10.T03: Done yesterday, a new data day wakes it again."""
    emp = FakeEmployee(_folder(tmp_path))
    step = _step(tmp_path, FakeCaller(GOOD, GOOD), emp)
    _run(step, tmp_path / "desk")
    emp.day = "2026-11-06"
    _run(step, tmp_path / "desk", 2)
    assert len(emp.seen_ctx) == 2


def test_stale_data(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.003.M10.T01: Stale facts keep the employee asleep; the reason is logged."""
    emp = FakeEmployee(_folder(tmp_path), fresh=False)
    caller = FakeCaller()
    with caplog.at_level(logging.INFO):
        _run(_step(tmp_path, caller, emp), tmp_path / "desk")
    assert emp.seen_ctx == [] and caller.calls == []
    assert "stays asleep: old data" in caplog.text


def test_fresh_data_wakes(tmp_path: Path) -> None:
    """UT-DSK-003.003.M10.T02: Fresh facts wake the employee."""
    emp = FakeEmployee(_folder(tmp_path), fresh=True)
    _run(_step(tmp_path, FakeCaller(GOOD), emp), tmp_path / "desk")
    assert len(emp.seen_ctx) == 1


def test_context_is_ask_only(tmp_path: Path) -> None:
    """UT-DSK-002.005.M10.T01: The employee sees only its home and ask."""
    emp = FakeEmployee(_folder(tmp_path))
    _run(_step(tmp_path, FakeCaller(GOOD), emp), tmp_path / "desk")
    ctx = emp.seen_ctx[0]
    public = {n for n in dir(ctx) if not n.startswith("_")}
    assert public == {"home", "ask", "answered", "refused"}
    assert ctx.home == tmp_path / "desk"


def test_job_files_untouched(tmp_path: Path) -> None:
    """UT-DSK-002.005.M10.T02: A full run leaves the job files as they were."""
    folder = _folder(tmp_path)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    _run(_step(tmp_path, FakeCaller(GOOD), FakeEmployee(folder)), tmp_path / "desk")
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


def test_source_switched_off(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-004.001.M11.T03: With OpenRouter off, the backup (Claude, default model) is used."""
    caller = FakeCaller(GOOD)
    settings = DeskAiSettings(claude_on=True, claude_model="claude-default")
    assert _gateway(tmp_path, rec, caller, settings).ask("f", View) is not None
    assert [(c[0], c[1]) for c in caller.calls] == [("claude", "claude-default")]


# ---------------- gateway checks ----------------

def test_valid_answer(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-004.002.M11.T01: JSON inside other words is accepted; one valid try recorded."""
    assert json_part('Sure! {"word": "x"} thanks') == '{"word": "x"}'
    assert _gateway(tmp_path, rec, FakeCaller(GOOD)).ask("f", View) == View(word="calm")
    assert _rows(tmp_path / "desk", "SELECT valid, attempt FROM activity") == [(1, 1)]


def test_retry_then_backup(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-004.002.M11.T02: Primary bad twice, backup good: 3 tries, 2 invalid with errors."""
    caller = FakeCaller(BAD, Reply('{"other": 1}', 5, 1, 0.0), GOOD)
    assert _gateway(tmp_path, rec, caller).ask("f", View) == View(word="calm")
    rows = _rows(tmp_path / "desk", "SELECT source, valid, error FROM activity ORDER BY id")
    assert [(s, v) for s, v, _ in rows] == [("openrouter", 0), ("openrouter", 0), ("claude", 1)]
    assert all(e for _, v, e in rows if not v)
    assert "not valid" in caller.calls[1][3]


def test_all_tries_bad(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-004.002.M11.T03: All answers bad or errors: None and 4 tries recorded."""
    caller = FakeCaller(BAD, RuntimeError("HTTP 500"), BAD, BAD)
    assert _gateway(tmp_path, rec, caller).ask("f", View) is None
    assert _rows(tmp_path / "desk", "SELECT COUNT(*), SUM(valid) FROM activity") == [(4, 0)]


# ---------------- budget ----------------

def _budget(rec: Recorder, settings: DeskAiSettings = ON) -> Budget:
    return Budget(rec, settings, lambda: NOW)


def test_budget_used_up(tmp_path: Path, rec: Recorder, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-004.003.M12.T01: With USD 10.00 of 10.00 spent no call is made."""
    rec.add(_attempt(employee="OTHER", cost=10.0))
    assert _budget(rec).refusal("TEST", 3.0, 3, "openrouter") == "monthly budget USD 10.00 used up"
    caller = FakeCaller(GOOD)
    with caplog.at_level(logging.WARNING):
        assert _gateway(tmp_path, rec, caller).ask("f", View) is None
    assert caller.calls == [] and "monthly budget" in caplog.text
    assert _budget(rec).refusal("TEST", 3.0, 3, "claude") is None  # subscription: no cost


def test_employee_cap_used_up(rec: Recorder) -> None:
    """UT-DSK-004.003.M12.T02: The employee's own monthly cap refuses."""
    rec.add(_attempt(cost=3.0))
    assert "TEST monthly cap" in (_budget(rec).refusal("TEST", 3.0, 3, "openrouter") or "")


def test_last_month_not_counted(rec: Recorder) -> None:
    """UT-DSK-004.003.M12.T03: Spend from last month does not count."""
    rec.add(_attempt(started="2026-10-30T10:00:00-04:00", cost=9.99))
    assert _budget(rec).refusal("TEST", 3.0, 3, "openrouter") is None


def test_claude_token_cap(rec: Recorder) -> None:
    """UT-DSK-004.004.M12.T01: 200,000 CLI tokens today refuses Claude but not OpenRouter."""
    rec.add(_attempt(employee="OTHER", source="claude", tokens=200_000))
    assert "200,000 tokens" in (_budget(rec).refusal("TEST", 3.0, 3, "claude") or "")
    assert _budget(rec).refusal("TEST", 3.0, 3, "openrouter") is None


def test_calls_per_day(rec: Recorder) -> None:
    """UT-DSK-004.004.M12.T02: calls_per_day 3 allows 12 tries a day (4 per call), then refuses."""
    for _ in range(12):
        rec.add(_attempt())
    assert "3 call(s) for today" in (_budget(rec).refusal("TEST", 3.0, 3, "openrouter") or "")


def test_under_the_caps(rec: Recorder) -> None:
    """UT-DSK-004.004.M12.T03: 150,000 CLI tokens with a 200,000 cap is allowed."""
    rec.add(_attempt(source="claude", tokens=150_000))
    assert _budget(rec).refusal("TEST", 3.0, 3, "claude") is None


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

def test_try_recorded(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-005.001.M14.T01: One try is stored with every field."""
    attempt = _attempt(cost=0.5, tokens=99)
    rec.add(attempt)
    row = _rows(tmp_path / "desk", "SELECT * FROM activity")[0]
    assert row[1:] == tuple(int(v) if isinstance(v, bool) else v for v in vars(attempt).values())


def test_call_error_recorded(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-005.001.M14.T02: A source error is stored as an invalid try with the error text."""
    caller = FakeCaller(RuntimeError("HTTP 401 no key"))
    _gateway(tmp_path, rec, caller, DeskAiSettings(openrouter_on=True)).ask("f", View)
    rows = _rows(tmp_path / "desk", "SELECT valid, answer, error FROM activity")
    assert rows[0] == (0, "", "HTTP 401 no key")


def test_append_only(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-005.002.M14.T01: Updates and deletes on activity and briefs are refused."""
    rec.add(_attempt())
    rec.add_briefs([FeedItem("TEST", "info", "hello", "2026-11-05")])
    con = sqlite3.connect(tmp_path / "desk" / "desk.db")
    try:
        for sql in ("UPDATE activity SET cost_usd = 0", "DELETE FROM activity",
                    "UPDATE briefs SET text = 'x'", "DELETE FROM briefs"):
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                con.execute(sql)
    finally:
        con.close()
    assert _rows(tmp_path / "desk", "SELECT COUNT(*) FROM activity") == [(1,)]


def test_inserts_still_work(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-005.002.M14.T02: After a refused update new tries are still added."""
    rec.add(_attempt())
    con = sqlite3.connect(tmp_path / "desk" / "desk.db")
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("UPDATE activity SET valid = 0")
    con.close()
    rec.add(_attempt())
    assert _rows(tmp_path / "desk", "SELECT COUNT(*) FROM activity") == [(2,)]


def test_brief_stored(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-005.003.M14.T01: A feed item is stored with its time and data day."""
    rec.add_briefs([FeedItem("ATLAS", "info", "Calm market.", "2026-11-05")], NOW)
    assert _rows(tmp_path / "desk", "SELECT created, data_day, author, kind, text FROM briefs") == [
        ("2026-11-06T17:30:00-05:00", "2026-11-05", "ATLAS", "info", "Calm market.")]


def test_empty_brief(tmp_path: Path, rec: Recorder) -> None:
    """UT-DSK-005.003.M14.T02: An empty brief is refused before anything is stored."""
    with pytest.raises(ValueError):
        rec.add_briefs([FeedItem("ATLAS", "info", "  ", "2026-11-05")])
    assert _rows(tmp_path / "desk", "SELECT COUNT(*) FROM briefs") == [(0,)]
