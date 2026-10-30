"""
Module: MD-BKT-002.026.M11 — backtest/steps/signals.py
Parent SRD: SRD-BKT-002.026

Step 2 · Signals: for each live strategy and each stock it may trade, the
periods when the entry and exit conditions are true on 3m bar closes, inside
the strategy's hours and days. One cache file per strategy and stock.
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from us_swing.backtest.cache import StepCache, make_key
from us_swing.backtest.spec import Period
from us_swing.backtest.steps.stocks import Cancel, Progress, StepCancelled
from us_swing.backtest.store import BacktestStore
from us_swing.core.expr import EvaluatorError
from us_swing.core.expr.series import ET, BoolArray, Evaluation, FloatArray, evaluate

STEP = "signals"
STEP_VERSION = 2  # 2: PRICE reads closed bars only (SRD-BKT-002.050)
INTRADAY_WARMUP_DAYS = 45
DAILY_WARMUP_DAYS = 400
_TIMEFRAMES = ("3m", "15m", "1d", "1w")
_KINDS = (("entry", "entry_condition"), ("exit", "exit_condition"))
PERIOD_COLUMNS = ["kind", "start", "end", "close_at_start", "values", "pnl"]
SIGNAL_COLUMNS = ["strategy", "symbol", *PERIOD_COLUMNS]
_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

_log = logging.getLogger(__name__)

Strategy = Mapping[str, Any]


def load_frames(store: BacktestStore, symbol: str, period: Period) -> dict[str, pd.DataFrame]:
    """Read 3m/15m from 45 days and 1d/1w from 400 days before the start."""
    frames = {}
    for tf in _TIMEFRAMES:
        warmup = INTRADAY_WARMUP_DAYS if tf in ("3m", "15m") else DAILY_WARMUP_DAYS
        frame = store.read(symbol, tf, period.start - timedelta(days=warmup), period.end)  # type: ignore[arg-type]  # tf is a StoredTf
        frames[tf] = frame.reset_index(drop=True)
    return frames


def _hhmm(text: str) -> time:
    hour, minute = text.split(":")[:2]
    return time(int(hour), int(minute))


def schedule_mask(close_et: pd.DatetimeIndex, strategy: Strategy) -> BoolArray:
    """Bars whose close is inside the strategy's hours (start ≤ t < end) and days."""
    start, end = _hhmm(str(strategy["start_time"])), _hhmm(str(strategy["end_time"]))
    times = np.array([t.hour * 60 + t.minute for t in close_et.time])
    days = set(strategy.get("days") or ())
    in_days = np.array([_DAY_NAMES[d] in days for d in close_et.weekday])
    in_hours = (times >= start.hour * 60 + start.minute) & (times < end.hour * 60 + end.minute)
    return np.asarray(in_hours & in_days, dtype=np.bool_)


def periods(fired: BoolArray, close_utc: pd.DatetimeIndex, close_px: FloatArray,
            ev: Evaluation, kind: str) -> pd.DataFrame:
    """One row per run of true bars (SRD-BKT-002.026)."""
    padded = np.concatenate(([False], fired, [False])).astype(np.int8)
    edges = np.diff(padded)
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1
    rows = [
        (kind, close_utc[s], close_utc[e], float(close_px[s]),
         json.dumps({k: None if np.isnan(v[s]) else round(float(v[s]), 4)
                     for k, v in ev.values.items()}),
         ev.uses_pnl)
        for s, e in zip(starts, ends)
    ]
    return pd.DataFrame(rows, columns=PERIOD_COLUMNS)


def compute(strategy: Strategy, frames: Mapping[str, pd.DataFrame], period: Period
            ) -> pd.DataFrame:
    """Entry and exit periods of one strategy on one stock's frames."""
    base = frames["3m"]
    if base.empty:
        return pd.DataFrame(columns=PERIOD_COLUMNS)
    close_utc = pd.DatetimeIndex(base["ts"]).tz_convert("UTC") + pd.Timedelta(minutes=3)
    close_et = close_utc.tz_convert(ET)
    in_period = np.asarray((close_et.date >= period.start) & (close_et.date <= period.end))
    keep = in_period & schedule_mask(close_et, strategy)
    close_px = base["close"].to_numpy(dtype=np.float64)
    parts = []
    for kind, field in _KINDS:
        text = str(strategy.get(field) or "").strip()
        if not text:
            continue
        ev = evaluate(text, frames)
        parts.append(periods(ev.fired & keep, close_utc, close_px, ev, kind))
    if not parts:
        return pd.DataFrame(columns=PERIOD_COLUMNS)
    return pd.concat(parts, ignore_index=True).sort_values("start", ignore_index=True)


