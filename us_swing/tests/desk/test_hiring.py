"""Tests for P6: MD-DSK-006.001.M18 (core/desk_hiring.py), MD-DSK-006.004.M19 (desk/shadow.py),
MD-DSK-006.009.M20 (desk/weekly_report.py), and the P6 parts of registry and settings.

Employee names here are made up: the code must never depend on who an employee is.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import tests.desk.test_harness as th
from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings, save_settings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_hiring import (
    agreement,
    decide,
    list_hires,
    seat_counts,
    shadow_report,
    start_hire,
)
from us_swing.desk.recorder import NY, Attempt, Recorder
from us_swing.desk.registry import load_employees
from us_swing.desk.shadow import SHADOW_DAYS, run_shadow
from us_swing.desk.weekly_report import WeeklyReportStep, report_friday

TODAY = date(2026, 11, 6)
NOW = datetime(2026, 11, 6, 17, 0, tzinfo=NY)
COMMENT = "# my note about this employee\n"


@pytest.fixture(autouse=True)
def _fresh_state() -> Iterator[None]:
    th.STATE = th.FakeState()
    th.CLOCK[0] = th.NOW
    yield


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "desk"


def _emp(home: Path, folder: str, name: str, level: str = "expert", skill: str = "fake",
         status: str = "", hired: str = "") -> Path:
    extra = (f"status: {status}\n" if status else "") + (f"hired_on: '{hired}'\n" if hired else "")
    return th.employee(home, folder, COMMENT + th.job(folder, name, level, skill, extra))


def _try(home: Path, emp: str, day: str, answer: dict[str, Any] | None, shadow: int,
         tokens: int = 100, cost: float = 0.01) -> None:
    rec = Recorder(home)
    try:
        rec.add(Attempt(1, emp, emp, 1, day, f"{day}T17:00:00-05:00", "claude", "m", 1, "p",
                        json.dumps(answer) if answer else "bad", answer is not None, "",
                        tokens, 0, cost, 1.0, 0, shadow))
    finally:
        rec.close()


def _days(n: int) -> list[str]:
    return [(date(2026, 10, 1) + timedelta(days=i)).isoformat() for i in range(n)]


def _status(folder: Path) -> tuple[str, str]:
    text = (folder / "job.yaml").read_text(encoding="utf-8")
    status = next((ln.split(":", 1)[1].strip() for ln in text.splitlines()
                   if ln.startswith("status:")), "active")
    version = next(ln.split(":", 1)[1].strip() for ln in text.splitlines()
                   if ln.startswith("version:"))
    return status, version


# ---------------- start a hire ----------------

def test_start_hire(home: Path) -> None:
    """UT-DSK-006.001.M18.T01: a hire gets a shadow folder with the chosen name and model."""
    new_id, reason = start_hire(home, "setup_review", "expert", "Made Up One", "claude",
                                "default", TODAY)
    assert (new_id, reason) == ("emp-001", "")
    hires = list_hires(home)
    assert len(hires) == 1
    e = hires[0].employee
    assert (e.name, e.level, e.skill, e.status, e.hired_on, e.model) == (
        "Made Up One", "expert", "setup_review", "shadow", "2026-11-06", "claude / default")
    soul = (home / "employees" / "emp-001" / "soul.md").read_text(encoding="utf-8")
    assert "{name}" in soul and "setup" in soul.lower()
    loaded = load_employees(home, {"setup_review": "us_swing.market.setup_review:SetupReviewSkill"})
    assert loaded[0].spec.status == "shadow" and loaded[0].spec.version == 1


def test_next_id(home: Path) -> None:
    """UT-DSK-006.001.M18.T02: the new id is one above the highest emp number."""
    for folder in ("emp-001", "emp-003", "emp-010"):
        _emp(home, folder, f"Person {folder}", level="junior")
    assert start_hire(home, "setup_review", "expert", "New Person", "claude", "default",
                      TODAY)[0] == "emp-011"


@pytest.mark.parametrize(("skill", "level", "name", "why"), [
    ("no_such_skill", "expert", "Someone", "unknown skill"),
    ("setup_review", "lead", "Someone", "expert, champion or junior"),
    ("setup_review", "expert", "person A", "already used"),
    ("setup_review", "champion", "Someone", "seats are taken"),
])
def test_refused_hires(home: Path, skill: str, level: str, name: str, why: str) -> None:
    """UT-DSK-006.002.M18.T01: unknown skill, lead, used name and full cap are refused."""
    _emp(home, "emp-001", "Person A")
    save_settings(DeskAiSettings(champion_cap=1), home)
    _emp(home, "emp-002", "Person B", level="champion")
    new_id, reason = start_hire(home, skill, level, name, "claude", "default", TODAY)
    assert new_id is None and why in reason
    assert sorted(p.name for p in (home / "employees").iterdir()) == ["emp-001", "emp-002"]


# ---------------- seat caps ----------------

def test_cap_defaults_and_save(home: Path) -> None:
    """UT-DSK-006.003.M13.T01: caps default to 8/5/30 and are saved."""
    caps = load_settings(home)
    assert (caps.expert_cap, caps.champion_cap, caps.junior_cap) == (8, 5, 30)
    assert caps.cap("lead") is None
    save_settings(DeskAiSettings(expert_cap=9, champion_cap=6, junior_cap=31), home)
    caps = load_settings(home)
    assert (caps.expert_cap, caps.champion_cap, caps.junior_cap) == (9, 6, 31)


def test_bad_cap() -> None:
    """UT-DSK-006.003.M13.T02: a cap of 0 is refused."""
    with pytest.raises(ValueError, match="seat caps"):
        DeskAiSettings(expert_cap=0)


def test_seat_count(home: Path) -> None:
    """UT-DSK-006.003.M18.T01: active and shadow count; retired does not."""
    _emp(home, "emp-001", "A")
    _emp(home, "emp-002", "B")
    _emp(home, "emp-003", "C", status="shadow", hired="2026-11-01")
    _emp(home, "emp-004", "D", status="retired")
    assert seat_counts(home)["expert"] == 3


# ---------------- shadow run ----------------

def _gateway(home: Path, rec: Recorder, folder: str) -> tuple[Any, Any]:
    from us_swing.desk.gateway import Gateway
    from us_swing.desk.registry import load_employee

    hire = load_employee(home / "employees" / folder, th.SKILLS)
    assert hire is not None
    caller = th.FakeCaller(th.GOOD)
    return hire, (Gateway(home, hire, rec, th.ON, "key", 7, "2026-11-05", caller,
                          lambda: NOW, shadow=True), caller)


def test_shadow_recorded_only(home: Path) -> None:
    """UT-DSK-006.004.M19.T01: a shadow answer is recorded with shadow 1; act is not called."""
    _emp(home, "emp-002", "Shadow Person", status="shadow", hired="2026-11-01")
    rec = Recorder(home)
    try:
        hire, (gateway, caller) = _gateway(home, rec, "emp-002")
        facts = hire.skill.facts(home)
        assert run_shadow(hire, facts, gateway, rec)
    finally:
        rec.close()
    assert th.STATE.seen == [] and len(caller.calls) == 1
    assert th._rows(home, "SELECT shadow, valid FROM activity") == [(1, 1)]
    assert th._rows(home, "SELECT COUNT(*) FROM briefs") == [(0,)]


def test_shadow_once_per_day(home: Path) -> None:
    """UT-DSK-006.004.M19.T02: a shadow already asked for the data day is not asked again."""
    _emp(home, "emp-002", "Shadow Person", status="shadow", hired="2026-11-01")
    _try(home, "emp-002", "2026-11-05", {"word": "x"}, 1)
    rec = Recorder(home)
    try:
        hire, (gateway, caller) = _gateway(home, rec, "emp-002")
        assert not run_shadow(hire, hire.skill.facts(home), gateway, rec)
    finally:
        rec.close()
    assert caller.calls == []


def test_shadow_through_step(home: Path) -> None:
    """UT-DSK-006.004.M19.T03: the holder writes its brief; the shadow writes only tries."""
    _emp(home, "emp-001", "Holder Person")
    _emp(home, "emp-002", "Shadow Person", status="shadow", hired="2026-11-01")
    th._run(th._step(th.FakeCaller()), home)
    assert th._rows(home, "SELECT employee_id FROM briefs") == [("emp-001",)]
    assert sorted(th._rows(home, "SELECT employee, shadow FROM activity")) == [
        ("emp-001", 0), ("emp-002", 1)]
    assert len(th.STATE.seen) == 1


def test_ready_after_14_days(home: Path) -> None:
    """UT-DSK-006.005.M18.T01: 13 shadow days are not ready; 14 are."""
    _emp(home, "emp-002", "Shadow Person", status="shadow", hired="2026-09-30")
    for day in _days(13):
        _try(home, "emp-002", day, {"word": "x"}, 1)
    assert not list_hires(home)[0].ready
    _try(home, "emp-002", "2026-11-01", None, 1)
    hire = list_hires(home)[0]
    assert hire.days == SHADOW_DAYS and hire.ready


def test_no_calls_after_14_days(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-006.005.M19.T01: day 14 logs ready once; after that no more calls."""
    _emp(home, "emp-002", "Shadow Person", status="shadow", hired="2026-09-30")
    for day in _days(13):
        _try(home, "emp-002", day, {"word": "x"}, 1)
    rec = Recorder(home)
    try:
        hire, (gateway, caller) = _gateway(home, rec, "emp-002")
        with caplog.at_level(logging.INFO, logger="us_swing.desk.shadow"):
            assert run_shadow(hire, hire.skill.facts(home), gateway, rec)
            th.STATE.day = "2026-11-06"
            assert not run_shadow(hire, hire.skill.facts(home), gateway, rec)
    finally:
        rec.close()
    assert len(caller.calls) == 1
    assert sum("ready for a decision" in r.getMessage() for r in caplog.records) == 1


