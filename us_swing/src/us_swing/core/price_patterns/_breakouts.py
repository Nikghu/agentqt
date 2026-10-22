"""
Module: MD-SCR-016.005.M29 — core/price_patterns/_breakouts.py
Parent SRD: SRD-SCR-016.005, SRD-SCR-016.016, SRD-SCR-016.017, SRD-SCR-016.018

Breakout, trend, volatility and chart-shape patterns on daily OHLCV arrays.
Every detector checks the last bar; formulas follow DD-SCR-016.005.D01.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import numpy.typing as npt
import talib

from us_swing.core.indicator_rules import BarArrays, ParamSpec
from us_swing.core.indicator_rules._ta import FloatArray, ema, safe_div
from us_swing.core.price_patterns._spec import (
    Detect,
    Direction,
    MinBars,
    PatternCategory,
    PatternSpec,
)

Params = Mapping[str, float]


def _i(params: Params, key: str) -> int:
    return int(params[key])


def _prior(series: FloatArray, bars: int) -> FloatArray:
    """The ``bars`` values before the last one."""
    return series[-(bars + 1):-1]


def _seeded_ema(close: FloatArray, period: int) -> FloatArray:
    """EMA seeded from the first close, as the legacy price action screener computed it."""
    k = 2.0 / (period + 1)
    out = np.empty_like(close)
    out[0] = close[0]
    for i in range(1, len(close)):
        out[i] = close[i] * k + out[i - 1] * (1.0 - k)
    return out


# ── Breakout ──────────────────────────────────────────────────────────────────

def _near_52w_high(a: BarArrays, p: Params) -> bool:
    top = a.high[-_i(p, "lookback"):].max()
    return bool(top > 0 and a.close[-1] / top >= p["min_ratio"])


def _high_52w_breakout(a: BarArrays, p: Params) -> bool:
    return bool(a.close[-1] > _prior(a.high, _i(p, "lookback")).max())


def _volume_breakout(a: BarArrays, p: Params) -> bool:
    lookback = _i(p, "lookback")
    return bool(
        a.close[-1] > _prior(a.high, lookback).max()
        and a.volume[-1] > _prior(a.volume, lookback).mean() * p["vol_multiplier"]
    )


def _gap_up(a: BarArrays, p: Params) -> bool:
    prev_high = a.high[-2]
    return bool(
        prev_high > 0
        and a.low[-1] > prev_high
        and (a.open[-1] / prev_high - 1.0) * 100.0 >= p["min_gap"]
    )


def _pocket_pivot(a: BarArrays, p: Params) -> bool:
    lookback = _i(p, "lookback")
    closes = _prior(a.close, lookback)
    prev_closes = a.close[-(lookback + 2):-2]
    down_volume = _prior(a.volume, lookback)[closes < prev_closes]
    return bool(
        a.close[-1] > a.close[-2]
        and a.volume[-1] > down_volume.max(initial=0.0)
        and a.close[-1] >= ema(a.close, _i(p, "ema_period"))[-1]
    )


def _darvas_box(a: BarArrays, p: Params) -> bool:
    box = _i(p, "box_bars")
    top = _prior(a.high, box).max()
    bottom = _prior(a.low, box).min()
    return bool(
        top > 0 and (top - bottom) / top * 100.0 <= p["max_depth"] and a.close[-1] > top
    )


def _bull_flag(a: BarArrays, p: Params) -> bool:
    pole, flag = _i(p, "pole_bars"), _i(p, "flag_bars")
    end = len(a.close) - 2 - flag
    start = end - pole
    c_start, c_end = a.close[start], a.close[end]
    if c_start <= 0:
        return False
    gain = (c_end / c_start - 1.0) * 100.0
    return bool(
        gain >= p["min_pole_gain"]
        and _prior(a.low, flag).min() >= c_end - 0.5 * (c_end - c_start)
        and a.close[-1] > _prior(a.high, flag).max()
    )


# ── Trend ─────────────────────────────────────────────────────────────────────

def _ema_pullback(a: BarArrays, p: Params) -> bool:
    line = _seeded_ema(a.close, _i(p, "ema_period"))
    return bool(a.close[-2] < line[-2] and a.close[-1] >= line[-1])


def _swing_extremes(a: BarArrays, p: Params) -> tuple[FloatArray, FloatArray]:
    size, swings = _i(p, "swing_bars"), _i(p, "swings")
    highs = a.high[-size * swings:].reshape(swings, size).max(axis=1)
    lows = a.low[-size * swings:].reshape(swings, size).min(axis=1)
    return highs, lows


def _higher_highs_lows(a: BarArrays, p: Params) -> bool:
    highs, lows = _swing_extremes(a, p)
    return bool(np.all(np.diff(highs) > 0) and np.all(np.diff(lows) > 0))


def _lower_highs_lows(a: BarArrays, p: Params) -> bool:
    highs, lows = _swing_extremes(a, p)
    return bool(np.all(np.diff(highs) < 0) and np.all(np.diff(lows) < 0))


def _golden_cross(a: BarArrays, p: Params) -> bool:
    fast, slow, within = _i(p, "fast"), _i(p, "slow"), _i(p, "within")
    if fast >= slow:
        return False
    gap = (ema(a.close, fast) - ema(a.close, slow))[-(within + 1):]
    return bool(np.any((gap[:-1] <= 0) & (gap[1:] > 0)))


def _fib_retracement_sell(a: BarArrays, p: Params) -> bool:
    lookback = _i(p, "lookback")
    highs, lows, closes = a.high[-lookback:], a.low[-lookback:], a.close[-lookback:]
    low_at = int(np.argmin(lows[:-1]))
    if low_at < 5 or p["zone_from"] > p["zone_to"]:
        return False
    high_at = int(np.argmax(highs[:low_at]))
    swing_low, leg = lows[low_at], highs[high_at] - lows[low_at]
    if low_at - high_at < 5 or leg < highs[high_at] * p["min_move"] / 100.0:
        return False
    zone_bottom = swing_low + leg * p["zone_from"] / 100.0
    zone_top = swing_low + leg * p["zone_to"] / 100.0
    return bool(highs[-1] >= zone_bottom and np.all(closes[low_at + 1:] <= zone_top))


def _fib_retracement_buy(a: BarArrays, p: Params) -> bool:
    lookback = _i(p, "lookback")
    highs, lows, closes = a.high[-lookback:], a.low[-lookback:], a.close[-lookback:]
    high_at = int(np.argmax(highs[:-1]))
    if high_at < 5 or p["zone_from"] > p["zone_to"]:
        return False
    low_at = int(np.argmin(lows[:high_at]))
    swing_high, leg = highs[high_at], highs[high_at] - lows[low_at]
    if high_at - low_at < 5 or lows[low_at] <= 0 or leg < lows[low_at] * p["min_move"] / 100.0:
        return False
    zone_bottom = swing_high - leg * p["zone_to"] / 100.0
    zone_top = swing_high - leg * p["zone_from"] / 100.0
    return bool(lows[-1] <= zone_top and np.all(closes[high_at + 1:] >= zone_bottom))


def _gap_down(a: BarArrays, p: Params) -> bool:
    prev_low = a.low[-2]
    return bool(
        prev_low > 0
        and a.high[-1] < prev_low
        and (1.0 - a.open[-1] / prev_low) * 100.0 >= p["min_gap"]
    )


def _outside_bar(a: BarArrays, p: Params) -> bool:
    return bool(a.high[-1] > a.high[-2] and a.low[-1] < a.low[-2])


# ── Volatility ────────────────────────────────────────────────────────────────

def _narrowest_of(bars: int) -> Detect:
    def detect(a: BarArrays, p: Params) -> bool:
        ranges = (a.high - a.low)[-bars:]
        return bool(ranges[-1] == ranges.min())

    return detect


def _inside_bar(a: BarArrays, p: Params) -> bool:
    return bool(a.high[-1] < a.high[-2] and a.low[-1] > a.low[-2])


def _vcp(a: BarArrays, p: Params) -> bool:
    lookback, parts, final = _i(p, "lookback"), _i(p, "contractions"), p["final_depth"]
    size = lookback // parts
    span = size * parts
    tops = a.high[-span:].reshape(parts, size).max(axis=1)
    bottoms = a.low[-span:].reshape(parts, size).min(axis=1)
    if np.any(tops <= 0):
        return False
    depths = (tops - bottoms) / tops * 100.0
    volumes = a.volume[-span:].reshape(parts, size).mean(axis=1)
    return bool(
        np.all(np.diff(depths) < 0)
        and depths[-1] <= final
        and volumes[-1] < volumes[0]
        and a.close[-1] >= a.high[-lookback:].max() * (1.0 - final / 100.0)
    )


def _bollinger_squeeze(a: BarArrays, p: Params) -> bool:
    upper, mid, lower = talib.BBANDS(
        a.close, timeperiod=_i(p, "period"), nbdevup=2.0, nbdevdn=2.0
    )
    width = safe_div(np.asarray(upper - lower, dtype=np.float64), np.asarray(mid))
    recent = width[-_i(p, "lookback"):]
    if np.isnan(recent).any():
        return False
    return bool(recent[-1] < recent[:-1].min())


# ── Chart shapes (rough checks) ───────────────────────────────────────────────

def _bars_since_first(hits: npt.NDArray[np.bool_]) -> int | None:
    """Bars from the first True in ``hits`` to its last element, or None if none."""
    idx = np.flatnonzero(hits)
    return None if idx.size == 0 else len(hits) - 1 - int(idx[0])


def _double_bottom(a: BarArrays, p: Params) -> bool:
    lookback = _i(p, "lookback")
    highs, lows, closes = a.high[-lookback:], a.low[-lookback:], a.close[-lookback:]
    half = lookback // 2
    first = int(np.argmin(lows[:half]))
    second = half + int(np.argmin(lows[half:-1]))
    if second - first < 10 or lows[first] <= 0:
        return False
    neck = highs[first:second + 1].max()
    age = _bars_since_first(closes[second + 1:] > neck)
    return bool(
        abs(lows[second] / lows[first] - 1.0) * 100.0 <= p["tolerance"]
        and neck >= max(lows[first], lows[second]) * 1.05
        and closes[-1] > neck
        and age is not None
        and age < _i(p, "within")
    )


def _double_top_breakdown(a: BarArrays, p: Params) -> tuple[FloatArray, float] | None:
    """Closes after the second top, and the neck, when the top shape holds."""
    lookback = _i(p, "lookback")
    highs, lows = a.high[-lookback:], a.low[-lookback:]
    half = lookback // 2
    first = int(np.argmax(highs[:half]))
    second = half + int(np.argmax(highs[half:-1]))
    if second - first < 10 or highs[first] <= 0:
        return None
    neck = float(lows[first:second + 1].min())
    if (
        abs(highs[second] / highs[first] - 1.0) * 100.0 > p["tolerance"]
        or neck * 1.05 > min(highs[first], highs[second])
    ):
        return None
    return a.close[-lookback:][second + 1:], neck


def _double_top(a: BarArrays, p: Params) -> bool:
    shape = _double_top_breakdown(a, p)
    if shape is None:
        return False
    closes, neck = shape
    age = _bars_since_first(closes < neck)
    return bool(closes[-1] < neck and age is not None and age < _i(p, "within"))


def _double_top_pullback(a: BarArrays, p: Params) -> bool:
    shape = _double_top_breakdown(a, p)
    if shape is None:
        return False
    closes, neck = shape
    age = _bars_since_first(closes < neck)
    return bool(
        age is not None
        and 1 <= age <= _i(p, "within")
        and np.all(closes[-(age + 1):] < neck)
        and a.high[-1] >= neck * (1.0 - p["near"] / 100.0)
    )


def _cup_with_handle(a: BarArrays, p: Params) -> bool:
    lookback, handle = _i(p, "lookback"), _i(p, "handle_bars")
    cup_high = a.high[-lookback:-(handle + 1)]
    cup_low = a.low[-lookback:-(handle + 1)]
    third = len(cup_high) // 3
    left = cup_high[:third].max()
    if left <= 0:
        return False
    right = cup_high[-third:].max()
    bottom = cup_low.min()
    depth = (left - bottom) / left * 100.0
    return bool(
        12.0 <= depth <= p["max_depth"]
        and right >= 0.95 * left
        and _prior(a.low, handle).min() >= right - 0.5 * (right - bottom)
        and a.close[-1] > _prior(a.high, handle).max()
    )


# ── Catalogue entries ─────────────────────────────────────────────────────────

def _bars(n: int) -> MinBars:
    return lambda p: n


_BULL, _BEAR, _NEUTRAL = Direction.BULLISH, Direction.BEARISH, Direction.NEUTRAL
_BREAKOUT, _TREND = PatternCategory.BREAKOUT, PatternCategory.TREND
_VOLATILITY, _SHAPES = PatternCategory.VOLATILITY, PatternCategory.CHART_SHAPES

_LOOKBACK_52W = ParamSpec("lookback", "Lookback", "int", 252, 20, 504, display="{} bars")
_MIN_GAP = ParamSpec("min_gap", "Min gap %", "float", 1.0, 0.1, 20.0, 0.1, display="≥ {}%")
_FIB_PARAMS = (
    ParamSpec("lookback", "Lookback", "int", 60, 20, 250),
    ParamSpec("zone_from", "Zone from %", "float", 50.0, 20.0, 90.0, 0.1),
    ParamSpec("zone_to", "Zone to %", "float", 61.8, 20.0, 90.0, 0.1),
    ParamSpec("min_move", "Min swing %", "float", 10.0, 3.0, 50.0, 1.0),
)
_SWINGS = (
    ParamSpec("swing_bars", "Bars per swing", "int", 5, 2, 20),
    ParamSpec("swings", "Swings", "int", 3, 2, 5),
)


def breakout_specs() -> tuple[PatternSpec, ...]:
    """Build the breakout, trend, volatility and chart-shape catalogue entries."""
    return (
        PatternSpec(
            "proximity_52w_high", "Near 52-Week High", "52wHigh", _BREAKOUT, _BULL,
            "Close within a set ratio of the highest high of the lookback.",
            (ParamSpec("min_ratio", "Min ratio", "float", 0.90, 0.50, 1.00, 0.01),
             _LOOKBACK_52W),
            _bars(2), _near_52w_high,
        ),
        PatternSpec(
            "high_52w_breakout", "52-Week High Breakout", "52wBreak", _BREAKOUT, _BULL,
            "Close above the highest high of the lookback.",
            (_LOOKBACK_52W,), lambda p: _i(p, "lookback") + 1, _high_52w_breakout,
        ),
        PatternSpec(
            "volume_breakout", "Volume Breakout", "VolBreak", _BREAKOUT, _BULL,
            "Close above the lookback high on volume above its average times a multiplier.",
            (ParamSpec("lookback", "Lookback", "int", 20, 5, 100),
             ParamSpec("vol_multiplier", "Volume ×", "float", 1.5, 1.0, 5.0, 0.1)),
            lambda p: _i(p, "lookback") + 1, _volume_breakout,
        ),
        PatternSpec(
            "gap_up", "Gap Up", "GapUp", _BREAKOUT, _BULL,
            "Bar trades fully above the previous high, opening at least the set gap higher.",
            (_MIN_GAP,), _bars(2), _gap_up,
        ),
        PatternSpec(
            "pocket_pivot", "Pocket Pivot", "PocketPivot", _BREAKOUT, _BULL,
            "Up day with volume above every down day's volume in the lookback, above its EMA.",
            (ParamSpec("lookback", "Lookback", "int", 10, 5, 20),
             ParamSpec("ema_period", "EMA period", "int", 10, 5, 50)),
            lambda p: max(_i(p, "lookback") + 2, _i(p, "ema_period")), _pocket_pivot,
        ),
        PatternSpec(
            "darvas_box", "Darvas Box Breakout", "Darvas", _BREAKOUT, _BULL,
            "Close above a tight trading box of recent bars.",
            (ParamSpec("box_bars", "Box bars", "int", 20, 10, 60),
             ParamSpec("max_depth", "Max depth %", "float", 15.0, 3.0, 30.0, 0.5)),
            lambda p: _i(p, "box_bars") + 1, _darvas_box,
        ),
        PatternSpec(
            "bull_flag", "Bull Flag", "BullFlag", _BREAKOUT, _BULL,
            "Strong pole, shallow flag, then a close above the flag high.",
            (ParamSpec("pole_bars", "Pole bars", "int", 5, 3, 20),
             ParamSpec("min_pole_gain", "Min pole gain %", "float", 10.0, 5.0, 50.0, 0.5),
             ParamSpec("flag_bars", "Flag bars", "int", 5, 3, 20)),
            lambda p: _i(p, "pole_bars") + _i(p, "flag_bars") + 2, _bull_flag,
        ),
        PatternSpec(
            "ema_pullback", "EMA Pullback", "EmaPB", _TREND, _BULL,
            "Close crosses back above the EMA after closing below it.",
            (ParamSpec("ema_period", "EMA period", "int", 21, 5, 200, display="EMA {}"),),
            lambda p: _i(p, "ema_period") + 1, _ema_pullback,
        ),
        PatternSpec(
            "higher_highs_lows", "Higher Highs & Lows", "HHHL", _TREND, _BULL,
            "Each recent swing makes a higher high and a higher low.",
            _SWINGS, lambda p: _i(p, "swing_bars") * _i(p, "swings"), _higher_highs_lows,
        ),
        PatternSpec(
            "lower_highs_lows", "Lower Highs & Lows", "LHLL", _TREND, _BEAR,
            "Each recent swing makes a lower high and a lower low.",
            _SWINGS, lambda p: _i(p, "swing_bars") * _i(p, "swings"), _lower_highs_lows,
        ),
        PatternSpec(
            "golden_cross", "Golden Cross", "GoldenX", _TREND, _BULL,
            "Fast EMA crossed above the slow EMA within the last few bars.",
            (ParamSpec("fast", "Fast EMA", "int", 50, 10, 100),
             ParamSpec("slow", "Slow EMA", "int", 200, 50, 300),
             ParamSpec("within", "Within bars", "int", 5, 1, 20)),
            lambda p: _i(p, "slow") + _i(p, "within"), _golden_cross,
        ),
        PatternSpec(
            "fib_retracement_sell", "Fib Retracement (Sell)", "FibSell", _TREND, _BEAR,
            "After a fall, price bounces into the Fibonacci zone of that swing.",
            _FIB_PARAMS, lambda p: _i(p, "lookback"), _fib_retracement_sell,
        ),
        PatternSpec(
            "fib_retracement_buy", "Fib Retracement (Buy)", "FibBuy", _TREND, _BULL,
            "After a rise, price dips into the Fibonacci zone of that swing.",
            _FIB_PARAMS, lambda p: _i(p, "lookback"), _fib_retracement_buy,
        ),
        PatternSpec(
            "gap_down", "Gap Down", "GapDown", _TREND, _BEAR,
            "Bar trades fully below the previous low, opening at least the set gap lower.",
            (_MIN_GAP,), _bars(2), _gap_down,
        ),
        PatternSpec(
            "outside_bar", "Outside Bar", "Outside", _TREND, _NEUTRAL,
            "Bar's high and low both exceed the previous bar's range.",
            (), _bars(2), _outside_bar,
        ),
        PatternSpec(
            "nr7_compression", "NR7", "NR7", _VOLATILITY, _NEUTRAL,
            "Narrowest high-low range of the last 7 bars.",
            (), _bars(7), _narrowest_of(7),
        ),
        PatternSpec(
            "nr4", "NR4", "NR4", _VOLATILITY, _NEUTRAL,
            "Narrowest high-low range of the last 4 bars.",
            (), _bars(4), _narrowest_of(4),
        ),
        PatternSpec(
            "inside_bar", "Inside Bar", "Inside", _VOLATILITY, _NEUTRAL,
            "Bar's high and low both sit inside the previous bar's range.",
            (), _bars(2), _inside_bar,
        ),
        PatternSpec(
            "vcp", "Volatility Contraction (VCP)", "VCP", _VOLATILITY, _BULL,
            "Each pullback is shallower than the last, volume dries up, price near the high.",
            (ParamSpec("lookback", "Lookback", "int", 60, 30, 250),
             ParamSpec("contractions", "Contractions", "int", 3, 2, 4),
             ParamSpec("final_depth", "Final depth %", "float", 10.0, 2.0, 20.0, 0.5)),
            lambda p: _i(p, "lookback"), _vcp,
        ),
        PatternSpec(
            "bollinger_squeeze", "Bollinger Squeeze", "Squeeze", _VOLATILITY, _NEUTRAL,
            "Bollinger Band width at its lowest of the lookback.",
            (ParamSpec("period", "Period", "int", 20, 10, 50),
             ParamSpec("lookback", "Lookback", "int", 120, 20, 250)),
            lambda p: _i(p, "period") + _i(p, "lookback") - 1, _bollinger_squeeze,
        ),
        PatternSpec(
            "double_bottom", "Double Bottom", "DblBottom", _SHAPES, _BULL,
            "Two similar lows, then a close above the peak between them (rough check).",
            (ParamSpec("lookback", "Lookback", "int", 60, 30, 250),
             ParamSpec("tolerance", "Tolerance %", "float", 3.0, 1.0, 10.0, 0.5),
             ParamSpec("within", "Breakout within", "int", 5, 1, 20)),
            lambda p: _i(p, "lookback"), _double_bottom,
        ),
        PatternSpec(
            "double_top", "Double Top", "DblTop", _SHAPES, _BEAR,
            "Two similar highs, then a recent close below the low between them (rough check).",
            (ParamSpec("lookback", "Lookback", "int", 60, 30, 250),
             ParamSpec("tolerance", "Tolerance %", "float", 3.0, 1.0, 10.0, 0.5),
             ParamSpec("within", "Breakdown within", "int", 5, 1, 20)),
            lambda p: _i(p, "lookback"), _double_top,
        ),
        PatternSpec(
            "double_top_pullback", "Double Top Pullback", "DblTopPB", _SHAPES, _BEAR,
            "Double Top breakdown, then a bounce back up near the broken neck (rough check).",
            (ParamSpec("lookback", "Lookback", "int", 60, 30, 250),
             ParamSpec("tolerance", "Tolerance %", "float", 3.0, 1.0, 10.0, 0.5),
             ParamSpec("within", "Breakdown within", "int", 10, 2, 30),
             ParamSpec("near", "Near neck %", "float", 2.0, 0.5, 5.0, 0.5)),
            lambda p: _i(p, "lookback"), _double_top_pullback,
        ),
        PatternSpec(
            "cup_with_handle", "Cup with Handle", "CupHandle", _SHAPES, _BULL,
            "Rounded base, small handle near the rim, then a breakout (rough check).",
            (ParamSpec("lookback", "Lookback", "int", 130, 60, 250),
             ParamSpec("max_depth", "Max depth %", "float", 35.0, 12.0, 50.0, 0.5),
             ParamSpec("handle_bars", "Handle bars", "int", 10, 5, 20)),
            lambda p: _i(p, "lookback"), _cup_with_handle,
        ),
    )