def signal_key(strategy: Strategy, symbol: str, period: Period, store: BacktestStore) -> str:
    """Cache key: condition text, hours, days, stock, period and candle coverage."""
    params = {
        "entry": strategy.get("entry_condition", ""), "exit": strategy.get("exit_condition", ""),
        "start_time": strategy.get("start_time"), "end_time": strategy.get("end_time"),
        "days": sorted(strategy.get("days") or ()), "symbol": symbol,
        "period": [period.start, period.end],
        "coverage": [store.coverage(symbol, "3m"), store.coverage(symbol, "1d")],
    }
    return make_key(STEP, STEP_VERSION, params)


def accepts(strategy: Strategy, symbol: str) -> bool:
    """Same stock filter as live ``_StrategyContext.accepts``."""
    mode = strategy.get("symbol_mode", "all")
    if mode == "all":
        return True
    if mode == "include":
        return symbol in (strategy.get("symbols_include") or ())
    if mode == "exclude":
        return symbol not in (strategy.get("symbols_exclude") or ())
    return False


def stocks_for(strategy: Strategy, daily: pd.DataFrame, top_n: int) -> list[str]:
    """Stocks ranked within top N on any day that the strategy accepts."""
    picked = daily if top_n == 0 else daily[daily["rank"] <= top_n]
    return sorted(s for s in set(picked["symbol"]) if accepts(strategy, s))


def _run_pair(strategy: dict[str, Any], symbol: str, root: str, period: Period
              ) -> tuple[str, str, pd.DataFrame]:
    store = BacktestStore(Path(root))
    try:
        frame = compute(strategy, load_frames(store, symbol, period), period)
    except EvaluatorError as exc:
        _log.warning("[Backtest] %s on %s could not be checked: %s",
                     strategy.get("name"), symbol, exc)
        frame = pd.DataFrame(columns=PERIOD_COLUMNS)
    return str(strategy["name"]), symbol, frame


def run_signals(
    period: Period,
    strategies: Sequence[dict[str, Any]],
    daily: pd.DataFrame,
    top_n: int,
    store: BacktestStore,
    cache: StepCache,
    *,
    workers: int = 4,
    progress: Progress | None = None,
    cancel: Cancel | None = None,
) -> pd.DataFrame:
    """Compute missing (strategy, stock) periods and return all of them (SRD-BKT-002.028).

    Raises:
        StepCancelled: ``cancel`` returned true; finished pairs stay cached.
    """
    report = progress or (lambda _done, _total: None)
    stop: Callable[[], bool] = cancel or (lambda: False)
    pairs = [(st, sym, signal_key(st, sym, period, store))
             for st in strategies for sym in stocks_for(st, daily, top_n)]
    keys = {(str(st["name"]), sym): key for st, sym, key in pairs}
    todo = [(st, sym) for st, sym, key in pairs if sym not in cache.names(STEP, key)]
    report(0, len(todo))

    def save(name: str, symbol: str, frame: pd.DataFrame, done: int) -> None:
        cache.write(STEP, keys[(name, symbol)], symbol, frame)
        report(done, len(todo))
        if stop():
            raise StepCancelled

    if workers == 0 or not todo:
        for done, (st, sym) in enumerate(todo, start=1):
            save(*_run_pair(st, sym, str(store.root), period), done)
    else:
        pool = ProcessPoolExecutor(max_workers=min(workers, os.cpu_count() or 1))
        try:
            futures = [pool.submit(_run_pair, st, sym, str(store.root), period)
                       for st, sym in todo]
            for done, future in enumerate(as_completed(futures), start=1):
                save(*future.result(), done)
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    frames = []
    for (name, symbol), key in keys.items():
        frame = cache.read(STEP, key, symbol)
        if frame is not None and not frame.empty:
            frames.append(frame.assign(strategy=name, symbol=symbol))
    if not frames:
        return pd.DataFrame(columns=SIGNAL_COLUMNS)
    return pd.concat(frames, ignore_index=True)[SIGNAL_COLUMNS].sort_values(
        ["start", "strategy", "symbol"], ignore_index=True)

