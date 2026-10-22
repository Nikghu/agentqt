"""
Module: MD-SCR-016.001.M27 — core/price_patterns/__init__.py
Parent SRD: SRD-SCR-016.001

Public surface of the shared price action pattern catalogue. The screener and
the GUI both import from here and never from each other.
"""
from __future__ import annotations

from us_swing.core.price_patterns._catalogue import PATTERNS, get_pattern
from us_swing.core.price_patterns._evaluate import evaluate_pattern, resolve_params
from us_swing.core.price_patterns._rules import (
    DEFAULT_THRESHOLD,
    PatternRule,
    default_pattern_rule,
    pattern_config_summary,
    pattern_rules_from_config,
    pattern_rules_to_config,
    pattern_settings_summary,
)
from us_swing.core.price_patterns._spec import (
    Direction,
    PatternCategory,
    PatternRuleError,
    PatternSpec,
)

__all__ = [
    "DEFAULT_THRESHOLD",
    "PATTERNS",
    "Direction",
    "PatternCategory",
    "PatternRule",
    "PatternRuleError",
    "PatternSpec",
    "default_pattern_rule",
    "evaluate_pattern",
    "get_pattern",
    "pattern_config_summary",
    "pattern_rules_from_config",
    "pattern_rules_to_config",
    "pattern_settings_summary",
    "resolve_params",
]
