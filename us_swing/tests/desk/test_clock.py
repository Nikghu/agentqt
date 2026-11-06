"""Tests for MD-DSK-001.015.M03 — desk/clock.py."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from us_swing.desk.clock import ET, evening_due, evening_task_time, market_events_due

IST = ZoneInfo("Asia/Kolkata")


def _et(y: int, mo: int, d: int, h: int, mi: int) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=ET)


def test_due_after_time_on_weekday() -> None:
    """UT-DSK-001.015.M03.T01: Due after 16:25 ET on a weekday."""
    assert evening_due(_et(2026, 11, 5, 16, 30), _et(2026, 11, 4, 16, 25))


def test_not_due_before_time() -> None:
    """UT-DSK-001.015.M03.T02: Not due before time."""
    assert not evening_due(_et(2026, 11, 5, 16, 20), _et(2026, 11, 4, 16, 25))


def test_not_due_twice() -> None:
    """UT-DSK-001.015.M03.T03: Not due twice."""
    assert not evening_due(_et(2026, 11, 5, 17, 0), _et(2026, 11, 5, 16, 25))


def test_weekend() -> None:
    """UT-DSK-001.015.M03.T04: Weekend."""
    assert not evening_due(_et(2026, 11, 7, 18, 0), _et(2026, 11, 6, 16, 25))


def test_task_time_ist_est() -> None:
    """UT-DSK-001.015.M03.T05: Evening task time in IST (EST)."""
    assert evening_task_time(date(2026, 11, 5), IST) == (
        "02:50", ["TUE", "WED", "THU", "FRI", "SAT"],
    )


def test_task_time_ist_edt() -> None:
    """UT-DSK-001.015.M03.T06: Evening task time in IST (EDT)."""
    assert evening_task_time(date(2026, 7, 1), IST) == (
        "01:50", ["TUE", "WED", "THU", "FRI", "SAT"],
    )


def test_clock_events_due() -> None:
    """UT-DSK-003.008.M03.T01: On a trading day market_open is due at 09:31, market_close at 16:01."""
    assert market_events_due(_et(2026, 11, 6, 9, 31)) == [("market_open", "2026-11-06")]
    assert market_events_due(_et(2026, 11, 6, 16, 1)) == [("market_close", "2026-11-06")]


def test_clock_events_not_trading_day() -> None:
    """UT-DSK-003.008.M03.T02: Nothing is due on a Saturday or a NYSE holiday."""
    assert market_events_due(_et(2026, 11, 7, 16, 1)) == []
    assert market_events_due(_et(2026, 11, 26, 16, 1)) == []
    assert market_events_due(_et(2026, 11, 27, 16, 1)) != []


def test_clock_events_before_open() -> None:
    """UT-DSK-003.008.M03.T03: Nothing is due at 09:29 on a trading day."""
    assert market_events_due(_et(2026, 11, 6, 9, 29)) == []


def test_clock_events_window() -> None:
    """UT-DSK-003.008.M03.T04: Events are due only in the 30 minutes after their time."""
    assert market_events_due(_et(2026, 11, 6, 9, 59)) == [("market_open", "2026-11-06")]
    assert market_events_due(_et(2026, 11, 6, 10, 0)) == []
    assert market_events_due(_et(2026, 11, 6, 12, 0)) == []
    assert market_events_due(_et(2026, 11, 6, 16, 29)) == [("market_close", "2026-11-06")]
    assert market_events_due(_et(2026, 11, 6, 16, 30)) == []
    assert market_events_due(_et(2026, 11, 6, 17, 0)) == []
