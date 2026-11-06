"""
Module: MD-MKT-006.004.M03 — core/econ_calendar.py
Parent SRD: SRD-MKT-006.004

The yearly US economic calendar as plain data, shared by the market news review and the
Market Floor. Dates are from the official schedules (Federal Reserve FOMC calendar, BLS
CPI and Employment Situation schedules, BEA release schedule), taken on 2026-11-06. FOMC
dates stay tentative until the meeting before confirms them; update this list once a year.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Literal

from us_swing.data.market_calendar import NYSE_HOLIDAYS

log = logging.getLogger(__name__)

Importance = Literal["high", "medium"]
COVERED_YEARS: tuple[int, ...] = (2026, 2027)


@dataclass(frozen=True)
class EconEvent:
    """One scheduled release; ``time`` is New York time."""

    day: date
    time: time
    name: str
    importance: Importance


_FOMC = ("2026-12-09", "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28",
         "2027-09-15", "2027-10-27", "2027-12-08")
_CPI = ("2026-11-10", "2026-12-10", "2027-01-13", "2027-02-11", "2027-03-10", "2027-04-13",
        "2027-05-12", "2027-06-10", "2027-07-14", "2027-08-11", "2027-09-14", "2027-10-14",
        "2027-11-10", "2027-12-10")
_JOBS = ("2026-11-06", "2026-12-04", "2027-01-08", "2027-02-05", "2027-03-05", "2027-04-02",
         "2027-05-07", "2027-06-04", "2027-07-02", "2027-08-06", "2027-09-03", "2027-10-08",
         "2027-11-05", "2027-12-03")
_BEA = ("2026-11-25", "2026-12-23", "2027-01-28", "2027-02-25", "2027-03-31", "2027-04-29",
        "2027-05-27", "2027-06-25", "2027-07-29", "2027-08-25", "2027-09-30", "2027-10-28",
        "2027-11-24", "2027-12-22")

_GROUPS: tuple[tuple[tuple[str, ...], time, str, Importance], ...] = (
    (_FOMC, time(14, 0), "FOMC rate decision", "high"),
    (_CPI, time(8, 30), "CPI inflation report", "high"),
    (_JOBS, time(8, 30), "Jobs report", "high"),
    (_BEA, time(8, 30), "PCE inflation", "medium"),
    (_BEA, time(8, 30), "GDP report", "medium"),
)
EVENTS: tuple[EconEvent, ...] = tuple(sorted(
    (EconEvent(date.fromisoformat(d), at, name, imp) for days, at, name, imp in _GROUPS
     for d in days),
    key=lambda e: (e.day, e.time, e.name)))

# NYSE full-day closures per year (observed dates). The app-wide list in
# data/market_calendar.py has no year, so it is right for 2026 only (T125).
NYSE_CLOSED: dict[int, frozenset[date]] = {
    2026: frozenset(date(2026, m, d) for m, d in NYSE_HOLIDAYS),
    2027: frozenset(date.fromisoformat(d) for d in (
        "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18",
        "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24")),
}

_warned: set[int] = set()


def events_between(first: date, last: date) -> list[EconEvent]:
    """Events from ``first`` to ``last`` (both included); a year not listed warns once."""
    for year in range(first.year, last.year + 1):
        if year not in COVERED_YEARS and year not in _warned:
            _warned.add(year)
            log.warning("[Calendar] No economic calendar for %d yet; update the yearly list",
                        year)
    return [e for e in EVENTS if first <= e.day <= last]


def is_trading_day(day: date) -> bool:
    """True when the NYSE opens on ``day`` (weekday and not a listed market holiday)."""
    return day.weekday() < 5 and day not in NYSE_CLOSED.get(day.year, frozenset())


def next_trading_day(day: date) -> date:
    """The first NYSE trading day after ``day``."""
    nxt = day + timedelta(days=1)
    while not is_trading_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def trading_days_after(day: date, count: int) -> date:
    """The ``count``-th NYSE trading day after ``day``."""
    out = day
    for _ in range(count):
        out = next_trading_day(out)
    return out
