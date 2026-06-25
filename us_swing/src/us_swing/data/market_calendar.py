"""Module: data/market_calendar.py — NYSE/NASDAQ trading-hours calendar.

Pure infrastructure — no GUI, no I/O, no external dependencies beyond stdlib.
Determines whether US equity markets are in one of four session states:
    'open' | 'pre_market' | 'after_hours' | 'closed'

Usage::

    from zoneinfo import ZoneInfo
    from datetime import datetime
    from us_swing.data.market_calendar import get_exchange_status, ET

    status = get_exchange_status(datetime.now(ET))
"""
from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

# Eastern Time — authoritative timezone for US equity markets.
ET: ZoneInfo = ZoneInfo("America/New_York")

# NYSE/NASDAQ observed holidays for 2026 (month, day).
# Source: NYSE holiday schedule — https://www.nyse.com/markets/hours-calendars
NYSE_HOLIDAYS: frozenset[tuple[int, int]] = frozenset([
    (1,  1),   # New Year's Day
    (1,  19),  # Martin Luther King Jr. Day
    (2,  16),  # Presidents' Day
    (4,  3),   # Good Friday
    (5,  25),  # Memorial Day
    (6,  19),  # Juneteenth National Independence Day
    (7,  3),   # Independence Day (observed — Jul 4 is Saturday)
    (9,  7),   # Labor Day
    (11, 26),  # Thanksgiving Day
    (12, 25),  # Christmas Day
])


def get_exchange_status(now_et: datetime.datetime) -> str:
    """Return the current US equity market session state.

    Args:
        now_et: Current local time in Eastern Time (tz-aware or naive ET).

    Returns:
        One of: ``'open'`` · ``'pre_market'`` · ``'after_hours'`` · ``'closed'``
    """
    if now_et.weekday() >= 5:                               # Saturday / Sunday
        return "closed"
    if (now_et.month, now_et.day) in NYSE_HOLIDAYS:
        return "closed"
    t = now_et.time()
    if datetime.time(9, 30) <= t < datetime.time(16, 0):
        return "open"
    if datetime.time(4, 0) <= t < datetime.time(9, 30):
        return "pre_market"
    if datetime.time(16, 0) <= t < datetime.time(20, 0):
        return "after_hours"
    return "closed"
