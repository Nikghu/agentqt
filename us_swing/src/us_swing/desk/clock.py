"""
Module: MD-DSK-001.015.M03 — desk/clock.py
Parent SRD: SRD-DSK-001.015
Also: SRD-DSK-003.008 (market clock events), SRD-DSK-003.013 (run kinds counted),
SRD-DSK-003.020 (check-in times), SRD-DSK-003.023 (market hours for the watchers)

Pure time rules for the desk. The caller always passes the clock.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from us_swing.core.desk_contract import MORNING_RUN
from us_swing.data.market_calendar import get_exchange_status

ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
CLOCK_WINDOW = timedelta(minutes=30)
CHECKINS = (time(10, 0), time(12, 30), time(15, 30))
RETRY_AFTER = timedelta(minutes=15)
MAX_TRIES = 3
MORNING = "morning"
MANUAL = "manual"

RunRow = tuple[str, datetime, str]  # kind, start, result


def is_trading_day(day: date) -> bool:
    """True when the NYSE opens on ``day`` (not a weekend or market holiday)."""
    return get_exchange_status(datetime.combine(day, time(12, 0), ET)) == "open"


def morning_due(now: datetime, runs: Sequence[RunRow]) -> bool:
    """Return True when the morning run should start now.

    Due on NYSE trading days from 04:00 to 16:00 New York time until a morning or manual
    run ends ok that day. A failed morning try is repeated after ``RETRY_AFTER``, at most
    ``MAX_TRIES`` times; interrupted tries do not count.

    Args:
        now: Current time (time-zone aware).
        runs: Recent runs as ``(kind, start, result)``; older days are ignored.
    """
    now_et = now.astimezone(ET)
    if not is_trading_day(now_et.date()) or not MORNING_RUN <= now_et.time() < MARKET_CLOSE:
        return False
    start = datetime.combine(now_et.date(), MORNING_RUN, ET)
    today = [(kind, at, result) for kind, at, result in runs
             if kind in (MORNING, MANUAL) and at >= start]
    if any(result == "ok" for _kind, _at, result in today):
        return False
    mornings = [(at, result) for kind, at, result in today if kind == MORNING]
    if sum(result == "failed" for _at, result in mornings) >= MAX_TRIES:
        return False
    last = max((at for at, _result in mornings), default=None)
    return last is None or now - last >= RETRY_AFTER


def market_events_due(now: datetime) -> list[tuple[str, str]]:
    """Return the market clock events due at ``now`` as ``(kind, day)`` pairs.

    On NYSE trading days ``market_open`` is due from 09:30 and ``market_close`` from
    16:00 New York time, each only for ``CLOCK_WINDOW`` after its time, so a desk started
    later in the day posts no stale clock event. The caller ignores repeats.
    """
    now_et = now.astimezone(ET)
    if not is_trading_day(now_et.date()):
        return []
    day = now_et.date()
    due: list[tuple[str, str]] = []
    for kind, at in (("market_open", MARKET_OPEN), ("market_close", MARKET_CLOSE)):
        start = datetime.combine(day, at, ET)
        if start <= now_et < start + CLOCK_WINDOW:
            due.append((kind, day.isoformat()))
    return due


def checkins_due(now: datetime) -> list[tuple[str, int]]:
    """Return the check-ins due at ``now`` as ``(day, slot)`` pairs, slot like ``1000``.

    On NYSE trading days each check-in time is due only for ``CLOCK_WINDOW`` after it
    (SRD-DSK-003.020); the caller ignores repeats.
    """
    now_et = now.astimezone(ET)
    if not is_trading_day(now_et.date()):
        return []
    day = now_et.date()
    due: list[tuple[str, int]] = []
    for at in CHECKINS:
        start = datetime.combine(day, at, ET)
        if start <= now_et < start + CLOCK_WINDOW:
            due.append((day.isoformat(), at.hour * 100 + at.minute))
    return due


def in_market_hours(now: datetime) -> bool:
    """True from 09:30 to 16:00 New York time on NYSE trading days."""
    now_et = now.astimezone(ET)
    return is_trading_day(now_et.date()) and MARKET_OPEN <= now_et.time() < MARKET_CLOSE
