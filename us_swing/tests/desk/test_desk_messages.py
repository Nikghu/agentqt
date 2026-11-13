"""Tests for MD-DSK-011.015.M29 — core/desk_messages.py, plus the M1 parts of M27 and M13."""
from __future__ import annotations

import logging
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.desk.conftest import THU_1500_ET
from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings, save_settings
from us_swing.core.desk_messages import (
    Person,
    accept,
    expire_due,
    inbox,
    inbox_text,
    mark_seen,
    messages_of,
    open_started,
    read_message,
    refuse_inbox,
    thread_rows,
)
from us_swing.core.desk_msg import Data, Draft, Verdict, load, with_messages
from us_swing.core.desk_registry import fill_registry

NOW = THU_1500_ET
DAY = "2026-11-05"
ROSTER = [Person("emp-a", "Ann", "setup_review"), Person("emp-b", "Bob", "news_review"),
          Person("emp-c", "Cid", "risk_check"), Person("emp-d", "Dee", "news_review")]
ASK = Draft(type="ask", to="skill:news_review", about=["NVDA"], subject="NVDA news",
            text="Any earnings in the next 5 days?")


def _rows(home: Path, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _reply(parent: int, result: str = "done", **kw: Any) -> Draft:
    return Draft(type="reply", parent=parent,
                 verdict=Verdict(result=result, reason=kw.pop("reason", None)),
                 text=kw.pop("text", "Earnings on Thursday."), **kw)


def _id(line: str) -> int:
    assert line.startswith("stored #"), line
    return int(line.removeprefix("stored #"))


def _ask(home: Path, sender: str = "emp-a", draft: Draft = ASK) -> int:
    return _id(accept(home, [draft], sender, ROSTER, NOW, DAY)[0])


# ── M27: send_back rule and drafts ───────────────────────────────────────────


def _msg(body: dict[str, Any], **head: Any) -> dict[str, Any]:
    return {"id": 2, "thread": 1, "sender": "emp-c", "at": "2026-11-05T15:00:00-05:00",
            "state": "submitted", "body": body, **head}


SEND_BACK = {"type": "send_back", "verdict": {"result": "fix", "reason": "Stop 11.4%"}}


def test_first_send_back() -> None:
    """UT-DSK-011.003.M27.T03: First send-back starts a thread."""
    assert load(_msg(SEND_BACK, to="emp-a")).parent is None


def test_send_back_parent_or_to() -> None:
    """UT-DSK-011.003.M27.T04: Send-back needs parent or to."""
    for head in ({"to": "emp-a", "parent": 1}, {}):
        with pytest.raises(ValidationError):
            load(_msg(SEND_BACK, **head))


def test_send_back_with_parent() -> None:
    """UT-DSK-011.004.M27.T03: Send-back with a parent has no to."""
    assert load(_msg(SEND_BACK, parent=5)).to is None


def test_to_on_answering_send_back() -> None:
    """UT-DSK-011.004.M27.T04: To on an answering send-back."""
    with pytest.raises(ValidationError):
        load(_msg(SEND_BACK, parent=5, to="emp-a"))


def test_answer_with_messages() -> None:
    """UT-DSK-011.016.M27.T01: Answer with messages."""
    from us_swing.market.setup_review import SetupReview

    first, second = with_messages(SetupReview), with_messages(SetupReview)
    assert first is second and issubclass(first, SetupReview)
    assert {"grades", "messages"} <= set(first.model_fields)


def test_too_many_drafts() -> None:
    """UT-DSK-011.016.M27.T02: Too many drafts."""
    from us_swing.market.setup_review import SetupReview

    grade = {"side": "long", "symbol": "NVDA", "grade": "A", "note": "Clean flag"}
    with pytest.raises(ValidationError):
        with_messages(SetupReview).model_validate(
            {"grades": [grade], "messages": [ASK.model_dump(exclude_none=True)] * 6})


# ── M29: store, types, receivers, check order ────────────────────────────────


def test_store_and_read_back(home: Path) -> None:
    """UT-DSK-011.015.M29.T01: Store and read back."""
    mid = _ask(home)
    assert _rows(home, "SELECT COUNT(*) FROM messages") == [(1,)]
    assert _rows(home, "SELECT id, starter, msgs, rounds, state FROM threads") == [
        (mid, "emp-a", 1, 0, "open")]
    msg = read_message(home, mid)
    assert msg is not None and msg.to == "emp-b" and msg.type == "ask"
    assert load(msg.model_dump(mode="json")) == msg


def test_no_database(home: Path) -> None:
    """UT-DSK-011.015.M29.T02: No database."""
    assert read_message(home, 1) is None and thread_rows(home, DAY) == []
    assert messages_of(home, 1) == [] and inbox(home, "emp-a") == []
    assert not open_started(home, "emp-a") and expire_due(home, NOW) == 0
    assert not (home / "desk.db").exists()


def test_one_writer() -> None:
    """UT-DSK-011.014.M29.T01: One writer."""
    src = Path(__file__).parents[2] / "src" / "us_swing"
    writers = sorted(p.name for p in src.rglob("*.py")
                     if any(w in p.read_text(encoding="utf-8") for w in
                            ("INSERT INTO messages", "UPDATE messages", "INSERT INTO threads",
                             "UPDATE threads")))
    assert writers == ["desk_messages.py"]


def test_m1_types(home: Path) -> None:
    """UT-DSK-011.017.M29.T01: M1 types."""
    mid = _ask(home)
    lines = accept(home, [_reply(mid)], "emp-b", ROSTER, NOW, DAY)
    back = Draft(type="send_back", to="emp-a", verdict=Verdict(result="fix", reason="Stop"),
                 text="long AMD: new stop")
    lines += accept(home, [back], "emp-c", ROSTER, NOW, DAY)
    assert all(x.startswith("stored") for x in lines)


def test_type_not_in_use(home: Path) -> None:
    """UT-DSK-011.017.M29.T02: Type not in use."""
    drafts = [Draft(type="handover", to="emp-b", subject="Done", text="All ideas graded"),
              Draft(type="escalate", to="emp-b", subject="Broken", text="NVDA plan broken")]
    assert accept(home, drafts, "emp-a", ROSTER, NOW, DAY) == [
        "refused: type handover is not in use yet", "refused: type escalate is not in use yet"]


def test_receivers(home: Path) -> None:
    """UT-DSK-011.018.M29.T01: Receivers."""
    by_id = _ask(home, draft=ASK.model_copy(update={"to": "emp-b"}))
    by_skill = _ask(home)
    assert [m.receiver for m in inbox(home, "emp-b")] == ["emp-b", "emp-b"]
    assert {by_id, by_skill} == {m.id for m in inbox(home, "emp-b")}


def test_nobody_to_take_it(home: Path) -> None:
    """UT-DSK-011.018.M29.T02: Nobody to take it."""
    for to in ("emp-z", "skill:lead_brief", "boss"):
        line = accept(home, [ASK.model_copy(update={"to": to})], "emp-a", ROSTER, NOW, DAY)
        assert line == [f"refused: nobody can take {to}"]
    retired = [p for p in ROSTER if p.id != "emp-b"]
    line = accept(home, [ASK.model_copy(update={"to": "emp-b"})], "emp-a", retired, NOW, DAY)
    assert line == ["refused: nobody can take emp-b"]


def test_bad_draft_refused_alone(home: Path) -> None:
    """UT-DSK-011.019.M29.T01: Bad draft refused alone."""
    bad = Draft(type="ask", to="emp-b", subject="Two\nlines")
    lines = accept(home, [ASK, bad, ASK], "emp-a", ROSTER, NOW, DAY)
    assert [x.split()[0] for x in lines] == ["stored", "refused:", "stored"]


def test_unknown_data_format(home: Path) -> None:
    """UT-DSK-011.019.M29.T02: Unknown data format."""
    fill_registry(home, NOW)
    mid = _ask(home)
    data = Data(schema="nope.v1", rows=[["NVDA", 1]])
    assert accept(home, [_reply(mid, data=data)], "emp-b", ROSTER, NOW, DAY) == [
        "refused: unknown table format nope.v1"]


# ── M29: guardrails ──────────────────────────────────────────────────────────


def _thread_of(home: Path, msgs: int, rounds: int) -> int:
    mid = _ask(home)
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("UPDATE threads SET msgs = ?, rounds = ? WHERE id = ?", (msgs, rounds, mid))
    con.close()
    return mid


def _fix_reply(home: Path) -> int:
    back = Draft(type="send_back", to="emp-a", verdict=Verdict(result="fix", reason="Stop"),
                 text="long AMD: new stop")
    sb = _id(accept(home, [back], "emp-c", ROSTER, NOW, DAY)[0])
    return _id(accept(home, [_reply(sb)], "emp-a", ROSTER, NOW, DAY)[0])


def _again(reply: int) -> Draft:
    return Draft(type="send_back", parent=reply, verdict=Verdict(result="fix", reason="Still"))


def test_within_limits(home: Path) -> None:
    """UT-DSK-011.020.M29.T01: Within limits."""
    mid = _thread_of(home, 5, 0)
    assert accept(home, [_reply(mid)], "emp-b", ROSTER, NOW, DAY)[0].startswith("stored")
    reply = _fix_reply(home)
    assert accept(home, [_again(reply)], "emp-c", ROSTER, NOW, DAY)[0].startswith("stored")
    other = tmp = home.parent / "other"
    for _ in range(20):
        last = accept(other, [ASK], "emp-a", ROSTER, NOW, DAY)
    assert last[0].startswith("stored") and tmp.exists()


def test_over_limits(home: Path) -> None:
    """UT-DSK-011.020.M29.T02: Over limits."""
    mid = _thread_of(home, 6, 0)
    assert "6 messages" in accept(home, [_reply(mid)], "emp-b", ROSTER, NOW, DAY)[0]
    reply = _fix_reply(home)
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("UPDATE threads SET rounds = 2 WHERE id = (SELECT thread FROM messages "
                    "WHERE id = ?)", (reply,))
    con.close()
    assert "2 send-back rounds" in accept(home, [_again(reply)], "emp-c", ROSTER, NOW, DAY)[0]
    other = home.parent / "other"
    for _ in range(20):
        accept(other, [ASK], "emp-a", ROSTER, NOW, DAY)
    assert "20 messages already started" in accept(other, [ASK], "emp-a", ROSTER, NOW, DAY)[0]


def test_reply_to_open_ask(home: Path) -> None:
    """UT-DSK-011.021.M29.T01: Reply to an open ask."""
    mid = _ask(home)
    rid = _id(accept(home, [_reply(mid)], "emp-b", ROSTER, NOW, DAY)[0])
    assert [m.id for m in inbox(home, "emp-a")] == [rid]


def test_bad_reply(home: Path) -> None:
    """UT-DSK-011.021.M29.T02: Bad reply."""
    mid = _ask(home)
    rid = _id(accept(home, [_reply(mid)], "emp-b", ROSTER, NOW, DAY)[0])
    assert "not open" in accept(home, [_reply(mid)], "emp-b", ROSTER, NOW, DAY)[0]
    mid2 = _ask(home)
    assert "not addressed" in accept(home, [_reply(mid2)], "emp-d", ROSTER, NOW, DAY)[0]
    assert "not open" in accept(home, [_reply(rid)], "emp-a", ROSTER, NOW, DAY)[0]


def test_loop_refused(home: Path) -> None:
    """UT-DSK-011.022.M29.T01: Loop refused."""
    mid = _ask(home)
    reply = _id(accept(home, [_reply(mid)], "emp-b", ROSTER, NOW, DAY)[0])
    con = sqlite3.connect(home / "desk.db")
    with con:  # emp-b now waits on emp-a in the same thread
        con.execute("INSERT INTO messages (thread, type, sender, receiver, at, state, body, "
                    "data_day) VALUES (?, 'ask', 'emp-b', 'emp-a', ?, 'submitted', '{}', ?)",
                    (mid, NOW.isoformat(), DAY))
    con.close()
    line = accept(home, [_again(reply)], "emp-a", ROSTER, NOW, DAY)
    assert line == ["refused: the receiver is waiting on you in this thread"]


def test_third_employee_in_thread(home: Path) -> None:
    """UT-DSK-011.022.M29.T02: Third employee in a thread."""
    reply = _fix_reply(home)
    assert accept(home, [_again(reply)], "emp-c", ROSTER, NOW, DAY)[0].startswith("stored")


def test_expiry(home: Path) -> None:
    """UT-DSK-011.023.M29.T01: Expiry."""
    mid = _ask(home)
    assert expire_due(home, NOW + timedelta(minutes=11)) == 1
    states = dict(_rows(home, "SELECT id, state FROM messages"))
    assert states[mid] == "expired"
    reply = next(m for m in messages_of(home, mid) if m.type == "reply")
    assert (reply.sender, reply.receiver, reply.body["verdict"]["result"]) == (
        "emp-b", "emp-a", "failed")
    assert _rows(home, "SELECT target FROM events WHERE key = ?", (f"message|{reply.id}",)) == [
        ("emp-a",)]
    assert read_message(home, reply.id) is not None  # a code reply reads back as desk.msg/1


def test_not_yet_due(home: Path) -> None:
    """UT-DSK-011.023.M29.T02: Not yet due."""
    mid = _ask(home)
    assert expire_due(home, NOW + timedelta(minutes=9)) == 0
    assert dict(_rows(home, "SELECT id, state FROM messages")) == {mid: "submitted"}


def test_wake_event(home: Path) -> None:
    """UT-DSK-011.024.M29.T01: Wake event."""
    mid = _ask(home)
    assert _rows(home, "SELECT kind, key, target, priority, state FROM events") == [
        ("message", f"message|{mid}", "emp-b", 1, "waiting")]


def test_no_event_for_refusal(home: Path) -> None:
    """UT-DSK-011.024.M29.T02: No event for a refusal."""
    accept(home, [ASK.model_copy(update={"to": "emp-z"})], "emp-a", ROSTER, NOW, DAY)
    assert _rows(home, "SELECT COUNT(*) FROM events") == [(0,)]


def test_inbox_block(home: Path) -> None:
    """UT-DSK-011.026.M29.T01: Inbox block."""
    mid = _ask(home)
    text = inbox_text(inbox(home, "emp-b"), ROSTER)
    assert f"#{mid} ask from emp-a (Ann, setup review), about NVDA:" in text
    assert "Any earnings in the next 5 days?" in text
    assert f"Reply with a message of type reply and parent {mid}." in text
    accept(home, [_reply(mid)], "emp-b", ROSTER, NOW, DAY)
    assert f"reply from emp-b (Bob, news review) to your #{mid}: done" in inbox_text(
        inbox(home, "emp-a"), ROSTER)


def test_seen_not_shown(home: Path) -> None:
    """UT-DSK-011.026.M29.T02: Seen rows not shown again."""
    _ask(home)
    mark_seen(home, [m.id for m in inbox(home, "emp-b")], NOW)
    assert inbox(home, "emp-b") == [] and inbox_text([], ROSTER) == ""


def test_reply_closes_parent(home: Path) -> None:
    """UT-DSK-011.027.M29.T01: Reply closes the parent."""
    for result, state in (("done", "completed"), ("failed", "failed"),
                          ("refused", "refused")):
        mid = _ask(home)
        accept(home, [_reply(mid, result, reason="No news feed today")], "emp-b", ROSTER, NOW,
               DAY)
        assert dict(_rows(home, "SELECT id, state FROM messages"))[mid] == state
    assert _rows(home, "SELECT COUNT(*) FROM events WHERE target = 'emp-a'") == [(3,)]
    assert {r[0] for r in _rows(home, "SELECT state FROM threads")} == {"closed"}


def test_closed_parent_unchanged(home: Path) -> None:
    """UT-DSK-011.027.M29.T02: Closed parent unchanged."""
    mid = _ask(home)
    expire_due(home, NOW + timedelta(minutes=11))
    assert "not open" in accept(home, [_reply(mid)], "emp-b", ROSTER, NOW, DAY)[0]
    assert dict(_rows(home, "SELECT id, state FROM messages"))[mid] == "expired"


def test_refuse_inbox(home: Path) -> None:
    """UT-DSK-011.028.M29: a refused reply is written once for each open ask (helper)."""
    _ask(home)
    rows = inbox(home, "emp-b")
    assert refuse_inbox(home, rows, "Bob cannot work now", NOW) == 1
    assert refuse_inbox(home, rows, "again", NOW) == 0
    assert open_started(home, "emp-a") is True  # the refused reply is not read yet
    mark_seen(home, [m.id for m in inbox(home, "emp-a")], NOW)
    assert open_started(home, "emp-a") is False


def test_message_logs(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-011.032.M29.T01: Message logs."""
    with caplog.at_level(logging.INFO, logger="us_swing.core.desk_messages"):
        _ask(home)
        accept(home, [ASK.model_copy(update={"to": "emp-z"})], "emp-a", ROSTER, NOW, DAY)
        expire_due(home, NOW + timedelta(minutes=11))
    lines = [r.getMessage() for r in caplog.records]
    assert "[Messages] Ann sent a question to Bob" in lines
    assert "[Messages] A message from Ann was refused: nobody can take emp-z" in lines
    assert "[Messages] 1 message(s) expired with no reply in 10 minutes" in lines
    assert not any("_" in line.split("]", 1)[1].split(":")[0] for line in lines)


def test_setting_saved_and_read(home: Path) -> None:
    """UT-DSK-011.031.M13.T01: Setting saved and read."""
    home.mkdir(parents=True)
    (home / "desk_ai.json").write_text('{"claude_on": true}', encoding="utf-8")
    assert load_settings(home).messages_on is False
    save_settings(DeskAiSettings(messages_on=True), home)
    assert load_settings(home).messages_on is True


def test_missing_verdict_filled(home: Path) -> None:
    """UT-DSK-011.021.M29.T03: A reply without a verdict gets done, or dropped on a send-back."""
    mid = _ask(home)
    accept(home, [Draft(type="reply", parent=mid, text="Earnings Thursday")], "emp-b", ROSTER,
           NOW, DAY)
    back = Draft(type="send_back", to="emp-a", verdict=Verdict(result="fix", reason="Stop"),
                 text="long AMD: new stop")
    sb = _id(accept(home, [back], "emp-c", ROSTER, NOW, DAY)[0])
    accept(home, [Draft(type="reply", parent=sb, text="AMD dropped: no level fits")], "emp-a",
           ROSTER, NOW, DAY)
    states = dict(_rows(home, "SELECT id, state FROM messages"))
    assert states[mid] == "completed" and states[sb] == "failed"
