"""Tests for MD-DSK-003.004.M15 — core/desk_events.py."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from us_swing.core.desk_events import (
    EVENT_KINDS,
    EVENT_RULES,
    STEP_DONE,
    Event,
    open_events,
    post_event,
    post_step_done,
    waiting_count,
)
from us_swing.desk.recorder import NY

NOW = datetime(2026, 11, 6, 16, 0, tzinfo=NY)


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_event_stored(home: Path) -> None:
    """UT-DSK-003.004.M15.T01: A posted market_close is stored as waiting with its times."""
    assert post_event(home, "market_close", "2026-11-06", NOW)
    assert _rows(home, "SELECT kind, priority, data_day, created, deadline, expires, state "
                       "FROM events") == [
        ("market_close", 2, "2026-11-06", "2026-11-06T16:00:00-05:00", None,
         "2026-11-06T16:30:00-05:00", "waiting")]
    assert waiting_count(home) == 1


def test_repeat_ignored(home: Path) -> None:
    """UT-DSK-003.004.M15.T02: The same event for one day is stored once; the repeat is False."""
    assert post_event(home, "market_close", "2026-11-06", NOW)
    assert not post_event(home, "market_close", "2026-11-06", NOW + timedelta(minutes=5))
    assert _rows(home, "SELECT COUNT(*) FROM events") == [(1,)]


def test_after_run_per_run(home: Path) -> None:
    """UT-DSK-003.004.M15.T03: after_run is stored once for each run, even on the same day."""
    assert post_event(home, "after_run", "2026-11-06", NOW, 7)
    assert post_event(home, "after_run", "2026-11-06", NOW, 8)
    assert not post_event(home, "after_run", "2026-11-06", NOW, 8)
    assert _rows(home, "SELECT COUNT(*) FROM events") == [(2,)]


def test_kind_rules() -> None:
    """UT-DSK-003.005.M15.T01: P0 regime_change, P1 after_run, P2 for both clock events;
    P0 chat_question added in P9 (SRD-MKT-010.002); P0 data_request added in P10
    (SRD-MKT-011.002); P2 market_checkin and P0 watch_flag added in step D (SRD-DSK-003.020,
    .021)."""
    assert {k: EVENT_RULES[k].priority for k in EVENT_KINDS} == {
        "regime_change": 0, "after_run": 1, "market_open": 2, "market_close": 2,
        "chat_question": 0, "data_request": 0, "market_checkin": 2, "watch_flag": 0,
            "research_done": 2}
    assert EVENT_RULES["market_open"].expiry == timedelta(minutes=30)


def test_unknown_kind(home: Path) -> None:
    """UT-DSK-003.005.M15.T02: An unknown kind raises ValueError and stores nothing."""
    with pytest.raises(ValueError, match="lunch"):
        post_event(home, "lunch", "2026-11-06", NOW)
    assert waiting_count(home) == 0


# ---------------- step_done (step B) ----------------

def _trigger(home: Path) -> Event:
    post_event(home, "after_run", "2026-11-06", NOW, 1)
    con = open_events(home)
    try:
        row = con.execute("SELECT id, kind, priority, data_day, created, deadline, expires "
                          "FROM events").fetchone()
    finally:
        con.close()
    return Event(*row)


def test_step_done_stored(home: Path) -> None:
    """UT-DSK-003.014.M15.T01: step_done keeps its parent and the trigger's priority and times."""
    trigger = _trigger(home)
    con = open_events(home)
    try:
        post_step_done(con, trigger, "e-1", 1, "ok", NOW + timedelta(minutes=1))
    finally:
        con.close()
    assert _rows(home, "SELECT kind, priority, data_day, deadline, expires, state, parent, due "
                       "FROM events WHERE kind = 'step_done'") == [
        ("step_done", 1, "2026-11-06", trigger.deadline, trigger.expires, "waiting", trigger.id,
         None)]


def test_step_done_repeat_ignored(home: Path) -> None:
    """UT-DSK-003.014.M15.T02: The same trigger, employee and try is stored once."""
    trigger = _trigger(home)
    con = open_events(home)
    try:
        post_step_done(con, trigger, "e-1", 1, "failed", NOW, NOW + timedelta(minutes=5))
        post_step_done(con, trigger, "e-1", 1, "failed", NOW, NOW + timedelta(minutes=5))
    finally:
        con.close()
    assert _rows(home, "SELECT COUNT(*) FROM events WHERE kind = 'step_done'") == [(1,)]


def test_old_desk_db(home: Path) -> None:
    """UT-DSK-003.014.M15.T03: An events table without parent and due gets them; rows load."""
    home.mkdir(parents=True)
    con = sqlite3.connect(home / "desk.db")
    con.executescript("CREATE TABLE events (id INTEGER PRIMARY KEY, key TEXT UNIQUE, kind TEXT, "
                      "priority INTEGER, data_day TEXT, created TEXT, deadline TEXT, "
                      "expires TEXT, state TEXT, handled TEXT, note TEXT);"
                      "INSERT INTO events (key, kind, state) VALUES ('k', 'after_run', 'done');")
    con.close()
    open_events(home).close()
    assert _rows(home, "SELECT kind, parent, due FROM events") == [("after_run", None, None)]


def test_tools_cannot_post_step_done(home: Path) -> None:
    """UT-DSK-003.014.M15.T04: step_done is not a tool event kind."""
    assert STEP_DONE not in EVENT_KINDS
    with pytest.raises(ValueError):
        post_event(home, STEP_DONE, "2026-11-06", NOW)
    assert waiting_count(home) == 0
