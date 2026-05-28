"""Shared test fixtures for analysis package tests."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from us_swing.data.models import OHLCVBar, OpenPosition, RealtimeBar


_BASE_DT = datetime(2024, 1, 15, 10, 0, 0)


def make_ohlcv(
    symbol: str = "AAPL",
    tf: str = "1m",
    close: float = 100.0,
    high: float | None = None,
    low: float | None = None,
    volume: int = 1000,
    offset_min: int = 0,
) -> OHLCVBar:
    """Factory for a single OHLCVBar."""
    h = high if high is not None else close + 0.5
    lo = low if low is not None else close - 0.5
    return OHLCVBar(
        symbol=symbol,
        datetime=_BASE_DT + timedelta(minutes=offset_min),
        open=close,
        high=h,
        low=lo,
        close=close,
        volume=volume,
        timeframe=tf,
    )


def make_ohlcv_series(
    closes: list[float],
    symbol: str = "AAPL",
    tf: str = "1m",
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volume: int = 1000,
) -> list[OHLCVBar]:
    """Factory for a list of OHLCVBars with sequential timestamps."""
    result = []
    for i, c in enumerate(closes):
        h = highs[i] if highs is not None else c + 0.5
        lo = lows[i] if lows is not None else c - 0.5
        result.append(
            OHLCVBar(
                symbol=symbol,
                datetime=_BASE_DT + timedelta(minutes=i),
                open=c,
                high=h,
                low=lo,
                close=c,
                volume=volume,
                timeframe=tf,
            )
        )
    return result


def make_rt_bars(
    closes: list[float],
    symbol: str = "AAPL",
    start: datetime | None = None,
    interval_sec: int = 5,
) -> list[RealtimeBar]:
    """Factory for a list of 5-second RealtimeBars."""
    t0 = start or _BASE_DT
    result = []
    for i, c in enumerate(closes):
        result.append(
            RealtimeBar(
                symbol=symbol,
                datetime=t0 + timedelta(seconds=i * interval_sec),
                open=c,
                high=c + 0.5,
                low=c - 0.5,
                close=c,
                volume=100,
            )
        )
    return result


def make_open_position(
    symbol: str = "AAPL",
    average_price: float = 100.0,
    stop_loss: float = 90.0,
    target_price: float = 120.0,
    trailing_stop: float = 0.0,
) -> OpenPosition:
    """Factory for an OpenPosition."""
    return OpenPosition(
        symbol=symbol,
        user_id=1,
        quantity=100,
        average_price=average_price,
        stop_loss=stop_loss,
        target_price=target_price,
        mode="paper",
        trailing_stop=trailing_stop,
    )
