"""Unit tests: MD-SCR-016.005.M29 — core/price_patterns/_breakouts.py
Refs: UT-SCR-016.005–.006 (M29)
"""
from __future__ import annotations

import random
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import talib

from us_swing.analysis.indicators import ema as legacy_ema
from us_swing.core.indicator_rules import BarArrays
from us_swing.core.price_patterns import PATTERNS, PatternRule, evaluate_pattern


def _arrays(
    close: list[float] | np.ndarray,
    high: list[float] | np.ndarray | None = None,
    low: list[float] | np.ndarray | None = None,
    volume: list[float] | np.ndarray | None = None,
    open_: list[float] | np.ndarray | None = None,
) -> BarArrays:
    c = np.asarray(close, dtype=np.float64)
    h = c + 1.0 if high is None else np.asarray(high, dtype=np.float64)
    lo = c - 1.0 if low is None else np.asarray(low, dtype=np.float64)
    v = np.full(len(c), 1e6) if volume is None else np.asarray(volume, dtype=np.float64)
    o = c.copy() if open_ is None else np.asarray(open_, dtype=np.float64)
    return BarArrays(o, h, lo, c, v)


def _flat(n: int = 300) -> BarArrays:
    return _arrays(np.full(n, 100.0))


def _with_last(
    n: int, *, o: float, h: float, low: float, c: float, v: float = 1e6
) -> BarArrays:
    a = _flat(n)
    a.open[-1], a.high[-1], a.low[-1], a.close[-1], a.volume[-1] = o, h, low, c, v
    return a


def _high_breakout() -> BarArrays:
    return _with_last(30, o=101.0, h=106.0, low=100.0, c=105.0)


def _gap_up() -> BarArrays:
    return _with_last(5, o=103.0, h=104.0, low=102.5, c=103.5)


def _gap_down() -> BarArrays:
    return _with_last(5, o=97.0, h=98.5, low=96.0, c=96.5)


def _pocket_pivot() -> BarArrays:
    return _with_last(30, o=100.0, h=101.5, low=99.5, c=101.0, v=2e6)


def _darvas() -> BarArrays:
    return _with_last(25, o=101.0, h=104.0, low=100.5, c=103.0)


def _bull_flag() -> BarArrays:
    closes = [100.0] * 10 + [103.0, 106.0, 109.0, 112.0, 115.0]
    closes += [114.0, 113.5, 114.0, 113.0, 114.0, 117.0]
    c = np.asarray(closes)
    return _arrays(c, c + 0.5, c - 0.5)


def _rising() -> BarArrays:
    return _arrays(np.arange(100.0, 115.0))


def _falling() -> BarArrays:
    return _arrays(np.arange(115.0, 100.0, -1.0))


def _golden_cross() -> BarArrays:
    closes = np.concatenate([np.linspace(150.0, 100.0, 60), np.linspace(101.0, 160.0, 40)])
    gap = talib.EMA(closes, 10) - talib.EMA(closes, 50)
    cross = next(j for j in range(51, len(closes)) if gap[j - 1] <= 0 < gap[j])
    return _arrays(closes[: cross + 2])


def _outside_bar() -> BarArrays:
    return _with_last(5, o=100.0, h=102.0, low=98.0, c=100.0)


def _nr4() -> BarArrays:
    return _with_last(10, o=100.0, h=100.2, low=99.8, c=100.0)


def _inside_bar() -> BarArrays:
    return _with_last(5, o=100.0, h=100.5, low=99.5, c=100.0)


def _vcp() -> BarArrays:
    c = np.full(60, 99.5)
    h = np.full(60, 100.0)
    lo = np.full(60, 99.0)
    lo[5], lo[25], lo[45] = 80.0, 88.0, 94.0
    v = np.concatenate([np.full(20, 2e6), np.full(20, 1.5e6), np.full(20, 1e6)])
    return _arrays(c, h, lo, v)


def _squeeze() -> BarArrays:
    amp = np.linspace(5.0, 0.1, 140)
    sign = np.where(np.arange(140) % 2 == 0, 1.0, -1.0)
    return _arrays(100.0 + amp * sign)


def _double_bottom() -> BarArrays:
    knots_x = [0, 10, 25, 45, 59]
    knots_y = [110.0, 90.0, 105.0, 90.5, 112.0]
    return _arrays(np.interp(np.arange(60), knots_x, knots_y))


def _double_top() -> BarArrays:
    knots_x = [0, 10, 25, 45, 59]
    knots_y = [90.0, 110.0, 95.0, 109.5, 88.0]
    return _arrays(np.interp(np.arange(60), knots_x, knots_y))


