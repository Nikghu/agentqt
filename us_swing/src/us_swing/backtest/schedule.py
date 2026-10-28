"""
Module: MD-BKT-001.009.M05 — backtest/schedule.py
Parent SRD: SRD-BKT-001.009

Decides when the auto delta fill is due. Pure — the caller passes the clock.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from us_swing.backtest.settings import BacktestDataSettings

_ET = ZoneInfo("America/New_York")


def delta_due(
    settings: BacktestDataSettings, last_delta: datetime | None, now: datetime
) -> bool:
    """Return True when a scheduled run time has passed since the last delta fill.

    Args:
        settings: Auto delta switch, run time (US/Eastern) and run days.
        last_delta: When the last delta finished, or ``None`` if never.
        now: Current time (timezone-aware).

    Returns:
        False when auto delta is off or the end date is fixed.
    """
    if not settings.auto_delta or settings.end_date is not None:
        return False
    now_et = now.astimezone(_ET)
    for back in range(8):
        day = now_et.date() - timedelta(days=back)
        moment = datetime.combine(day, settings.run_time, _ET)
        if day.weekday() in settings.run_days and moment <= now_et:
            return last_delta is None or last_delta < moment
    return False
