"""
Module: MD-MKT-001.002.M02 — market/regime.py
Parent SRD: SRD-MKT-001.002

Pure market rules on daily data: regime, volatility, breadth and fear.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

REGIME_BARS = 210
YEAR = 252
VOL_WINDOW = 20
CALM_PCT = 30.0
HIGH_PCT = 70.0


def _min_bars(window: int) -> int:
    """Bars a member needs inside a window; up to 5% may be missing (data gaps)."""
    return window - window // 20


def regime_series(close: pd.Series) -> pd.Series:
    """Return Uptrend, Downtrend or Choppy per day; ``None`` before 210 bars."""
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    rising = sma50 > sma50.shift(10)
    falling = sma50 < sma50.shift(10)
    up = (close > sma50) & (close > sma200) & rising
    down = (close < sma50) & (close < sma200) & falling
    out = pd.Series(np.where(up, "Uptrend", np.where(down, "Downtrend", "Choppy")),
                    index=close.index, dtype=object)
    out[np.arange(len(close)) < REGIME_BARS - 1] = None
    return out


def averages(close: pd.Series) -> pd.DataFrame:
    """Return the 50 and 200-day averages of ``close``."""
    return pd.DataFrame({"sma50": close.rolling(50).mean(), "sma200": close.rolling(200).mean()})


def volatility_series(close: pd.Series) -> pd.DataFrame:
    """Return ``vol20`` (annualised), ``vol_pct`` (rank in the past year) and ``volatility``."""
    vol20 = np.log(close).diff().rolling(VOL_WINDOW).std() * math.sqrt(YEAR)
    pct = vol20.rolling(YEAR).apply(lambda w: float((w[:-1] < w[-1]).mean() * 100), raw=True)
    label = pd.Series(np.where(pct < CALM_PCT, "Calm", np.where(pct > HIGH_PCT, "High", "Normal")),
                      index=close.index, dtype=object)
    label[pct.isna()] = None
    return pd.DataFrame({"vol20": vol20, "vol_pct": pct, "volatility": label})


def breadth_frame(closes: pd.DataFrame, highs: pd.DataFrame, lows: pd.DataFrame) -> pd.DataFrame:
    """Return daily breadth for the member columns of the wide frames."""
    out = pd.DataFrame(index=closes.index)
    out["members"] = closes.notna().sum(axis=1)
    for n in (20, 50, 200):
        sma = closes.rolling(n, min_periods=_min_bars(n)).mean()
        valid = sma.notna() & closes.notna()
        above = ((closes > sma) & valid).sum(axis=1)
        count = valid.sum(axis=1)
        out[f"pct_above_{n}"] = (above / count.replace(0, np.nan)) * 100
    top = highs.rolling(YEAR, min_periods=_min_bars(YEAR)).max()
    bottom = lows.rolling(YEAR, min_periods=_min_bars(YEAR)).min()
    out["new_highs"] = ((highs >= top) & top.notna()).sum(axis=1)
    out["new_lows"] = ((lows <= bottom) & bottom.notna()).sum(axis=1)
    prev = closes.shift(1)
    out["advancers"] = (closes > prev).sum(axis=1)
    out["decliners"] = (closes < prev).sum(axis=1)
    return out


@dataclass(frozen=True)
class Fear:
    """A day's fear reading."""

    label: str
    score: int
    note: str


def fear_reading(
    vix: float | None, vix3m: float | None, volatility: str | None, pct_above_50: float | None
) -> Fear:
    """Add fear points and map them to Calm (0–1), Nervous (2–3) or Fearful (4+)."""
    score = 0
    note = ""
    if vix is None or math.isnan(vix):
        note = "no VIX"
    else:
        score += 2 if vix >= 30 else 1 if vix >= 20 else 0
        if vix3m is not None and not math.isnan(vix3m) and vix > vix3m:
            score += 2
    if volatility == "High":
        score += 1
    if pct_above_50 is not None and not math.isnan(pct_above_50) and pct_above_50 < 40:
        score += 1
    label = "Calm" if score <= 1 else "Nervous" if score <= 3 else "Fearful"
    return Fear(label, score, note)
