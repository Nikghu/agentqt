"""Unit tests — MD-INF-004.001.M01 DatabaseManager.

Refs: UT-INF-004.001.M01.T01 – T06
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from us_swing.data.models import OHLCVBar, PositionRecord
from us_swing.db.manager import DatabaseManager


def _bar(dt: datetime, symbol: str = "AAPL", tf: str = "1d") -> OHLCVBar:
    return OHLCVBar(
        symbol=symbol, datetime=dt,
        open=100.0, high=105.0, low=99.0, close=103.0,
        volume=1_000_000, timeframe=tf,
    )


def _make_bars(n: int, symbol: str = "AAPL", tf: str = "1d") -> list[OHLCVBar]:
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    from datetime import timedelta
    return [_bar(base + timedelta(days=i), symbol=symbol, tf=tf) for i in range(n)]


def test_T01_insert_and_fetch_bars(in_memory_db: DatabaseManager) -> None:
    """UT-INF-004.001.M01.T01 — insert_bars() stores bars; fetch_bars() retrieves them."""
    bars = _make_bars(5)
    inserted = in_memory_db.insert_bars("AAPL", "1d", bars)
    assert inserted == 5

    start = bars[0].datetime
    end   = bars[-1].datetime
    fetched = in_memory_db.fetch_bars("AAPL", "1d", start, end)
    assert len(fetched) == 5
    assert all(b.symbol == "AAPL" for b in fetched)


def test_T02_no_duplicate_on_reinsert(in_memory_db: DatabaseManager) -> None:
    """UT-INF-004.001.M01.T02 — inserting same bars twice → no duplicates in DB."""
    bars = _make_bars(5)
    in_memory_db.insert_bars("AAPL", "1d", bars)
    in_memory_db.insert_bars("AAPL", "1d", bars)  # second insert — all duplicates

    start = bars[0].datetime
    end   = bars[-1].datetime
    fetched = in_memory_db.fetch_bars("AAPL", "1d", start, end)
    assert len(fetched) == 5


def test_T03_get_last_timestamp_returns_max(in_memory_db: DatabaseManager) -> None:
    """UT-INF-004.001.M01.T03 — get_last_timestamp() returns the latest datetime."""
    bars = _make_bars(10)
    in_memory_db.insert_bars("AAPL", "1d", bars)
    last = in_memory_db.get_last_timestamp("AAPL", "1d")
    assert last == bars[-1].datetime


def test_T04_get_last_timestamp_none_for_empty(in_memory_db: DatabaseManager) -> None:
    """UT-INF-004.001.M01.T04 — get_last_timestamp() returns None when table empty."""
    result = in_memory_db.get_last_timestamp("AAPL", "1d")
    assert result is None


def test_T05_fetch_bars_respects_date_range(in_memory_db: DatabaseManager) -> None:
    """UT-INF-004.001.M01.T05 — fetch_bars() returns only bars inside [start, end]."""
    bars = _make_bars(10)   # days 0..9
    in_memory_db.insert_bars("AAPL", "1d", bars)

    start = bars[2].datetime   # day 2
    end   = bars[6].datetime   # day 6
    fetched = in_memory_db.fetch_bars("AAPL", "1d", start, end)
    assert len(fetched) == 5   # days 2, 3, 4, 5, 6
    assert fetched[0].datetime  == bars[2].datetime
    assert fetched[-1].datetime == bars[6].datetime


def test_T06_upsert_and_delete_position_round_trip(in_memory_db: DatabaseManager) -> None:
    """UT-INF-004.001.M01.T06 — upsert_position + delete_position → empty open positions."""
    pos = PositionRecord(
        symbol="AAPL", user_id=1, quantity=50,
        average_price=150.0, stop_loss=140.0, target_price=170.0,
        mode="paper",
    )
    in_memory_db.upsert_position(pos)
    assert len(in_memory_db.fetch_open_positions(1)) == 1

    in_memory_db.delete_position(user_id=1, symbol="AAPL")
    assert in_memory_db.fetch_open_positions(1) == []
