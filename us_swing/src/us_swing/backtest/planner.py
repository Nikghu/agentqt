"""
Module: MD-BKT-001.005.M03 — backtest/planner.py
Parent SRD: SRD-BKT-001.005, SRD-BKT-001.015

Builds the IBKR request list from the settings and what is already saved. Pure — no I/O.
Trading days are counted as weekdays; a holiday only makes a delta request one day longer.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from us_swing.backtest.settings import BacktestDataSettings
from us_swing.backtest.store import Timeframe

CoverageFn = Callable[[str, Timeframe], "tuple[date, date] | None"]

_WINDOW_MONTHS = 3
_BACKFILL_SLACK = timedelta(days=7)
_MIN_DELTA_DAYS = 2
_MAX_3M_DAYS = 60
_MAX_1D_DAYS = 250
_TIMEFRAMES: tuple[Timeframe, ...] = ("1d", "3m")


@dataclass(frozen=True, slots=True)
class Job:
    """One historical-data request.

    Attributes:
        symbol: Stock ticker.
        tf: ``"1d"`` or ``"3m"``.
        start: Oldest date the request is meant to reach.
        end: Request end date (US/Eastern).
        duration: IBKR duration string, e.g. ``"3 M"``.
    """

    symbol: str
    tf: Timeframe
    start: date
    end: date
    duration: str


def plan(
    symbols: list[str],
    settings: BacktestDataSettings,
    coverage: CoverageFn,
    floors: Mapping[str, date],
    last_session: date,
    delta_only: bool = False,
    daily_only: Sequence[str] = (),
) -> list[Job]:
    """Return the jobs still needed: all 1d jobs, then 3m jobs newest end first.

    Args:
        symbols: Stocks to download.
        settings: Range and auto delta settings.
        coverage: Returns the saved ``(first, last)`` date for a stock and timeframe.
        floors: Per stock, the date before which IBKR has no data.
        last_session: Latest finished trading day.
        delta_only: Only ask for days since each stock's last saved bar.
        daily_only: Extra symbols that get 1d jobs only (SPY for the RS rule).

    Returns:
        Ordered job list; empty when nothing is missing.
    """
    if delta_only and settings.end_date is not None:
        return []
    end = min(settings.end_date or last_session, last_session)
    jobs: dict[Timeframe, list[Job]] = {"1d": [], "3m": []}
    for symbol in [*symbols, *daily_only]:
        start = max(settings.start_date, floors.get(symbol, settings.start_date))
        for tf in ("1d",) if symbol in daily_only else _TIMEFRAMES:
            saved = coverage(symbol, tf)
            if delta_only:
                if saved is not None:
                    jobs[tf].extend(_forward(symbol, tf, saved[1], end))
                continue
            jobs[tf].extend(_missing(symbol, tf, start, end, saved, floors.get(symbol)))
    jobs["3m"].sort(key=lambda j: j.end, reverse=True)
    return jobs["1d"] + jobs["3m"]


def _missing(
    symbol: str,
    tf: Timeframe,
    start: date,
    end: date,
    saved: tuple[date, date] | None,
    floor: date | None,
) -> list[Job]:
    if saved is None:
        return _back(symbol, tf, start, end, floor)
    first, last = saved
    jobs: list[Job] = []
    if last < end:
        jobs.extend(_forward(symbol, tf, last, end))
    if first > start + _BACKFILL_SLACK:
        jobs.extend(_back(symbol, tf, start, first - timedelta(days=1), floor))
    return jobs


def _back(symbol: str, tf: Timeframe, start: date, end: date, floor: date | None) -> list[Job]:
    if tf == "1d":
        return [Job(symbol, tf, start, end, _years(start, end))]
    return [
        Job(symbol, tf, max(w_start, start), w_end, f"{_WINDOW_MONTHS} M")
        for w_start, w_end in _windows(start, end)
        if floor is None or w_end > floor
    ]


def _forward(symbol: str, tf: Timeframe, last: date, end: date) -> list[Job]:
    weekdays = _weekdays_after(last, end)
    if weekdays == 0:
        return []
    days = max(weekdays + 1, _MIN_DELTA_DAYS)
    if tf == "3m" and days > _MAX_3M_DAYS:
        return [
            Job(symbol, tf, w_start, w_end, f"{_WINDOW_MONTHS} M")
            for w_start, w_end in _windows(last, end)
        ]
    if tf == "1d" and days > _MAX_1D_DAYS:
        return [Job(symbol, tf, last, end, _years(last, end))]
    return [Job(symbol, tf, last, end, f"{days} D")]


def _windows(start: date, end: date) -> list[tuple[date, date]]:
    """3-month windows ``(w_start, w_end]`` from ``end`` back until one reaches ``start``."""
    anchor = pd.Timestamp(end)
    out: list[tuple[date, date]] = []
    k = 0
    while True:
        w_end = (anchor - pd.DateOffset(months=_WINDOW_MONTHS * k)).date()
        if w_end < start:
            return out
        w_start = (anchor - pd.DateOffset(months=_WINDOW_MONTHS * (k + 1))).date()
        out.append((w_start, w_end))
        k += 1


def _weekdays_after(last: date, end: date) -> int:
    return sum(
        1 for n in range(1, (end - last).days + 1) if (last + timedelta(days=n)).weekday() < 5
    )


def _years(start: date, end: date) -> str:
    return f"{max(1, math.ceil((end - start).days / 365.25))} Y"
