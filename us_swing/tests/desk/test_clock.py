"""Tests for MD-DSK-001.015.M03 — desk/clock.py."""
from __future__ import annotations

from datetime import datetime

from us_swing.desk.clock import ET, market_events_due, morning_due


def _et(y: int, mo: int, d: int, h: int, mi: int) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=ET)


def test_due_at_window_start() -> None:
    """UT-DSK-001.015.M03.T01: Due at the open of the morning window (SRD-DSK-001.015)."""
    assert morning_due(_et(2026, 11, 11, 4, 0), [])


def test_not_due_outside_window() -> None:
    """UT-DSK-001.015.M03.T02: Not due before 04:00 ET or from 16:00 ET (SRD-DSK-001.015)."""
    assert not morning_due(_et(2026, 11, 11, 3, 59), [])
    assert not morning_due(_et(2026, 11, 11, 16, 0), [])


def test_not_due_after_ok_run() -> None:
    """UT-DSK-001.015.M03.T03: Not due after an ok morning or manual run today."""
    now = _et(2026, 11, 11, 9, 0)
    assert not morning_due(now, [("morning", _et(2026, 11, 11, 8, 31), "ok")])
    assert not morning_due(now, [("manual", _et(2026, 11, 11, 8, 40), "ok")])


def test_weekend_and_holiday() -> None:
    """UT-DSK-001.015.M03.T04: Weekend and NYSE holiday (SRD-DSK-001.015)."""
    assert not morning_due(_et(2026, 11, 14, 9, 0), [])
    assert not morning_due(_et(2026, 11, 26, 9, 0), [])


def test_retry_after_failed_try() -> None:
    """UT-DSK-001.015.M03.T05: Retry 15 min after a failed try, at most 3 (SRD-DSK-001.015)."""
    failed = [("morning", _et(2026, 11, 11, 8, 31), "failed")]
    assert not morning_due(_et(2026, 11, 11, 8, 45), failed)
    assert morning_due(_et(2026, 11, 11, 8, 46), failed)
    three = [("morning", _et(2026, 11, 11, 8, m), "failed") for m in (1, 16, 31)]
    assert not morning_due(_et(2026, 11, 11, 10, 0), three)


def test_old_and_interrupted_runs_do_not_count() -> None:
    """UT-DSK-001.015.M03.T06: Yesterday's ok run and an interrupted try do not count."""
    runs = [("morning", _et(2026, 11, 10, 8, 31), "ok"),
            ("morning", _et(2026, 11, 11, 8, 31), "interrupted")]
    assert not morning_due(_et(2026, 11, 11, 8, 35), runs)
    assert morning_due(_et(2026, 11, 11, 8, 46), runs)


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
