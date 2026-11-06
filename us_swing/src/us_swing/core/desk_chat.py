"""
Module: MD-MKT-010.001.M01 — core/desk_chat.py
Parent SRD: SRD-MKT-010.001

The lead chat in ``desk.db``. The GUI adds the Master's questions (and posts one
``chat_question`` event each); the desk adds the replies. The table is append-only.
Shared by the GUI and the desk; this module imports neither ``desk``, ``market`` nor ``gui``.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_events import post_event

MAX_QUESTION = 500
OPEN_FOR = timedelta(minutes=30)
WAITING = "Waiting for the answer"
START_DESK = "Start the desk to get an answer"
EXPIRED = "No answer: the question expired"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat (
    id INTEGER PRIMARY KEY, created TEXT, role TEXT, text TEXT, reply_to INTEGER, state TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS chat_one_reply ON chat (reply_to) WHERE role = 'lead';
CREATE TRIGGER IF NOT EXISTS chat_no_update BEFORE UPDATE ON chat
BEGIN SELECT RAISE(ABORT, 'chat is append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_no_delete BEFORE DELETE ON chat
BEGIN SELECT RAISE(ABORT, 'chat is append-only'); END;
"""


@dataclass(frozen=True)
class ChatTurn:
    """One chat row: a Master question or a lead reply."""

    id: int
    created: str
    role: str
    text: str
    reply_to: int | None
    state: str


def _open(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.executescript(_SCHEMA)
    return con


def _turns(con: sqlite3.Connection, sql: str, args: tuple[object, ...] = ()) -> list[ChatTurn]:
    return [ChatTurn(*row) for row in con.execute(sql, args).fetchall()]


def ask_question(home: Path, text: str, now: datetime) -> int:
    """Save a Master question and post its event; return the question id.

    Raises:
        ValueError: When the text is empty or longer than 500 characters.
    """
    text = text.strip()
    if not text or len(text) > MAX_QUESTION:
        raise ValueError("a question needs 1 to 500 characters")
    con = _open(home)
    try:
        with con:
            cur = con.execute("INSERT INTO chat (created, role, text, reply_to, state) "
                              "VALUES (?, 'master', ?, NULL, 'asked')",
                              (now.isoformat(timespec="seconds"), text))
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
        asked = _turns(con, "SELECT id, created, role, text, reply_to, state FROM chat "
                            "WHERE role = 'master' AND id NOT IN (SELECT reply_to FROM chat "
                            "WHERE role = 'lead') ORDER BY id")
    finally:
        con.close()
    return next((q for q in asked if now - datetime.fromisoformat(q.created) <= OPEN_FOR), None)


def add_reply(home: Path, question_id: int, text: str, ok: bool, now: datetime) -> None:
    """Save the desk's reply to a question (``ok`` False marks a failed reply)."""
    con = _open(home)
    try:
        with con:
            con.execute("INSERT INTO chat (created, role, text, reply_to, state) "
                        "VALUES (?, 'lead', ?, ?, ?)",
                        (now.isoformat(timespec="seconds"), text, question_id,
                         "answered" if ok else "failed"))
    finally:
        con.close()


def chat_turns(home: Path, limit: int = 50) -> list[ChatTurn]:
    """The last ``limit`` chat rows, oldest first; empty when there is no desk database."""
    if not (home / DB_NAME).exists():
        return []
    con = _open(home)
    try:
        rows = _turns(con, "SELECT id, created, role, text, reply_to, state FROM chat "
                           "ORDER BY id DESC LIMIT ?", (limit,))
    finally:
        con.close()
    return rows[::-1]


def question_note(home: Path, question_id: int, now: datetime, desk_up: bool) -> str:
    """What the chat shows under a question: empty once replied, else waiting, start or expired."""
    con = _open(home)
    try:
        replied = con.execute("SELECT 1 FROM chat WHERE role = 'lead' AND reply_to = ?",
                              (question_id,)).fetchone()
        row = con.execute("SELECT created FROM chat WHERE id = ?", (question_id,)).fetchone()
    finally:
        con.close()
    if replied or row is None:
        return ""
    if now - datetime.fromisoformat(row[0]) > OPEN_FOR:
        return EXPIRED
    return WAITING if desk_up else START_DESK