def _double_top_pullback() -> BarArrays:
    knots_x = [0, 10, 25, 40, 50, 59]
    knots_y = [90.0, 110.0, 95.0, 109.5, 88.0, 93.0]
    return _arrays(np.interp(np.arange(60), knots_x, knots_y))


def _swing(knots_y: list[float]) -> BarArrays:
    return _arrays(np.interp(np.arange(60), [0, 10, 30, 59], knots_y))


def _fib_sell() -> BarArrays:
    return _swing([80.0, 100.0, 60.0, 82.0])


def _fib_buy() -> BarArrays:
    return _swing([120.0, 100.0, 140.0, 118.0])


def _cup_with_handle() -> BarArrays:
    cup = np.interp(np.arange(119), [0, 60, 118], [100.0, 75.0, 99.0])
    handle = np.asarray([98.0, 97.5, 97.0, 97.5, 98.0, 97.5, 97.0, 97.5, 98.0, 97.5])
    c = np.concatenate([cup, handle, [102.0]])
    return _arrays(c)


_POSITIVE: dict[str, tuple[Callable[[], BarArrays], dict[str, float]]] = {
    "high_52w_breakout": (_high_breakout, {"lookback": 20}),
    "gap_up": (_gap_up, {}),
    "pocket_pivot": (_pocket_pivot, {}),
    "darvas_box": (_darvas, {}),
    "bull_flag": (_bull_flag, {}),
    "higher_highs_lows": (_rising, {}),
    "lower_highs_lows": (_falling, {}),
    "golden_cross": (_golden_cross, {"fast": 10, "slow": 50, "within": 5}),
    "gap_down": (_gap_down, {}),
    "outside_bar": (_outside_bar, {}),
    "nr4": (_nr4, {}),
    "inside_bar": (_inside_bar, {}),
    "vcp": (_vcp, {}),
    "bollinger_squeeze": (_squeeze, {}),
    "double_bottom": (_double_bottom, {}),
    "double_top": (_double_top, {}),
    "double_top_pullback": (_double_top_pullback, {"within": 15}),
    "fib_retracement_sell": (_fib_sell, {}),
    "fib_retracement_buy": (_fib_buy, {}),
    "cup_with_handle": (_cup_with_handle, {}),
}


@pytest.mark.parametrize("pattern_id", list(_POSITIVE))
def test_new_pattern_matches_built_series(pattern_id: str) -> None:
    """UT-SCR-016.005.M29.T01: each new pattern matches its built series."""
    build, params = _POSITIVE[pattern_id]
    assert evaluate_pattern(PatternRule(pattern_id, params), build()) is True


@pytest.mark.parametrize("pattern_id", list(_POSITIVE))
def test_new_pattern_rejects_flat_series(pattern_id: str) -> None:
    """UT-SCR-016.005.M29.T02: each new pattern rejects a flat series (NR4: widening ranges)."""
    _, params = _POSITIVE[pattern_id]
    if pattern_id == "nr4":
        c = np.full(10, 100.0)
        spread = np.arange(1.0, 11.0)
        arrays = _arrays(c, c + spread, c - spread)
    else:
        arrays = _flat()
    assert evaluate_pattern(PatternRule(pattern_id, params), arrays) is False


def test_golden_cross_needs_fast_below_slow() -> None:
    """UT-SCR-016.005.M29.T03: fast ≥ slow never matches."""
    rule = PatternRule("golden_cross", {"fast": 100, "slow": 100, "within": 20})
    assert evaluate_pattern(rule, _golden_cross()) is False


def test_double_top_pullback_rejects_breakdown_still_falling() -> None:
    """UT-SCR-016.016.M29.T01: a breakdown far below the neck is not a pullback."""
    assert evaluate_pattern(PatternRule("double_top_pullback", {}), _double_top()) is False


def test_double_top_pullback_rejects_close_back_above_neck() -> None:
    """UT-SCR-016.016.M29.T02: a close back above the neck ends the setup."""
    knots_x = [0, 10, 25, 40, 50, 59]
    knots_y = [90.0, 110.0, 95.0, 109.5, 88.0, 96.0]
    arrays = _arrays(np.interp(np.arange(60), knots_x, knots_y))
    assert evaluate_pattern(PatternRule("double_top_pullback", {"within": 15}), arrays) is False


def test_double_bottom_rejects_stale_breakout() -> None:
    """UT-SCR-016.017.M29.T01: a breakout older than `within` bars does not match."""
    knots_x = [0, 10, 25, 35, 42, 59]
    knots_y = [110.0, 90.0, 105.0, 90.5, 112.0, 113.0]
    arrays = _arrays(np.interp(np.arange(60), knots_x, knots_y))
    assert evaluate_pattern(PatternRule("double_bottom", {}), arrays) is False
    assert evaluate_pattern(PatternRule("double_bottom", {"within": 20}), arrays) is True


