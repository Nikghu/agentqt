"""
Module: MD-SCR-016.001.M27 — core/price_patterns/_catalogue.py
Parent SRD: SRD-SCR-016.001

The assembled price action pattern catalogue.
"""
from __future__ import annotations

from us_swing.core.price_patterns._breakouts import breakout_specs
from us_swing.core.price_patterns._candles import candle_specs
from us_swing.core.price_patterns._spec import PatternRuleError, PatternSpec

PATTERNS: tuple[PatternSpec, ...] = candle_specs() + breakout_specs()

_BY_ID: dict[str, PatternSpec] = {spec.id: spec for spec in PATTERNS}


def get_pattern(pattern_id: str) -> PatternSpec:
    """Return the catalogue entry for ``pattern_id``.

    Raises:
        PatternRuleError: If no pattern has that id.
    """
    try:
        return _BY_ID[pattern_id]
    except KeyError:
        raise PatternRuleError(f"Unknown price action pattern: {pattern_id}") from None
