"""Tests for MD-MKT-010.001.M01 (core/desk_chat.py), MD-MKT-010.002.M02 (chat event),
MD-MKT-010.003.M03 (lead chat skill) and MD-MKT-010.007.M04 (default chat employee).
Employee names here are made up."""
from __future__ import annotations

import importlib
import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel, ValidationError

import tests.desk.test_harness as th
from tests.market.test_desk_results import _four
from us_swing.core.desk_employee import load
from us_swing.core import desk_chat as dc
from us_swing.core.desk_contract import DB_NAME, StepContext
from us_swing.core.desk_events import post_event
from us_swing.core.desk_steps import SKILL_PATHS
from us_swing.data.market_calendar import ET
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.market import lead_chat as lc

T = TypeVar("T", bound=BaseModel)
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=ET)
EMP = Path(lc.__file__).parent / "employees" / "emp-008"


def _q(home: Path, sql: str) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(home / DB_NAME)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


class _Ctx:
    def __init__(self, home: Path, reply: str | None, extra: dict[str, Any] | None = None) -> None:
        self.home, self._reply, self._extra = home, reply, extra or {}

    def ask(self, facts: str, schema: type[T]) -> T | None:
        if self._reply is None:
            return None
        return schema.model_validate({"answer": self._reply, **self._extra})


def _skill(now: datetime = NOW) -> lc.LeadChatSkill:
    return lc.LeadChatSkill(Path("missing-candles.db"), lambda: now)


def test_question_saved(tmp_path: Path) -> None:
    """UT-MKT-010.001.M01.T01: a question adds one master row and one waiting event."""
    qid = dc.ask_question(tmp_path, "  Why AAPL?  ", NOW)
    assert _q(tmp_path, "SELECT id, role, text, state FROM chat") == [(qid, "master", "Why AAPL?", "asked")]
    assert _q(tmp_path, "SELECT kind, state FROM events") == [("chat_question", "waiting")]


def test_bad_question(tmp_path: Path) -> None:
    """UT-MKT-010.001.M01.T02: empty or too long questions are refused."""
    for text in ("   ", "x" * 501):
        with pytest.raises(ValueError):
            dc.ask_question(tmp_path, text, NOW)
    assert not (tmp_path / DB_NAME).exists() or _q(tmp_path, "SELECT * FROM chat") == []


def test_notes_and_turns(tmp_path: Path) -> None:
    """UT-MKT-010.001.M01.T03: waiting, start, expired and replied notes; turns oldest first."""
    qid = dc.ask_question(tmp_path, "Why?", NOW)
    assert dc.question_note(tmp_path, qid, NOW, True) == dc.WAITING
    assert dc.question_note(tmp_path, qid, NOW, False) == dc.START_DESK
    assert dc.question_note(tmp_path, qid, NOW + timedelta(minutes=31), True) == dc.EXPIRED
    dc.add_reply(tmp_path, qid, "Because.", True, NOW)
    assert dc.question_note(tmp_path, qid, NOW, True) == ""
    assert [(t.role, t.text) for t in dc.chat_turns(tmp_path)] == [("master", "Why?"),
                                                                    ("lead", "Because.")]


def test_append_only(tmp_path: Path) -> None:
    """UT-MKT-010.001.M01.T04: chat rows never change."""
    dc.ask_question(tmp_path, "Why?", NOW)
    con = sqlite3.connect(tmp_path / DB_NAME)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE chat SET text = 'x'")
    finally:
        con.close()


def test_one_event_per_question(tmp_path: Path) -> None:
    """UT-MKT-010.002.M02.T01: two questions give two priority-0 events with their limits."""
    dc.ask_question(tmp_path, "One?", NOW)
    dc.ask_question(tmp_path, "Two?", NOW)
    rows = _q(tmp_path, "SELECT priority, created, deadline, expires FROM events")
    assert len(rows) == 2
    for prio, created, deadline, expires in rows:
        start = datetime.fromisoformat(created)
        assert prio == 0
        assert datetime.fromisoformat(deadline) - start == timedelta(minutes=2)
        assert datetime.fromisoformat(expires) - start == timedelta(minutes=30)


def test_unknown_kind(tmp_path: Path) -> None:
    """UT-MKT-010.002.M02.T02: an unknown event kind is still refused."""
    with pytest.raises(ValueError):
        post_event(tmp_path, "chat_answer", "2026-11-07", NOW)


def test_desk_answers_end_to_end(tmp_path: Path) -> None:
    """UT-MKT-010.002.M02.T03: the desk wakes the chat employee and saves its reply."""
    home = tmp_path / "desk"
    th.employee(home, "c-1", th.job("c-1", "Chat Person", "lead", "lead_chat")
                .replace("trigger: after_run", "trigger: chat_question"))
    qid = dc.ask_question(home, "What is the regime?", datetime.now(ET))
    caller = th.FakeCaller(Reply(json.dumps({"answer": "Calm, from the facts."}), 100, 20, 0.0))
    step = EmployeesStep(lambda: {"lead_chat": "us_swing.market.lead_chat:LeadChatSkill"},
                         lambda: [], lambda: th.ON, lambda: "key", caller)
    assert step.has_work(home)
    step.handle_events(StepContext(1, "event", datetime.now(ET), home))
    assert _q(home, "SELECT role, text, reply_to, state FROM chat WHERE role = 'lead'") == [
        ("lead", "Calm, from the facts.", qid, "answered")]
    assert f"Question #{qid}: What is the regime?" in caller.calls[0][3]


