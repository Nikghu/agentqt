"""Unit tests: MD-SCR-016.001.M27 — core/price_patterns/_catalogue.py
Refs: UT-SCR-016.001–.002 (M27)
"""
from __future__ import annotations

from collections import Counter

import pytest

from us_swing.core.price_patterns import (
    PATTERNS,
    Direction,
    PatternCategory,
    PatternRuleError,
    get_pattern,
)


def test_catalogue_entries_unique_and_valid() -> None:
    """UT-SCR-016.001.M27.T01: 51 unique ids, short labels without "_", defaults in range."""
    ids = [s.id for s in PATTERNS]
    assert len(ids) == 51
    assert len(set(ids)) == 51
    for spec in PATTERNS:
        assert "_" not in spec.short, spec.id
        for p in spec.params:
            assert p.min <= p.default <= p.max, (spec.id, p.key)
        assert get_pattern(spec.id) is spec


def test_unknown_pattern_rejected() -> None:
    """UT-SCR-016.001.M27.T02: unknown id raises PatternRuleError."""
    with pytest.raises(PatternRuleError):
        get_pattern("nope")


def test_category_sizes() -> None:
    """UT-SCR-016.002.M27.T01: category sizes match the release list."""
    counts = Counter(s.category for s in PATTERNS)
    assert [counts[c] for c in PatternCategory] == [11, 11, 5, 7, 8, 5, 4]


def test_candle_groups_carry_direction() -> None:
    """UT-SCR-016.002.M27.T02: candle groups carry their direction."""
    expected = {
        PatternCategory.BULLISH_CANDLES: Direction.BULLISH,
        PatternCategory.BEARISH_CANDLES: Direction.BEARISH,
        PatternCategory.NEUTRAL_CANDLES: Direction.NEUTRAL,
    }
    for spec in PATTERNS:
        if spec.category in expected:
            assert spec.direction is expected[spec.category], spec.id
