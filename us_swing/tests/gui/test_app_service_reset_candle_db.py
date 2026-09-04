"""
Module: MD-GUI-006 — tests (ISS-GUI-0001)
Parent SRD: SRD-GUI-006.018

Resetting the candle database must clear the daily and weekly candles in place.
Unlinking the file fails on Windows because the app holds the database open for
its own lifetime, and it would also destroy the trades, cycles and strategies
that share the same file.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from us_swing.gui import app_service as svc_mod


@pytest.fixture()
def candle_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real candles.db carrying both candle rows and trading rows."""
    db_path = tmp_path / "candles.db"
    conn = sqlite3.connect(db_path)
    svc_mod._ensure_candle_tables(conn)
    conn.execute("CREATE TABLE price_1m (symbol TEXT, datetime TEXT, close REAL)")
    conn.execute("CREATE TABLE trade_cycles (id INTEGER PRIMARY KEY, symbol TEXT)")
    conn.execute("CREATE TABLE strategies (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany(
        "INSERT INTO price_1d VALUES (?,?,?,?,?,?,?)",
        [("AAPL", "2026-09-01", 1.0, 2.0, 0.5, 1.5, 100)],
    )
    conn.executemany(
        "INSERT INTO price_1w VALUES (?,?,?,?,?,?,?)",
        [("AAPL", "2026-08-31", 1.0, 2.0, 0.5, 1.5, 700)],
    )
    conn.execute("INSERT INTO price_1m VALUES ('AAPL', '2026-09-01T13:30', 1.5)")
    conn.execute("INSERT INTO trade_cycles VALUES (1, 'AAPL')")
    conn.execute("INSERT INTO strategies VALUES (1, 'Momentum')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(svc_mod, "_CANDLE_DB_PATH", db_path)
    monkeypatch.setattr(svc_mod, "_CHECKPOINT_PATH", tmp_path / "checkpoint.json")
    monkeypatch.setattr(svc_mod, "_FAILED_SYMBOLS_PATH", tmp_path / "failed.json")
    return db_path


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def _reset(service: object) -> None:
    """Call the unbound method so no AppService instance is needed."""
    svc_mod.AppService.reset_candle_db(service)  # type: ignore[arg-type]


class _StubService:
    """Stands in for AppService — only what reset_candle_db touches."""

    def __init__(self) -> None:
        self.stopped = False
        self.refreshed = False
        self.logged: list[tuple[str, str]] = []
        self.log_message = self

    def emit(self, level: str, text: str) -> None:
        self.logged.append((level, text))

    def stop_candle_download(self) -> None:
        self.stopped = True

    def refresh_candle_db_status(self) -> None:
        self.refreshed = True


def test_reset_survives_an_open_connection(candle_db: Path) -> None:
    """UT-GUI-006.001.M01.T05: Reset succeeds while the database is held open.

    Reproduces the Windows PermissionError (WinError 32) crash: another live
    connection on candles.db must not stop the reset.
    """
    holder = sqlite3.connect(candle_db)
    holder.execute("SELECT COUNT(*) FROM price_1d").fetchone()
    try:
        _reset(_StubService())
    finally:
        holder.close()

    assert _count(candle_db, "price_1d") == 0
    assert _count(candle_db, "price_1w") == 0


def test_reset_keeps_trading_tables(candle_db: Path) -> None:
    """UT-GUI-006.001.M01.T06: Reset clears candles but keeps trades and strategies."""
    _reset(_StubService())

    assert _count(candle_db, "price_1d") == 0
    assert _count(candle_db, "price_1w") == 0
    assert _count(candle_db, "trade_cycles") == 1
    assert _count(candle_db, "strategies") == 1


def test_reset_keeps_intraday_candles(candle_db: Path) -> None:
    """UT-GUI-006.001.M01.T07: Reset leaves the intraday price tables untouched."""
    _reset(_StubService())

    assert _count(candle_db, "price_1m") == 1


def test_reset_keeps_the_database_file(candle_db: Path) -> None:
    """UT-GUI-006.001.M01.T08: The database file is never unlinked by a reset."""
    _reset(_StubService())

    assert candle_db.exists()


def test_reset_clears_ancillary_files_and_refreshes(
    candle_db: Path, tmp_path: Path
) -> None:
    """UT-GUI-006.001.M01.T09: Reset removes checkpoint plus failed-symbols, then refreshes."""
    (tmp_path / "checkpoint.json").write_text("{}", encoding="utf-8")
    (tmp_path / "failed.json").write_text("{}", encoding="utf-8")

    service = _StubService()
    _reset(service)

    assert not (tmp_path / "checkpoint.json").exists()
    assert not (tmp_path / "failed.json").exists()
    assert service.stopped
    assert service.refreshed


def test_reset_recreates_missing_candle_tables(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-006.001.M01.T10: Reset on a fresh path creates empty candle tables."""
    db_path = tmp_path / "candles.db"
    monkeypatch.setattr(svc_mod, "_CANDLE_DB_PATH", db_path)
    monkeypatch.setattr(svc_mod, "_CHECKPOINT_PATH", tmp_path / "checkpoint.json")
    monkeypatch.setattr(svc_mod, "_FAILED_SYMBOLS_PATH", tmp_path / "failed.json")

    _reset(_StubService())

    assert _count(db_path, "price_1d") == 0
    assert _count(db_path, "price_1w") == 0
