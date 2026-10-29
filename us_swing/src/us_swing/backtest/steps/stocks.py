"""
Module: MD-BKT-002.010.M07 — backtest/steps/stocks.py
Parent SRD: SRD-BKT-002.010

Step 1 · Stocks: replay a screener preset on each trading day with only the
1d bars up to that day's close, cache one file per day and join the days into
a ranked daily list keyed by session: the list for a session is made at the
previous trading day's close, like the pre-market screener run (SRD-BKT-002.051).
"""
from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from us_swing.backtest.cache import StepCache, make_key
from us_swing.backtest.spec import Period, RunPlan
from us_swing.backtest.store import BacktestStore
from us_swing.core.backtest_bridge import screen_day
from us_swing.core.indicator_rules import IndicatorRuleError, rules_from_config

STEP = "stocks"
STEP_VERSION = 1
LOOKBACK_BARS = 600
WARMUP_DAYS = 900
BENCHMARK = "SPY"
_SESSION_LOOKBACK_DAYS = 10
_KEY_FIELDS = ("preset_type", "groups", "screeners", "threshold", "timeframe")
_DAY_COLUMNS = ["symbol", "passed", "score"]
_RS_RULE = "rs_index"
_INDICATOR_SCREENER = "indicator_composite"

Progress = Callable[[int, int], None]
Cancel = Callable[[], bool]
_BarHistory = tuple[npt.NDArray[np.datetime64], list["_Bar"]]


class StepCancelled(Exception):
    """The user cancelled the step; finished days stay cached."""


class StepRefused(Exception):
    """The plan asks for something Step 1 cannot do yet."""


@dataclass(frozen=True, slots=True)
class _Bar:
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def trading_days(store: BacktestStore, period: Period, symbols: list[str]) -> list[date]:
    """Return SPY's 1d dates in the period, or all stocks' dates when SPY is missing."""
    spy = store.read(BENCHMARK, "1d", period.start, period.end)
    if not spy.empty:
        return sorted({ts.date() for ts in spy["ts"]})
    days: set[date] = set()
    for sym in symbols:
        frame = store.read(sym, "1d", period.start, period.end)
        days.update(ts.date() for ts in frame["ts"])
    return sorted(days)


def sessions(store: BacktestStore, period: Period, symbols: list[str]) -> dict[date, date]:
    """Map each session in the period to the trading day whose close made its list."""
    early = Period(period.start - timedelta(days=_SESSION_LOOKBACK_DAYS), period.end)
    days = trading_days(store, early, symbols)
    return {s: d for d, s in zip(days, days[1:]) if s >= period.start}


def rules_key(preset_dict: dict[str, Any], symbols: list[str]) -> str:
    """Cache key of the preset fields that change results plus the whole stock list."""
    rules = {k: preset_dict.get(k) for k in _KEY_FIELDS}
    return make_key(STEP, STEP_VERSION, {"rules": rules, "symbols": sorted(symbols)})


def needs_benchmark(preset_dict: dict[str, Any]) -> bool:
    """True when an enabled indicator screener has an enabled RS rule (needs SPY)."""
    refs: list[dict[str, Any]] = list(preset_dict.get("screeners") or ())
    for group in preset_dict.get("groups") or ():
        refs += group.get("screeners") or ()
    for ref in refs:
        if not ref.get("enabled", True) or ref.get("screener_id") != _INDICATOR_SCREENER:
            continue
        try:
            rules = rules_from_config(ref.get("config") or {})
        except IndicatorRuleError:
            continue
        if any(r.enabled and r.indicator_id == _RS_RULE for r in rules):
            return True
    return False


def has_benchmark(store: BacktestStore) -> bool:
    """True when SPY daily candles are in the store (the backtest is S&P 500 only)."""
    return store.coverage(BENCHMARK, "1d") is not None


def refusals(plan: RunPlan, preset_dict: dict[str, Any], benchmark: bool) -> list[str]:
    """Return plain messages for plans Step 1 cannot run (SRD-BKT-002.016, .018)."""
    errors: list[str] = []
    if needs_benchmark(preset_dict) and not benchmark:
        errors.append("This screener uses the RS rule, which compares stocks with SPY. "
                      "The backtest uses S&P 500 stocks only, so turn the RS rule off "
                      "or pick another screener")
    if preset_dict.get("timeframe", "1d") != "1d":
        errors.append("Weekly screener presets are not supported in backtest yet")
    if plan.screener.ai_ranking:
        errors.append("AI ranking is not built yet — untick it to run")
    return errors


def missing_days(cache: StepCache, key: str, days: list[date]) -> list[date]:
    """Return the days with no cache file under ``key``."""
    saved = cache.names(STEP, key)
    return [d for d in days if d.isoformat() not in saved]


def load_bars(root: Path, symbols: list[str], start: date, end: date) -> dict[str, _BarHistory]:
    """Read each stock's 1d bars once as (dates, bar objects)."""
    store = BacktestStore(root)
    out: dict[str, _BarHistory] = {}
    for sym in symbols:
        frame = store.read(sym, "1d", start, end)
        if frame.empty:
            continue
        stamps = frame["ts"].dt.to_pydatetime()
        bars = [
            _Bar(ts.replace(tzinfo=timezone.utc), float(o), float(h), float(lo), float(c),
                 float(v))
            for ts, o, h, lo, c, v in zip(stamps, frame["open"], frame["high"], frame["low"],
                                          frame["close"], frame["volume"])
        ]
        out[sym] = (frame["ts"].to_numpy().astype("datetime64[D]"), bars)
    return out


