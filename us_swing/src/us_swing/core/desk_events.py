"""
Module: MD-DSK-003.004.M15 — core/desk_events.py
Parent SRD: SRD-DSK-003.004
Also: SRD-DSK-003.005 (event kinds and priorities); MD-MKT-010.002.M02 — ``chat_question`` (SRD-MKT-010.002)
Also: MD-MKT-011.002.M02 — ``data_request`` (SRD-MKT-011.002)
Also: SRD-DSK-003.014 (``step_done`` events and the ``steps`` table for the baton)

Wake-up events in ``desk.db``. Any tool may post one (for example the market regime step
posts ``regime_change``); only the desk router changes an event's state. Clock and regime
events come once per kind and data day; ``after_run`` comes once per desk run.
``step_done`` is posted only by the router, when an employee's turn in a chain ends.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from us_swing.core.desk_contract import DB_NAME

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY, key TEXT UNIQUE, kind TEXT, priority INTEGER, data_day TEXT,
    created TEXT, deadline TEXT, expires TEXT, state TEXT, handled TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS steps (
    event_id INTEGER, employee TEXT, tries INTEGER, result TEXT, updated TEXT,
    PRIMARY KEY (event_id, employee)
);
"""
_NEW_COLUMNS = (("parent", "INTEGER"), ("due", "TEXT"))
STEP_DONE = "step_done"


@dataclass(frozen=True)
class EventRule:
    """Priority (0 is the most urgent), deadline and expiry of one event kind."""

    priority: int
    deadline: timedelta | None
    expiry: timedelta


EVENT_RULES: dict[str, EventRule] = {
    "regime_change": EventRule(0, timedelta(minutes=15), timedelta(hours=2)),
    "after_run": EventRule(1, timedelta(hours=2), timedelta(hours=6)),
    "market_open": EventRule(2, None, timedelta(minutes=30)),
    "market_close": EventRule(2, None, timedelta(minutes=30)),
    "chat_question": EventRule(0, timedelta(minutes=2), timedelta(minutes=30)),
    "data_request": EventRule(0, timedelta(minutes=5), timedelta(hours=2)),
}
EVENT_KINDS: tuple[str, ...] = tuple(EVENT_RULES)
_PER_ID = ("after_run", "chat_question", "data_request")


@dataclass(frozen=True)
class Event:
    """One stored event; times are ISO text in New York time."""

    id: int
    kind: str
    priority: int
    data_day: str
    created: str
    deadline: str | None
    expires: str
    parent: int | None = None
    due: str | None = None


def open_events(home: Path) -> sqlite3.Connection:
    """Open ``desk.db`` in ``home`` with the ``events`` table ready."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    have = {row[1] for row in con.execute("PRAGMA table_info(events)")}
    for name, kind in _NEW_COLUMNS:
        if name not in have:
            con.execute(f"ALTER TABLE events ADD COLUMN {name} {kind}")
    return con


def waiting_count(home: Path, now: datetime | None = None) -> int:
    """Number of waiting events (only those due at ``now`` when given); 0 with no database."""
    if not (home / DB_NAME).exists():
        return 0
    con = open_events(home)
    try:
        rows = con.execute("SELECT due FROM events WHERE state = 'waiting'").fetchall()
        return sum(1 for (due,) in rows
                   if now is None or due is None or datetime.fromisoformat(due) <= now)
    finally:
        con.close()


def post_event(home: Path, kind: str, data_day: str, now: datetime,
               run_id: int | None = None) -> bool:
    """Post one waiting event; ``False`` when the same event was already posted.

    Args:
        home: Desk folder.
        kind: One of ``EVENT_KINDS``.
        data_day: Data day (``YYYY-MM-DD``) the event is about.
        now: Time-zone aware time of posting.
        run_id: Desk run for ``after_run``, the question id for ``chat_question`` or the
            request id for ``data_request``, so each one posts its own event.

    Raises:
        ValueError: When ``kind`` is not a known event kind.
    """
    rule = EVENT_RULES.get(kind)
    if rule is None:
        raise ValueError(f"unknown event kind {kind}")
    key = (f"{kind}|{data_day}|{run_id}" if kind in _PER_ID
           else f"{kind}|{data_day}")
    deadline = (now + rule.deadline).isoformat(timespec="seconds") if rule.deadline else None
    con = open_events(home)
    try:
        with con:
            cur = con.execute(
                "INSERT OR IGNORE INTO events (key, kind, priority, data_day, created, deadline, "
                "expires, state) VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting')",
                (key, kind, rule.priority, data_day, now.isoformat(timespec="seconds"),
                 deadline, (now + rule.expiry).isoformat(timespec="seconds")))
        return cur.rowcount == 1
    finally:
        con.close()


def post_step_done(con: sqlite3.Connection, trigger: Event, employee: str, tries: int,
                   result: str, now: datetime, due: datetime | None = None) -> None:
    """Post a waiting ``step_done`` for one employee's try in the chain of ``trigger``.

    Args:
        con: Open ``desk.db`` connection (from ``open_events``).
        trigger: The event that started the chain.
        employee: Employee id.
        tries: Try number, from 1.
        result: ``ok``, ``slept``, ``failed`` or ``skipped``.
        now: Time-zone aware time of posting.
        due: Not handled before this time; ``None`` for at once.
    """
    with con:
        con.execute(
            "INSERT OR IGNORE INTO events (key, kind, priority, data_day, created, deadline, "
            "expires, state, parent, due, note) VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting', ?, ?, ?)",
            (f"{STEP_DONE}|{trigger.id}|{employee}|{tries}", STEP_DONE, trigger.priority,
             trigger.data_day, now.isoformat(timespec="seconds"), trigger.deadline,
             trigger.expires, trigger.id,
             due.isoformat(timespec="seconds") if due else None, f"{employee} {result}"))
