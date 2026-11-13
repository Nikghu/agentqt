"""
Module: MD-MKT-010.001.M01 — core/desk_chat.py
Parent SRD: SRD-MKT-010.001
Also: SRD-MKT-010.010–.012 (sessions), SRD-MKT-010.017 (update rows), SRD-MKT-010.018 (team note)

The lead chat in ``desk.db``. The GUI adds the Master's questions (and posts one
``chat_question`` event each); the desk adds the replies and updates. The ``chat`` table is
append-only; with Chat sessions on each question is saved with its session (AI Desk v3 M4).
Shared by the GUI and the desk; this module imports neither ``desk``, ``market`` nor ``gui``.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_events import post_event

NY = ZoneInfo("America/New_York")
MAX_QUESTION = 500
OPEN_FOR = timedelta(minutes=30)
TEAM_FOR = timedelta(hours=1)
QUIET_NEW = timedelta(hours=2)
QUIET_CLOSE = timedelta(hours=24)
TITLE_CHARS = 40
MAX_SUMMARY = 400
WAITING = "Waiting for the answer"
START_DESK = "Start the desk to get an answer"
EXPIRED = "No answer: the question expired"
TEAM = "Waiting for the team"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat (
    id INTEGER PRIMARY KEY, created TEXT, role TEXT, text TEXT, reply_to INTEGER, state TEXT,
    session INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS chat_one_reply ON chat (reply_to) WHERE role = 'lead';
CREATE UNIQUE INDEX IF NOT EXISTS chat_one_update ON chat (reply_to) WHERE role = 'update';
CREATE TRIGGER IF NOT EXISTS chat_no_update BEFORE UPDATE ON chat
BEGIN SELECT RAISE(ABORT, 'chat is append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_no_delete BEFORE DELETE ON chat
BEGIN SELECT RAISE(ABORT, 'chat is append-only'); END;
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY, title TEXT, opened TEXT, last TEXT, state TEXT,
    summary TEXT DEFAULT ''
);
"""
_TURN = "SELECT id, created, role, text, reply_to, state, session FROM chat "
_SESSION = "SELECT id, title, opened, last, state, summary FROM chat_sessions "


@dataclass(frozen=True)
class ChatTurn:
    """One chat row: a Master question, a lead reply or a lead update."""

    id: int
    created: str
    role: str
    text: str
    reply_to: int | None
    state: str
    session: int | None = None


@dataclass(frozen=True)
class ChatSession:
    """One discussion between the Master and the chat lead."""

    id: int
    title: str
    opened: str
    last: str
    state: str
    summary: str


@dataclass(frozen=True)
class TeamReply:
    """The answer the team gave to the lead's ask about a question."""

    text: str
    result: str


def _open(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    has_chat = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'chat'").fetchone()
    if has_chat and not con.execute(
            "SELECT 1 FROM pragma_table_info('chat') WHERE name = 'session'").fetchone():
        try:
            con.execute("ALTER TABLE chat ADD COLUMN session INTEGER")
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc):
                raise  # the other process added it first otherwise
    con.executescript(_SCHEMA)
    return con


def _turns(con: sqlite3.Connection, sql: str, args: tuple[object, ...] = ()) -> list[ChatTurn]:
    return [ChatTurn(*row) for row in con.execute(sql, args).fetchall()]


def _sessions(con: sqlite3.Connection, sql: str,
              args: tuple[object, ...] = ()) -> list[ChatSession]:
    return [ChatSession(*row) for row in con.execute(sql, args).fetchall()]


def _stamp(now: datetime) -> str:
    return now.isoformat(timespec="seconds")


def _ny_day(stamp: str) -> str:
    return datetime.fromisoformat(stamp).astimezone(NY).date().isoformat()


def ask_question(home: Path, text: str, now: datetime, session: int | None = None) -> int:
    """Save a Master question (in ``session`` when given) and post its event; return its id.

    Raises:
        ValueError: When the text is empty or longer than 500 characters.
    """
    text = text.strip()
    if not text or len(text) > MAX_QUESTION:
        raise ValueError("a question needs 1 to 500 characters")
    con = _open(home)
    try:
        with con:
            cur = con.execute("INSERT INTO chat (created, role, text, reply_to, state, session) "
                              "VALUES (?, 'master', ?, NULL, 'asked', ?)",
                              (_stamp(now), text, session))
            if session is not None:
                con.execute("UPDATE chat_sessions SET last = ? WHERE id = ?",
                            (_stamp(now), session))
        qid = int(cur.lastrowid or 0)
    finally:
        con.close()
    post_event(home, "chat_question", now.date().isoformat(), now, run_id=qid)
    return qid


