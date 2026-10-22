"""Unit tests: MD-SCR-016.007.M30 — core/price_patterns/_rules.py
Refs: UT-SCR-016.007–.010, .014 (M30), UT-SCR-016.014.M24
"""
from __future__ import annotations

import dataclasses

import pytest

from us_swing.core.price_patterns import (
    PATTERNS,
    PatternRule,
    PatternRuleError,
    default_pattern_rule,
    pattern_config_summary,
    pattern_rules_from_config,
    pattern_rules_to_config,
    pattern_settings_summary,
)

_LEGACY = {
    "patterns": {
        "proximity_52w_high": {"enabled": False, "min_ratio": 0.8, "lookback": 120},
        "volume_breakout": {"enabled": True, "lookback": 30, "vol_multiplier": 2.0},
        "nr7_compression": {"enabled": True},
        "ema_pullback": {"enabled": True, "ema_period": 50},
        "engulfing": {"enabled": True},
    },
    "threshold": 0.4,
}


def _one(rule: dict[str, object]) -> PatternRule:
    rules, _ = pattern_rules_from_config({"schema": 2, "rules": [rule]})
    return rules[0]


def test_missing_params_get_defaults() -> None:
    """UT-SCR-016.007.M30.T01: rule without params gets catalogue defaults."""
    assert dict(_one({"pattern_id": "vcp"}).params) == {
        "lookback": 60.0, "contractions": 3.0, "final_depth": 10.0,
    }


def test_rule_is_frozen() -> None:
    """UT-SCR-016.007.M30.T02: a PatternRule cannot be changed in place."""
    rule = PatternRule("hammer")
    with pytest.raises(dataclasses.FrozenInstanceError):
        rule.enabled = False  # type: ignore[misc]


def test_round_trip_lossless() -> None:
    """UT-SCR-016.008.M30.T01: round trip returns the same rules and threshold."""
    rules = [
        PatternRule("hammer", {"within": 2.0}),
        PatternRule("vcp", {"lookback": 90.0, "contractions": 2.0, "final_depth": 8.0},
                    enabled=False),
        PatternRule("nr4", {}),
    ]
    cfg = pattern_rules_to_config(rules, 0.4)
    assert cfg["schema"] == 2
    assert pattern_rules_from_config(cfg) == (rules, 0.4)


def test_empty_rule_list_round_trip() -> None:
    """UT-SCR-016.008.M30.T02: empty rule list round trips."""
    assert pattern_rules_from_config(pattern_rules_to_config([], 0.2)) == ([], 0.2)


def test_non_numeric_threshold_refused() -> None:
    """UT-SCR-016.008.M30.T03: non-numeric threshold raises."""
    with pytest.raises(PatternRuleError):
        pattern_rules_from_config({"schema": 2, "rules": [], "threshold": "high"})


def test_legacy_dict_maps_to_five_rules() -> None:
    """UT-SCR-016.009.M30.T01: legacy dict → 5 rules; engulfing → bullish_engulfing."""
    rules, threshold = pattern_rules_from_config(_LEGACY)
    assert [r.pattern_id for r in rules] == [
        "proximity_52w_high", "volume_breakout", "nr7_compression", "ema_pullback",
        "bullish_engulfing",
    ]
    assert [r.enabled for r in rules] == [False, True, True, True, True]
    assert dict(rules[0].params) == {"min_ratio": 0.8, "lookback": 120.0}
    assert dict(rules[1].params) == {"lookback": 30.0, "vol_multiplier": 2.0}
    assert dict(rules[3].params) == {"ema_period": 50.0}
    assert threshold == 0.4


def test_empty_config_uses_legacy_defaults() -> None:
    """UT-SCR-016.009.M30.T02: {} → 52w + volume on, other 3 off, threshold 0.2."""
    rules, threshold = pattern_rules_from_config({})
    assert [r.enabled for r in rules] == [True, True, False, False, False]
    assert threshold == 0.2


def test_bad_legacy_param_refused() -> None:
    """UT-SCR-016.009.M30.T03: non-numeric legacy param raises."""
    with pytest.raises(PatternRuleError):
        pattern_rules_from_config({"patterns": {"ema_pullback": {"ema_period": "x"}}})


def test_unknown_pattern_raises() -> None:
    """UT-SCR-016.010.M30.T01: unknown pattern id raises."""
    with pytest.raises(PatternRuleError):
        _one({"pattern_id": "nope"})


@pytest.mark.parametrize("config", [
    {"schema": 2, "rules": [{"pattern_id": "hammer", "params": {"within": "x"}}]},
    {"schema": 2, "rules": "hammer"},
    {"schema": 2, "rules": [{"pattern_id": "hammer", "params": {"period": 3}}]},
    {"schema": 2, "rules": ["hammer"]},
    {"schema": 2, "rules": [{"pattern_id": "hammer", "params": {"within": float("nan")}}]},
    {"patterns": {"nr7_compression": True}},
])
def test_bad_rules_raise(config: dict[str, object]) -> None:
    """UT-SCR-016.010.M30.T02: bad param value, unknown key or malformed list raise."""
    with pytest.raises(PatternRuleError):
        pattern_rules_from_config(config)


def test_every_catalogue_id_loads() -> None:
    """UT-SCR-016.010.M30.T03: a default rule for every catalogue entry loads."""
    rules = [default_pattern_rule(s) for s in PATTERNS]
    loaded, _ = pattern_rules_from_config(pattern_rules_to_config(rules))
    assert len(loaded) == 51


def test_summary_of_legacy_defaults() -> None:
    """UT-SCR-016.014.M30.T01: summary text of the legacy defaults."""
    assert pattern_config_summary({}) == "PA ≥ 20%  ·  52wHigh  ·  VolBreak"


def test_summary_empty_when_nothing_on_or_unreadable() -> None:
    """UT-SCR-016.014.M30.T02: no enabled rules or a bad config → ""."""
    off = pattern_rules_to_config([PatternRule("hammer", enabled=False)])
    assert pattern_config_summary(off) == ""
    assert pattern_config_summary({"rules": [{"pattern_id": "nope"}]}) == ""


def test_settings_summary_text() -> None:
    """UT-SCR-016.014.M30.T03: settings text names one param, joins several, empty for none."""
    assert pattern_settings_summary(PatternRule("hammer", {"within": 1})) == "1-bar window"
    assert pattern_settings_summary(PatternRule("ema_pullback", {"ema_period": 21})) == "EMA 21"
    assert pattern_settings_summary(PatternRule("proximity_52w_high", {})) == "0.9 · 252"
    assert pattern_settings_summary(PatternRule("nr4")) == ""


def test_indicator_settings_summary_unchanged() -> None:
    """UT-SCR-016.014.M24.T01: indicator settings text unchanged after the helper move."""
    from us_swing.core.indicator_rules import default_rule, get_spec, settings_summary

    assert settings_summary(default_rule(get_spec("rsi"))) == "period 14"
    assert settings_summary(default_rule(get_spec("macd"))) == "12 · 26 · 9"
    assert settings_summary(default_rule(get_spec("price"))) == ""
