"""
Module: MD-DSK-003.004.M15 — core/desk_events.py
Parent SRD: SRD-DSK-003.004
Also: SRD-DSK-003.005 (event kinds and priorities); MD-MKT-010.002.M02 — ``chat_question`` (SRD-MKT-010.002)

Wake-up events in ``desk.db``. Any tool may post one (for example the market regime step
posts ``regime_change``); only the desk router changes an event's state. Clock and regime
events come once per kind and data day; ``after_run`` comes once per desk run.
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
"""


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
}
EVENT_KINDS: tuple[str, ...] = tuple(EVENT_RULES)


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


def open_events(home: Path) -> sqlite3.Connection:
    """Open ``desk.db`` in ``home`` with the ``events`` table ready."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    return con


def waiting_count(home: Path) -> int:
    """Number of waiting events; 0 when there is no desk database yet."""
    if not (home / DB_NAME).exists():
        return 0
    con = open_events(home)
    try:
        return int(con.execute("SELECT COUNT(*) FROM events WHERE state = 'waiting'")
                   .fetchone()[0])
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
        run_id: Desk run for ``after_run``, or the question id for ``chat_question``, so
            each run or question posts its own event.

    Raises:
        ValueError: When ``kind`` is not a known event kind.
    """
    rule = EVENT_RULES.get(kind)
    if rule is None:
        raise ValueError(f"unknown event kind {kind}")
    key = (f"{kind}|{data_day}|{run_id}" if kind in ("after_run", "chat_question")
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
