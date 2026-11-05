"""Tests for MD-MKT-001.001.M01 (candles), .005.M03 (vix) and .007.M04 (store)."""
from __future__ import annotations

import hashlib
import logging
import sqlite3
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from us_swing.core.desk_contract import DeskState
from us_swing.desk.store import DeskStore
from us_swing.market.candles import CandleReader
from us_swing.market.store import BreadthRow, MarketStore, RegimeRow
from us_swing.market.vix import fetch_vix

Maker = Callable[[dict[str, Sequence[float]]], Path]


def test_reads_bars_read_only(candle_file: Maker) -> None:
    """UT-MKT-001.001.M01.T01: Reads bars read-only."""
    path = candle_file({s: list(np.linspace(10, 20, 30)) for s in ("SPY", "A", "B", "C")})
    before = hashlib.md5(path.read_bytes()).hexdigest()
    bars = CandleReader(path).read(["SPY", "A", "B", "C"])
    assert list(bars.closes.columns) == ["A", "B", "C", "SPY"]
    assert len(bars.closes) == 30
    assert hashlib.md5(path.read_bytes()).hexdigest() == before


def test_missing_candles_file(tmp_path: Path) -> None:
    """UT-MKT-001.001.M01.T02: Missing candles file."""
    with pytest.raises(FileNotFoundError):
        CandleReader(tmp_path / "candles.db")
    assert not (tmp_path / "candles.db").exists()


def test_vix_rows_from_download() -> None:
    """UT-MKT-001.005.M03.T01: VIX rows from download."""
    idx = pd.to_datetime(["2026-11-03", "2026-11-04"])
    fake = pd.DataFrame({"^VIX": [20.0, 18.0], "^VIX3M": [21.0, 19.5]}, index=idx)
    out = fetch_vix(date(2026, 11, 3), lambda _t, _s: fake)
    assert list(out.columns) == ["vix", "vix3m"]
    assert out.loc["2026-11-04", "vix"] == 18.0


def test_vix_download_fails(caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-001.005.M03.T02: Download fails."""

    def boom(_t: list[str], _s: date) -> pd.DataFrame:
        raise ConnectionError("offline")

    with caplog.at_level(logging.WARNING):
        out = fetch_vix(date(2026, 11, 3), boom)
    assert out.empty
    assert "Could not download VIX" in caplog.text


def _regime(day: str, regime: str = "Uptrend") -> RegimeRow:
    return RegimeRow(day, regime, "Calm", 0.1, 20.0, 500.0, 490.0, 450.0, 15.0, 17.0,
                     "Calm", 0, "", "2026-11-05T00:00:00+00:00")


def _breadth(day: str) -> BreadthRow:
    return BreadthRow(day, 500, 60.0, 55.0, 50.0, 20, 5, 300, 200)


def test_rows_round_trip(tmp_path: Path) -> None:
    """UT-MKT-001.007.M04.T01: Rows round trip."""
    store = MarketStore(tmp_path)
    store.write_days([_regime("2026-11-03"), _regime("2026-11-04")],
                     [_breadth("2026-11-03"), _breadth("2026-11-04")])
    store.write_days([_regime("2026-11-04", "Choppy")], [])
    assert store.last_date("regime_snapshot") == date(2026, 11, 4)
    rows = store._con.execute("SELECT date, regime FROM regime_snapshot ORDER BY date").fetchall()
    store.close()
    assert rows == [("2026-11-03", "Uptrend"), ("2026-11-04", "Choppy")]


def test_tables_beside_desk_tables(tmp_path: Path) -> None:
    """UT-MKT-001.007.M04.T02: Tables beside desk tables."""
    desk = DeskStore(tmp_path)
    desk.set_state(DeskState.SLEEPING, datetime.now(UTC))
    desk.close()
    MarketStore(tmp_path).close()
    con = sqlite3.connect(tmp_path / "desk.db")
    assert con.execute("SELECT state FROM desk_state").fetchone() == ("Sleeping",)
    con.close()


def test_row_without_date_refused(tmp_path: Path) -> None:
    """UT-MKT-001.007.M04.T03: Row without a date refused."""
    store = MarketStore(tmp_path)
    with pytest.raises(ValueError):
        store.write_days([_regime("")], [])
    assert store.last_date("regime_snapshot") is None
    store.close()