def test_chat_facts(tmp_path: Path) -> None:
    """UT-MKT-010.003.M03.T01: facts hold the question, the recent chat, today and the picks."""
    _four(tmp_path)
    first = dc.ask_question(tmp_path, "Earlier?", NOW)
    dc.add_reply(tmp_path, first, "Earlier answer.", True, NOW)
    qid = dc.ask_question(tmp_path, "Why TGT?", NOW)
    facts = _skill().facts(tmp_path)
    assert facts.fresh
    for part in (f"Question #{qid}: Why TGT?", "Master: Earlier?", "Lead: Earlier answer.",
                 "Today (", "2026-11-06 long TGT: waiting, paper target, R 2.0"):
        assert part in facts.text


def test_nothing_to_answer(tmp_path: Path) -> None:
    """UT-MKT-010.003.M03.T02: no question, or only an old one, keeps the employee asleep."""
    assert not _skill().facts(tmp_path).fresh
    dc.ask_question(tmp_path, "Old?", NOW)
    assert not _skill(NOW + timedelta(minutes=31)).facts(tmp_path).fresh


def test_oldest_first(tmp_path: Path) -> None:
    """UT-MKT-010.003.M03.T03: the older open question is answered first."""
    older = dc.ask_question(tmp_path, "First?", NOW)
    dc.ask_question(tmp_path, "Second?", NOW)
    skill = _skill()
    facts = skill.facts(tmp_path)
    assert f"Question #{older}: First?" in facts.text
    skill.act(_Ctx(tmp_path, "One."), facts)
    assert _q(tmp_path, "SELECT reply_to FROM chat WHERE role = 'lead'") == [(older,)]


def test_answer_saved(tmp_path: Path) -> None:
    """UT-MKT-010.004.M03.T01: a valid answer is saved as a lead reply to the question."""
    qid = dc.ask_question(tmp_path, "Why?", NOW)
    skill = _skill()
    assert skill.act(_Ctx(tmp_path, "Because ..."), skill.facts(tmp_path)) == []
    assert _q(tmp_path, "SELECT text, reply_to, state FROM chat WHERE role = 'lead'") == [
        ("Because ...", qid, "answered")]


def test_answer_too_long() -> None:
    """UT-MKT-010.004.M03.T02: an answer over 1500 characters or with extra fields is refused."""
    with pytest.raises(ValidationError):
        lc.LeadChatAnswer.model_validate({"answer": "x" * 1501})
    with pytest.raises(ValidationError):
        lc.LeadChatAnswer.model_validate({"answer": "ok", "action": "reject"})


def test_no_answer(tmp_path: Path) -> None:
    """UT-MKT-010.005.M03.T01: without a valid answer a failed reply is saved."""
    dc.ask_question(tmp_path, "Why?", NOW)
    skill = _skill()
    skill.act(_Ctx(tmp_path, None), skill.facts(tmp_path))
    assert _q(tmp_path, "SELECT text, state FROM chat WHERE role = 'lead'") == [
        (lc.FAILED_TEXT, "failed")]


def test_answers_only() -> None:
    """UT-MKT-010.006.M03.T01: the answer has one text field and the skill has no trade code."""
    assert list(lc.LeadChatAnswer.model_fields) == ["answer"]
    text = Path(lc.__file__).read_text(encoding="utf-8")
    for word in ("record_trade_decision", "send_desk_pick", "pending", "place_order", "approvals"):
        assert word not in text


def test_default_chat_employee() -> None:
    """UT-MKT-010.007.M04.T01: emp-008 is a lead-level chat employee and the skill loads."""
    spec = load(EMP).spec.model_dump(mode="json")
    assert (spec["id"], spec["level"], spec["skill"], spec["trigger"], spec["calls_per_day"]) == (
        "emp-008", "lead", "lead_chat", ["chat_question"], 200)
    module, _, cls = SKILL_PATHS["lead_chat"].partition(":")
    assert getattr(importlib.import_module(module), cls)().key == "lead_chat"


def test_no_real_names() -> None:
    """UT-MKT-010.007.M04.T02: generic name only, and market does not import desk."""
    assert load(EMP).spec.model_dump(mode="json")["name"] == "Lead 2"
    assert "{name}" in load(EMP).prompt
    src = Path(lc.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import) us_swing\.desk\b", src, re.M)


def test_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-010.008.M03.T01: answer and failure log lines carry the question numbers."""
    one = dc.ask_question(tmp_path, "One?", NOW)
    two = dc.ask_question(tmp_path, "Two?", NOW)
    skill = _skill()
    with caplog.at_level(logging.INFO, logger="us_swing.market.lead_chat"):
        skill.act(_Ctx(tmp_path, "Yes."), skill.facts(tmp_path))
        skill.act(_Ctx(tmp_path, None), skill.facts(tmp_path))
    assert f"[Chat] Question {one} answered in" in caplog.text
    assert f"[Chat] Question {two} got no answer" in caplog.text
