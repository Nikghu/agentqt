"""
Module: MD-SCR-015.008.M25 — core/indicator_rules/_ta.py
Parent SRD: SRD-SCR-015.008

TA-Lib backed indicator series. Every function takes float64 numpy arrays and
returns a series of the same length; bars without enough history are NaN.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import numpy.typing as npt
import talib

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class BarArrays:
    """One symbol's OHLCV history as float64 arrays, oldest bar first."""

    open: FloatArray
    high: FloatArray
    low: FloatArray
    close: FloatArray
    volume: FloatArray

    @classmethod
    def from_bars(cls, bars: Sequence[Any]) -> BarArrays:
        """Build arrays from bar objects exposing open/high/low/close/volume."""

        def col(name: str) -> FloatArray:
            return np.asarray([float(getattr(b, name)) for b in bars], dtype=np.float64)

        return cls(col("open"), col("high"), col("low"), col("close"), col("volume"))


@dataclass(frozen=True, slots=True)
class Series:
    """Indicator output: the main series plus an optional reference (signal) line."""

    value: FloatArray
    reference: FloatArray | None = None


def ema(close: FloatArray, period: int) -> FloatArray:
    """Exponential moving average."""
    return np.asarray(talib.EMA(close, timeperiod=period), dtype=np.float64)


def rsi(close: FloatArray, period: int) -> FloatArray:
    """Wilder RSI."""
    return np.asarray(talib.RSI(close, timeperiod=period), dtype=np.float64)


def atr_pct(high: FloatArray, low: FloatArray, close: FloatArray, period: int) -> FloatArray:
    """Wilder ATR as a percentage of the close."""
    atr = np.asarray(talib.ATR(high, low, close, timeperiod=period), dtype=np.float64)
    return safe_div(atr, close) * 100.0


def macd(
    close: FloatArray, fast: int, slow: int, signal: int
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """MACD line, signal line and histogram."""
    line, sig, hist = talib.MACD(
        close, fastperiod=fast, slowperiod=slow, signalperiod=signal
    )
    return (
        np.asarray(line, dtype=np.float64),
        np.asarray(sig, dtype=np.float64),
        np.asarray(hist, dtype=np.float64),
    )


def ppo(
    close: FloatArray, fast: int, slow: int, signal: int
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """EMA-based PPO line (%), its signal EMA and the histogram."""
    ema_slow = ema(close, slow)
    line = safe_div(ema(close, fast) - ema_slow, ema_slow) * 100.0
    sig = ema(line, signal)
    return line, sig, line - sig


def volume_ratio(volume: FloatArray, period: int) -> FloatArray:
    """Each bar's volume divided by the mean volume of the previous ``period`` bars."""
    prior_mean = _shift(np.asarray(talib.SMA(volume, timeperiod=period), dtype=np.float64))
    return safe_div(volume, prior_mean)


def n_bar_breakout(close: FloatArray, lookback: int) -> FloatArray:
    """1.0 where the close is above the highest close of the previous ``lookback`` bars."""
    prior_high = np.full_like(close, np.nan)
    if len(close) > lookback:
        windows = np.lib.stride_tricks.sliding_window_view(close[:-1], lookback)
        prior_high[lookback:] = windows.max(axis=1)
    out = np.where(close > prior_high, 1.0, 0.0)
    out[np.isnan(prior_high)] = np.nan
    return out


def _shift(series: FloatArray) -> FloatArray:
    out = np.full_like(series, np.nan)
    out[1:] = series[:-1]
    return out


def safe_div(num: FloatArray, den: FloatArray) -> FloatArray:
    """Element-wise ``num / den``; NaN where the denominator is zero, negative or NaN."""
    out = np.full_like(num, np.nan)
    np.divide(num, den, out=out, where=(den > 0) & ~np.isnan(den))
    return out
