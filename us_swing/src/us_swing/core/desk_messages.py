"""
Module: MD-DSK-011.015.M29 — core/desk_messages.py
Parent SRD: SRD-DSK-011.015
Also: SRD-DSK-011.014 (the only writer of messages), .017–.024 (check, guardrails, store and
wake), .026 (inbox block), .027 (reply closes the parent), .028 (refused reply), .029 (open
started messages), .032 (logs)

Agent messages in ``desk.db``. Employees only write drafts in their answers; this module
checks each draft, stores it as a ``desk.msg/1`` row, keeps the thread counts and posts the
``message`` event that wakes the receiver. Replies written by code (refused, expired) go the
same way. Design: DD-DSK-011.015.D01.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_events import open_events, post_message
from us_swing.core.desk_msg import Draft, Message, reason
from us_swing.core.desk_registry import get_format

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
M1_TYPES = frozenset({"ask", "reply", "send_back"})
MAX_THREAD_MSGS = 6
MAX_ROUNDS = 2
MAX_STARTED_A_DAY = 20
REPLY_WINDOW = timedelta(minutes=10)
_ASKING = ("ask", "send_back")
_KIND_WORDS = {"ask": "a question", "reply": "a reply", "send_back": "work back for a fix"}
_PARENT_STATE = {"done": "completed", "partial": "completed", "failed": "failed",
                 "dropped": "failed", "refused": "refused"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY, thread INTEGER, parent INTEGER, type TEXT, sender TEXT,
    receiver TEXT, at TEXT, due TEXT, state TEXT, body TEXT, meta TEXT, seen TEXT,
    data_day TEXT
);
CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY, starter TEXT, msgs INTEGER, rounds INTEGER, state TEXT,
    opened TEXT, closed TEXT
);
"""
_COLS = "id, thread, parent, type, sender, receiver, at, due, state, body, data_day"


@dataclass(frozen=True)
class Person:
    """One active employee as messages see it."""

    id: str
    name: str
    skill: str


@dataclass(frozen=True)
class MessageRow:
    """One stored message; times are New York ISO text."""

    id: int
    thread: int
    parent: int | None
    type: str
    sender: str
    receiver: str
    at: str
    due: str | None
    state: str
    body: dict[str, Any]
    data_day: str


@dataclass(frozen=True)
class ThreadRow:
    """One thread for the Threads view."""

    id: int
    starter: str
    msgs: int
    rounds: int
    state: str
    opened: str
    tokens: int


class _Refused(Exception):
    """A draft broke a rule; the text says which."""


def _connect(home: Path) -> sqlite3.Connection:
    con = open_events(home)
    con.executescript(SCHEMA)
    return con


def _stamp(moment: datetime) -> str:
    return moment.astimezone(NY).isoformat(timespec="seconds")


def _row(r: tuple[Any, ...]) -> MessageRow:
    return MessageRow(int(r[0]), int(r[1]), None if r[2] is None else int(r[2]), str(r[3]),
                      str(r[4]), str(r[5]), str(r[6]), r[7], str(r[8]), json.loads(r[9]),
                      str(r[10]))


def _get(con: sqlite3.Connection, message_id: int) -> MessageRow | None:
    r = con.execute(f"SELECT {_COLS} FROM messages WHERE id = ?", (message_id,)).fetchone()
    return _row(r) if r else None


def _name(roster: Sequence[Person], emp: str) -> str:
    return next((p.name for p in roster if p.id == emp), emp)


# ── accept ───────────────────────────────────────────────────────────────────


def accept(home: Path, drafts: Sequence[Draft], sender: str, roster: Sequence[Person],
           now: datetime, data_day: str) -> list[str]:
    """Check, store and wake for each draft; a broken draft is refused alone (SRD-DSK-011.019).

    Args:
        home: Desk folder.
        drafts: The drafts of one answer, in order.
        sender: Id of the employee that wrote them.
        roster: Active employees.
        now: Time-zone aware time.
        data_day: Data day of the turn.

    Returns:
        One line per draft: ``stored #<id>`` or ``refused: <why>``.
    """
    if not drafts:
        return []
    con = _connect(home)
    out: list[str] = []
    try:
        for draft in drafts:
            try:
                with con:
                    mid, receiver = _accept_one(home, con, draft, sender, roster, now, data_day)
                out.append(f"stored #{mid}")
                log.info("[Messages] %s sent %s to %s", _name(roster, sender),
                         _KIND_WORDS.get(draft.type, draft.type), _name(roster, receiver))
            except _Refused as why:
                out.append(f"refused: {why}")
                log.info("[Messages] A message from %s was refused: %s",
                         _name(roster, sender), why)
    finally:
        con.close()
    return out


