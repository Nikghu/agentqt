"""Tests for MD-MKT-006.004.M03 — core/econ_calendar.py (economic calendar data)."""
from __future__ import annotations

import logging
from datetime import date, time

import pytest

from us_swing.core import econ_calendar
from us_swing.core.econ_calendar import (
    EVENTS,
    events_between,
    next_trading_day,
    trading_days_after,
)

NAMES = {"FOMC rate decision", "CPI inflation report", "Jobs report", "PCE inflation",
         "GDP report"}


@pytest.fixture
def fresh_warnings(monkeypatch: pytest.MonkeyPatch) -> set[int]:
    """Reset the one-time warning memory for the test."""
    warned: set[int] = set()
    monkeypatch.setattr(econ_calendar, "_warned", warned)
    return warned


def test_events_listed() -> None:
    """UT-MKT-006.004.M03.T01: 2026-11-09 to 2026-11-13 holds CPI on 2026-11-10 at 08:30, high."""
    found = events_between(date(2026, 11, 9), date(2026, 11, 13))
    assert [(e.day, e.time, e.name, e.importance) for e in found] == [
        (date(2026, 11, 10), time(8, 30), "CPI inflation report", "high")]


def test_year_not_covered_warns_once(
        fresh_warnings: set[int], caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-006.004.M03.T02: days in 2029 give no events, asked twice, one warning only."""
    with caplog.at_level(logging.WARNING):
        assert events_between(date(2029, 3, 1), date(2029, 3, 9)) == []
        assert events_between(date(2029, 3, 1), date(2029, 3, 9)) == []
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "2029" in warnings[0].getMessage()


def test_next_trading_day() -> None:
    """UT-MKT-006.004.M03.T03: Thanksgiving is skipped; a Friday gives the next Monday."""
    assert next_trading_day(date(2026, 11, 25)) == date(2026, 11, 27)
    assert next_trading_day(date(2026, 11, 6)) == date(2026, 11, 9)
    assert trading_days_after(date(2026, 11, 6), 2) == date(2026, 11, 10)


def test_calendar_data_sane() -> None:
    """UT-MKT-006.004.M03.T04: events are sorted, known names, and importance matches the name."""
    assert len(EVENTS) > 0
    assert list(EVENTS) == sorted(EVENTS, key=lambda e: (e.day, e.time, e.name))
    assert {e.name for e in EVENTS} == NAMES
    for event in EVENTS:
        expected = "high" if event.name in {"FOMC rate decision", "CPI inflation report",
                                            "Jobs report"} else "medium"
        assert event.importance == expected, event
        assert event.day.year in econ_calendar.COVERED_YEARS


def test_covered_year_gives_no_warning(
        fresh_warnings: set[int], caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-006.004.M03.T05: a listed year (2026) asks without any warning."""
    with caplog.at_level(logging.WARNING):
        assert events_between(date(2026, 11, 9), date(2026, 11, 13))
    assert fresh_warnings == set() and caplog.records == []


def test_next_trading_day_2027() -> None:
    """UT-MKT-006.004.M03.T06: 2027 holidays are skipped (Thanksgiving 2027-11-25)."""
    assert next_trading_day(date(2027, 11, 24)) == date(2027, 11, 26)
    assert next_trading_day(date(2027, 12, 23)) == date(2027, 12, 27)
    assert next_trading_day(date(2027, 1, 15)) == date(2027, 1, 19)