def compute_day(
    history: dict[str, _BarHistory],
    preset_dict: dict[str, Any],
    symbols: list[str],
    day: date,
    market_caps: dict[str, float],
) -> pd.DataFrame:
    """Screen one day with each stock's last ``LOOKBACK_BARS`` bars up to ``day``.

    A stock with no bar on ``day`` is left out; the benchmark is passed as bars only.
    """
    target = np.datetime64(day, "D")
    window: dict[str, list[Any]] = {}
    for sym, (dates, bars) in history.items():
        end = int(np.searchsorted(dates, target, side="right"))
        if end == 0 or (sym != BENCHMARK and dates[end - 1] != target):
            continue
        window[sym] = bars[max(0, end - LOOKBACK_BARS):end]
    names = [s for s in symbols if s in window]
    result = screen_day(preset_dict, names, window, market_caps)
    rows = sorted((sym, True, score) for sym, (passed, score) in result.items() if passed)
    return pd.DataFrame(rows, columns=_DAY_COLUMNS).astype(
        {"symbol": str, "passed": bool, "score": float}
    )


_history: dict[str, _BarHistory] = {}


def _init_worker(root: Path, symbols: list[str], start: date, end: date) -> None:
    global _history
    _history = load_bars(root, symbols, start, end)


def _run_day(
    preset_dict: dict[str, Any], symbols: list[str], day: date, market_caps: dict[str, float]
) -> tuple[date, pd.DataFrame]:
    try:
        return day, compute_day(_history, preset_dict, symbols, day, market_caps)
    except Exception as exc:  # noqa: BLE001 — sent back once as plain text (SRD-BKT-002.019)
        raise RuntimeError(f"{day.isoformat()}: {exc}") from None


def run_stocks(
    plan: RunPlan,
    preset_dict: dict[str, Any],
    symbols: list[str],
    store: BacktestStore,
    cache: StepCache,
    market_caps: dict[str, float],
    *,
    workers: int = 4,
    progress: Progress | None = None,
    cancel: Cancel | None = None,
) -> tuple[str, dict[date, date]]:
    """Compute and cache the list of every session's data day that is not cached yet.

    Args:
        workers: Worker processes; 0 runs in this process.
        progress: Called with (days done, days to compute).
        cancel: Checked after each day; true raises ``StepCancelled``.

    Returns:
        The cache key and each session of the period mapped to its data day.

    Raises:
        StepRefused: weekly preset or AI ranking ticked.
        StepCancelled: ``cancel`` returned true.
    """
    errors = refusals(plan, preset_dict, has_benchmark(store))
    if errors:
        raise StepRefused("; ".join(errors))
    report = progress or (lambda _done, _total: None)
    stop = cancel or (lambda: False)
    by_session = sessions(store, plan.period, symbols)
    key = rules_key(preset_dict, symbols)
    todo = missing_days(cache, key, list(by_session.values()))
    report(0, len(todo))
    if not todo:
        return key, by_session
    load_args = (store.root, sorted({*symbols, BENCHMARK}),
                 plan.period.start - timedelta(days=WARMUP_DAYS), plan.period.end)

    def save(day: date, frame: pd.DataFrame, done: int) -> None:
        cache.write(STEP, key, day.isoformat(), frame)
        report(done, len(todo))
        if stop():
            raise StepCancelled

    if workers == 0:
        history = load_bars(*load_args)
        for done, day in enumerate(todo, start=1):
            save(day, compute_day(history, preset_dict, symbols, day, market_caps), done)
        return key, by_session

    pool = ProcessPoolExecutor(
        max_workers=min(workers, os.cpu_count() or 1),
        initializer=_init_worker, initargs=load_args,
    )
    try:
        futures = [pool.submit(_run_day, preset_dict, symbols, d, market_caps) for d in todo]
        for done, future in enumerate(as_completed(futures), start=1):
            save(*future.result(), done)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    return key, by_session


def daily_list(cache: StepCache, key: str, by_session: dict[date, date]) -> pd.DataFrame:
    """Join cached days into ``date, symbol, score, rank``; ``date`` is the session.

    Rank 1 is the best score, ties by symbol.
    """
    frames = []
    for session, day in by_session.items():
        frame = cache.read(STEP, key, day.isoformat())
        if frame is not None and not frame.empty:
            frames.append(frame.assign(date=session))
    if not frames:
        return pd.DataFrame(columns=["date", "symbol", "score", "rank"])
    joined = pd.concat(frames, ignore_index=True).sort_values(
        ["date", "score", "symbol"], ascending=[True, False, True], ignore_index=True
    )
    joined["rank"] = joined.groupby("date").cumcount() + 1
    return joined[["date", "symbol", "score", "rank"]]


def top_n(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    """Keep the top ``n`` stocks per day; ``n`` 0 keeps all."""
    return frame if n == 0 else frame[frame["rank"] <= n].reset_index(drop=True)