def _accept_one(home: Path, con: sqlite3.Connection, draft: Draft, sender: str,
                roster: Sequence[Person], now: datetime, day: str) -> tuple[int, str]:
    body = draft.body()
    try:
        Message.model_validate({"id": 1, "thread": 1, "parent": draft.parent, "sender": sender,
                                "to": draft.to, "at": now, "state": "submitted",
                                "due": now + REPLY_WINDOW if draft.type in _ASKING else None,
                                "body": body})
    except ValidationError as exc:
        raise _Refused(reason(exc)) from exc
    if draft.type not in M1_TYPES:
        raise _Refused(f"type {draft.type} is not in use yet")
    parent = _get(con, draft.parent) if draft.parent is not None else None
    if draft.parent is not None and parent is None:
        raise _Refused(f"message #{draft.parent} does not exist")
    receiver = parent.sender if parent else _receiver(str(draft.to), roster)
    _guard(con, draft, sender, receiver, parent, now)
    data = body.get("data")
    if data is not None and get_format(home, str(data["schema"])) is None:
        raise _Refused(f"unknown table format {data['schema']}")
    return _store(con, draft.type, body, sender, receiver, parent, now, day), receiver


def _receiver(to: str, roster: Sequence[Person]) -> str:
    if to.startswith("skill:"):
        holders = sorted(p.id for p in roster if p.skill == to[6:])
        if holders:
            return holders[0]
    elif any(p.id == to for p in roster):
        return to
    raise _Refused(f"nobody can take {to}")


def _guard(con: sqlite3.Connection, draft: Draft, sender: str, receiver: str,
           parent: MessageRow | None, now: datetime) -> None:
    if parent is not None:
        if parent.receiver != sender:
            raise _Refused(f"message #{parent.id} is not addressed to you")
        wanted = _ASKING if draft.type == "reply" else ("reply",)
        if parent.type not in wanted or (draft.type == "reply" and parent.state != "submitted"):
            raise _Refused(f"message #{parent.id} is not open for a {draft.type}")
        msgs, rounds = con.execute("SELECT msgs, rounds FROM threads WHERE id = ?",
                                   (parent.thread,)).fetchone()
        if msgs >= MAX_THREAD_MSGS:
            raise _Refused(f"thread #{parent.thread} already has {MAX_THREAD_MSGS} messages")
        if draft.type == "send_back" and rounds >= MAX_ROUNDS:
            raise _Refused(f"thread #{parent.thread} already had {MAX_ROUNDS} send-back rounds")
        if draft.type in _ASKING and con.execute(
                "SELECT 1 FROM messages WHERE thread = ? AND sender = ? AND receiver = ? "
                "AND state = 'submitted' AND type IN ('ask', 'send_back')",
                (parent.thread, receiver, sender)).fetchone():
            raise _Refused("the receiver is waiting on you in this thread")
        return
    started = con.execute(
        "SELECT COUNT(*) FROM messages WHERE sender = ? AND parent IS NULL "
        "AND substr(at, 1, 10) = ?", (sender, now.astimezone(NY).date().isoformat())
    ).fetchone()[0]
    if started >= MAX_STARTED_A_DAY:
        raise _Refused(f"{MAX_STARTED_A_DAY} messages already started today")


def _store(con: sqlite3.Connection, kind: str, body: dict[str, Any], sender: str,
           receiver: str, parent: MessageRow | None, now: datetime, day: str) -> int:
    fields = {k: v for k, v in body.items() if k != "type"}
    due = _stamp(now + REPLY_WINDOW) if kind in _ASKING else None
    state = "submitted" if kind in _ASKING else "completed"
    cur = con.execute(
        "INSERT INTO messages (thread, parent, type, sender, receiver, at, due, state, body, "
        "data_day) VALUES (0, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (parent.id if parent else None, kind, sender, receiver, _stamp(now), due, state,
         json.dumps(fields), day))
    mid = int(cur.lastrowid or 0)
    round_up = 1 if kind == "send_back" else 0
    if parent is None:
        con.execute("UPDATE messages SET thread = id WHERE id = ?", (mid,))
        con.execute("INSERT INTO threads VALUES (?, ?, 1, ?, 'open', ?, NULL)",
                    (mid, sender, round_up, _stamp(now)))
    else:
        con.execute("UPDATE messages SET thread = ? WHERE id = ?", (parent.thread, mid))
        con.execute("UPDATE threads SET msgs = msgs + 1, rounds = rounds + ? WHERE id = ?",
                    (round_up, parent.thread))
        if kind == "reply":
            result = str(fields.get("verdict", {}).get("result", "done"))
            con.execute("UPDATE messages SET state = ? WHERE id = ?",
                        (_PARENT_STATE.get(result, "completed"), parent.id))
        _close_if_done(con, parent.thread, now)
    post_message(con, mid, receiver, day, now)
    return mid


