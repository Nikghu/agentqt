"""Tests for MD-BKT-001.001.M01 — backtest/store.py."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow.parquet as pq
import pytest

from us_swing.backtest import store as store_mod
from us_swing.backtest.settings import BacktestDataSettings, DownloadState
from us_swing.backtest.store import BacktestStore

_ET = ZoneInfo("America/New_York")
_LATE = datetime(2026, 10, 28, 20, 0, tzinfo=_ET)


def _bars(stamps: list[str], close: float = 10.0, tz: str | None = "UTC") -> pd.DataFrame:
    ts = pd.to_datetime(stamps, utc=tz is not None)
    if tz is not None:
        ts = ts.tz_convert(tz)
    n = len(stamps)
    return pd.DataFrame({
        "ts": ts,
        "open": [close] * n,
        "high": [close + 1] * n,
        "low": [close - 1] * n,
        "close": [close] * n,
        "volume": [1000.0] * n,
    })


def test_3m_bars_split_by_year(tmp_path: Path) -> None:
    """UT-BKT-001.001.M01.T01: 3m bars are split into one file per year."""
    store = BacktestStore(tmp_path)
    df = _bars(["2024-12-31 20:57", "2024-12-31 15:00", "2025-01-02 14:30"])

    store.save("AAPL", "3m", df, _LATE)

    assert (tmp_path / "3m" / "AAPL" / "2024.parquet").exists()
    assert (tmp_path / "3m" / "AAPL" / "2025.parquet").exists()
    out = store.read("AAPL", "3m")
    assert len(out) == 3
    assert out["ts"].is_monotonic_increasing


def test_unknown_stock_reads_empty(tmp_path: Path) -> None:
    """UT-BKT-001.001.M01.T02: An unknown stock reads empty and creates no file."""
    store = BacktestStore(tmp_path)

    assert store.read("ZZZZ", "1d").empty
    assert store.read("ZZZZ", "3m").empty
    assert store.coverage("ZZZZ", "1d") is None
    assert store.coverage("ZZZZ", "3m") is None
    assert list(tmp_path.iterdir()) == []


def test_overlap_merge_keeps_one_row_per_ts(tmp_path: Path) -> None:
    """UT-BKT-001.002.M01.T01: Overlapping save keeps one row per ts, newest values."""
    store = BacktestStore(tmp_path)
    store.save("AAPL", "1d", _bars(["2025-01-02", "2025-01-03"], 10.0, None), _LATE)
    store.save("AAPL", "1d", _bars(["2025-01-03", "2025-01-06"], 20.0, None), _LATE)

    out = store.read("AAPL", "1d")

    assert len(out) == 3
    assert not out["ts"].duplicated().any()
    assert out.set_index("ts").loc[pd.Timestamp("2025-01-03"), "close"] == 20.0


def test_failed_write_keeps_old_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-BKT-001.002.M01.T02: A write that fails mid-save keeps the old file intact."""
    store = BacktestStore(tmp_path)
    store.save("AAPL", "1d", _bars(["2025-01-02"], 10.0, None), _LATE)

    def broken_write(table: Any, where: Any, **kwargs: Any) -> None:
        Path(where).write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(store_mod.pq, "write_table", broken_write)
    with pytest.raises(OSError):
        store.save("AAPL", "1d", _bars(["2025-01-03"], 20.0, None), _LATE)
    monkeypatch.undo()

    out = store.read("AAPL", "1d")
    assert list(out["close"]) == [10.0]
    assert not list((tmp_path / "1d").glob("*.tmp"))


def test_unfinished_day_dropped(tmp_path: Path) -> None:
    """UT-BKT-001.003.M01.T01: Today's bars are not saved before 16:15 ET."""
    store = BacktestStore(tmp_path)
    now = datetime(2026, 10, 28, 14, 0, tzinfo=_ET)

    store.save("AAPL", "1d", _bars(["2026-10-27", "2026-10-28"], tz=None), now)
    store.save("AAPL", "3m", _bars(["2026-10-27 15:00", "2026-10-28 15:00"]), now)

    assert list(store.read("AAPL", "1d")["ts"].dt.date) == [date(2026, 10, 27)]
    assert len(store.read("AAPL", "3m")) == 1


def test_finished_day_kept(tmp_path: Path) -> None:
    """UT-BKT-001.003.M01.T02: Today's bars are saved after 16:15 ET."""
    store = BacktestStore(tmp_path)
    now = datetime(2026, 10, 28, 16, 20, tzinfo=_ET)

    store.save("AAPL", "1d", _bars(["2026-10-27", "2026-10-28"], tz=None), now)
    store.save("AAPL", "3m", _bars(["2026-10-27 15:00", "2026-10-28 15:00"]), now)

    assert len(store.read("AAPL", "1d")) == 2
    assert len(store.read("AAPL", "3m")) == 2


def test_clear_keeps_settings(tmp_path: Path) -> None:
    """UT-BKT-001.010.M01.T01: Clear removes candles and state, keeps settings and candles.db."""
    store = BacktestStore(tmp_path)
    store.save("AAPL", "1d", _bars(["2025-01-02"], tz=None), _LATE)
    store.save("AAPL", "3m", _bars(["2025-01-02 15:00"]), _LATE)
    BacktestDataSettings(auto_delta=False).save(tmp_path)
    DownloadState(failed=["ZZZZ"]).save(tmp_path)
    (tmp_path / "candles.db").write_bytes(b"db")

    store.clear()

    assert not (tmp_path / "1d").exists()
    assert not (tmp_path / "3m").exists()
    assert not (tmp_path / "state.json").exists()
    assert BacktestDataSettings.load(tmp_path).auto_delta is False
    assert (tmp_path / "candles.db").read_bytes() == b"db"


def test_clear_on_empty_store_is_safe(tmp_path: Path) -> None:
    """UT-BKT-001.010.M01.T02: Clear on an empty store raises nothing and keeps settings."""
    BacktestDataSettings().save(tmp_path)
    before = (tmp_path / "settings.json").read_bytes()

    BacktestStore(tmp_path).clear()

    assert (tmp_path / "settings.json").read_bytes() == before


def test_stats_from_metadata(tmp_path: Path) -> None:
    """UT-BKT-001.011.M01.T01: Stats count stocks, bars, dates and size from metadata."""
    store = BacktestStore(tmp_path)
    store.save("AAPL", "1d", _bars(["2025-01-02", "2025-01-03"], tz=None), _LATE)
    store.save("MSFT", "1d", _bars(["2024-06-03"], tz=None), _LATE)
    store.save("AAPL", "3m", _bars(["2024-12-31 15:00", "2025-01-02 15:00"]), _LATE)

    stats = store.stats()

    assert stats.stocks == 2
    assert stats.bars_1d == 3
    assert stats.bars_3m == 2
    assert stats.first == date(2024, 6, 3)
    assert stats.last == date(2025, 1, 3)
    files = list(tmp_path.rglob("*.parquet"))
    assert stats.size_bytes == sum(f.stat().st_size for f in files)
    assert stats.last_delta is None
    assert store.coverage("AAPL", "3m") is not None
    assert pq.read_metadata(tmp_path / "1d" / "AAPL.parquet").num_rows == 2
