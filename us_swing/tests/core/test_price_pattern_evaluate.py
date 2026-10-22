"""Unit tests: MD-SCR-016.011.M31 — core/price_patterns/_evaluate.py
Refs: UT-SCR-016.011 (M31)
"""
from __future__ import annotations

import numpy as np

from us_swing.core.indicator_rules import BarArrays
from us_swing.core.price_patterns import PatternRule, evaluate_pattern, get_pattern, resolve_params


def _flat(n: int) -> BarArrays:
    c = np.full(n, 100.0)
    return BarArrays(c, c + 1.0, c - 1.0, c.copy(), np.full(n, 1e6))


def test_params_are_clamped() -> None:
    """UT-SCR-016.011.M31.T01: out-of-range params are clamped, no error."""
    assert resolve_params(get_pattern("hammer"), {"within": 99})["within"] == 5.0
    assert resolve_params(get_pattern("gap_up"), {"min_gap": -3})["min_gap"] == 0.1
    assert evaluate_pattern(PatternRule("hammer", {"within": 99}), _flat(40)) is False


def test_too_few_bars_no_match() -> None:
    """UT-SCR-016.011.M31.T02: 5 bars for VCP (lookback 60) gives no match."""
    assert evaluate_pattern(PatternRule("vcp"), _flat(5)) is False
