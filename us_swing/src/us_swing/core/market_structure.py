"""
Module: MD-EXE-011.027.M01 — core/market_structure.py
Parent SRD: SRD-EXE-011.027

BOSS_ST market structure shared by the live evaluator and the backtest series
(DD-EXE-011.027.D01). Every array is causal: the value at bar *i* uses bars up
to *i* only, so the live last value equals the backtest value at that bar.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd
import talib
from numpy.lib.stride_tricks import sliding_window_view

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
BoolArray = npt.NDArray[np.bool_]

TIMEFRAME_MINUTES = {"3m": 3, "15m": 15, "30m": 30}
MIN_LTF_BARS = 200
_EMA_PERIOD = 200
_ATR_PERIOD = 14
_ST_PERIOD = 10
_ST_FACTOR = 3.0
_NS_PER_MIN = 60_000_000_000


@dataclass(frozen=True, slots=True)
class Bars:
    """One timeframe's closed bars, oldest first; ``close_ns`` is each bar's UTC close."""

    high: FloatArray
    low: FloatArray
    close: FloatArray
    close_ns: IntArray


@dataclass(frozen=True, slots=True)
class BossStParams:
    """User inputs of BOSS_ST that shape the structure."""

    swing_lookback: int
    min_break_atr: float


@dataclass(frozen=True, slots=True)
class BossSt:
    """BOSS_ST arrays on the LTF bars; ``state`` and ``fresh`` are NaN without enough history."""

    state: FloatArray
    fresh: FloatArray
    bos: IntArray
    choch: IntArray
    choch_htf: FloatArray
    ema: FloatArray
    st_dir: IntArray


def bars_from_frame(frame: pd.DataFrame, minutes: int) -> Bars:
    """Build ``Bars`` from a candle frame with a ``ts`` (backtest) or ``datetime`` (live) column."""
    stamps = pd.DatetimeIndex(frame["ts"] if "ts" in frame.columns else frame["datetime"])
    utc = stamps.tz_localize("UTC") if stamps.tz is None else stamps.tz_convert("UTC")
    open_ns = utc.tz_localize(None).to_numpy(dtype="datetime64[ns]").view(np.int64)
    return Bars(
        high=frame["high"].to_numpy(dtype=np.float64),
        low=frame["low"].to_numpy(dtype=np.float64),
        close=frame["close"].to_numpy(dtype=np.float64),
        close_ns=np.asarray(open_ns + minutes * _NS_PER_MIN, dtype=np.int64),
    )


def break_ok(bars: Bars, min_break_atr: float) -> BoolArray:
    """True where the candle range is at least ``min_break_atr`` × ATR(14)."""
    if min_break_atr <= 0:
        return np.ones(len(bars.close), dtype=np.bool_)
    atr = talib.ATR(bars.high, bars.low, bars.close, timeperiod=_ATR_PERIOD)
    with np.errstate(invalid="ignore"):
        big = (bars.high - bars.low) >= min_break_atr * atr
    return np.asarray(big | np.isnan(atr), dtype=np.bool_)


def swings(values: FloatArray, lookback: int, *, high: bool) -> FloatArray:
    """Swing price at the bar it is confirmed (``lookback`` bars after it), NaN elsewhere."""
    n, width = len(values), 2 * lookback + 1
    out = np.full(n, np.nan)
    if n < width:
        return out
    centre = values[lookback:n - lookback]
    before = values[lookback - 1:n - lookback - 1]
    after = values[lookback + 1:n - lookback + 1]
    window = sliding_window_view(values, width)
    if high:
        hit = (centre > before) & (centre > after) & (centre == window.max(axis=1))
    else:
        hit = (centre < before) & (centre < after) & (centre == window.min(axis=1))
    out[2 * lookback:][hit] = centre[hit]
    return out


def structure(bars: Bars, lookback: int, ok: BoolArray) -> tuple[IntArray, IntArray]:
    """BOS and CHOCH per bar from causal swings; a break counts only where ``ok``."""
    swing_high = swings(bars.high, lookback, high=True)
    swing_low = swings(bars.low, lookback, high=False)
    n = len(bars.close)
    bos = np.zeros(n, dtype=np.int64)
    choch = np.zeros(n, dtype=np.int64)
    last_high = last_low = np.nan
    trend = cur_bos = cur_choch = 0
    for i in range(n):
        if not np.isnan(swing_high[i]):
            last_high = swing_high[i]
        if not np.isnan(swing_low[i]):
            last_low = swing_low[i]
        if ok[i]:
            up, down = bars.close[i] > last_high, bars.close[i] < last_low
            if up and trend >= 0:
                cur_bos, trend = 1, 1
            elif down and trend <= 0:
                cur_bos, trend = -1, -1
            elif down and trend == 1:
                cur_choch, cur_bos, trend = -1, 0, -1
            elif up and trend == -1:
                cur_choch, cur_bos, trend = 1, 0, 1
        bos[i], choch[i] = cur_bos, cur_choch
    return bos, choch


def supertrend_direction(bars: Bars) -> IntArray:
    """Supertrend(10, 3) direction: 1 up, -1 down; bands ratchet while the direction holds."""
    atr = talib.ATR(bars.high, bars.low, bars.close, timeperiod=_ST_PERIOD)
    hl2 = (bars.high + bars.low) / 2.0
    upper, lower = hl2 + _ST_FACTOR * atr, hl2 - _ST_FACTOR * atr
    close = bars.close
    direction = np.ones(len(close), dtype=np.int64)
    for i in range(1, len(close)):
        if close[i] > upper[i - 1]:
            direction[i] = 1
        elif close[i] < lower[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]
            if direction[i] > 0 and lower[i] < lower[i - 1]:
                lower[i] = lower[i - 1]
            if direction[i] < 0 and upper[i] > upper[i - 1]:
                upper[i] = upper[i - 1]
    return direction


def _positions(long_entry: BoolArray, short_entry: BoolArray,
               long_exit: BoolArray, short_exit: BoolArray) -> FloatArray:
    state = np.zeros(len(long_entry), dtype=np.float64)
    pos = 0
    for i in range(len(long_entry)):
        if pos == 0:
            pos = 1 if long_entry[i] else -1 if short_entry[i] else 0
        elif (pos == 1 and long_exit[i]) or (pos == -1 and short_exit[i]):
            pos = 0
        state[i] = pos
    return state


def boss_st(ltf: Bars, htf: Bars, params: BossStParams) -> BossSt:
    """Run BOSS_ST on the LTF bars with HTF CHOCH from HTF bars closed by each LTF close."""
    lookback = params.swing_lookback
    bos, choch = structure(ltf, lookback, break_ok(ltf, params.min_break_atr))
    _htf_bos, htf_choch = structure(htf, lookback, break_ok(htf, params.min_break_atr))
    htf_idx = np.searchsorted(htf.close_ns, ltf.close_ns, side="right") - 1
    choch_htf = np.where(htf_idx >= 0, htf_choch[np.maximum(htf_idx, 0)], np.nan)
    ema = np.asarray(talib.EMA(ltf.close, timeperiod=_EMA_PERIOD), dtype=np.float64)
    st_dir = supertrend_direction(ltf)
    with np.errstate(invalid="ignore"):
        long_entry = (choch_htf == 1) & (bos == 1) & (ltf.close > ema) & (st_dir == 1)
        short_entry = (choch_htf == -1) & (bos == -1) & (ltf.close < ema) & (st_dir == -1)
    state = _positions(long_entry, short_entry, (choch == -1) | (st_dir == -1),
                       (choch == 1) | (st_dir == 1))
    previous = np.concatenate(([0.0], state[:-1]))
    fresh = np.where(state != previous, state, 0.0)
    ready = (np.arange(len(state)) >= MIN_LTF_BARS - 1) & (htf_idx + 1 >= 2 * lookback + 1)
    return BossSt(
        state=np.where(ready, state, np.nan),
        fresh=np.where(ready, fresh, np.nan),
        bos=bos,
        choch=choch,
        choch_htf=choch_htf,
        ema=ema,
        st_dir=st_dir,
    )
