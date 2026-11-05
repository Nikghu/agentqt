"""
Module: MD-DSK-001.015.M03 — desk/clock.py
Parent SRD: SRD-DSK-001.015

Pure time rules for the desk. The caller always passes the clock.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
EVENING_RUN = time(16, 25)
TASK_LEAD = timedelta(minutes=5)
_DAY_CODES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def evening_due(now: datetime, last_start: datetime | None) -> bool:
    """Return True when today's weekday evening run time has passed and has not run yet.

    Args:
        now: Current time (time-zone aware).
        last_start: Start of the last evening run, or ``None`` if never.
    """
    now_et = now.astimezone(ET)
    if now_et.weekday() >= 5:
        return False
    moment = datetime.combine(now_et.date(), EVENING_RUN, ET)
    if now_et < moment:
        return False
    return last_start is None or last_start < moment


def evening_task_time(day: date, local: tzinfo) -> tuple[str, list[str]]:
    """Return the local ``HH:MM`` and local weekday codes for the evening Windows task.

    The task starts ``TASK_LEAD`` before the evening run on each US weekday, using the
    New York and local clock offsets that apply on ``day``.

    Args:
        day: Day whose clock offsets to use.
        local: The PC's time zone.
    """
    start_et = datetime.combine(day, EVENING_RUN, ET) - TASK_LEAD
    start_local = start_et.astimezone(local)
    shift = (start_local.date() - day).days
    codes = [_DAY_CODES[(wd + shift) % 7] for wd in range(5)]
    return start_local.strftime("%H:%M"), codes