# ---------------- shadow report ----------------

def test_shadow_report(home: Path) -> None:
    """UT-DSK-006.006.M18.T01: figures for both sides over the shadow days and agreement."""
    _emp(home, "emp-001", "Holder Person")
    _emp(home, "emp-002", "Shadow Person", status="shadow", hired="2026-10-01")
    days = _days(3)
    for day in days:
        _try(home, "emp-002", day, {"grade": "A"}, 1)
    _try(home, "emp-002", days[2], None, 1)
    _try(home, "emp-001", days[0], {"grade": "A"}, 0)
    _try(home, "emp-001", days[1], {"grade": "B"}, 0)
    _try(home, "emp-001", "2026-12-01", {"grade": "A"}, 0)
    report = shadow_report(home, "emp-002")
    hire, holder = report.rows
    assert (hire.who, hire.days, hire.valid, hire.tokens) == ("Shadow Person", 3, 1.0, 400)
    assert (holder.who, holder.days, holder.valid, holder.tokens) == ("Holder Person", 2, 1.0,
                                                                       200)
    assert report.agreement == 0.5


def test_report_without_holder(home: Path) -> None:
    """UT-DSK-006.006.M18.T02: without an active holder there is one row and no agreement."""
    _emp(home, "emp-001", "Old Person", status="retired")
    _emp(home, "emp-002", "Shadow Person", status="shadow", hired="2026-10-01")
    _try(home, "emp-002", "2026-10-01", {"grade": "A"}, 1)
    report = shadow_report(home, "emp-002")
    assert len(report.rows) == 1 and report.agreement is None


