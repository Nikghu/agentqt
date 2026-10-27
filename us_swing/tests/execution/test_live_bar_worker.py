"""
Module: MD-EXE-007.001.M01 test cases
Parent SRD: SRD-EXE-007.010
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from us_swing.analysis.candle_builder import CandleBuilder
from us_swing.execution.live_bar_worker import LiveBarWorker

# Monday 2026-10-26 — 14:30 UTC is 10:30 ET, inside regular trading hours.
_WINDOW_START = datetime(2026, 10, 26, 14, 30, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "candles.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE price_15m (symbol TEXT, datetime TEXT, open REAL, high REAL,"
        " low REAL, close REAL, volume INTEGER, PRIMARY KEY (symbol, datetime))"
    )
    conn.close()
    return str(path)


def _worker(db_path: str = "") -> LiveBarWorker:
    return LiveBarWorker(["DELL"], "127.0.0.1", 7497, 1, db_path)


def _saved_15m_windows(first_bar: datetime, later_bars: list[datetime]) -> int:
    """Feed IBKR 5-second bars and return how many 15m candles were passed on for saving."""
    worker = _worker()
    builder = CandleBuilder(["15m"], on_candle_closed=worker._on_candle_closed)
    saved: list[str] = []
    worker.candle_closed.connect(saved.append)
    handler = worker._make_bar_handler("DELL", builder)
    bars: list[SimpleNamespace] = []
    for t in [first_bar, *later_bars]:
        bars.append(SimpleNamespace(time=t, open_=100.0, high=101.0, low=99.0, close=100.5, volume=10))
        handler(bars, True)
    return len(saved)


def test_yahoo_forming_bar_not_saved(db_path: str) -> None:
    """UT-EXE-007.001.M01.T27: a Yahoo 15m bar still forming is skipped; closed bars are saved."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    closed_start = now - timedelta(minutes=40)
    forming_start = now - timedelta(minutes=5)
    df = pd.DataFrame(
        {"Open": [470.0, 471.38], "High": [472.0, 471.38], "Low": [469.0, 471.38],
         "Close": [471.0, 471.38], "Volume": [5000, 0]},
        index=pd.DatetimeIndex([closed_start, forming_start]),
    )

    wrote = _worker(db_path)._write_yfinance_direct("DELL", df, "15m")

    rows = sqlite3.connect(db_path).execute("SELECT datetime FROM price_15m").fetchall()
    assert wrote == 1
    assert rows == [(closed_start.strftime("%Y-%m-%dT%H:%M:%S"),)]


def test_first_partial_ibkr_window_not_saved() -> None:
    """UT-EXE-007.001.M01.T28: the first IBKR window after a mid-window start is not saved."""
    start = _WINDOW_START + timedelta(minutes=8)  # feed starts 8 min into the 14:30 window
    closes_1430 = _WINDOW_START + timedelta(minutes=15)

    assert _saved_15m_windows(start, [closes_1430]) == 0


def test_full_ibkr_windows_saved() -> None:
    """UT-EXE-007.001.M01.T29: windows that start at or after the first bar are saved."""
    on_boundary = _saved_15m_windows(_WINDOW_START, [_WINDOW_START + timedelta(minutes=15)])
    after_partial = _saved_15m_windows(
        _WINDOW_START + timedelta(minutes=8),
        [_WINDOW_START + timedelta(minutes=15), _WINDOW_START + timedelta(minutes=30)],
    )

    assert on_boundary == 1
    assert after_partial == 1
