"""
Module: MD-GUI-006 — tests (ISS-GUI-0003)
Parent SRD: SRD-GUI-006.019

Weekly candles are built from the stored daily candles. IBKR's own weekly bars
stamped the in-progress week with the request day (one extra row per download)
and started short request windows mid-week (a cut-short bar overwrote the full one).
"""
from __future__ import annotations

import asyncio
import datetime
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from us_swing.gui import app_service as svc_mod

_MON = datetime.date(2026, 10, 12)


def _day(offset: int) -> str:
    return (_MON + datetime.timedelta(days=offset)).strftime("%Y-%m-%dT00:00:00")


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp_path / "candles.db")
    svc_mod._ensure_candle_tables(c)
    return c


def _insert_daily(c: sqlite3.Connection, symbol: str, offsets: list[int]) -> None:
    c.executemany(
        "INSERT INTO price_1d VALUES (?,?,?,?,?,?,?)",
        [(symbol, _day(i), 10.0 + i, 20.0 + i, 5.0 + i, 15.0 + i, 100 * (i + 1)) for i in offsets],
    )


def _weekly(c: sqlite3.Connection, symbol: str) -> list[tuple[Any, ...]]:
    return c.execute(
        "SELECT datetime, open, high, low, close, volume FROM price_1w "
        "WHERE symbol = ? ORDER BY datetime",
        (symbol,),
    ).fetchall()


def test_full_week_aggregates_daily(conn: sqlite3.Connection) -> None:
    """UT-GUI-006.001.M01.T11: a Mon–Fri week becomes one Friday-dated weekly row."""
    _insert_daily(conn, "AAPL", [0, 1, 2, 3, 4])

    written = svc_mod._rebuild_weekly_from_daily(conn, "AAPL")

    assert written == 1
    assert _weekly(conn, "AAPL") == [(_day(4), 10.0, 24.0, 5.0, 19.0, 1500)]


def test_rebuild_replaces_stale_rows_for_same_week(conn: sqlite3.Connection) -> None:
    """UT-GUI-006.001.M01.T12: stale in-progress and cut-short rows are replaced."""
    _insert_daily(conn, "AAPL", [0, 1, 2])
    conn.executemany(
        "INSERT INTO price_1w VALUES (?,?,?,?,?,?,?)",
        [("AAPL", _day(1), 10.0, 21.0, 5.0, 16.0, 300),
         ("AAPL", _day(4), 12.0, 22.0, 7.0, 17.0, 300)],
    )

    svc_mod._rebuild_weekly_from_daily(conn, "AAPL")

    assert _weekly(conn, "AAPL") == [(_day(2), 10.0, 22.0, 5.0, 17.0, 600)]


def test_holiday_week_dated_on_last_trading_day(conn: sqlite3.Connection) -> None:
    """UT-GUI-006.001.M01.T13: a week ending on a Thursday is dated Thursday."""
    _insert_daily(conn, "AAPL", [0, 1, 2, 3, 7])

    svc_mod._rebuild_weekly_from_daily(conn, "AAPL")

    assert [row[0] for row in _weekly(conn, "AAPL")] == [_day(3), _day(7)]


def test_rebuild_touches_only_given_symbol(conn: sqlite3.Connection) -> None:
    """UT-GUI-006.001.M01.T14: other symbols' weekly rows are left alone."""
    _insert_daily(conn, "AAPL", [0, 1])
    conn.execute("INSERT INTO price_1w VALUES ('MSFT', ?, 1, 2, 0.5, 1.5, 9)", (_day(4),))

    svc_mod._rebuild_weekly_from_daily(conn, "AAPL")

    assert _weekly(conn, "MSFT") == [(_day(4), 1.0, 2.0, 0.5, 1.5, 9)]


class _FakeIB:
    """Stands in for ``ib_insync.IB``; records the bar sizes requested."""

    def __init__(self, daily: list[SimpleNamespace]) -> None:
        self._daily = daily
        self.bar_sizes: list[str] = []

    async def reqHistoricalDataAsync(self, contract: Any, **kwargs: Any) -> list[SimpleNamespace]:
        self.bar_sizes.append(kwargs["barSizeSetting"])
        return self._daily if kwargs["barSizeSetting"] == "1 day" else []

    def isConnected(self) -> bool:
        return True


@pytest.fixture()
def worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: Any) -> Any:
    monkeypatch.setattr(svc_mod, "_CANDLE_DB_PATH", tmp_path / "candles.db")
    monkeypatch.setattr(svc_mod, "_CHECKPOINT_PATH", tmp_path / "checkpoint.json")
    monkeypatch.setattr(svc_mod, "_CANDLE_SYMBOL_PAUSE_S", 0.0)
    return svc_mod._CandleDownloadWorker(
        symbols=["AAPL"], start_date=_MON, end_date=_MON + datetime.timedelta(days=4),
        mode="full", ibkr_host="127.0.0.1", ibkr_port=7497, ibkr_client_id=1,
        benchmark_symbol="",
    )


def test_download_builds_weekly_from_daily(worker: Any, tmp_path: Path) -> None:
    """UT-GUI-006.001.M01.T15: no IBKR weekly request; weekly built from saved daily bars."""
    daily = [
        SimpleNamespace(date=_MON + datetime.timedelta(days=i), open=10.0, high=20.0 + i,
                        low=5.0, close=15.0 + i, volume=100)
        for i in range(5)
    ]
    ib = _FakeIB(daily)
    finished: list[tuple[int, int]] = []
    worker.finished.connect(lambda d, w: finished.append((d, w)))

    asyncio.run(worker._download_all(ib))

    assert ib.bar_sizes == ["1 day"]
    assert finished == [(5, 1)]
    conn = sqlite3.connect(tmp_path / "candles.db")
    assert _weekly(conn, "AAPL") == [(_day(4), 10.0, 24.0, 5.0, 19.0, 500)]


def test_download_without_daily_bars_reports_no_data(worker: Any, tmp_path: Path) -> None:
    """UT-GUI-006.001.M01.T16: no daily bars → NO_DATA and no weekly rows."""
    failures: list[tuple[str, str]] = []
    worker.symbol_failed.connect(lambda s, r: failures.append((s, r)))

    asyncio.run(worker._download_all(_FakeIB([])))

    assert failures == [("AAPL", "NO_DATA")]
    conn = sqlite3.connect(tmp_path / "candles.db")
    assert _weekly(conn, "AAPL") == []
