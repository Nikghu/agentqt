"""
Module: MD-SCR-016.011.M31 — core/price_patterns/_evaluate.py
Parent SRD: SRD-SCR-016.011

Evaluates one pattern rule on one symbol's bar arrays.
"""
from __future__ import annotations

from collections.abc import Mapping

from us_swing.core.indicator_rules import BarArrays
from us_swing.core.price_patterns._catalogue import get_pattern
from us_swing.core.price_patterns._rules import PatternRule
from us_swing.core.price_patterns._spec import PatternSpec


def resolve_params(spec: PatternSpec, params: Mapping[str, float]) -> dict[str, float]:
    """Fill missing params with defaults and clamp each to its range."""
    out: dict[str, float] = {}
    for p in spec.params:
        value = min(max(float(params.get(p.key, p.default)), p.min), p.max)
        out[p.key] = float(round(value)) if p.kind == "int" else value
    return out


def evaluate_pattern(rule: PatternRule, arrays: BarArrays) -> bool:
    """Return whether the rule's pattern shows on the last bar.

    Too few bars, or NaN values in the inputs the pattern reads, give no match.
    """
    spec = get_pattern(rule.pattern_id)
    params = resolve_params(spec, rule.params)
    if len(arrays.close) < spec.min_bars(params):
        return False
    return bool(spec.detect(arrays, params))
