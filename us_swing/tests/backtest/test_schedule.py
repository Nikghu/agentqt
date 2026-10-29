"""Tests for MD-BKT-001.009.M05 — backtest/schedule.py."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from us_swing.backtest.schedule import delta_due
from us_swing.backtest.settings import BacktestDataSettings

_ET = ZoneInfo("America/New_York")
_ON = BacktestDataSettings()


def _et(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=_ET)


def test_due_after_run_time() -> None:
    """UT-BKT-001.009.M05.T01: Due once the run time has passed since the last delta."""
    assert delta_due(_ON, _et(26, 17, 35), _et(27, 17, 31))


def test_not_due_before_run_time() -> None:
    """UT-BKT-001.009.M05.T02: Not due before today's run time."""
    assert not delta_due(_ON, _et(26, 17, 35), _et(27, 17, 0))


def test_missed_friday_caught_up_monday_morning() -> None:
    """UT-BKT-001.009.M05.T03: A missed Friday run is due on Monday morning."""
    assert delta_due(_ON, _et(22, 17, 35), _et(26, 9, 0))


def test_off_when_end_date_fixed() -> None:
    """UT-BKT-001.009.M05.T04: Never due while the end date is fixed."""
    fixed = BacktestDataSettings(end_date=date(2025, 12, 31))

    assert not delta_due(fixed, _et(26, 17, 35), _et(27, 17, 31))
    assert not delta_due(BacktestDataSettings(auto_delta=False), None, _et(27, 17, 31))
