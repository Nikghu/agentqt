"""
Module: MD-GUI-004.001.M03 / MD-GUI-004.001.M01 — tests
Parent SRD: SRD-GUI-004.013

At app start, intraday candles of stocks the app no longer tracks are deleted,
so the database does not grow forever without "Clear Old Data".
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from us_swing.gui import intraday_cleanup
from us_swing.gui.app_service import AppService
from us_swing.gui.intraday_cleanup import remove_stale_intraday

_TABLES = ("price_1m", "price_3m", "price_15m")


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "candles.db"
    conn = sqlite3.connect(path)
    for table in _TABLES:
        conn.execute(f"CREATE TABLE {table} (symbol TEXT, datetime TEXT, close REAL)")
    conn.commit()
    conn.close()
    return path


def _add(db: Path, symbol: str, newest: str) -> None:
    conn = sqlite3.connect(db)
    for table in _TABLES:
        conn.execute(f"INSERT INTO {table} VALUES (?, ?, 1.0)", (symbol, newest))
    conn.commit()
    conn.close()


def _symbols(db: Path) -> dict[str, list[str]]:
    conn = sqlite3.connect(db)
    out = {t: sorted(r[0] for r in conn.execute(f"SELECT DISTINCT symbol FROM {t}")) for t in _TABLES}
    conn.close()
    return out


def test_stale_stock_deleted_from_all_tables(db: Path) -> None:
    """UT-GUI-004.001.M01.T21: an idle, untracked stock loses all its intraday rows."""
    _add(db, "NEW", "2026-10-22T16:00:00")
    _add(db, "OLD", "2026-10-12T16:00:00")

    assert remove_stale_intraday(db, set(), 5) == ["OLD"]

    assert _symbols(db) == {t: ["NEW"] for t in _TABLES}


def test_kept_stock_survives(db: Path) -> None:
    """UT-GUI-004.001.M01.T22: a kept stock is never deleted, even when idle."""
    _add(db, "NEW", "2026-10-22T16:00:00")
    _add(db, "OLD", "2026-10-12T16:00:00")

    assert remove_stale_intraday(db, {"OLD"}, 5) == []

    assert _symbols(db)["price_1m"] == ["NEW", "OLD"]


def test_recently_idle_stock_survives(db: Path) -> None:
    """UT-GUI-004.001.M01.T23: a stock idle for less than the retention period stays."""
    _add(db, "NEW", "2026-10-22T16:00:00")
    _add(db, "RECENT", "2026-10-19T16:00:00")

    assert remove_stale_intraday(db, set(), 5) == []


def test_long_break_deletes_nothing(db: Path) -> None:
    """UT-GUI-004.001.M01.T24: idle is measured against the newest stored bar, not today."""
    _add(db, "A", "2026-09-01T16:00:00")
    _add(db, "B", "2026-08-31T16:00:00")

    assert remove_stale_intraday(db, set(), 5) == []


def test_cleanup_skipped_without_trade_cycles(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-004.001.M01.T25: with open trades unreadable, nothing is deleted."""
    def _fail(*_args: object) -> list[str]:
        raise AssertionError("cleanup must not run")

    monkeypatch.setattr(intraday_cleanup, "remove_stale_intraday", _fail)

    AppService._cleanup_stale_intraday(SimpleNamespace(_tc_query=None), [])  # type: ignore[arg-type]
