"""Tests for MD-MKT-020.007.M04 — meetings in core/desk_messages.py (AI Desk v3 M5)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from tests.desk.conftest import THU_1500_ET
from us_swing.core.desk_messages import (
    Person,
    accept,
    expire_due,
    inbox,
    mark_seen,
    open_started,
)
from us_swing.core.desk_msg import Draft, Verdict

NOW = THU_1500_ET
DAY = "2026-11-05"
ROSTER = [Person("emp-l", "Lee", "lead_brief"), Person("emp-r", "Ray", "regime_view"),
          Person("emp-s", "Sam", "sector_flow_view"), Person("emp-t", "Tia", "setup_review"),
          Person("emp-u", "Uma", "news_review")]
MEETING = Draft(type="meeting", to="skill:regime_view,skill:sector_flow_view",
                subject="Huddle: views clash", text="Regime says Downtrend but sector favours Tech.")


def _rows(home: Path, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _meet(home: Path, draft: Draft = MEETING) -> list[str]:
    return accept(home, [draft], "emp-l", ROSTER, NOW, DAY, meetings=True)


def _reply(parent: int) -> Draft:
    return Draft(type="reply", parent=parent, verdict=Verdict(result="done"),
                 text="Breadth fell 4 days in a row.")


def _meeting_ids(home: Path) -> list[int]:
    return [int(r[0]) for r in _rows(home, "SELECT id FROM messages WHERE type = 'meeting' "
                                     "ORDER BY id")]


def test_meeting_rows(tmp_path: Path) -> None:
    """UT-MKT-020.007.M04.T01: One row per receiver in one thread, due in 10 minutes."""
    out = _meet(tmp_path)
    assert out[0].startswith("stored #")
    rows = _rows(tmp_path, "SELECT thread, receiver, due, state FROM messages ORDER BY id")
    assert [r[1] for r in rows] == ["emp-r", "emp-s"]
    assert len({r[0] for r in rows}) == 1
    assert all(datetime.fromisoformat(r[2]) == NOW + timedelta(minutes=10) for r in rows)
    assert all(r[3] == "submitted" for r in rows)
    assert _rows(tmp_path, "SELECT msgs FROM threads") == [(2,)]
    events = _rows(tmp_path, "SELECT target FROM events WHERE kind = 'message' ORDER BY id")
    assert [e[0] for e in events] == ["emp-r", "emp-s"]


def test_meetings_off(tmp_path: Path) -> None:
    """UT-MKT-020.007.M04.T02: With meetings off a meeting is refused."""
    out = accept(tmp_path, [MEETING], "emp-l", ROSTER, NOW, DAY)
    assert out == ["refused: type meeting is not in use yet"]


def test_bad_receiver_list(tmp_path: Path) -> None:
    """UT-MKT-020.007.M04.T03: The sender, a repeat or four receivers are refused."""
    for to in ("emp-l,emp-r", "emp-r,skill:regime_view",
               "emp-r,emp-s,emp-t,emp-u"):
        out = _meet(tmp_path, Draft(type="meeting", to=to, subject="Huddle", text="Clash"))
        assert out[0].startswith("refused:"), to
    assert _rows(tmp_path, "SELECT COUNT(*) FROM messages") == [(0,)]


def test_starter_waits(tmp_path: Path) -> None:
    """UT-MKT-020.007.M04.T04: The sender waits while a meeting is open and its replies unread."""
    _meet(tmp_path)
    assert open_started(tmp_path, "emp-l")
    first, second = _meeting_ids(tmp_path)
    accept(tmp_path, [_reply(first)], "emp-r", ROSTER, NOW, DAY, meetings=True)
    accept(tmp_path, [_reply(second)], "emp-s", ROSTER, NOW, DAY, meetings=True)
    replies = [int(r[0]) for r in _rows(tmp_path, "SELECT id FROM messages WHERE type = "
                                        "'reply'")]
    assert open_started(tmp_path, "emp-l")  # replies not read yet
    mark_seen(tmp_path, replies, NOW)
    assert not open_started(tmp_path, "emp-l")


def test_reply_closes(tmp_path: Path) -> None:
    """UT-MKT-020.008.M04.T01: Each reply closes its meeting; the thread closes after both."""
    _meet(tmp_path)
    first, second = _meeting_ids(tmp_path)
    assert accept(tmp_path, [_reply(first)], "emp-r", ROSTER, NOW, DAY,
                  meetings=True)[0].startswith("stored #")
    assert _rows(tmp_path, "SELECT state FROM threads") == [("open",)]
    accept(tmp_path, [_reply(second)], "emp-s", ROSTER, NOW, DAY, meetings=True)
    states = _rows(tmp_path, "SELECT state FROM messages WHERE type = 'meeting'")
    assert states == [("completed",), ("completed",)]
    assert _rows(tmp_path, "SELECT state FROM threads") == [("closed",)]


def test_meeting_expiry(tmp_path: Path) -> None:
    """UT-MKT-020.008.M04.T02: An unanswered meeting expires after 10 minutes."""
    _meet(tmp_path)
    assert expire_due(tmp_path, NOW + timedelta(minutes=11), ROSTER) == 2
    assert _rows(tmp_path, "SELECT DISTINCT state FROM messages WHERE type = 'meeting'") == [
        ("expired",)]
    bodies = _rows(tmp_path, "SELECT body FROM messages WHERE type = 'reply'")
    assert all("no reply within 10 minutes" in b[0] for b in bodies)


def test_no_send_back_to_meeting(tmp_path: Path) -> None:
    """UT-MKT-020.008.M04.T03: A send-back cannot answer a meeting."""
    _meet(tmp_path)
    first = _meeting_ids(tmp_path)[0]
    draft = Draft(type="send_back", parent=first, verdict=Verdict(result="fix", reason="why"),
                  text="Fix this")
    out = accept(tmp_path, [draft], "emp-r", ROSTER, NOW, DAY, meetings=True)
    assert out[0].startswith("refused:")


def test_closed_meeting_not_in_inbox(tmp_path: Path) -> None:
    """UT-MKT-020.008.M04.T04: An expired meeting no longer wakes its receiver."""
    _meet(tmp_path)
    assert [m.type for m in inbox(tmp_path, "emp-r")] == ["meeting"]
    expire_due(tmp_path, NOW + timedelta(minutes=11), ROSTER)
    assert inbox(tmp_path, "emp-r") == []
