"""
Module: MD-MKT-003.003.M03 — market/setups.py
Parent SRD: SRD-MKT-003.003

Pure setup rules on wide daily frames: long (Squeeze, Flat base, Pullback) and short
(Failed breakout, Lower highs, Breakdown), each with trigger, stop and tightness
(DD-MKT-003.001.D01).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from us_swing.market.flow import roll


Candidate = tuple[str, pd.DataFrame, pd.DataFrame, pd.DataFrame]


@dataclass(frozen=True)
class Bars:
    """Wide daily frames for the members, aligned to SPY's days."""

    closes: pd.DataFrame
    highs: pd.DataFrame
    lows: pd.DataFrame
    volumes: pd.DataFrame


@dataclass(frozen=True)
class SetupResult:
    """Best setup per day and stock: name (None when no match), trigger, stop, tightness."""

    name: pd.DataFrame
    trigger: pd.DataFrame
    stop: pd.DataFrame
    tightness: pd.DataFrame


def sma(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    """Return the n-day simple average."""
    return roll(frame, n, "mean")


def atr(bars: Bars, n: int) -> pd.DataFrame:
    """Return the n-day average true range."""
    prev = bars.closes.shift(1)
    true_range = np.maximum(bars.highs - bars.lows,
                            np.maximum((bars.highs - prev).abs(), (bars.lows - prev).abs()))
    return roll(pd.DataFrame(true_range, index=bars.closes.index,
                             columns=bars.closes.columns), n, "mean")


def _hi(bars: Bars, n: int) -> pd.DataFrame:
    return roll(bars.highs, n, "max")


def _lo(bars: Bars, n: int) -> pd.DataFrame:
    return roll(bars.lows, n, "min")


def _best(bars: Bars, candidates: list[Candidate]) -> SetupResult:
    """Keep, per cell, the matching setup with the highest tightness (ties: first listed)."""
    idx, cols = bars.closes.index, bars.closes.columns
    contraction = 0.5 * (1 - atr(bars, 10) / atr(bars, 50)).clip(0.0, 1.0)
    two_atr14 = 2 * atr(bars, 14)
    name = pd.DataFrame(None, index=idx, columns=cols, dtype=object)
    trigger = pd.DataFrame(np.nan, index=idx, columns=cols)
    stop = trigger.copy()
    tight = pd.DataFrame(-1.0, index=idx, columns=cols)
    for label, mask, trig, stp in candidates:
        t = contraction + 0.5 * (1 - (trig - bars.closes).abs() / two_atr14).clip(0.0, 1.0)
        better = mask.fillna(False).astype(bool) & t.notna() & (t > tight)
        name = name.mask(better, label)
        trigger = trigger.mask(better, trig)
        stop = stop.mask(better, stp)
        tight = tight.mask(better, t)
    return SetupResult(name, trigger, stop, tight.where(name.notna(), 0.0))


def _rising(avg: pd.DataFrame) -> pd.DataFrame:
    return avg > avg.shift(10)


def long_setups(bars: Bars) -> SetupResult:
    """Return the best long setup per day and stock: Squeeze, Flat base or Pullback."""
    return _best(bars, long_candidates(bars))


def short_setups(bars: Bars) -> SetupResult:
    """Return the best short setup per day and stock: Failed breakout, Lower highs or Breakdown."""
    return _best(bars, short_candidates(bars))


def long_candidates(bars: Bars) -> list[Candidate]:
    """Return each long setup as (name, match, trigger, stop) frames."""
    c = bars.closes
    sma20, sma21, sma50 = sma(c, 20), sma(c, 21), sma(c, 50)
    uptrend = (c > sma50) & _rising(sma50)
    width = 4 * roll(c, 20, "std") / sma20
    squeeze = (uptrend & (width <= 1.1 * roll(width, 126, "min"))
               & (atr(bars, 10) / atr(bars, 50) < 0.8))
    hi25, lo25 = _hi(bars, 25), _lo(bars, 25)
    flat = (c >= 0.9 * _hi(bars, 252)) & ((hi25 - lo25) / hi25 <= 0.15) & (c > sma50)
    pullback = uptrend & (_lo(bars, 3) <= sma21 * 1.02) & (c >= sma21)
    return [
        ("Squeeze", squeeze, _hi(bars, 20), _lo(bars, 20)),
        ("Flat base", flat, hi25, lo25),
        ("Pullback", pullback, _hi(bars, 3), _lo(bars, 5)),
    ]


def short_candidates(bars: Bars) -> list[Candidate]:
    """Return each short setup as (name, match, trigger, stop) frames."""
    c = bars.closes
    sma20, sma50 = sma(c, 20), sma(c, 50)
    pivot = roll(bars.highs, 25, "max").shift(1)
    broke = c > pivot
    last_pivot = pivot.where(broke).ffill(limit=9)
    recent = roll(broke.astype(float), 10, "max") > 0
    failed = recent & (c < last_pivot) & (c < sma20)
    h1 = _hi(bars, 10)
    h2, h3 = h1.shift(10), h1.shift(20)
    lower = (c < sma50) & (sma50 < sma50.shift(10)) & (h1 < h2) & (h2 < h3)
    avg_vol = roll(bars.volumes, 50, "mean")
    hi5 = _hi(bars, 5)
    breakdown = ((c < sma50) & (c.shift(1) >= sma50.shift(1))
                 & (bars.volumes >= 1.5 * avg_vol))
    return [
        ("Failed breakout", failed, _lo(bars, 5), h1),
        ("Lower highs", lower, _lo(bars, 10), h1),
        ("Breakdown", breakdown, bars.lows, sma50.where(sma50 >= hi5, hi5)),
    ]
