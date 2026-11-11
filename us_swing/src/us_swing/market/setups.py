"""
Module: MD-MKT-003.003.M03 — market/setups.py
Parent SRD: SRD-MKT-003.003
Also: SRD-MKT-015.002 (limits read from the setup knobs)

Pure setup rules on wide daily frames: long (Squeeze, Flat base, Pullback) and short
(Failed breakout, Lower highs, Breakdown), each with trigger, stop and tightness
(DD-MKT-003.001.D01).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from us_swing.market.flow import roll
from us_swing.market.setup_knobs import Values, knob_value, window

Tests = Mapping[str, Values] | None


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


def long_candidates(bars: Bars, values: Tests = None) -> list[Candidate]:
    """Return each long setup as (name, match, trigger, stop) frames.

    ``values`` holds tested knob values by setup; missing knobs keep their defaults.
    """
    c = bars.closes
    sma20, sma50 = sma(c, 20), sma(c, 50)
    sma_pull = sma(c, window(values, "Pullback", "sma_days"))
    uptrend = (c > sma50) & _rising(sma50)
    width = 4 * roll(c, 20, "std") / sma20
    squeeze = (uptrend
               & (width <= knob_value(values, "Squeeze", "width_vs_min")
                  * roll(width, 126, "min"))
               & (atr(bars, 10) / atr(bars, 50) < knob_value(values, "Squeeze", "atr_ratio")))
    hi25, lo25 = _hi(bars, 25), _lo(bars, 25)
    flat = ((c >= knob_value(values, "Flat base", "near_high") * _hi(bars, 252))
            & ((hi25 - lo25) / hi25 <= knob_value(values, "Flat base", "depth")) & (c > sma50))
    pullback = (uptrend & (_lo(bars, 3) <= sma_pull * knob_value(values, "Pullback", "near_sma"))
                & (c >= sma_pull))
    return [
        ("Squeeze", squeeze, _hi(bars, 20), _lo(bars, 20)),
        ("Flat base", flat, hi25, lo25),
        ("Pullback", pullback, _hi(bars, 3), _lo(bars, 5)),
    ]


def short_candidates(bars: Bars, values: Tests = None) -> list[Candidate]:
    """Return each short setup as (name, match, trigger, stop) frames.

    ``values`` holds tested knob values by setup; missing knobs keep their defaults.
    """
    c = bars.closes
    sma20, sma50 = sma(c, 20), sma(c, 50)
    recent_days = window(values, "Failed breakout", "recent_days")
    pivot = roll(bars.highs, window(values, "Failed breakout", "pivot_days"), "max").shift(1)
    broke = c > pivot
    last_pivot = pivot.where(broke).ffill(limit=recent_days - 1)
    recent = roll(broke.astype(float), recent_days, "max") > 0
    failed = recent & (c < last_pivot) & (c < sma20)
    h10 = _hi(bars, 10)
    swing = window(values, "Lower highs", "swing_days")
    h1 = _hi(bars, swing)
    h2, h3 = h1.shift(swing), h1.shift(2 * swing)
    lower = (c < sma50) & (sma50 < sma50.shift(10)) & (h1 < h2) & (h2 < h3)
    avg_vol = roll(bars.volumes, 50, "mean")
    hi5 = _hi(bars, 5)
    breakdown = ((c < sma50) & (c.shift(1) >= sma50.shift(1))
                 & (bars.volumes >= knob_value(values, "Breakdown", "volume_x") * avg_vol))
    return [
        ("Failed breakout", failed, _lo(bars, 5), h10),
        ("Lower highs", lower, _lo(bars, 10), h1),
        ("Breakdown", breakdown, bars.lows, sma50.where(sma50 >= hi5, hi5)),
    ]
