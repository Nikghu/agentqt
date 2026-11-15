"""Tests for AI Desk v3 M6 table asks in the lead chat: MD-MKT-010.001.M01
(core/desk_chat.py ``table_text``) and MD-MKT-010.003.M03 (market/lead_chat.py).

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

import tests.desk.test_harness as th
from tests.desk import task_support as ts
from tests.market.test_lead_chat_sessions import NOW, _Ctx, _new, _replied, _rows, _skill, _Talk
from us_swing.core import desk_chat as dc
from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_messages import Person, accept, inbox
from us_swing.core.desk_msg import Data, Draft, Verdict, Want
from us_swing.core.desk_registry import fill_registry
from us_swing.core.desk_tasks import fill_plans
from us_swing.data.market_calendar import ET
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.market import lead_chat as lc

DAY = "2026-11-07"
ROSTER = [Person("lead", "Lead", "lead_chat"), Person("plan", "Maker", "task_planner")]
FORMAT_LINE = ("- setup_table.v1: symbol, close, rs_rank, atr_pct, side, setup, trigger, stop, "
               "earn_days")


def _on(home: Path, cards: bool = True, plans: bool = True, planner: bool = True) -> None:
    save_settings(DeskAiSettings(sessions_on=True, messages_on=True, task_cards_on=cards), home)
    if plans:
        fill_registry(home, NOW)
        fill_plans(home, NOW)
    if planner:
        th.employee(home, "p-1", th.job("p-1", "Maker", "champion", "task_planner"))


def _facts_seen(home: Path) -> str:
    sid = _new(home)
    dc.ask_question(home, "Tech?", NOW, session=sid)
    ctx = _Talk(home, [])
    skill = _skill()
    skill.act(ctx, skill.facts(home))
    return ctx.facts_seen


def _body(**data: Any) -> dict[str, Any]:
    return {"type": "reply", "verdict": {"result": "done"},
            "data": {"schema": "setup_table.v1", **data}}


# ── table hint (SRD-MKT-010.020) ─────────────────────────────────────────────


def test_table_hint(tmp_path: Path) -> None:
    """UT-MKT-010.020.M03.T01: Table hint."""
    _on(tmp_path)
    seen = _facts_seen(tmp_path)
    assert lc.ASK_HINT in seen and lc.TABLE_HINT in seen
    assert '"skill:task_planner"' in seen and FORMAT_LINE in seen
    assert seen.index(lc.ASK_HINT) < seen.index(lc.TABLE_HINT)


def test_no_hint_when_off(tmp_path: Path) -> None:
    """UT-MKT-010.020.M03.T02: No hint when off."""
    off, bare, alone = tmp_path / "off", tmp_path / "bare", tmp_path / "alone"
    _on(off, cards=False)
    _on(bare, plans=False)
    _on(alone, planner=False)
    for home in (off, bare, alone):
        assert lc.table_hint(home) == ""
        seen = _facts_seen(home)
        assert lc.ASK_HINT in seen and lc.TABLE_HINT not in seen


# ── table text (SRD-MKT-010.021) ─────────────────────────────────────────────


def test_table_text(tmp_path: Path) -> None:
    """UT-MKT-010.021.M01.T01: Table text."""
    body = _body(cols=["symbol", "close", "earn_days"],
                 rows=[["AAA", 10.5, 3], ["BBB", 20.0, None]],
                 nulls={"BBB.earn_days": "no earnings date found", "BBB.trigger": "no setup",
                        "AAA.trigger": "no setup"})
    body["flags"] = [{"about": "AAA", "note": "earnings in 3 trading days"}]
    assert dc.table_text(tmp_path, body).split("\n") == [
        "symbol | close | earn_days",
        "AAA | 10.5 | 3",
        "BBB | 20 | -",
        "Missing (no earnings date found): BBB earn_days",
        "Missing (no setup): BBB trigger, AAA trigger",
        "Note: AAA: earnings in 3 trading days"]
    fill_registry(tmp_path, NOW)
    whole = dc.table_text(tmp_path, _body(rows=[["AAA", 1.0, 80, 2.5, "long", "flag", 2.0, 1.5,
                                                 4]]))
    assert whole.split("\n")[0] == FORMAT_LINE.removeprefix("- setup_table.v1: ").replace(
        ", ", " | ")


def test_partial_and_many_reasons(tmp_path: Path) -> None:
    """UT-MKT-010.021.M01.T02: Partial and many reasons."""
    body = _body(cols=["symbol", "close"], rows=[["AAA", 10.5]],
                 nulls={f"K{n}": f"reason {n}" for n in range(12)})
    body["verdict"] = {"result": "partial", "reason": "Calendar tools failed: timed out"}
    lines = dc.table_text(tmp_path, body).split("\n")
    assert lines[0] == "Partial: Calendar tools failed: timed out"
    assert [line for line in lines if line.startswith("Missing (")] == [
        f"Missing (reason {n}): K{n}" for n in range(10)]
    assert lines[-1] == "... and 2 more"


def test_text_reply_has_no_table(tmp_path: Path) -> None:
    """UT-MKT-010.021.M01.T03: Text reply has no table."""
    text_only = {"type": "reply", "verdict": {"result": "done"}, "text": "Calm."}
    refused = {"type": "reply", "verdict": {"result": "refused", "reason": "not my area"}}
    by_ref = _body(ref="cards/12", n=500)
    for body in (text_only, refused, by_ref):
        assert dc.table_text(tmp_path, body) == ""


# ── update written by code (SRD-MKT-010.021) ─────────────────────────────────


def test_update_by_code(tmp_path: Path) -> None:
    """UT-MKT-010.021.M03.T01: Update by code."""
    _on(tmp_path)
    qid = _replied(tmp_path)
    want = Want(goal="table", done_when="table sent", inputs={"symbols": ["AAA"]},
                schema="setup_table.v1")
    ask = Draft(type="ask", to="skill:task_planner", subject=dc.team_subject(qid), want=want)
    assert accept(tmp_path, [ask], "lead", ROSTER, NOW, DAY)[0].startswith("stored")
    data = Data.model_validate({"schema": "setup_table.v1", "cols": ["symbol", "rs_rank"],
                                "rows": [["AAA", 91]]})
    reply = Draft(type="reply", parent=inbox(tmp_path, "plan")[0].id,
                  verdict=Verdict(result="done"), data=data)
    assert accept(tmp_path, [reply], "plan", ROSTER, NOW, DAY)[0].startswith("stored")
    ctx = _Ctx(tmp_path)
    skill = _skill()
    skill.act(ctx, skill.facts(tmp_path))
    assert _rows(tmp_path, "SELECT role, text, reply_to FROM chat WHERE role = 'update'") == [
        ("update", "symbol | rs_rank\nAAA | 91", qid)]
    assert ctx.asked == []


def test_chat_question_to_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-010.021.M03.T02: Chat question to table."""
    home = tmp_path / "desk"
    ts.prepare(home, monkeypatch)
    th.employee(home, "c-1", th.job("c-1", "Chat Person", "lead", "lead_chat")
                .replace("trigger: after_run", "trigger: chat_question"))
    now = datetime.now(ET)
    sid = dc.session_for(home, now, None, "Table?", new=True)
    qid = dc.ask_question(home, "Show RS and earnings days for AVGO and MU", now, session=sid)
    answer = {"answer": "I asked the planner for the table.", "messages": [{
        "type": "ask", "to": "skill:task_planner", "subject": "table",
        "want": {"goal": "table", "done_when": "table sent",
                 "inputs": {"symbols": ["AVGO", "MU"]}, "schema": "setup_table.v1",
                 "cols": ["rs_rank", "earn_days"]}}]}
    caller = th.FakeCaller(Reply(json.dumps(answer), 100, 20, 0.0))
    step = EmployeesStep(lambda: {"lead_chat": "us_swing.market.lead_chat:LeadChatSkill",
                                  "task_planner": "us_swing.desk.planner:TaskPlannerSkill"},
                         lambda: [], lambda: ts.SETTINGS, lambda: "key", caller,
                         lambda: datetime.now(ET))
    step.handle_events(StepContext(1, "event", datetime.now(ET), home))
    turns = _rows(home, "SELECT role, text, reply_to FROM chat ORDER BY id")
    assert [t[0] for t in turns] == ["master", "lead", "update"]
    assert turns[1] == ("lead", "I asked the planner for the table.", qid)
    assert turns[2] == ("update", "symbol | rs_rank | earn_days\nAVGO | 80 | 12\nMU | 81 | 12",
                        qid)
    assert len(caller.calls) == 1
    assert _rows(home, "SELECT type, sender, receiver, state FROM messages ORDER BY id") == [
        ("ask", "c-1", ts.PLANNER, "completed"), ("reply", ts.PLANNER, "c-1", "completed")]
    assert dc.question_note(home, qid, datetime.now(ET), True) == ""
