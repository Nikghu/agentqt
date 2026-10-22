"""
Module: MD-SCR-015.001.M23 — core/indicator_rules/__init__.py
Parent SRD: SRD-SCR-015.001

Public surface of the shared indicator catalogue and rule engine. The screener
and the GUI both import from here and never from each other.
"""
from __future__ import annotations

from us_swing.core.indicator_rules._catalogue import (
    CATALOGUE,
    Category,
    Condition,
    IndicatorRuleError,
    IndicatorSpec,
    ParamSpec,
    get_spec,
)
from us_swing.core.indicator_rules._evaluate import RuleContext, evaluate_rule, rs_slope_up
from us_swing.core.indicator_rules._rules import (
    Rule,
    config_summary,
    default_rule,
    format_param_values,
    params_summary,
    rule_label,
    rule_summary,
    rules_from_config,
    rules_to_config,
    settings_summary,
)
from us_swing.core.indicator_rules._ta import BarArrays, Series

__all__ = [
    "CATALOGUE",
    "BarArrays",
    "Category",
    "Condition",
    "IndicatorRuleError",
    "IndicatorSpec",
    "ParamSpec",
    "Rule",
    "RuleContext",
    "Series",
    "config_summary",
    "default_rule",
    "evaluate_rule",
    "format_param_values",
    "get_spec",
    "params_summary",
    "rs_slope_up",
    "rule_label",
    "rule_summary",
    "rules_from_config",
    "rules_to_config",
    "settings_summary",
]
