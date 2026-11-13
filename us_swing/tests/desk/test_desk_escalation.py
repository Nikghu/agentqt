"""Tests for the AI Desk v3 M2 parts of MD-DSK-011.015.M29 (core/desk_messages.py), M15
(core/desk_events.py), M21 (core/desk_alerts.py), M22 (core/desk_employee.py), M13 (settings)
and M16 (router expiry).

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.desk.conftest import THU_1500_ET
from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings, save_settings
from us_swing.core.desk_alerts import open_alerts
from us_swing.core.desk_employee import JobSpec, read_employee, render, save_employee
from us_swing.core.desk_events import open_events, post_message
from us_swing.core.desk_messages import (
    MASTER,
    NY,
    Person,
    accept,
    expire_due,
    hand_to_deputy,
    inbox,
    open_started,
)
from us_swing.core.desk_msg import Draft, Verdict
from us_swing.desk.router import Router

NOW = THU_1500_ET
DAY = "2026-11-05"
# analyst -> lead -> chief; helper is the analyst's deputy; loner has no boss
ROSTER = [Person("emp-a", "Ann", "watch_flag", boss="emp-l", deputy="emp-h"),
          Person("emp-l", "Lou", "lead_brief", boss="emp-c"),
          Person("emp-c", "Cy", "chief"),
          Person("emp-h", "Hal", "news_review"),
          Person("emp-n", "Ned", "solo")]
ESC = Draft(type="escalate", to="boss", subject="AAPL plan broken",
            text="AAPL touched its stop at 174.90", about=["AAPL"])
SENT: list[str] = []


def _send(text: str) -> bool:
    SENT.append(text)
    return True


@pytest.fixture(autouse=True)
def _clear_sent() -> None:
    SENT.clear()


def _rows(home: Path, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _id(line: str) -> int:
    assert line.startswith("stored #"), line
    return int(line.removeprefix("stored #"))


def _esc(home: Path, sender: str = "emp-a") -> int:
    return _id(accept(home, [ESC], sender, ROSTER, NOW, DAY, True, _send)[0])


def _msg(home: Path, mid: int) -> tuple[Any, ...]:
    return _rows(home, "SELECT receiver, state, due, meta, handed FROM messages WHERE id = ?",
                 (mid,))[0]


def _ny(moment: datetime) -> str:
    return moment.astimezone(NY).isoformat(timespec="seconds")


def _ask(to: str = "emp-a") -> Draft:
    return Draft(type="ask", to=to, subject="NVDA news", text="Any earnings soon?")


# ── accept: type, boss, master ───────────────────────────────────────────────


def test_escalate_accepted(home: Path) -> None:
    """UT-DSK-011.033.M29.T01: Escalate accepted."""
    mid = _esc(home)
    receiver, state, due, _, _ = _msg(home, mid)
    assert (receiver, state) == ("emp-l", "submitted")
    assert due == _ny(NOW + timedelta(minutes=5))


def test_escalate_when_off(home: Path) -> None:
    """UT-DSK-011.033.M29.T02: Escalate when off."""
    assert accept(home, [ESC], "emp-a", ROSTER, NOW, DAY) == []
    assert not (home / "desk.db").exists() or _rows(home, "SELECT * FROM messages") == []
    hand = Draft(type="handover", to="emp-l", subject="Done", text="All ideas graded")
    assert accept(home, [hand], "emp-a", ROSTER, NOW, DAY, True) == [
        "refused: type handover is not in use yet"]


def test_boss_address(home: Path) -> None:
    """UT-DSK-011.034.M29.T01: Boss address."""
    assert _msg(home, _esc(home))[0] == "emp-l"


def test_no_boss(home: Path) -> None:
    """UT-DSK-011.034.M29.T02: No boss."""
    mid = _esc(home, "emp-n")
    receiver, state, due, meta, _ = _msg(home, mid)
    assert (receiver, state, due) == (MASTER, "input_required", None)
    assert "nobody above" in json.loads(meta)["blocked"]
    assert _rows(home, "SELECT kind, source FROM alerts") == [("escalation", str(mid))]
    assert _rows(home, "SELECT COUNT(*) FROM events WHERE kind = 'message'") == [(0,)]


# ── events: priority and repost key ──────────────────────────────────────────


def test_priority_by_type(home: Path) -> None:
    """UT-DSK-011.035.M15.T01: Priority by type."""
    _esc(home)
    accept(home, [_ask()], "emp-h", ROSTER, NOW, DAY, True)
    assert _rows(home, "SELECT target, priority FROM events WHERE kind = 'message' "
                       "ORDER BY id") == [("emp-l", 0), ("emp-a", 1)]


def test_repost_key(home: Path) -> None:
    """UT-DSK-011.035.M15.T02: Repost key."""
    con = open_events(home)
    with con:
        post_message(con, 7, "emp-a", DAY, NOW)
        post_message(con, 7, "emp-a", DAY, NOW)
        post_message(con, 7, "emp-h", DAY, NOW, again="emp-h")
    con.close()
    assert _rows(home, "SELECT key, target FROM events ORDER BY id") == [
        ("message|7", "emp-a"), ("message|7|emp-h", "emp-h")]


# ── move up ──────────────────────────────────────────────────────────────────


def test_move_up(home: Path) -> None:
    """UT-DSK-011.036.M29.T01: Move up after 5 minutes."""
    mid = _esc(home)
    later = NOW + timedelta(minutes=6)
    expire_due(home, later, ROSTER, _send)
    receiver, state, due, _, _ = _msg(home, mid)
    assert (receiver, state) == ("emp-c", "submitted")
    assert due == _ny(later + timedelta(minutes=5))
    assert [m.id for m in inbox(home, "emp-c")] == [mid]
    assert _rows(home, "SELECT target, priority FROM events WHERE key = ?",
                 (f"message|{mid}|emp-c",)) == [("emp-c", 0)]


def test_no_move_before_due(home: Path) -> None:
    """UT-DSK-011.036.M29.T02: No move before due."""
    mid = _esc(home)
    before = _msg(home, mid)
    expire_due(home, NOW + timedelta(minutes=4), ROSTER, _send)
    assert _msg(home, mid) == before


def test_past_top_boss(home: Path) -> None:
    """UT-DSK-011.036.M29.T03: Past the top boss."""
    mid = _esc(home)
    expire_due(home, NOW + timedelta(minutes=6), ROSTER, _send)
    expire_due(home, NOW + timedelta(minutes=12), ROSTER, _send)
    expire_due(home, NOW + timedelta(minutes=20), ROSTER, _send)
    receiver, state, due, meta, _ = _msg(home, mid)
    assert (receiver, state, due) == (MASTER, "input_required", None)
    assert json.loads(meta)["blocked"] == ("Lou did not answer in 5 minutes; "
                                           "Cy did not answer in 5 minutes")
    assert _rows(home, "SELECT kind FROM alerts") == [("escalation",)]
    assert len(SENT) == 1 and "Escalation not answered" in SENT[0]


def test_router_moves_escalates(home: Path) -> None:
    """UT-DSK-011.036.M16.T01: Router moves escalates."""
    mid = _esc(home)
    router = Router(home, [], lambda *a: "ok", set(), lambda: NOW + timedelta(minutes=6),
                    roster=ROSTER, send=_send)
    router.has_work()
    assert _msg(home, mid)[0] == "emp-c"


def test_move_writes_reason(home: Path) -> None:
    """UT-DSK-011.037.M29.T01: Move writes reason."""
    mid = _esc(home)
    expire_due(home, NOW + timedelta(minutes=6), ROSTER, _send)
    assert json.loads(_msg(home, mid)[3])["blocked"] == "Lou did not answer in 5 minutes"
    assert _rows(home, "SELECT msgs FROM threads WHERE id = ?", (mid,)) == [(2,)]


def test_thread_full(home: Path) -> None:
    """UT-DSK-011.037.M29.T02: Thread full."""
    mid = _esc(home)
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("UPDATE threads SET msgs = 6 WHERE id = ?", (mid,))
    con.close()
    expire_due(home, NOW + timedelta(minutes=6), ROSTER, _send)
    assert _msg(home, mid)[:2] == (MASTER, "input_required")


# ── day cap ──────────────────────────────────────────────────────────────────


def _fill_day(home: Path, asks: int, escalates: int) -> None:
    """Messages emp-a started today, written straight into the table."""
    accept(home, [_ask("emp-l")], "emp-h", ROSTER, NOW, DAY)  # makes the tables
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("DELETE FROM messages")
        for kind, n in (("ask", asks), ("escalate", escalates)):
            for _ in range(n):
                con.execute("INSERT INTO messages (thread, type, sender, receiver, at, state, "
                            "body, data_day) VALUES (0, ?, 'emp-a', 'emp-l', ?, 'completed', "
                            "'{}', ?)", (kind, _ny(NOW), DAY))
    con.close()


def test_escalate_free_of_day_cap(home: Path) -> None:
    """UT-DSK-011.038.M29.T01: Escalate free of day cap."""
    _fill_day(home, 20, 0)
    assert accept(home, [_ask("emp-l")], "emp-a", ROSTER, NOW, DAY, True)[0].startswith(
        "refused")
    assert accept(home, [ESC], "emp-a", ROSTER, NOW, DAY, True, _send)[0].startswith("stored")


def test_escalates_not_counted(home: Path) -> None:
    """UT-DSK-011.038.M29.T02: Escalates not counted."""
    _fill_day(home, 19, 3)
    lines = accept(home, [_ask("emp-l"), _ask("emp-c")], "emp-a", ROSTER, NOW, DAY, True)
    assert lines[0].startswith("stored") and lines[1].startswith("refused")


# ── replies to escalates ─────────────────────────────────────────────────────


def test_reply_wakes_nobody(home: Path) -> None:
    """UT-DSK-011.040.M29.T01: Reply wakes nobody."""
    mid = _esc(home)
    reply = Draft(type="reply", parent=mid, verdict=Verdict(result="dropped", reason="Off"),
                  text="Take AAPL off today")
    assert accept(home, [reply], "emp-l", ROSTER, NOW, DAY, True)[0].startswith("stored")
    assert _msg(home, mid)[1] == "failed"
    assert _rows(home, "SELECT COUNT(*) FROM events WHERE target = 'emp-a'") == [(0,)]
    assert inbox(home, "emp-a") == [] and not open_started(home, "emp-a")


# ── deputy ───────────────────────────────────────────────────────────────────


def test_hand_to_deputy(home: Path) -> None:
    """UT-DSK-011.041.M29.T01: Hand to deputy."""
    mid = _id(accept(home, [_ask("emp-a")], "emp-l", ROSTER, NOW, DAY)[0])
    left = hand_to_deputy(home, inbox(home, "emp-a"), ROSTER[0], ROSTER, "news is old", NOW)
    assert left == []
    receiver, state, _, meta, handed = _msg(home, mid)
    assert (receiver, state, handed) == ("emp-h", "submitted", "emp-a")
    assert "Ann could not work (news is old); sent to deputy Hal" in json.loads(meta)["blocked"]
    assert [m.id for m in inbox(home, "emp-h")] == [mid]
    assert _rows(home, "SELECT COUNT(*) FROM events WHERE key = ?",
                 (f"message|{mid}|emp-h",)) == [(1,)]


def test_no_deputy_or_handed_once(home: Path) -> None:
    """UT-DSK-011.041.M29.T02: No deputy or handed once."""
    mid = _id(accept(home, [_ask("emp-l")], "emp-h", ROSTER, NOW, DAY)[0])
    rows = inbox(home, "emp-l")
    assert hand_to_deputy(home, rows, ROSTER[1], ROSTER, "asleep", NOW) == rows  # no deputy
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("UPDATE messages SET handed = 'emp-x' WHERE id = ?", (mid,))
    con.close()
    lou = Person("emp-l", "Lou", "lead_brief", deputy="emp-c")
    assert [m.id for m in hand_to_deputy(home, inbox(home, "emp-l"), lou, ROSTER, "asleep",
                                         NOW)] == [mid]
    assert _msg(home, mid)[0] == "emp-l"


# ── settings, alert, employee file ───────────────────────────────────────────


def test_escalation_setting(home: Path) -> None:
    """UT-DSK-011.042.M13.T01: Setting saved and read."""
    assert load_settings(home).escalation_on is False
    save_settings(DeskAiSettings(escalation_on=True), home)
    assert load_settings(home).escalation_on is True


def test_escalation_logs(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-011.043.M29.T01: Escalation logs."""
    with caplog.at_level(logging.INFO):
        mid = _esc(home)
        expire_due(home, NOW + timedelta(minutes=6), ROSTER, _send)
        expire_due(home, NOW + timedelta(minutes=12), ROSTER, _send)
        ask = _id(accept(home, [_ask("emp-a")], "emp-l", ROSTER, NOW, DAY)[0])
        hand_to_deputy(home, inbox(home, "emp-a"), ROSTER[0], ROSTER, "asleep", NOW)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("[Messages]")]
    assert "[Messages] An escalation from Ann moved up to Cy" in lines
    assert "[Messages] An escalation from Ann reached the Master user" in lines
    assert "[Messages] 1 message(s) for Ann went to the deputy Hal" in lines
    assert mid and ask and not any("emp-" in x or "_" in x for x in lines)