def _close_if_done(con: sqlite3.Connection, thread: int, now: datetime) -> None:
    if not con.execute("SELECT 1 FROM messages WHERE thread = ? AND state = 'submitted'",
                       (thread,)).fetchone():
        con.execute("UPDATE threads SET state = 'closed', closed = ? WHERE id = ?",
                    (_stamp(now), thread))


# ── code replies: refused and expired ────────────────────────────────────────


def _code_reply(con: sqlite3.Connection, row: MessageRow, result: str, why: str,
                parent_state: str, now: datetime) -> None:
    """A reply written by code in the receiver's name; it wakes the asker."""
    body = {"verdict": {"result": result, "reason": why[:200]}}
    cur = con.execute(
        "INSERT INTO messages (thread, parent, type, sender, receiver, at, due, state, body, "
        "data_day) VALUES (?, ?, 'reply', ?, ?, ?, NULL, 'completed', ?, ?)",
        (row.thread, row.id, row.receiver, row.sender, _stamp(now), json.dumps(body),
         row.data_day))
    con.execute("UPDATE messages SET state = ? WHERE id = ?", (parent_state, row.id))
    con.execute("UPDATE threads SET msgs = msgs + 1 WHERE id = ?", (row.thread,))
    _close_if_done(con, row.thread, now)
    post_message(con, int(cur.lastrowid or 0), row.sender, row.data_day, now)


def refuse_inbox(home: Path, rows: Sequence[MessageRow], why: str, now: datetime) -> int:
    """Answer each open ask or send-back in ``rows`` with a refused reply (SRD-DSK-011.028)."""
    con = _connect(home)
    done = 0
    try:
        with con:
            for row in rows:
                fresh = _get(con, row.id)
                if fresh is None or fresh.type not in _ASKING or fresh.state != "submitted":
                    continue
                _code_reply(con, fresh, "refused", why, "refused", now)
                done += 1
    finally:
        con.close()
    if done:
        log.info("[Messages] %d message(s) were refused at once: %s", done, why)
    return done


def expire_due(home: Path, now: datetime) -> int:
    """Expire open asks and send-backs past their due time (SRD-DSK-011.023)."""
    if not (home / DB_NAME).exists():
        return 0
    con = _connect(home)
    done = 0
    try:
        with con:
            rows = [_row(r) for r in con.execute(
                f"SELECT {_COLS} FROM messages WHERE state = 'submitted' AND due IS NOT NULL")]
            for row in rows:
                if row.due and datetime.fromisoformat(row.due) <= now:
                    _code_reply(con, row, "failed", "no reply within 10 minutes", "expired",
                                now)
                    done += 1
    finally:
        con.close()
    if done:
        log.info("[Messages] %d message(s) expired with no reply in 10 minutes", done)
    return done


# ── inbox ────────────────────────────────────────────────────────────────────


def inbox(home: Path, emp: str) -> list[MessageRow]:
    """Messages to ``emp`` that no wake has shown yet, oldest first."""
    if not (home / DB_NAME).exists():
        return []
    con = _connect(home)
    try:
        return [_row(r) for r in con.execute(
            f"SELECT {_COLS} FROM messages WHERE receiver = ? AND seen IS NULL "
            "AND (type NOT IN ('ask', 'send_back') OR state = 'submitted') ORDER BY id",
            (emp,))]
    finally:
        con.close()


def mark_seen(home: Path, ids: Sequence[int], now: datetime) -> None:
    """Mark messages as shown in their receiver's inbox."""
    if not ids:
        return
    con = _connect(home)
    try:
        with con:
            con.executemany("UPDATE messages SET seen = ? WHERE id = ?",
                            [(_stamp(now), i) for i in ids])
    finally:
        con.close()


def _who(emp: str, roster: Sequence[Person]) -> str:
    person = next((p for p in roster if p.id == emp), None)
    if person is None:
        return emp
    return f"{emp} ({person.name}, {person.skill.replace('_', ' ')})"


def _data_line(data: Mapping[str, Any]) -> str:
    if "rows" in data:
        rows = "; ".join(" ".join(str(c) for c in r) for r in data["rows"][:20])
        return f"  data {data['schema']}: {rows}"
    return f"  data {data['schema']}: {data.get('n', '?')} rows at {data.get('ref', '')}"


