"""
Module: MD-MKT-021.001.M01 — market/table_tools.py
Parent SRD: SRD-MKT-021.001
Also: SRD-MKT-021.002 (RS rank), .003 (ATR percent), .004 (setup of the better side),
.005 (trading days to earnings), .006 (read-only, no AI call)

Table tools for task cards (AI Desk v3 M6). Each tool fills some columns of a table for a
list of symbols and returns a ``ToolResult``. A tool only reads: daily bars through the
reader the daily views use, and the day's RS and score rows in ``desk.db``. It takes no
gateway, so it cannot call a model, and a read error rises to its tool group
(``desk/champions.py``), the only caller. Design: DD-MKT-021.001.D01.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_registry import ToolResult
from us_swing.core.econ_calendar import is_trading_day
from us_swing.data.market_calendar import ET
from us_swing.market.candles import CANDLE_DB, CandleReader, DailyBars
from us_swing.market.earnings import next_earnings
from us_swing.market.score import NO_SETUP
from us_swing.market.setups import Bars, atr

KEY = "symbol"
ATR_DAYS = 14
NEAR_DAYS = 5
NO_CANDLE_FILE = "the candle database was not found"
NO_BARS = "no daily bars"
NO_RS = "no RS rating for the latest day"
FEW_BARS = f"fewer than {ATR_DAYS + 1} daily bars"
NOT_SCORED = "not scored on the latest day"
NO_SETUP_REASON = "no setup"
NO_EARNINGS = "no earnings date found"


def _bars(home: Path, symbols: Sequence[str]) -> DailyBars:
    try:
        reader = CandleReader(CANDLE_DB, topup=home)
    except FileNotFoundError:
        raise FileNotFoundError(NO_CANDLE_FILE) from None
    return reader.read(symbols)


def _latest(home: Path, table: str, columns: str,
            symbols: Sequence[str]) -> list[tuple[Any, ...]]:
    """Rows of ``table`` for ``symbols`` on its latest date; empty with no file or table."""
    path = home / DB_NAME
    if not path.exists():
        return []
    marks = ",".join("?" * len(symbols))
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        return con.execute(
            f"SELECT {columns} FROM {table} WHERE date = (SELECT MAX(date) FROM {table}) "  # noqa: S608 — names are constants
            f"AND symbol IN ({marks})", tuple(symbols)).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return []
        raise
    finally:
        con.close()


def _data_day(home: Path) -> date:
    """The latest scored day, or today in New York when nothing is scored yet."""
    path = home / DB_NAME
    if path.exists():
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
        try:
            row = con.execute("SELECT MAX(date) FROM stock_rs").fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc):
                raise
            row = None
        finally:
            con.close()
        if row and row[0]:
            return date.fromisoformat(str(row[0]))
    return datetime.now(ET).date()


def _trading_days(start: date, end: date) -> int:
    """Trading days after ``start`` up to and including ``end``."""
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        count += is_trading_day(day)
    return count


def daily_close(home: Path, symbols: Sequence[str]) -> ToolResult:
    """Last daily close of each symbol."""
    if not symbols:
        return ToolResult()
    closes = _bars(home, symbols).closes
    rows: list[dict[str, Any]] = []
    missing: dict[str, str] = {}
    for symbol in symbols:
        series = closes[symbol].dropna() if symbol in closes.columns else None
        if series is None or series.empty:
            missing[symbol] = NO_BARS
        else:
            rows.append({KEY: symbol, "close": round(float(series.iloc[-1]), 2)})
    return ToolResult(rows=rows, missing=missing)


def rs_rank(home: Path, symbols: Sequence[str]) -> ToolResult:
    """RS rating of each symbol on the latest data day."""
    if not symbols:
        return ToolResult()
    found = {str(s): r for s, r in _latest(home, "stock_rs", "symbol, rs_rating", symbols)
             if r is not None}
    return ToolResult(
        rows=[{KEY: s, "rs_rank": int(found[s])} for s in symbols if s in found],
        missing={s: NO_RS for s in symbols if s not in found})


def atr_pct(home: Path, symbols: Sequence[str]) -> ToolResult:
    """14-day average true range of each symbol as a percent of its last close."""
    if not symbols:
        return ToolResult()
    bars = _bars(home, symbols)
    rows: list[dict[str, Any]] = []
    missing: dict[str, str] = {}
    for symbol in symbols:
        days = (bars.closes[symbol].dropna().index[-(ATR_DAYS + 1):]
                if symbol in bars.closes.columns else None)
        value = None
        if days is not None and len(days) == ATR_DAYS + 1:
            own = Bars(*(frame.loc[days, [symbol]]
                         for frame in (bars.closes, bars.highs, bars.lows, bars.volumes)))
            last = float(atr(own, ATR_DAYS)[symbol].iloc[-1])
            close = float(own.closes[symbol].iloc[-1])
            value = last / close * 100 if last == last and close > 0 else None
        if value is None:
            missing[symbol] = FEW_BARS
        else:
            rows.append({KEY: symbol, "atr_pct": round(value, 2)})
    return ToolResult(rows=rows, missing=missing)


def setup(home: Path, symbols: Sequence[str]) -> ToolResult:
    """Better-scored side of each symbol on the latest data day, with its setup, trigger and
    stop."""
    if not symbols:
        return ToolResult()
    best: dict[str, tuple[Any, ...]] = {}
    for symbol, side, score, name, trigger, stop in _latest(
            home, "stock_score", 'symbol, side, score, setup, "trigger", stop', symbols):
        rank = -1.0 if score is None else float(score)
        old = best.get(str(symbol))
        if old is None or rank > old[1] or (rank == old[1] and side == "long"):
            best[str(symbol)] = (side, rank, name, trigger, stop)
    rows: list[dict[str, Any]] = []
    missing: dict[str, str] = {}
    for symbol in symbols:
        if symbol not in best:
            missing[symbol] = NOT_SCORED
            continue
        side, _score, name, trigger, stop = best[symbol]
        has_setup = bool(name) and name != NO_SETUP
        rows.append({KEY: symbol, "side": str(side), "setup": str(name) if has_setup else "none",
                     "trigger": trigger if has_setup else None,
                     "stop": stop if has_setup else None})
        if not has_setup:
            missing[f"{symbol}.trigger"] = missing[f"{symbol}.stop"] = NO_SETUP_REASON
    return ToolResult(rows=rows, missing=missing)


def earnings(home: Path, symbols: Sequence[str]) -> ToolResult:
    """Trading days from the latest data day to each symbol's next earnings date."""
    if not symbols:
        return ToolResult()
    day = _data_day(home)
    dates = next_earnings(symbols)
    rows: list[dict[str, Any]] = []
    missing: dict[str, str] = {}
    flags: dict[str, str] = {}
    for symbol in symbols:
        when = dates.get(symbol)
        if when is None or when < day:
            missing[symbol] = NO_EARNINGS
            continue
        days = _trading_days(day, when)
        rows.append({KEY: symbol, "earn_days": days})
        if days <= NEAR_DAYS:
            flags[symbol] = ("earnings today" if days == 0 else
                             f"earnings in {days} trading day{'' if days == 1 else 's'}")
    return ToolResult(rows=rows, missing=missing, flags=flags)