def test_escalation_alert(home: Path) -> None:
    """UT-DSK-007.011.M21.T01: Escalation alert."""
    from us_swing.core.desk_alerts import raise_alert

    assert raise_alert(home, "escalation", "5", 0, "Ann: AAPL", NOW, _send) is not None
    assert raise_alert(home, "escalation", "5", 0, "Ann: AAPL", NOW, _send) is None
    alerts = open_alerts(home, NOW + timedelta(hours=3))
    assert [(a.kind, a.title) for a in alerts] == [("escalation", "Escalation not answered")]


def _employee(home: Path, emp_id: str) -> None:
    folder = home / "employees" / emp_id
    folder.mkdir(parents=True)
    (folder / "employee.md").write_text(f"""---
id: {emp_id}
name: Emp {emp_id}
title: Test helper
level: expert
reports_to: null
skill: news_review
version: 1
trigger: after_run
models:
  primary: {{source: openrouter, model: m}}
  backup: {{source: claude, model: default}}
calls_per_day: 20
monthly_cost_usd: 3.0
kpis: [valid answers]
---
You are {{name}}.
""", encoding="utf-8")


def test_deputy_saved(home: Path) -> None:
    """UT-DSK-008.010.M22.T01: Deputy saved."""
    _employee(home, "emp-1")
    _employee(home, "emp-9")
    assert save_employee(home, "emp-1", {"deputy": "emp-9"}, "You are {name}.") == ""
    emp = read_employee(home / "employees" / "emp-1")
    assert emp is not None and emp.spec.deputy == "emp-9"
    spec = JobSpec.model_validate(emp.spec.model_dump() | {"deputy": None})
    assert "deputy" not in render(spec, "x")


def test_bad_deputy(home: Path) -> None:
    """UT-DSK-008.010.M22.T02: Bad deputy."""
    _employee(home, "emp-1")
    assert save_employee(home, "emp-1", {"deputy": "emp-1"}, "x") == (
        "the deputy cannot be the employee itself")
    assert save_employee(home, "emp-1", {"deputy": "emp-999"}, "x") == (
        "no employee emp-999 for deputy")
