"""
Module: MD-SCR-016.007.M30 — core/price_patterns/_rules.py
Parent SRD: SRD-SCR-016.007

Pattern rule model, config schema v2, the legacy ``patterns`` reader and summary text.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from us_swing.core.indicator_rules import format_param_values
from us_swing.core.price_patterns._catalogue import get_pattern
from us_swing.core.price_patterns._spec import PatternRuleError, PatternSpec

SCHEMA_VERSION = 2
DEFAULT_THRESHOLD = 0.2
_SEP = "  ·  "


@dataclass(frozen=True, slots=True)
class PatternRule:
    """One pattern rule; params missing here fall back to catalogue defaults."""

    pattern_id: str
    params: Mapping[str, float] = field(default_factory=dict)
    enabled: bool = True


def default_pattern_rule(spec: PatternSpec) -> PatternRule:
    """Return a new enabled rule for ``spec`` with default params."""
    return PatternRule(spec.id, {p.key: p.default for p in spec.params})


# ── Config read / write ───────────────────────────────────────────────────────

def pattern_rules_to_config(
    rules: list[PatternRule], threshold: float = DEFAULT_THRESHOLD
) -> dict[str, Any]:
    """Serialise rules and the pass threshold to the schema-2 config dict."""
    return {
        "schema": SCHEMA_VERSION,
        "rules": [_rule_to_dict(r) for r in rules],
        "threshold": threshold,
    }


def pattern_rules_from_config(config: Mapping[str, Any]) -> tuple[list[PatternRule], float]:
    """Read rules and threshold from a schema-2 config, or map a legacy ``patterns`` config.

    Raises:
        PatternRuleError: For malformed rules, unknown patterns or a non-numeric threshold.
    """
    try:
        threshold = float(config.get("threshold", DEFAULT_THRESHOLD))
    except (TypeError, ValueError):
        raise PatternRuleError("Pass threshold must be a number") from None
    if "rules" not in config:
        return _rules_from_legacy(config.get("patterns", {}) or {}), threshold
    raw = config["rules"]
    if not isinstance(raw, list):
        raise PatternRuleError("Price action rules must be a list")
    return [_rule_from_dict(item) for item in raw], threshold


def _rule_to_dict(rule: PatternRule) -> dict[str, Any]:
    spec = get_pattern(rule.pattern_id)
    params = {p.key: float(rule.params.get(p.key, p.default)) for p in spec.params}
    return {"pattern_id": rule.pattern_id, "params": params, "enabled": rule.enabled}


def _rule_from_dict(item: Any) -> PatternRule:
    if not isinstance(item, Mapping):
        raise PatternRuleError("Each price action rule must be an object")
    spec = get_pattern(str(item.get("pattern_id", "")))
    raw_params = item.get("params") or {}
    if not isinstance(raw_params, Mapping):
        raise PatternRuleError(f"{spec.name} settings must be an object")
    return PatternRule(spec.id, _params(spec, raw_params), bool(item.get("enabled", True)))


def _params(spec: PatternSpec, raw: Mapping[str, Any]) -> dict[str, float]:
    params = {p.key: float(p.default) for p in spec.params}
    for key, value in raw.items():
        if key not in params:
            raise PatternRuleError(f"{spec.name} has no setting called {key}")
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = math.nan
        if not math.isfinite(number):
            raise PatternRuleError(f"{spec.name} has an invalid number for {key}")
        params[key] = number
    return params


# ── Legacy ``patterns`` mapping (SRD-SCR-016.009) ────────────────────────────

# legacy section, rule id, enabled when the section is missing
_LEGACY: tuple[tuple[str, str, bool], ...] = (
    ("proximity_52w_high", "proximity_52w_high", True),
    ("volume_breakout", "volume_breakout", True),
    ("nr7_compression", "nr7_compression", False),
    ("ema_pullback", "ema_pullback", False),
    ("engulfing", "bullish_engulfing", False),
)


def _rules_from_legacy(patterns: Any) -> list[PatternRule]:
    if not isinstance(patterns, Mapping):
        raise PatternRuleError("Saved price action patterns must be an object")
    rules = []
    for section_id, rule_id, default_on in _LEGACY:
        section = patterns.get(section_id) or {}
        spec = get_pattern(rule_id)
        if not isinstance(section, Mapping):
            raise PatternRuleError(f"Saved {spec.name} settings must be an object")
        settings = {k: v for k, v in section.items() if k != "enabled"}
        legacy_keys = {p.key for p in spec.params}
        params = _params(spec, {k: v for k, v in settings.items() if k in legacy_keys})
        rules.append(PatternRule(rule_id, params, bool(section.get("enabled", default_on))))
    return rules


# ── Summary text (SRD-SCR-016.014) ────────────────────────────────────────────

def pattern_settings_summary(rule: PatternRule) -> str:
    """Settings-column text, e.g. ``1-bar window`` or ``0.9 · 252``; ``""`` without params."""
    return format_param_values(get_pattern(rule.pattern_id).params, rule.params)


def pattern_config_summary(config: Mapping[str, Any]) -> str:
    """Details-column text such as ``PA ≥ 20%  ·  52wHigh``; ``""`` if none on or unreadable."""
    try:
        rules, threshold = pattern_rules_from_config(config)
    except PatternRuleError:
        return ""
    shorts = [get_pattern(r.pattern_id).short for r in rules if r.enabled]
    if not shorts:
        return ""
    return _SEP.join([f"PA ≥ {round(threshold * 100)}%", *shorts])