def test_agreement_values() -> None:
    """UT-DSK-006.006.M18.T03: same answers agree fully; free text is left out."""
    a = {"grades": [{"side": "long", "symbol": "AAA", "grade": "A"},
                    {"side": "long", "symbol": "BBB", "grade": "B"}],
         "note": "A long free text note that is surely more than twenty characters"}
    b = json.loads(json.dumps(a))
    assert agreement(a, b) == 1.0
    b["note"] = "Another long free text note, also more than twenty characters"
    assert agreement(a, b) == 1.0
    b["grades"][1]["grade"] = "C"
    assert 0 < agreement(a, b) < 1


# ---------------- decisions ----------------

def _ready(home: Path, folder: str = "emp-002", skill: str = "fake") -> None:
    _emp(home, folder, f"Shadow {folder}", status="shadow", hired="2026-09-30", skill=skill)
    for day in _days(SHADOW_DAYS):
        _try(home, folder, day, {"word": "x"}, 1)


def test_replace(home: Path) -> None:
    """UT-DSK-006.007.M18.T01: Replace retires the holder and activates the hire."""
    holder = _emp(home, "emp-001", "Holder Person")
    _ready(home)
    assert decide(home, "emp-002", "replace", NOW) == ""
    assert _status(holder) == ("retired", "2")
    assert _status(home / "employees" / "emp-002") == ("active", "2")
    assert COMMENT.strip() in (holder / "job.yaml").read_text(encoding="utf-8")
    assert th._rows(home, "SELECT subject, decision, detail FROM approvals") == [
        ("emp-002", "replace", "emp-001")]
    assert [h.spec.id for h in load_employees(home, th.SKILLS)] == ["emp-002"]


def test_add_and_reject(home: Path) -> None:
    """UT-DSK-006.007.M18.T02: Add activates a hire without holder; Reject retires one."""
    _ready(home)
    _emp(home, "emp-003", "Other Hire", status="shadow", hired="2026-11-01")
    assert decide(home, "emp-002", "add", NOW) == ""
    assert decide(home, "emp-003", "reject", NOW) == ""
    assert _status(home / "employees" / "emp-002")[0] == "active"
    assert _status(home / "employees" / "emp-003")[0] == "retired"


