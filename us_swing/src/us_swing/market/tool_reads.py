"""
Module: MD-MKT-021.007.M02 — market/tool_reads.py
Parent SRD: SRD-MKT-021.007
Also: SRD-MKT-021.008 (intraday bars), .009 (desk rows), .010 (plain data, input checks)

Read functions a built tool may call inside its sandbox (AI Desk v3 M7b). ``reads()`` binds
them to the desk folder and the Backtest Data folder. They only read, return plain lists and
dicts (never a pandas object, whose methods can write files), refuse bad input with a short
``ValueError`` the tool may pass on, and never call a model. The sandbox child loads ``reads``
by import path. Design: DD-MKT-021.007.D01.
"""
from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_recipes import MENU
from us_swing.data.market_calendar import ET
from us_swing.market.proof_data import BACKTEST_ROOT

MAX_DAILY = 1300
MAX_INTRADAY = 60
MAX_DESK = 60
MINUTES = (15, 30)
BAD_SYMBOL = "bad symbol"
_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9. -]{0,9}$")
_PRICES = ["open", "high", "low", "close", "volume"]
Read = Callable[..., list[dict[str, Any]]]


def _symbol(symbol: object) -> str:
    text = symbol.strip().upper() if isinstance(symbol, str) else ""
    if not _SYMBOL.match(text):
        raise ValueError(BAD_SYMBOL)
    return text


def _count(days: object, most: int) -> int:
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= most:
        raise ValueError(f"days must be 1 to {most}")
    return days


def _bars(frame: pd.DataFrame, stamp: str, stamps: pd.Series) -> list[dict[str, Any]]:
    """Plain dicts, oldest first: the time text and the five prices as floats."""
    prices = frame[_PRICES].astype("float64").to_numpy().tolist()
    return [{stamp: text, **dict(zip(_PRICES, row, strict=True))}
            for text, row in zip(stamps.tolist(), prices, strict=True)]


def _daily(root: Path, symbol: object, days: object = 260) -> list[dict[str, Any]]:
    """The last ``days`` daily bars of a stock from Backtest Data, oldest first (.007)."""
    sym, count = _symbol(symbol), _count(days, MAX_DAILY)
    path = root / "1d" / f"{sym}.parquet"
    if not path.is_file():
        return []
    frame = pd.read_parquet(path, columns=["ts", *_PRICES])
    frame["ts"] = pd.to_datetime(frame["ts"]).dt.normalize()
    frame = frame.drop_duplicates("ts", keep="last").sort_values("ts").tail(count)
    return _bars(frame, "day", frame["ts"].dt.strftime("%Y-%m-%d"))


def _intraday(root: Path, symbol: object, minutes: object = 30,
              days: object = 10) -> list[dict[str, Any]]:
    """The 15- or 30-minute bars of a stock's last ``days`` New York dates, oldest first (.008)."""
    sym = _symbol(symbol)
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes not in MINUTES:
        raise ValueError("minutes must be 15 or 30")
    count = _count(days, MAX_INTRADAY)
    files = sorted((root / f"{minutes}m" / sym).glob("*.parquet"))[-2:]
    if not files:
        return []
    frame = pd.concat([pd.read_parquet(f, columns=["ts", *_PRICES]) for f in files],
                      ignore_index=True)
    stamps = pd.to_datetime(frame["ts"], utc=True).dt.tz_convert(ET)
    frame = frame.assign(ts=stamps).drop_duplicates("ts", keep="last").sort_values("ts")
    dates = frame["ts"].dt.date
    keep = sorted(set(dates))[-count:]
    frame = frame[dates.isin(keep)]
    return _bars(frame, "time", frame["ts"].dt.strftime("%Y-%m-%d %H:%M"))


def _value(value: object) -> object:
    return round(value, 4) if isinstance(value, float) else value


def _desk(home: Path, source: object, symbol: object = None,
          days: object = 1) -> list[dict[str, Any]]:
    """The date and menu columns of one data recipe source for its last ``days`` dates,
    oldest first (.009). SQL names come only from the menu; values are bound."""
    if not isinstance(source, str) or source not in MENU:
        raise ValueError(f"unknown source {source}")
    src = MENU[source]
    count = _count(days, MAX_DESK)
    keyed = "symbol" in src.columns
    if keyed and symbol is None:
        raise ValueError(f"{source} needs a symbol")
    if not keyed and symbol is not None:
        raise ValueError(f"{source} takes no symbol")
    sym = _symbol(symbol) if keyed else None
    path = home / DB_NAME
    if not path.exists():
        return []
    names = list(src.columns)
    pick = ", ".join(f"{src.columns[c][0]} AS {c}" for c in names)
    day_table = src.day.split(".")[0]
    day_from = src.table if day_table == "s" else day_table
    sql = (f"SELECT {src.day} AS date, {pick} FROM {src.table} WHERE {src.day} IN "
           f"(SELECT DISTINCT {src.day} FROM {day_from} ORDER BY 1 DESC LIMIT ?)")
    params: list[object] = [count]
    if sym is not None:
        sql += f" AND {src.columns['symbol'][0]} = ?"
        params.append(sym)
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        rows = con.execute(sql + f" ORDER BY {src.day}", params).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return []
        raise
    finally:
        con.close()
    return [{name: _value(v) for name, v in zip(["date", *names], row, strict=True)}
            for row in rows]


def reads(home: Path, backtest: Path | None = None) -> dict[str, Read]:
    """The three read functions bound to the desk folder and the Backtest Data folder (.010).

    Args:
        home: Desk folder holding ``desk.db``.
        backtest: Backtest Data folder; the app's folder when ``None``.

    Returns:
        ``daily_bars``, ``intraday_bars`` and ``desk_rows`` by name.
    """
    root = backtest or BACKTEST_ROOT

    def daily_bars(symbol: str, days: int = 260) -> list[dict[str, Any]]:
        return _daily(root, symbol, days)

    def intraday_bars(symbol: str, minutes: int = 30, days: int = 10) -> list[dict[str, Any]]:
        return _intraday(root, symbol, minutes, days)

    def desk_rows(source: str, symbol: str | None = None, days: int = 1) -> list[dict[str, Any]]:
        return _desk(home, source, symbol, days)

    return {"daily_bars": daily_bars, "intraday_bars": intraday_bars, "desk_rows": desk_rows}