def open_question(home: Path, now: datetime) -> ChatTurn | None:
    """The oldest question without a reply that is not older than 30 minutes."""
    if not (home / DB_NAME).exists():
        return None
    con = _open(home)
    try:
        asked = _turns(con, _TURN + "WHERE role = 'master' AND id NOT IN (SELECT reply_to "
                                    "FROM chat WHERE role = 'lead') ORDER BY id")
    finally:
        con.close()
    return next((q for q in asked if now - datetime.fromisoformat(q.created) <= OPEN_FOR), None)


def add_reply(home: Path, question_id: int, text: str, ok: bool, now: datetime) -> None:
    """Save the desk's reply to a question (``ok`` False marks a failed reply)."""
    con = _open(home)
    try:
        with con:
            con.execute("INSERT INTO chat (created, role, text, reply_to, state, session) "
                        "SELECT ?, 'lead', ?, ?, ?, session FROM chat WHERE id = ?",
                        (_stamp(now), text, question_id, "answered" if ok else "failed",
                         question_id))
    finally:
        con.close()


def add_update(home: Path, question_id: int, text: str, now: datetime) -> bool:
    """Save the lead's one update to a question; ``False`` when it already has one."""
    con = _open(home)
    try:
        with con:
            cur = con.execute("INSERT INTO chat (created, role, text, reply_to, state, "
                              "session) SELECT ?, 'update', ?, ?, 'answered', session "
                              "FROM chat WHERE id = ?",
                              (_stamp(now), text, question_id, question_id))
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()
    return cur.rowcount > 0


def chat_turns(home: Path, limit: int = 50) -> list[ChatTurn]:
    """The last ``limit`` chat rows, oldest first; empty when there is no desk database."""
    if not (home / DB_NAME).exists():
        return []
    con = _open(home)
    try:
        rows = _turns(con, _TURN + "ORDER BY id DESC LIMIT ?", (limit,))
    finally:
        con.close()
    return rows[::-1]


