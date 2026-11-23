"""
Module: MD-EXE-022.015.M06 — usswing testing kit
Parent SRD: SRD-EXE-022.015

Load the tool's saved candles and run an indicator on them, for tests and scripts.
The candle file is opened read-only, so nothing here can change the tool's data.

Example::

    from usswing.testing import load_candles, run
    from my_st import MySt

    candles = load_candles("AAPL", ["3m"], days=5)
    print(run(MySt, candles).table().tail(20))
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import closing
from pathlib import Path
from typing import Any

import pandas as pd

from usswing._indicator import Result, USSwingIndicator, compute

__all__ = ["CANDLES_DB", "TIMEFRAMES", "Result", "connect", "load_candles", "run"]

CANDLES_DB = Path.home() / ".usswing" / "candles.db"
TIMEFRAMES = ("3m", "15m", "30m", "1d", "1w")
_DAILY = ("1d", "1w")
_MARKET_TZ = "America/New_York"

Day = str | dt.date


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open the candle file read-only; any write through it fails."""
    path = Path(db_path or CANDLES_DB)
    if not path.is_file():
        raise FileNotFoundError(f"No candle file at {path}")
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def load_candles(symbol: str, timeframes: Iterable[str] = ("3m",), days: int = 30, *,
                 start: Day | None = None, end: Day | None = None,
                 db_path: Path | str | None = None) -> dict[str, pd.DataFrame]:
    """Saved candles of one stock, oldest first, one frame per timeframe.

    Args:
        symbol: Stock symbol, for example ``"AAPL"``.
        timeframes: Any of 3m, 15m, 30m, 1d, 1w. The first one sets the market days.
        days: Keep the last this many market days of the first timeframe.
        start: First day to keep (``"2026-11-02"``); used with ``end`` instead of ``days``.
        end: Last day to keep.
        db_path: Another candle file; the tool's own file by default.

    Returns:
        ``{timeframe: frame}`` with columns datetime, open, high, low, close, volume.
    """
    wanted = list(timeframes)
    for timeframe in wanted:
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Timeframe {timeframe!r} is not one of {', '.join(TIMEFRAMES)}")
    if not wanted:
        raise ValueError("Give at least one timeframe")
    with closing(connect(db_path)) as conn:
        frames = {tf: _read(conn, symbol.upper(), tf) for tf in wanted}
    first, last = _day_range(frames[wanted[0]], wanted[0], days, start, end)
    return {tf: _between(frame, tf, first, last) for tf, frame in frames.items()}


def run(indicator_class: type[USSwingIndicator], candles: Mapping[str, pd.DataFrame],
        values: Mapping[str, Any] | None = None) -> Result:
    """Run the indicator the way the tool does; missing values use the defaults.

    Returns:
        The values, the debug series and the main timeframe; ``.table()`` lists them.
    """
    def source(_symbol_type: str, timeframe: str) -> pd.DataFrame:
        frame = candles.get(timeframe)
        if frame is None or frame.empty:
            raise LookupError(f"No candles for timeframe {timeframe!r}")
        return frame

    return compute(indicator_class(source, values))


def _read(conn: sqlite3.Connection, symbol: str, timeframe: str) -> pd.DataFrame:
    try:
        frame = pd.read_sql_query(
            f"SELECT datetime, open, high, low, close, volume FROM price_{timeframe} "
            "WHERE symbol = ? ORDER BY datetime", conn, params=(symbol,))
    except pd.errors.DatabaseError:
        frame = pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
    frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
    return frame


def _days(frame: pd.DataFrame, timeframe: str) -> pd.Series:
    """Market day of each candle; intraday times are saved in UTC."""
    times = frame["datetime"]
    if timeframe not in _DAILY:
        times = times.dt.tz_convert(_MARKET_TZ)
    days: pd.Series = times.dt.date
    return days


def _day_range(frame: pd.DataFrame, timeframe: str, days: int, start: Day | None,
               end: Day | None) -> tuple[dt.date | None, dt.date | None]:
    if start is not None or end is not None:
        return _as_date(start), _as_date(end)
    if days < 1:
        raise ValueError("days must be 1 or more")
    market_days = sorted(set(_days(frame, timeframe)))
    return (market_days[-days] if len(market_days) >= days else None), None


def _as_date(day: Day | None) -> dt.date | None:
    if day is None or isinstance(day, dt.date):
        return day
    return dt.date.fromisoformat(day)


def _between(frame: pd.DataFrame, timeframe: str, first: dt.date | None,
             last: dt.date | None) -> pd.DataFrame:
    days = _days(frame, timeframe)
    keep = pd.Series(True, index=frame.index)
    if first is not None:
        keep &= days >= first
    if last is not None:
        keep &= days <= last
    return frame[keep].reset_index(drop=True)
