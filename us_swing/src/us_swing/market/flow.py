"""
Module: MD-MKT-003.002.M02 — market/flow.py
Parent SRD: SRD-MKT-003.002

Pure money flow rules: dollar volume for the liquidity cut, and a 0–1 money flow value
from accumulation and distribution days, Chaikin money flow and up against down volume
(DD-MKT-003.001.D01).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

MIN_DOLLAR_VOLUME = 20_000_000.0
AD_DAYS = 25
CMF_DAYS = 20
UD_DAYS = 50
AVG_VOLUME_DAYS = 50


def roll(frame: pd.DataFrame, n: int, how: str) -> pd.DataFrame:
    """Rolling ``mean``, ``sum``, ``max``, ``min`` or ``std`` over ``n`` rows, all columns at once.

    Same result as the pandas rolling window with its defaults: a window with any missing
    value gives NaN, and ``std`` uses ddof=1.
    """
    arr = frame.to_numpy(dtype=float)
    out = np.full(arr.shape, np.nan)
    if len(arr) >= n:
        windows = sliding_window_view(arr, n, axis=0)
        if how == "std":
            out[n - 1:] = windows.std(axis=-1, ddof=1)
        elif how == "sum":
            out[n - 1:] = windows.sum(axis=-1)
        elif how == "mean":
            out[n - 1:] = windows.mean(axis=-1)
        elif how == "max":
            out[n - 1:] = windows.max(axis=-1)
        else:
            out[n - 1:] = windows.min(axis=-1)
    return pd.DataFrame(out, index=frame.index, columns=frame.columns)


def dollar_volume(closes: pd.DataFrame, volumes: pd.DataFrame) -> pd.DataFrame:
    """Return the 20-day average dollar volume per day and stock."""
    return roll(closes * volumes, 20, "mean")


def _clip01(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.clip(lower=0.0, upper=1.0)


def money_flow(
    closes: pd.DataFrame, highs: pd.DataFrame, lows: pd.DataFrame, volumes: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return the long money flow (0–1), accumulation days and distribution days.

    Days are counted over the last 25 sessions. The short money flow is ``1 - long``.
    """
    prev = closes.shift(1)
    up = closes > prev
    down = closes < prev
    heavy = volumes > roll(volumes, AVG_VOLUME_DAYS, "mean")
    acc = roll((up & heavy).astype(float), AD_DAYS, "sum")
    dist = roll((down & heavy).astype(float), AD_DAYS, "sum")
    net_ad = acc - dist
    span = highs - lows
    location = ((closes - lows) - (highs - closes)) / span.where(span > 0)
    cmf = (roll(location.fillna(0.0) * volumes, CMF_DAYS, "sum")
           / roll(volumes, CMF_DAYS, "sum"))
    up_vol = roll(volumes.where(up, 0.0), UD_DAYS, "sum")
    down_vol = roll(volumes.where(down, 0.0), UD_DAYS, "sum")
    ud = up_vol / down_vol.where(down_vol > 0)
    no_down = pd.DataFrame(np.where(up_vol > 0, 10.0, 1.0), index=ud.index, columns=ud.columns)
    ud = ud.where(down_vol > 0, no_down).where(up_vol.notna() & down_vol.notna())
    parts = (_clip01(net_ad / 10 + 0.5) + _clip01(cmf / 0.4 + 0.5)
             + _clip01((ud - 0.5) / 1.5)) / 3
    return parts.where(closes.notna()), acc, dist
