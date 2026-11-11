"""
Module: MD-MKT-016.004.M02 — market/post_mortem_facts.py
Parent SRD: SRD-MKT-016.004
Also: SRD-MKT-016.005 (price path from Backtest Data, then candles.db)

Code part of the pick post-mortem: one plain record per chosen lead pick, built from the
facts the desk stored on its data day and from its price path after that day. Daily bars
come from Backtest Data; candles.db only fills days Backtest Data does not have yet.
"""
from __future__ import annotations

import logging
import math
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from us_swing.core.desk_contract import DB_NAME
from us_swing.market.candles import BENCHMARK, CANDLE_DB, CandleReader
from us_swing.market.pick_results import ENTRY_DAYS, HOLD_DAYS
from us_swing.market.proof_data import BACKTEST_ROOT, read_daily

log = logging.getLogger(__name__)

CUT = 120
PATH_DAYS = ENTRY_DAYS + HOLD_DAYS


@dataclass(frozen=True)
class PickBars:
    """Wide daily frames by date; ``opens`` may miss days that came from candles.db."""

    opens: pd.DataFrame
    highs: pd.DataFrame
    lows: pd.DataFrame
    closes: pd.DataFrame


def _plain(frame: pd.DataFrame) -> pd.DataFrame:
    index = pd.DatetimeIndex(frame.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    out = frame.copy()
    out.index = index.normalize()
    return out[~out.index.duplicated(keep="last")].sort_index()


def _empty() -> pd.DataFrame:
    return pd.DataFrame(index=pd.DatetimeIndex([]))


def pick_bars(symbols: Iterable[str], root: Path = BACKTEST_ROOT,
              candles: Path = CANDLE_DB) -> PickBars:
    """Daily bars of ``symbols`` and SPY: Backtest Data first, candles.db for missing days."""
    wanted = sorted({*symbols, BENCHMARK})
    bt = read_daily(wanted, root)
    frames = {k: _empty() for k in ("open", "high", "low", "close")}
    if bt is not None:
        frames = {"open": _plain(bt.opens), "high": _plain(bt.bars.highs),
                  "low": _plain(bt.bars.lows), "close": _plain(bt.bars.closes)}
    try:
        local = CandleReader(candles).read(wanted)
    except (FileNotFoundError, sqlite3.Error, pd.errors.DatabaseError, ValueError) as exc:
        log.info("[Research] No candles.db bars to fill in: %s", exc)
    else:
        for key, extra in (("high", local.highs), ("low", local.lows), ("close", local.closes)):
            frames[key] = frames[key].combine_first(_plain(extra))
    return PickBars(frames["open"], frames["high"], frames["low"], frames["close"])


def _column(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    return pd.to_numeric(frame[col], errors="coerce").astype(float)


def _value(frame: pd.DataFrame, col: str, when: pd.Timestamp) -> float | None:
    value = _column(frame, col).get(when)
    return None if value is None or math.isnan(value) else float(value)


def path_line(bars: PickBars, side: str, symbol: str, day: str, trigger: float, stop: float,
              exit_day: str | None) -> str:
    """Entry gap, best and worst move in R, and SPY's move from the data day to the exit."""
    high_col = _column(bars.highs, symbol).dropna()
    low_col = _column(bars.lows, symbol)
    start = pd.Timestamp(day)
    after = high_col[high_col.index > start]
    if exit_day:
        after = after[after.index <= pd.Timestamp(exit_day)]
    after = after.iloc[:PATH_DAYS]
    risk = abs(trigger - stop)
    if after.empty or risk <= 0:
        return "path: no bars"
    days = list(after.index)
    long = side == "long"
    highs = [float(v) for v in after]
    lows = [float(v) for v in low_col.reindex(days).fillna(after)]
    best = (max(highs) - trigger) / risk if long else (trigger - min(lows)) / risk
    worst = (min(lows) - trigger) / risk if long else (trigger - max(highs)) / risk
    parts = [f"best {best:+.1f}R", f"worst {worst:+.1f}R"]
    first_open = _value(bars.opens, symbol, days[0])
    if first_open is not None and trigger:
        parts.insert(0, f"gap {(first_open / trigger - 1) * 100:+.1f}%")
    spy_from = _value(bars.closes, BENCHMARK, start)
    spy_to = _value(bars.closes, BENCHMARK, days[-1])
    if spy_from and spy_to is not None:
        parts.append(f"SPY {(spy_to / spy_from - 1) * 100:+.1f}%")
    return "path " + ", ".join(parts)


def _has(con: sqlite3.Connection, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                       (table,)).fetchone() is not None


def _one(con: sqlite3.Connection, table: str, cols: str, key: tuple[str, str, str]
         ) -> tuple[object, ...] | None:
    if not _has(con, table):
        return None
    row = con.execute(f"SELECT {cols} FROM {table} WHERE date = ? AND side = ? "  # noqa: S608
                      "AND symbol = ?", key).fetchone()
    return tuple(row) if row else None


def _cut(text: object) -> str:
    return str(text or "").strip().replace("\n", " ")[:CUT]


def _num(value: object, fmt: str) -> str:
    return format(float(value), fmt) if isinstance(value, int | float) else "?"


@dataclass(frozen=True)
class _Facts:
    text: str
    trigger: float | None
    stop: float | None
    exit_day: str | None


def _facts(con: sqlite3.Connection, key: tuple[str, str, str]) -> _Facts:
    parts: list[str] = []
    trigger = stop = None
    idea = _one(con, "ideas", "setup, score, trigger, stop", key)
    if idea:
        setup, score, trig, stp = idea
        trigger = float(trig) if isinstance(trig, int | float) else None
        stop = float(stp) if isinstance(stp, int | float) else None
        parts.append(f"{setup or 'no setup'}, score {_num(score, '.0f')}, "
                     f"trigger {_num(trig, '.2f')}, stop {_num(stp, '.2f')}")
    if _has(con, "idea_reasons"):
        reasons = [str(r[0]) for r in con.execute(
            "SELECT reason FROM idea_reasons WHERE date = ? AND side = ? AND symbol = ? "
            "ORDER BY seq LIMIT 2", key)]
        if reasons:
            parts.append("idea: " + _cut("; ".join(reasons)))
    review = _one(con, "setup_review", "grade, note", key)
    if review:
        parts.append(f"grade {review[0]} ({_cut(review[1])})")
    risk = _one(con, "risk_check", "verdict, reason", key)
    if risk:
        parts.append(f"risk {risk[0]}" + (f" ({_cut(risk[1])})" if risk[1] else ""))
    lead = _one(con, "lead_picks", "reason", key)
    if lead and lead[0]:
        parts.append("lead: " + _cut(lead[0]))
    tone = _one(con, "news_tags", "tone, reason", key)
    if tone:
        parts.append(f"tone {tone[0]}")
    if _has(con, "regime_snapshot"):
        row = con.execute("SELECT regime FROM regime_snapshot WHERE date = ?",
                          (key[0],)).fetchone()
        if row:
            parts.append(f"regime {row[0]}")
    result = _one(con, "pick_results", "status, entry_day, exit_day, r", key)
    exit_day = None
    if result:
        status, entry_day, out_day, r = result
        exit_day = str(out_day) if out_day else None
        parts.append(f"result {status} {_num(r, '+.2f')}R (in {entry_day or '?'}, "
                     f"out {out_day or '?'})")
    return _Facts("; ".join(parts) or "no stored facts", trigger, stop, exit_day)


def pick_records(home: Path, keys: Sequence[str],
                 bars: Callable[[Iterable[str]], PickBars] = pick_bars) -> list[str]:
    """One record line per ``date|side|symbol`` key: stored facts, then the price path."""
    if not keys:
        return []
    split = [tuple(k.split("|", 2)) for k in keys]
    loaded = bars(sorted({s[2] for s in split if len(s) == 3}))
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    try:
        lines = []
        for key, parts in zip(keys, split, strict=True):
            if len(parts) != 3:
                continue
            day, side, symbol = parts
            facts = _facts(con, (day, side, symbol))
            path = ("path: no levels" if facts.trigger is None or facts.stop is None else
                    path_line(loaded, side, symbol, day, facts.trigger, facts.stop,
                              facts.exit_day))
            lines.append(f"{key}: {facts.text}; {path}")
        return lines
    finally:
        con.close()
