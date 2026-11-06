"""
Module: MD-MKT-003.009.M05 — market/earnings.py
Parent SRD: SRD-MKT-003.009

Next earnings date per stock from Yahoo Finance, for the few names near the top of
the idea list.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, datetime
from typing import Any

log = logging.getLogger(__name__)

TIME_BUDGET_S = 10.0
NAMES_PER_BUDGET = 30
WORKERS = 6


def _yahoo_calendar(symbol: str) -> Any:
    import yfinance as yf  # type: ignore[import-untyped]  # noqa: PLC0415 — slow import

    return yf.Ticker(symbol.replace(" ", "-").replace(".", "-")).calendar


def _first_date(calendar: Any) -> date | None:
    dates = calendar.get("Earnings Date") if isinstance(calendar, dict) else None
    if not dates:
        return None
    first = dates[0] if isinstance(dates, list | tuple) else dates
    if isinstance(first, datetime):
        return first.date()
    return first if isinstance(first, date) else None


def next_earnings(
    symbols: Iterable[str],
    calendar: Callable[[str], Any] = _yahoo_calendar,
    budget_s: float = TIME_BUDGET_S,
) -> dict[str, date | None]:
    """Return the next earnings date per symbol; ``None`` when it could not be read.

    Asks Yahoo for several symbols at once and waits at most ``budget_s`` seconds per
    30 symbols; a symbol not answered in time gets ``None``, so a stuck call never holds
    up the desk run.
    """
    names = list(dict.fromkeys(symbols))
    if not names:
        return {}
    pool = ThreadPoolExecutor(max_workers=WORKERS)
    jobs = {pool.submit(calendar, s): s for s in names}
    wait(jobs, timeout=budget_s * math.ceil(len(names) / NAMES_PER_BUDGET))
    pool.shutdown(wait=False, cancel_futures=True)
    out: dict[str, date | None] = {}
    for job, symbol in jobs.items():
        if not job.done() or job.cancelled() or job.exception() is not None:
            log.debug("[Ideas] Earnings date for %s not read", symbol)
            out[symbol] = None
            continue
        out[symbol] = _first_date(job.result())
    failed = sum(1 for job in jobs if not job.done() or job.cancelled()
                 or job.exception() is not None)
    if failed:
        log.warning("[Ideas] Earnings dates not checked for %d of %d stock(s)", failed, len(names))
    return out
