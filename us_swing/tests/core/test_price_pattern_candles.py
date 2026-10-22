"""Unit tests: MD-SCR-016.003.M28 — core/price_patterns/_candles.py
Refs: UT-SCR-016.003–.004 (M28)
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest
import talib

from us_swing.core.indicator_rules import BarArrays
from us_swing.core.price_patterns import (
    PATTERNS,
    Direction,
    PatternRule,
    evaluate_pattern,
)
from us_swing.core.price_patterns._candles import _CANDLES

_FUNCTION = {row[0]: row[4] for row in _CANDLES}
_CANDLE_IDS = [row[0] for row in _CANDLES]
_TWO_SIDED = {
    "bullish_engulfing": "bearish_engulfing",
    "bullish_harami": "bearish_harami",
    "three_inside_up": "three_inside_down",
    "three_outside_up": "three_outside_down",
}


def _flat(n: int = 40) -> BarArrays:
    c = np.full(n, 100.0)
    return BarArrays(c, c + 1.0, c - 1.0, c.copy(), np.full(n, 1e6))


def _patch_signal(
    monkeypatch: pytest.MonkeyPatch, function: str, value: int, bars_back: int = 1
) -> None:
    def fake(o: Any, h: Any, low: Any, c: Any) -> Any:
        out = np.zeros(len(c), dtype=np.int32)
        out[-bars_back] = value
        return out

    monkeypatch.setattr(talib, function, fake)


@pytest.mark.parametrize("pattern_id", _CANDLE_IDS)
def test_candle_matches_its_signal(monkeypatch: pytest.MonkeyPatch, pattern_id: str) -> None:
    """UT-SCR-016.003.M28.T01: each candle entry matches when its TA-Lib signal fires."""
    spec = next(s for s in PATTERNS if s.id == pattern_id)
    value = -100 if spec.direction is Direction.BEARISH else 100
    _patch_signal(monkeypatch, _FUNCTION[pattern_id], value)
    assert evaluate_pattern(PatternRule(pattern_id), _flat()) is True


@pytest.mark.parametrize("bull_id,bear_id", list(_TWO_SIDED.items()))
def test_two_sided_entries_reject_opposite_sign(
    monkeypatch: pytest.MonkeyPatch, bull_id: str, bear_id: str
) -> None:
    """UT-SCR-016.003.M28.T02: two-sided entries reject the opposite sign."""
    _patch_signal(monkeypatch, _FUNCTION[bull_id], -100)
    assert evaluate_pattern(PatternRule(bull_id), _flat()) is False
    _patch_signal(monkeypatch, _FUNCTION[bear_id], 100)
    assert evaluate_pattern(PatternRule(bear_id), _flat()) is False


def test_real_bars_bullish_engulfing() -> None:
    """UT-SCR-016.003.M28.T03: real bars give a TA-Lib bullish engulfing, not bearish."""
    closes = list(np.linspace(120.0, 100.0, 12))
    opens = [c + 1.0 for c in closes]
    opens += [99.0, 94.5]
    closes += [95.0, 101.0]
    o = np.asarray(opens)
    c = np.asarray(closes)
    arrays = BarArrays(o, np.maximum(o, c) + 0.5, np.minimum(o, c) - 0.5, c, np.full(len(c), 1e6))
    assert evaluate_pattern(PatternRule("bullish_engulfing"), arrays) is True
    assert evaluate_pattern(PatternRule("bearish_engulfing"), arrays) is False


def test_within_finds_older_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-SCR-016.004.M28.T01: within 3 finds a signal 2 bars back."""
    _patch_signal(monkeypatch, "CDLHAMMER", 100, bars_back=3)
    assert evaluate_pattern(PatternRule("hammer", {"within": 3}), _flat()) is True


def test_default_within_ignores_older_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-SCR-016.004.M28.T02: default within 1 ignores a signal 2 bars back."""
    _patch_signal(monkeypatch, "CDLHAMMER", 100, bars_back=3)
    assert evaluate_pattern(PatternRule("hammer", {"within": 1}), _flat()) is False