def test_fib_sell_rejects_close_above_zone() -> None:
    """UT-SCR-016.018.M29.T01: a bounce that closed above the 61.8 % level does not match."""
    rule = PatternRule("fib_retracement_sell", {})
    assert evaluate_pattern(rule, _swing([80.0, 100.0, 60.0, 88.0])) is False


def test_fib_sell_rejects_bounce_below_zone() -> None:
    """UT-SCR-016.018.M29.T02: a bounce that has not reached the 50 % level does not match."""
    rule = PatternRule("fib_retracement_sell", {})
    assert evaluate_pattern(rule, _swing([80.0, 100.0, 60.0, 72.0])) is False


def test_fib_rejects_swing_below_min_move() -> None:
    """UT-SCR-016.018.M29.T03: a swing smaller than `min_move` is ignored."""
    arrays = _swing([100.0, 102.0, 97.0, 99.6])
    assert evaluate_pattern(PatternRule("fib_retracement_sell", {}), arrays) is False
    assert evaluate_pattern(PatternRule("fib_retracement_sell", {"min_move": 5}), arrays) is True


# ── Legacy equivalence (old PriceActionScreener helpers, verbatim logic) ──────

def _old_52w(bars: list[Any], cfg: dict[str, Any]) -> bool:
    lookback = int(cfg.get("lookback", 252))
    window = bars if len(bars) < lookback else bars[-lookback:]
    period_high = max(b.high for b in window)
    return bool(period_high > 0 and bars[-1].close / period_high >= cfg.get("min_ratio", 0.9))


def _old_volume(bars: list[Any], cfg: dict[str, Any]) -> bool:
    lookback = int(cfg.get("lookback", 20))
    if len(bars) < lookback + 1:
        return False
    prior = bars[-(lookback + 1):-1]
    vol_ma = sum(b.volume for b in prior) / len(prior)
    return bool(
        bars[-1].close > max(b.high for b in prior)
        and bars[-1].volume > vol_ma * cfg.get("vol_multiplier", 1.5)
    )


def _old_nr7(bars: list[Any], cfg: dict[str, Any]) -> bool:
    if len(bars) < 7:
        return False
    ranges = [b.high - b.low for b in bars[-7:]]
    return bool(ranges[-1] == min(ranges))


def _old_ema(bars: list[Any], cfg: dict[str, Any]) -> bool:
    period = int(cfg.get("ema_period", 21))
    if len(bars) < period + 1:
        return False
    line = legacy_ema(bars, period)
    return bool(bars[-2].close < line[-2] and bars[-1].close >= line[-1])


_LEGACY: dict[str, tuple[Callable[[list[Any], dict[str, Any]], bool], dict[str, Any]]] = {
    "proximity_52w_high": (_old_52w, {"min_ratio": 0.95, "lookback": 60}),
    "volume_breakout": (_old_volume, {"lookback": 10, "vol_multiplier": 1.2}),
    "nr7_compression": (_old_nr7, {}),
    "ema_pullback": (_old_ema, {"ema_period": 10}),
}


def _random_bars(n: int, seed: int) -> list[SimpleNamespace]:
    rng = random.Random(seed)
    price, bars = 100.0, []
    for _ in range(n):
        price = max(price * (1 + rng.gauss(0.0005, 0.02)), 1.0)
        spread = price * rng.uniform(0.002, 0.03)
        bars.append(SimpleNamespace(
            open=price, high=price + spread, low=price - spread, close=price,
            volume=rng.uniform(5e5, 3e6),
        ))
    return bars


@pytest.mark.parametrize("pattern_id", list(_LEGACY))
def test_legacy_patterns_equal_old_code(pattern_id: str) -> None:
    """UT-SCR-016.006.M29.T01: legacy patterns give the same flags as the old helpers."""
    old, cfg = _LEGACY[pattern_id]
    bars = _random_bars(260, seed=11)
    rule = PatternRule(pattern_id, cfg)
    hits = 0
    for end in range(60, 260):
        window = bars[:end]
        expected = old(window, cfg)
        hits += expected
        assert evaluate_pattern(rule, BarArrays.from_bars(window)) is expected, end
    assert hits > 0, "series never triggers the pattern; test proves nothing"


def test_legacy_ids_unchanged() -> None:
    """UT-SCR-016.006.M29.T02: legacy ids are still in the catalogue."""
    ids = {s.id for s in PATTERNS}
    assert {"proximity_52w_high", "volume_breakout", "nr7_compression", "ema_pullback"} <= ids