def test_refused_decisions(home: Path) -> None:
    """UT-DSK-006.007.M18.T03: not ready, Add with a holder and unknown hire are refused."""
    _emp(home, "emp-001", "Holder Person")
    _emp(home, "emp-003", "Early Hire", status="shadow", hired="2026-11-01")
    _ready(home)
    before = (home / "employees" / "emp-003" / "job.yaml").read_text(encoding="utf-8")
    assert "not ready" in decide(home, "emp-003", "replace", NOW)
    assert "active holder" in decide(home, "emp-002", "add", NOW)
    assert decide(home, "emp-999", "reject", NOW) == "unknown hire or decision"
    assert (home / "employees" / "emp-003" / "job.yaml").read_text(encoding="utf-8") == before
    assert not (home / "desk.db").exists() or th._rows(
        home, "SELECT name FROM sqlite_master WHERE name = 'approvals'") == []


def test_approvals_append_only(home: Path) -> None:
    """UT-DSK-006.007.M18.T04: UPDATE and DELETE on approvals are refused."""
    _ready(home)
    decide(home, "emp-002", "add", NOW)
    con = sqlite3.connect(home / "desk.db")
    try:
        for sql in ("UPDATE approvals SET decision = 'x'", "DELETE FROM approvals"):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                with con:
                    con.execute(sql)
    finally:
        con.close()


def test_status_read(home: Path) -> None:
    """UT-DSK-006.008.M09.T01: retired is not loaded; shadow is; no status means active."""
    _emp(home, "emp-001", "A")
    _emp(home, "emp-002", "B", status="shadow", hired="2026-11-01")
    _emp(home, "emp-003", "C", status="retired")
    hires = {h.spec.id: h.spec.status for h in load_employees(home, th.SKILLS)}
    assert hires == {"emp-001": "active", "emp-002": "shadow"}


# ---------------- weekly report ----------------

def _report_rows(home: Path) -> list[tuple[str, str]]:
    return th._rows(home, "SELECT week, text FROM desk_reports ORDER BY id")


def test_friday_report(home: Path) -> None:
    """UT-DSK-006.009.M20.T01: a Friday run writes one report with figures and shadow days."""
    _emp(home, "emp-001", "Holder Person")
    _emp(home, "emp-002", "Shadow Person", status="shadow", hired="2026-11-01")
    _try(home, "emp-001", "2026-11-05", {"word": "x"}, 0, tokens=300, cost=0.02)
    _try(home, "emp-001", "2026-11-05", None, 0)
    _try(home, "emp-002", "2026-11-05", {"word": "x"}, 1)
    _try(home, "emp-001", "2026-10-20", {"word": "x"}, 0)
    WeeklyReportStep(lambda: NOW)(StepContext(1, "evening", NOW, home))
    ((week, text),) = _report_rows(home)
    assert week == "2026-11-06"
    assert "Holder Person | 2 | 50% | 1 | 400 | 0.0300" in text
    assert "Shadow Person (shadow) | 1 | 100%" in text
    assert "Shadow Person (fake): 1 of 14 days" in text


def test_once_per_week(home: Path) -> None:
    """UT-DSK-006.009.M20.T02: a second run in the same week writes nothing new."""
    step = WeeklyReportStep(lambda: NOW)
    step(StepContext(1, "evening", NOW, home))
    step(StepContext(2, "evening", NOW, home))
    assert len(_report_rows(home)) == 1


def test_missed_friday(home: Path) -> None:
    """UT-DSK-006.009.M20.T03: a Monday first run writes the report for the Friday before."""
    monday = datetime(2026, 11, 9, 17, 0, tzinfo=NY)
    assert report_friday(monday.date()) == date(2026, 11, 6)
    assert report_friday(date(2026, 11, 6)) == date(2026, 11, 6)
    WeeklyReportStep(lambda: monday)(StepContext(1, "evening", monday, home))
    ((week, text),) = _report_rows(home)
    assert week == "2026-11-06" and "2026-10-31 to 2026-11-06" in text
    assert "(no AI work this week)" in text


def test_log_lines(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-006.010.M18.T01: start, decide and weekly report log plain [Topic] lines."""
    with caplog.at_level(logging.INFO):
        new_id, _ = start_hire(home, "setup_review", "expert", "Made Up Two", "claude",
                               "default", TODAY)
        assert new_id is not None
        decide(home, new_id, "reject", NOW)
        WeeklyReportStep(lambda: NOW)(StepContext(1, "evening", NOW, home))
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith(("[Hiring]",
                                                                                  "[Report]"))]
    assert any(ln.startswith("[Hiring] Made Up Two started in shadow") for ln in lines)
    assert any(ln.startswith("[Hiring] Made Up Two: reject") for ln in lines)
    assert any(ln.startswith("[Report] Weekly report for 2026-11-06") for ln in lines)
    assert not any("_" in ln for ln in lines)