def inbox_text(rows: Sequence[MessageRow], roster: Sequence[Person]) -> str:
    """The inbox block for a woken employee's facts (SRD-DSK-011.026)."""
    if not rows:
        return ""
    lines = ["INBOX: answer only what is asked here; leave your other work as it is."]
    for m in rows:
        about = f", about {', '.join(m.body['about'])}" if m.body.get("about") else ""
        if m.type == "reply":
            verdict = m.body.get("verdict", {})
            lines.append(f"#{m.id} reply from {_who(m.sender, roster)} to your #{m.parent}: "
                         f"{verdict.get('result', '')}"
                         + (f" ({verdict['reason']})" if verdict.get("reason") else ""))
        else:
            label = "send_back" if m.type == "send_back" else m.type
            lines.append(f"#{m.id} {label} from {_who(m.sender, roster)}{about}:")
            if m.body.get("verdict", {}).get("reason"):
                lines.append(f"  {m.body['verdict']['reason']}")
        for key in ("subject", "text"):
            if m.body.get(key):
                lines.append(f"  {m.body[key]}")
        if m.body.get("data"):
            lines.append(_data_line(m.body["data"]))
        if m.type in _ASKING:
            lines.append(f"  Reply with a message of type reply and parent {m.id}.")
    return "\n".join(lines)


def open_started(home: Path, emp: str) -> bool:
    """True while an ask or send-back that ``emp`` sent waits for its reply, or a reply to it
    is not yet read in its inbox (SRD-DSK-011.029)."""
    if not (home / DB_NAME).exists():
        return False
    con = _connect(home)
    try:
        return con.execute(
            "SELECT 1 FROM messages WHERE (sender = ? AND state = 'submitted' "
            "AND type IN ('ask', 'send_back')) OR (receiver = ? AND seen IS NULL "
            "AND type = 'reply')", (emp, emp)).fetchone() is not None
    finally:
        con.close()


# ── reads ────────────────────────────────────────────────────────────────────


def _read_only(home: Path) -> sqlite3.Connection | None:
    path = home / DB_NAME
    if not path.exists():
        return None
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'messages'").fetchone():
        con.close()
        return None
    return con


def read_message(home: Path, message_id: int) -> Message | None:
    """A stored message as a ``desk.msg/1`` model, or ``None``."""
    con = _read_only(home)
    if con is None:
        return None
    try:
        r = con.execute(f"SELECT {_COLS} FROM messages WHERE id = ?", (message_id,)).fetchone()
    finally:
        con.close()
    if r is None:
        return None
    row = _row(r)
    first = row.parent is None
    return Message.model_validate({
        "id": row.id, "thread": row.thread, "parent": row.parent, "sender": row.sender,
        "to": row.receiver if first else None, "at": row.at, "due": row.due,
        "state": row.state, "body": {"type": row.type, **row.body}})


def messages_of(home: Path, thread: int) -> list[MessageRow]:
    """Messages of one thread, oldest first; empty without data."""
    con = _read_only(home)
    if con is None:
        return []
    try:
        return [_row(r) for r in con.execute(
            f"SELECT {_COLS} FROM messages WHERE thread = ? ORDER BY id", (thread,))]
    finally:
        con.close()


def thread_rows(home: Path, day: str) -> list[ThreadRow]:
    """Threads opened on New York ``day``, newest first, with their tokens."""
    con = _read_only(home)
    if con is None:
        return []
    try:
        has_activity = con.execute("SELECT 1 FROM pragma_table_info('activity') "
                                   "WHERE name = 'message'").fetchone() is not None
        tokens = ("(SELECT COALESCE(SUM(a.tokens_in + a.tokens_out), 0) FROM activity a "
                  "JOIN messages m ON m.id = a.message WHERE m.thread = t.id)"
                  if has_activity else "0")
        rows = con.execute(
            f"SELECT t.id, t.starter, t.msgs, t.rounds, t.state, t.opened, {tokens} "  # noqa: S608
            "FROM threads t WHERE substr(t.opened, 1, 10) = ? ORDER BY t.id DESC", (day,))
        return [ThreadRow(int(i), str(s), int(n), int(r), str(st), str(o), int(tk))
                for i, s, n, r, st, o, tk in rows]
    finally:
        con.close()


def thread_starter(home: Path, thread: int) -> str | None:
    """The employee that started ``thread`` (the payer), or ``None``."""
    con = _read_only(home)
    if con is None:
        return None
    try:
        row = con.execute("SELECT starter FROM threads WHERE id = ?", (thread,)).fetchone()
    finally:
        con.close()
    return str(row[0]) if row else None


def sent_on(home: Path, day: str, kind: str, text_start: str) -> bool:
    """True when a ``kind`` message of data day ``day`` starts with ``text_start``."""
    con = _read_only(home)
    if con is None:
        return False
    try:
        rows = con.execute("SELECT body FROM messages WHERE type = ? AND data_day = ?",
                           (kind, day)).fetchall()
    finally:
        con.close()
    return any(str(json.loads(b).get("text", "")).startswith(text_start) for (b,) in rows)