def question_note(home: Path, question_id: int, now: datetime, desk_up: bool) -> str:
    """What the chat shows under a question: waiting, start, expired, team or empty."""
    con = _open(home)
    try:
        replied = con.execute("SELECT 1 FROM chat WHERE role = 'lead' AND reply_to = ?",
                              (question_id,)).fetchone()
        updated = con.execute("SELECT 1 FROM chat WHERE role = 'update' AND reply_to = ?",
                              (question_id,)).fetchone()
        row = con.execute("SELECT created FROM chat WHERE id = ?", (question_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        return ""
    age = now - datetime.fromisoformat(row[0])
    if replied:
        team = not updated and age <= TEAM_FOR and _team_ask(home, question_id) is not None
        return TEAM if team else ""
    if age > OPEN_FOR:
        return EXPIRED
    return WAITING if desk_up else START_DESK


# ── sessions (SRD-MKT-010.010–.012) ──────────────────────────────────────


def session_for(home: Path, now: datetime, chosen: int | None, text: str,
                new: bool = False) -> int:
    """The session for a new question: the chosen one, the recent open one or a new one.

    Raises:
        ValueError: When the text is empty or longer than 500 characters, so no empty
            session is made.
    """
    if not text.strip() or len(text.strip()) > MAX_QUESTION:
        raise ValueError("a question needs 1 to 500 characters")
    mark_quiet(home, now)
    con = _open(home)
    try:
        with con:
            if chosen is not None and con.execute(
                    "SELECT 1 FROM chat_sessions WHERE id = ?", (chosen,)).fetchone():
                con.execute("UPDATE chat_sessions SET state = 'open' WHERE id = ?", (chosen,))
                return chosen
            recent = _sessions(con, _SESSION + "WHERE state = 'open' ORDER BY last DESC LIMIT 1")
            if recent and not new:
                last = recent[0].last
                if (now - datetime.fromisoformat(last) < QUIET_NEW
                        and _ny_day(last) == _ny_day(_stamp(now))):
                    return recent[0].id
            cur = con.execute("INSERT INTO chat_sessions (title, opened, last, state) "
                              "VALUES (?, ?, ?, 'open')",
                              (text.strip()[:TITLE_CHARS], _stamp(now), _stamp(now)))
            return int(cur.lastrowid or 0)
    finally:
        con.close()


def mark_quiet(home: Path, now: datetime) -> int:
    """Mark open sessions quiet for 24 hours as closing; return how many."""
    con = _open(home)
    try:
        quiet = [s.id for s in _sessions(con, _SESSION + "WHERE state = 'open'")
                 if now - datetime.fromisoformat(s.last) >= QUIET_CLOSE]
        with con:
            con.executemany("UPDATE chat_sessions SET state = 'closing' WHERE id = ?",
                            [(sid,) for sid in quiet])
    finally:
        con.close()
    return len(quiet)


def close_session(home: Path, session: int) -> None:
    """Mark an open session as closing (New discussion)."""
    con = _open(home)
    try:
        with con:
            con.execute("UPDATE chat_sessions SET state = 'closing' WHERE id = ? "
                        "AND state = 'open'", (session,))
    finally:
        con.close()


def sessions(home: Path) -> list[ChatSession]:
    """All sessions, newest first; empty when there is no desk database."""
    if not (home / DB_NAME).exists():
        return []
    con = _open(home)
    try:
        return _sessions(con, _SESSION + "ORDER BY last DESC, id DESC")
    finally:
        con.close()


def get_session(home: Path, session: int) -> ChatSession | None:
    """One session, or ``None``."""
    con = _open(home)
    try:
        found = _sessions(con, _SESSION + "WHERE id = ?", (session,))
    finally:
        con.close()
    return found[0] if found else None


def session_turns(home: Path, session: int, limit: int = 50) -> list[ChatTurn]:
    """The last ``limit`` rows of one session, oldest first."""
    con = _open(home)
    try:
        rows = _turns(con, _TURN + "WHERE session = ? ORDER BY id DESC LIMIT ?",
                      (session, limit))
    finally:
        con.close()
    return rows[::-1]


def closing_sessions(home: Path) -> list[ChatSession]:
    """Sessions waiting for their summary, oldest first."""
    if not (home / DB_NAME).exists():
        return []
    con = _open(home)
    try:
        return _sessions(con, _SESSION + "WHERE state = 'closing' ORDER BY id")
    finally:
        con.close()


def save_summary(home: Path, session: int, text: str) -> None:
    """Save a session's summary and close it, unless it was opened again meanwhile."""
    con = _open(home)
    try:
        with con:
            con.execute("UPDATE chat_sessions SET summary = ?, state = 'closed' WHERE id = ? "
                        "AND state = 'closing'", (text.strip()[:MAX_SUMMARY], session))
    finally:
        con.close()


# ── the team ask (SRD-MKT-010.016–.018) ──────────────────────────────────


def team_subject(question_id: int) -> str:
    """The subject code gives the lead's ask about a question."""
    return f"Chat question #{question_id}"


def _messages(home: Path) -> sqlite3.Connection | None:
    path = home / DB_NAME
    if not path.exists():
        return None
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'messages'").fetchone():
        con.close()
        return None
    return con


def _team_ask(home: Path, question_id: int) -> int | None:
    con = _messages(home)
    if con is None:
        return None
    try:
        row = con.execute("SELECT id FROM messages WHERE type = 'ask' "
                          "AND json_extract(body, '$.subject') = ? ORDER BY id LIMIT 1",
                          (team_subject(question_id),)).fetchone()
    finally:
        con.close()
    return int(row[0]) if row else None


def team_reply(home: Path, question_id: int) -> TeamReply | None:
    """The reply to the lead's ask about a question, or ``None`` while there is none."""
    ask = _team_ask(home, question_id)
    con = _messages(home) if ask is not None else None
    if con is None:
        return None
    try:
        row = con.execute("SELECT body FROM messages WHERE parent = ? AND type = 'reply' "
                          "ORDER BY id LIMIT 1", (ask,)).fetchone()
    finally:
        con.close()
    if row is None:
        return None
    body = json.loads(row[0])
    verdict = body.get("verdict") or {}
    return TeamReply(str(body.get("text") or verdict.get("reason") or ""),
                     str(verdict.get("result", "done")))


def waiting_updates(home: Path, now: datetime) -> list[ChatTurn]:
    """Replied questions of the last hour with a team reply and no update, oldest first."""
    if not (home / DB_NAME).exists():
        return []
    con = _open(home)
    try:
        asked = _turns(con, _TURN + "WHERE role = 'master' "
                                    "AND id IN (SELECT reply_to FROM chat WHERE role = 'lead') "
                                    "AND id NOT IN (SELECT reply_to FROM chat "
                                    "WHERE role = 'update') ORDER BY id")
    finally:
        con.close()
    return [q for q in asked if now - datetime.fromisoformat(q.created) <= TEAM_FOR
            and team_reply(home, q.id) is not None]
