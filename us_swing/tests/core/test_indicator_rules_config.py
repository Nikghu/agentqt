"""Unit tests: MD-SCR-015.006.M24 — core/indicator_rules/_rules.py
Refs: UT-SCR-015.004–.007, .015 (M24)
"""
from __future__ import annotations

import dataclasses

import pytest

from us_swing.core.indicator_rules import (
    Condition,
    IndicatorRuleError,
    Rule,
    config_summary,
    rules_from_config,
    rules_to_config,
)

_LEGACY = {
    "filters": {
        "volatility": {"enabled": True, "min_atr_pct": 0.01},
        "rsi": {"enabled": True, "min": 30, "max": 70, "period": 14},
        "range": {"enabled": True, "min_price": 5.0, "max_price": 5000.0},
        "breakout": {"enabled": True, "lookback": 10},
        "volume": {"enabled": True, "min_volume_ratio": 1.0, "ma_period": 10},
        "rs_index": {"enabled": False, "rs_min_percentile": 70.0, "rs_slope_days": 63},
    }
}


def _one(rule: dict[str, object]) -> list[Rule]:
    return rules_from_config({"schema": 2, "rules": [rule]})


def test_missing_params_get_defaults() -> None:
    """UT-SCR-015.004.M24.T01: rule without params gets catalogue defaults."""
    (rule,) = _one({"indicator_id": "rsi", "condition": "between", "value": 30, "to": 70})
    assert dict(rule.params) == {"period": 14.0}


def test_rule_is_frozen() -> None:
    """UT-SCR-015.004.M24.T02: a Rule cannot be changed in place."""
    rule = Rule("rsi", Condition.BETWEEN, 30.0, 70.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rule.value = 5.0  # type: ignore[misc]


def test_condition_flags() -> None:
    """UT-SCR-015.005.M24.T01: needs_to only for between; needs_value only for comparisons."""
    assert [c for c in Condition if c.needs_to] == [Condition.BETWEEN]
    assert {c for c in Condition if c.needs_value} == {
        Condition.AT_LEAST, Condition.AT_MOST, Condition.BETWEEN,
    }


def test_unknown_condition_refused() -> None:
    """UT-SCR-015.005.M24.T02: unknown condition string raises."""
    with pytest.raises(IndicatorRuleError):
        _one({"indicator_id": "rsi", "condition": "sideways"})


def test_condition_not_allowed_for_indicator() -> None:
    """UT-SCR-015.005.M24.T03: EMA does not accept 'between'."""
    with pytest.raises(IndicatorRuleError):
        _one({"indicator_id": "ema_50", "condition": "between", "value": 1, "to": 2})


def test_round_trip_lossless() -> None:
    """UT-SCR-015.006.M24.T01: rules_from_config(rules_to_config(r)) == r."""
    rules = [
        Rule("rsi", Condition.BETWEEN, 30.0, 70.0, {"period": 10.0}),
        Rule("macd", Condition.CROSSES_ABOVE, None, None,
             {"fast": 12.0, "slow": 26.0, "signal": 9.0}, enabled=False),
        Rule("ema_50", Condition.PRICE_ABOVE),
    ]
    cfg = rules_to_config(rules, "QQQ")
    assert cfg["schema"] == 2 and cfg["benchmark_symbol"] == "QQQ"
    assert rules_from_config(cfg) == rules


def test_empty_rule_list_round_trip() -> None:
    """UT-SCR-015.006.M24.T02: empty rule list round trips."""
    cfg = rules_to_config([])
    assert cfg["rules"] == []
    assert rules_from_config(cfg) == []


def test_malformed_rule_list_refused() -> None:
    """UT-SCR-015.006.M24.T03: non-list rules raise."""
    with pytest.raises(IndicatorRuleError):
        rules_from_config({"schema": 2, "rules": "rsi"})


def test_legacy_dict_maps_to_six_rules() -> None:
    """UT-SCR-015.007.M24.T01: full legacy dict → 6 rules with mapped values."""
    rules = {r.indicator_id: r for r in rules_from_config(_LEGACY)}
    assert list(rules) == ["atr_pct", "rsi", "price", "breakout", "volume_ratio", "rs_index"]
    assert rules["atr_pct"].value == pytest.approx(1.0)
    assert (rules["rsi"].value, rules["rsi"].to, rules["rsi"].params["period"]) == (30, 70, 14)
    assert rules["rs_index"].enabled is False


def test_empty_config_uses_legacy_defaults() -> None:
    """UT-SCR-015.007.M24.T02: {} → 5 enabled rules + RS disabled."""
    rules = rules_from_config({})
    assert sum(r.enabled for r in rules) == 5
    assert [r.indicator_id for r in rules if not r.enabled] == ["rs_index"]


def test_disabled_legacy_section_stays_disabled() -> None:
    """UT-SCR-015.007.M24.T03: rsi.enabled=False → rsi rule disabled."""
    rules = rules_from_config({"filters": {"rsi": {"enabled": False}}})
    assert next(r for r in rules if r.indicator_id == "rsi").enabled is False


def test_summary_of_legacy_defaults() -> None:
    """UT-SCR-015.015.M24.T01: summary text of the legacy defaults."""
    assert config_summary({}) == (
        "ATR ≥ 1.0%  ·  RSI 30–70 (14)  ·  $5–$5K  ·  Breakout 10  ·  Vol ≥ 1.0×"
    )


def test_disabled_rules_left_out_of_summary() -> None:
    """UT-SCR-015.015.M24.T02: all disabled → empty summary."""
    rules = [dataclasses.replace(r, enabled=False) for r in rules_from_config({})]
    assert config_summary(rules_to_config(rules)) == ""


def test_settings_summary_labels() -> None:
    """UT-SCR-015.015.M24.T03: settings text names one-parameter values, joins several."""
    from us_swing.core.indicator_rules import default_rule, get_spec, settings_summary

    assert settings_summary(default_rule(get_spec("rsi"))) == "period 14"
    assert settings_summary(default_rule(get_spec("volume_ratio"))) == "MA 10"
    assert settings_summary(default_rule(get_spec("breakout"))) == "10 bars"
    assert settings_summary(default_rule(get_spec("rs_index"))) == "slope 63 d"
    assert settings_summary(default_rule(get_spec("macd"))) == "12 · 26 · 9"
    assert settings_summary(default_rule(get_spec("price"))) == ""
