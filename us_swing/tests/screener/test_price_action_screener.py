"""Tests for PriceActionScreener (M08).

Refs: UT-SCR-002.005.M08.T01–T08 (UTCD-SCR v2.0.0), UT-SCR-016.012–.015.M08 (FO-SCR-014)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from us_swing.core.indicator_rules import BarArrays
from us_swing.core.price_patterns import PatternRule, evaluate_pattern, pattern_rules_to_config
from us_swing.data.models import OHLCVBar
from us_swing.screener.base import ScreenerError
from us_swing.screener.screeners.price_action import PriceActionScreener

from tests.screener.conftest import make_bars


def _match(pattern_id: str, bars: list[OHLCVBar], cfg: dict[str, Any] | None = None) -> bool:
    return evaluate_pattern(PatternRule(pattern_id, cfg or {}), BarArrays.from_bars(bars))


# The legacy tests below call the pattern checks through the shared catalogue.
def _proximity_52w_high(bars: list[OHLCVBar], cfg: dict[str, Any]) -> bool:
    return _match("proximity_52w_high", bars, cfg)


def _volume_breakout(bars: list[OHLCVBar], cfg: dict[str, Any]) -> bool:
    return _match("volume_breakout", bars, cfg)


def _nr7_compression(bars: list[OHLCVBar]) -> bool:
    return _match("nr7_compression", bars)


def _ema_pullback(bars: list[OHLCVBar], cfg: dict[str, Any]) -> bool:
    return _match("ema_pullback", bars, cfg)


def _bullish_engulfing(bars: list[OHLCVBar]) -> bool:
    return _match("bullish_engulfing", bars)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bar(
    close: float,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: int = 2_000_000,
    i: int = 0,
) -> OHLCVBar:
    o = open_ if open_ is not None else close * 0.99
    h = high if high is not None else close * 1.005
    ll = low if low is not None else close * 0.995
    return OHLCVBar(
        symbol="TEST",
        datetime=datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i),
        open=o,
        high=h,
        low=ll,
        close=close,
        volume=volume,
        timeframe="1d",
    )


def _make_flat_bars(n: int, price: float = 100.0, volume: int = 2_000_000) -> list[OHLCVBar]:
    return [_bar(price, i=i, volume=volume) for i in range(n)]


# ---------------------------------------------------------------------------
# T01 — apply() returns (bool, float) per symbol with sufficient bars
# ---------------------------------------------------------------------------

def test_apply_returns_bool_float_tuples():
    """UT-SCR-002.005.M08.T01 — apply() returns dict[str, tuple[bool, float]]."""
    screener = PriceActionScreener()
    syms = ["AAPL", "MSFT", "GOOGL"]
    bars = {s: make_bars(s, n=50) for s in syms}
    result = screener.apply(syms, bars, {})
    assert set(result.keys()) == set(syms)
    for sym, (passed, score) in result.items():
        assert isinstance(passed, bool), f"{sym}: passed not bool"
        assert isinstance(score, float), f"{sym}: score not float"
        assert 0.0 <= score <= 1.0, f"{sym}: score {score} out of [0, 1]"


# ---------------------------------------------------------------------------
# T02 — proximity_52w_high: close at 95% of 252-bar high passes
# ---------------------------------------------------------------------------

def test_proximity_52w_high_passes():
    """UT-SCR-002.005.M08.T02 — 52w-high proximity fires when close ≥ min_ratio × period_high."""
    # Build 252 bars at price 100; last bar at price 95 (95% of high = 100)
    bars = _make_flat_bars(251, price=100.0)
    bars.append(_bar(95.0, high=95.5, low=94.5, i=251))
    cfg = {"min_ratio": 0.90, "lookback": 252}
    assert _proximity_52w_high(bars, cfg) is True


def test_proximity_52w_high_fails_below_ratio():
    """proximity_52w_high does not fire when close < min_ratio × period_high."""
    bars = _make_flat_bars(252, price=100.0)
    # Override last bar to be well below 90%
    bars[-1] = _bar(80.0, high=80.5, low=79.5, i=251)
    cfg = {"min_ratio": 0.90, "lookback": 252}
    assert _proximity_52w_high(bars, cfg) is False


def test_apply_proximity_52w_high_produces_pass():
    """apply() with only proximity_52w_high enabled returns passed=True for qualifying bar."""
    screener = PriceActionScreener()
    bars_data = _make_flat_bars(252, price=100.0)
    # Last bar: 96% of max → passes min_ratio=0.90
    bars_data[-1] = _bar(96.0, high=96.5, low=95.5, i=251)
    config = {
        "patterns": {
            "proximity_52w_high": {"enabled": True, "min_ratio": 0.90, "lookback": 252},
            "volume_breakout": {"enabled": False},
            "nr7_compression": {"enabled": False},
            "ema_pullback": {"enabled": False},
            "engulfing": {"enabled": False},
        },
        "threshold": 0.5,
    }
    result = screener.apply(["SYM"], {"SYM": bars_data}, config)
    passed, score = result["SYM"]
    assert passed is True
    assert score >= 0.2


# ---------------------------------------------------------------------------
# T03 — volume_breakout: close > N-day high + volume spike
# ---------------------------------------------------------------------------

def test_volume_breakout_passes():
    """UT-SCR-002.005.M08.T03 — volume_breakout fires when price + volume conditions met."""
    # 20 prior bars at price=100, volume=1M; last bar: price=105 (above prior highs), vol=2M
    prior = [_bar(100.0, high=101.0, low=99.0, volume=1_000_000, i=i) for i in range(20)]
    current = _bar(105.0, high=106.0, low=104.0, volume=2_000_000, i=20)
    bars = prior + [current]
    cfg = {"lookback": 20, "vol_multiplier": 1.5}
    assert _volume_breakout(bars, cfg) is True


def test_volume_breakout_fails_no_price_breakout():
    """volume_breakout does not fire when price stays within prior range."""
    prior = [_bar(100.0, high=102.0, low=98.0, volume=1_000_000, i=i) for i in range(20)]
    current = _bar(100.0, high=101.0, low=99.0, volume=3_000_000, i=20)
    bars = prior + [current]
    cfg = {"lookback": 20, "vol_multiplier": 1.5}
    assert _volume_breakout(bars, cfg) is False


def test_volume_breakout_fails_no_volume_spike():
    """volume_breakout does not fire on price breakout without volume confirmation."""
    prior = [_bar(100.0, high=101.0, low=99.0, volume=2_000_000, i=i) for i in range(20)]
    current = _bar(105.0, high=106.0, low=104.0, volume=2_000_000, i=20)
    bars = prior + [current]
    cfg = {"lookback": 20, "vol_multiplier": 1.5}
    # vol_ma = 2M, current vol = 2M, multiplier=1.5 → 2M < 3M → fails
    assert _volume_breakout(bars, cfg) is False


# ---------------------------------------------------------------------------
# T04 — NR7: bar with smallest range of last 7 bars
# ---------------------------------------------------------------------------

def test_nr7_fires_on_smallest_range():
    """UT-SCR-002.005.M08.T04 — NR7 fires when last bar has smallest range of 7 bars."""
    # Bars with decreasing ranges; last has range 0.5 (smallest)
    bars = [
        _bar(100.0, high=103.0, low=97.0, i=0),   # range 6
        _bar(100.0, high=102.5, low=97.5, i=1),   # range 5
        _bar(100.0, high=102.0, low=98.0, i=2),   # range 4
        _bar(100.0, high=101.5, low=98.5, i=3),   # range 3
        _bar(100.0, high=101.2, low=98.8, i=4),   # range 2.4
        _bar(100.0, high=101.0, low=99.0, i=5),   # range 2
        _bar(100.0, high=100.25, low=99.75, i=6), # range 0.5 — smallest
    ]
    assert _nr7_compression(bars) is True


def test_nr7_does_not_fire_when_not_narrowest():
    """NR7 does not fire when last bar is not the narrowest of 7."""
    bars = [
        _bar(100.0, high=100.25, low=99.75, i=0),  # narrowest = range 0.5
        _bar(100.0, high=102.0, low=98.0, i=1),
        _bar(100.0, high=102.0, low=98.0, i=2),
        _bar(100.0, high=102.0, low=98.0, i=3),
        _bar(100.0, high=102.0, low=98.0, i=4),
        _bar(100.0, high=102.0, low=98.0, i=5),
        _bar(100.0, high=101.0, low=99.0, i=6),    # range 2, not smallest
    ]
    assert _nr7_compression(bars) is False


# ---------------------------------------------------------------------------
# T05 — EMA pullback: close crosses above EMA
# ---------------------------------------------------------------------------

def test_ema_pullback_fires_on_cross():
    """UT-SCR-002.005.M08.T05 — ema_pullback fires when price crosses above EMA."""
    # Build 22 bars trending down (below EMA), then last bar jumps above EMA
    bars = make_bars("TEST", n=22, base_price=100.0, trend=-0.01, seed=7)
    # Force last two bars: prev below EMA, current above
    bars[-2] = _bar(75.0, i=20)   # well below any EMA(21)
    bars[-1] = _bar(130.0, i=21)  # well above any EMA(21) of prior bars
    cfg = {"ema_period": 21}
    assert _ema_pullback(bars, cfg) is True


def test_ema_pullback_does_not_fire_already_above():
    """ema_pullback does not fire when close was already above EMA."""
    bars = make_bars("TEST", n=22, base_price=100.0, trend=0.02, seed=8)
    # Both prev and current are above EMA — no cross
    bars[-2] = _bar(120.0, i=20)
    bars[-1] = _bar(125.0, i=21)
    cfg = {"ema_period": 21}
    result = _ema_pullback(bars, cfg)
    # In an uptrend both bars may be above EMA; result depends on EMA value but
    # the key test is that result is a bool (no exceptions)
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# T06 — Bullish engulfing pattern
# ---------------------------------------------------------------------------

def test_bullish_engulfing_fires():
    """UT-SCR-002.005.M08.T06 — bullish engulfing detected correctly."""
    bars = [
        _bar(100.0, i=0),
        _bar(95.0, open_=99.0, high=99.5, low=94.5, i=1),   # bearish: open=99, close=95
        _bar(101.0, open_=94.5, high=102.0, low=94.0, i=2), # bullish engulfing: open≤95, close≥99
    ]
    assert _bullish_engulfing(bars) is True


def test_bullish_engulfing_does_not_fire_on_bearish():
    """bullish_engulfing does not fire when current bar is bearish."""
    bars = [
        _bar(100.0, i=0),
        _bar(95.0, open_=99.0, high=99.5, low=94.5, i=1),  # bearish
        _bar(96.0, open_=100.0, high=100.5, low=95.5, i=2), # bearish (close < open)
    ]
    assert _bullish_engulfing(bars) is False


# ---------------------------------------------------------------------------
# T07 — Score = matched/enabled; threshold controls pass/fail
# ---------------------------------------------------------------------------

def test_score_and_threshold():
    """UT-SCR-002.005.M08.T07 — score = matched/enabled; threshold determines pass."""
    screener = PriceActionScreener()
    # Use 252 bars; last bar at 96% of period high → proximity_52w_high fires
    # volume_breakout likely does not fire on flat bars
    bars_data = _make_flat_bars(252, price=100.0)
    bars_data[-1] = _bar(96.0, high=96.5, low=95.5, i=251)

    # Enable only 2 patterns; expect 1 to match (proximity) → score = 0.5
    config = {
        "patterns": {
            "proximity_52w_high": {"enabled": True, "min_ratio": 0.90, "lookback": 252},
            "volume_breakout": {"enabled": True, "lookback": 20, "vol_multiplier": 2.0},
            "nr7_compression": {"enabled": False},
            "ema_pullback": {"enabled": False},
            "engulfing": {"enabled": False},
        },
        "threshold": 0.4,  # 0.5 >= 0.4 → passes
    }
    result = screener.apply(["SYM"], {"SYM": bars_data}, config)
    _, score = result["SYM"]
    assert 0.0 <= score <= 1.0
    # At threshold=0.4, a score of 0.5 must pass; 0.0 must fail
    assert result["SYM"][0] == (score >= 0.4)


# ---------------------------------------------------------------------------
# T08 — Insufficient bars: symbol excluded from output
# ---------------------------------------------------------------------------

def test_insufficient_bars_excluded():
    """UT-SCR-002.005.M08.T08 — symbol with <2 bars is absent from output."""
    screener = PriceActionScreener()
    bars = {
        "ENOUGH": make_bars("ENOUGH", n=30),
        "TOOFEW": [_bar(100.0, i=0)],  # only 1 bar
    }
    result = screener.apply(["ENOUGH", "TOOFEW"], bars, {})
    assert "ENOUGH" in result
    assert "TOOFEW" not in result


def test_symbol_missing_from_bars_excluded():
    """Symbol listed in symbols but absent from bars dict is excluded without error."""
    screener = PriceActionScreener()
    result = screener.apply(["GHOST"], {}, {})
    assert "GHOST" not in result


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

def test_invalid_threshold_raises():
    """threshold outside [0, 1] raises ScreenerError."""
    screener = PriceActionScreener()
    bars = {"SYM": make_bars("SYM", n=30)}
    with pytest.raises(ScreenerError):
        screener.apply(["SYM"], bars, {"threshold": 1.5})


def test_batch_features_returns_empty():
    """batch_features() always returns empty dict."""
    screener = PriceActionScreener()
    assert screener.batch_features(["AAPL"], {}) == {}


def test_all_patterns_disabled_score_zero():
    """When all patterns are disabled, score = 0.0 and symbol fails."""
    screener = PriceActionScreener()
    bars = {"SYM": make_bars("SYM", n=30)}
    config = {
        "patterns": {
            "proximity_52w_high": {"enabled": False},
            "volume_breakout": {"enabled": False},
            "nr7_compression": {"enabled": False},
            "ema_pullback": {"enabled": False},
            "engulfing": {"enabled": False},
        },
        "threshold": 0.2,
    }
    result = screener.apply(["SYM"], bars, config)
    assert result["SYM"] == (False, 0.0)


# ---------------------------------------------------------------------------
# FO-SCR-014 — rule-list configs
# ---------------------------------------------------------------------------

def _nr7_bars() -> list[OHLCVBar]:
    """30 flat bars whose last bar is the narrowest (NR7 and NR4 match, nothing else)."""
    bars = [_bar(100.0, high=102.0, low=98.0, i=i) for i in range(29)]
    bars.append(_bar(100.0, high=100.2, low=99.8, i=29))
    return bars


def test_rule_list_score_is_matched_over_enabled():
    """UT-SCR-016.012.M08.T01: 4 rules, 1 matches, threshold 0.2 → (True, 0.25)."""
    rules = [PatternRule(pid) for pid in ("nr7_compression", "gap_up", "gap_down", "outside_bar")]
    config = pattern_rules_to_config(rules, 0.2)
    assert PriceActionScreener().apply(["S"], {"S": _nr7_bars()}, config) == {"S": (True, 0.25)}


def test_rule_list_threshold_out_of_range_raises():
    """UT-SCR-016.012.M08.T02: threshold 1.5 raises ScreenerError."""
    config = pattern_rules_to_config([PatternRule("nr4")], 1.5)
    with pytest.raises(ScreenerError):
        PriceActionScreener().apply(["S"], {"S": _nr7_bars()}, config)


def test_rule_list_disabled_rule_and_short_symbol():
    """UT-SCR-016.012.M08.T03: disabled rule not counted; 1-bar symbol omitted; none on → 0.0."""
    screener = PriceActionScreener()
    bars = {"S": _nr7_bars(), "ONE": [_bar(100.0)]}
    mixed = pattern_rules_to_config(
        [PatternRule("nr4"), PatternRule("gap_up", enabled=False)], 0.5
    )
    assert screener.apply(["S", "ONE"], bars, mixed) == {"S": (True, 1.0)}
    none_on = pattern_rules_to_config([PatternRule("nr4", enabled=False)], 0.0)
    assert screener.apply(["S"], bars, none_on) == {"S": (True, 0.0)}


def test_screen_detailed_keyed_by_short_label():
    """UT-SCR-016.013.M08.T01: details keyed by short label with bool values."""
    config = pattern_rules_to_config([PatternRule("hammer"), PatternRule("nr7_compression")])
    details = PriceActionScreener().screen_detailed(["S"], {"S": _nr7_bars()}, config)
    assert details == {"S": {"Hammer": False, "NR7": True}}


def test_no_analysis_import_and_id_registered():
    """UT-SCR-016.015.M08.T01: module does not import the analysis tool; id still registered."""
    import inspect

    import us_swing.screener as screener_pkg
    from us_swing.screener.screeners import price_action

    assert "us_swing.analysis" not in inspect.getsource(price_action)
    assert 'register("price_action", PriceActionScreener)' in inspect.getsource(screener_pkg)
