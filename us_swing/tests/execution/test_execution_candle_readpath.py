"""Read-path tests for execution candle assembly (SRD-EXE-006.010).

Covers UT-EXE-006.001.M01.T14-T16: 3m/15m frames derived from ``price_1m``,
live-bar merge/de-duplication, and the empty-source case.
"""
from __future__ import annotations

import datetime as dt

from us_swing.config.settings import DataConfig
from us_swing.data.engine import HistoricalDataEngine
from us_swing.data.models import OHLCVBar
from us_swing.data.providers.dummy_provider import DummyProvider
from us_swing.db.manager import DatabaseManager
from us_swing.execution.intraday_candle_loader import (
    assemble_execution_bars,
    load_execution_frames,
    load_latest_execution_bar,
)

_SYM = "SYM"


def _make(tmp_path) -> tuple[DatabaseManager, HistoricalDataEngine]:
    db = DatabaseManager(f"sqlite:///{tmp_path / 'candles.db'}")
    db.create_schema()
    hist = HistoricalDataEngine(DummyProvider(), db, DataConfig())
    return db, hist


def _one_minute_bars(symbol: str, count: int) -> list[OHLCVBar]:
    # Aligned to the top of an hour one day ago so 3m and 15m buckets are complete.
    start = (dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(days=1)).replace(
        minute=0, second=0, microsecond=0
    )
    return [
        OHLCVBar(
            symbol=symbol,
            datetime=start + dt.timedelta(minutes=i),
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.0 + i * 0.01,
            volume=100,
            timeframe="1m",
        )
        for i in range(count)
    ]


def test_frames_derived_from_1m(tmp_path):
    """UT-EXE-006.001.M01.T14: 3m/15m derived from price_1m when live tables empty."""
    db, hist = _make(tmp_path)
    db.insert_bars(_SYM, "1m", _one_minute_bars(_SYM, 900))

    frames = load_execution_frames(db, hist, _SYM)

    assert set(frames) == {"3m", "15m"}
    assert len(frames["3m"]) >= 250
    assert len(frames["15m"]) >= 50
    assert list(frames["3m"].columns) == [
        "datetime", "open", "high", "low", "close", "volume"
    ]


def test_live_bar_merged_and_deduplicated(tmp_path):
    """UT-EXE-006.001.M01.T15: live price_3m bar overrides aggregated bar at same ts."""
    db, hist = _make(tmp_path)
    db.insert_bars(_SYM, "1m", _one_minute_bars(_SYM, 90))

    base = assemble_execution_bars(db, hist, _SYM, "3m")
    assert base, "expected aggregated 3m bars from 1m history"
    target_dt = base[0].datetime

    live = OHLCVBar(
        symbol=_SYM, datetime=target_dt, open=1.0, high=1.0, low=1.0,
        close=999.0, volume=1, timeframe="3m",
    )
    db.insert_bars(_SYM, "3m", [live])

    merged = assemble_execution_bars(db, hist, _SYM, "3m")
    same_ts = [b for b in merged if b.datetime == target_dt]
    assert len(same_ts) == 1
    assert same_ts[0].close == 999.0


def test_empty_sources_return_empty(tmp_path):
    """UT-EXE-006.001.M01.T16: no 1m and no live bars yields empty result, not error."""
    db, hist = _make(tmp_path)

    assert load_execution_frames(db, hist, _SYM) == {}
    assert load_latest_execution_bar(db, hist, _SYM, "3m") is None
    assert load_latest_execution_bar(db, hist, _SYM, "1d") is None


def test_latest_bar_returns_most_recent(tmp_path):
    """UT-EXE-006.001.M01.T14: latest-bar accessor returns the final aggregated 3m bar."""
    db, hist = _make(tmp_path)
    db.insert_bars(_SYM, "1m", _one_minute_bars(_SYM, 90))

    bars = assemble_execution_bars(db, hist, _SYM, "3m")
    latest = load_latest_execution_bar(db, hist, _SYM, "3m")
    assert latest is not None
    assert latest.datetime == bars[-1].datetime
