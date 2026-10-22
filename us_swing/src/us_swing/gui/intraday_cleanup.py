"""
Module: MD-GUI-004.001.M03 — gui/intraday_cleanup.py
Parent SRD: SRD-GUI-004.013

Deletes the intraday candles of stocks the app no longer tracks, so the
database does not grow forever when the user never runs "Clear Old Data".
"""
from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path

_INTRADAY_TABLES: tuple[str, ...] = ("price_1m", "price_3m", "price_15m")


def _newest_bar_per_symbol(conn: sqlite3.Connection) -> dict[str, str]:
    newest: dict[str, str] = {}
    for table in _INTRADAY_TABLES:
        try:
            rows = conn.execute(
                f"SELECT symbol, MAX(datetime) FROM {table} GROUP BY symbol"  # noqa: S608
            ).fetchall()
        except sqlite3.OperationalError:
            continue
        for symbol, last in rows:
            if last and last > newest.get(symbol, ""):
                newest[symbol] = last
    return newest


def remove_stale_intraday(db_path: Path, keep: set[str], idle_days: int) -> list[str]:
    """Delete all intraday rows of stocks that are not kept and have gone idle.

    A stock is idle when its newest bar is more than ``idle_days`` older than
    the newest bar in the database. Measuring against the database, not today,
    means a long break from the app deletes nothing.

    Returns:
        The symbols whose rows were deleted, sorted.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        newest = _newest_bar_per_symbol(conn)
        if not newest:
            return []
        latest = datetime.datetime.fromisoformat(max(newest.values()))
        cutoff = (latest - datetime.timedelta(days=idle_days)).strftime("%Y-%m-%dT%H:%M:%S")
        stale = sorted(s for s, last in newest.items() if last < cutoff and s not in keep)
        if not stale:
            return []
        placeholders = ",".join("?" * len(stale))
        for table in _INTRADAY_TABLES:
            try:
                conn.execute(
                    f"DELETE FROM {table} WHERE symbol IN ({placeholders})",  # noqa: S608
                    stale,
                )
            except sqlite3.OperationalError:
                continue
        conn.commit()
        return stale
    finally:
        conn.close()
