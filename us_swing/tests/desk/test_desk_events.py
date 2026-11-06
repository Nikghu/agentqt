"""Tests for MD-DSK-003.004.M15 — core/desk_events.py."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from us_swing.core.desk_events import EVENT_KINDS, EVENT_RULES, post_event, waiting_count
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
    """UT-DSK-003.005.M15.T01: P0 regime_change, P1 after_run, P2 for both clock events."""
    assert {k: EVENT_RULES[k].priority for k in EVENT_KINDS} == {
        "regime_change": 0, "after_run": 1, "market_open": 2, "market_close": 2}
    assert EVENT_RULES["market_open"].expiry == timedelta(minutes=30)


def test_unknown_kind(home: Path) -> None:
    """UT-DSK-003.005.M15.T02: An unknown kind raises ValueError and stores nothing."""
    with pytest.raises(ValueError, match="lunch"):
        post_event(home, "lunch", "2026-11-06", NOW)
    assert waiting_count(home) == 0
