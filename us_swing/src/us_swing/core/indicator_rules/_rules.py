"""
Module: MD-SCR-015.006.M24 — core/indicator_rules/_rules.py
Parent SRD: SRD-SCR-015.006

Rule model, config schema v2, the legacy ``filters`` reader and summary text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from us_swing.core.indicator_rules._catalogue import (
    Condition,
    IndicatorRuleError,
    IndicatorSpec,
    ParamSpec,
    get_spec,
)

SCHEMA_VERSION = 2
_SEP = "  ·  "


@dataclass(frozen=True, slots=True)
class Rule:
    """One screening rule; params missing here fall back to catalogue defaults."""

    indicator_id: str
    condition: Condition
    value: float | None = None
    to: float | None = None
    params: Mapping[str, float] = field(default_factory=dict)
    enabled: bool = True


def default_rule(spec: IndicatorSpec) -> Rule:
    """Return a new rule for ``spec`` using its first condition and default values."""
    cond = spec.conditions[0]
    return Rule(
        indicator_id=spec.id,
        condition=cond,
        value=spec.default_value if cond.needs_value else None,
        to=_default_to(spec) if cond.needs_to else None,
        params={p.key: p.default for p in spec.params},
    )


def _default_to(spec: IndicatorSpec) -> float:
    return spec.default_to if spec.default_to is not None else spec.value_max


# ── Config read / write ───────────────────────────────────────────────────────

def rules_to_config(rules: list[Rule], benchmark_symbol: str = "SPY") -> dict[str, Any]:
    """Serialise rules to the schema-2 config dict."""
    return {
        "schema": SCHEMA_VERSION,
        "rules": [_rule_to_dict(r) for r in rules],
        "benchmark_symbol": benchmark_symbol,
    }


def rules_from_config(config: Mapping[str, Any]) -> list[Rule]:
    """Read rules from a schema-2 config, or map a legacy ``filters`` config.

    Raises:
        IndicatorRuleError: For malformed rules, unknown or unavailable indicators.
    """
    if "rules" not in config:
        return _rules_from_legacy(config.get("filters", {}) or {})
    raw = config["rules"]
    if not isinstance(raw, list):
        raise IndicatorRuleError("Indicator rules must be a list")
    return [_rule_from_dict(item) for item in raw]


def _rule_to_dict(rule: Rule) -> dict[str, Any]:
    return {
        "indicator_id": rule.indicator_id,
        "condition": rule.condition.value,
        "value": rule.value,
        "to": rule.to,
        "params": dict(rule.params),
        "enabled": rule.enabled,
    }


def _rule_from_dict(item: Any) -> Rule:
    if not isinstance(item, Mapping):
        raise IndicatorRuleError("Each indicator rule must be an object")
    spec = get_spec(str(item.get("indicator_id", "")))
    if not spec.available:
        raise IndicatorRuleError(f"{spec.name} is not available: {spec.unavailable_reason}")
    try:
        cond = Condition(item.get("condition"))
    except ValueError:
        raise IndicatorRuleError(f"Unknown condition: {item.get('condition')}") from None
    if cond not in spec.conditions:
        raise IndicatorRuleError(f"{spec.name} does not support '{cond.label}'")
    try:
        params = {p.key: float(p.default) for p in spec.params}
        params.update(
            {k: float(v) for k, v in (item.get("params") or {}).items() if k in params}
        )
        return Rule(
            indicator_id=spec.id,
            condition=cond,
            value=_opt_float(item.get("value")),
            to=_opt_float(item.get("to")),
            params=params,
            enabled=bool(item.get("enabled", True)),
        )
    except (TypeError, ValueError, AttributeError):
        raise IndicatorRuleError(f"{spec.name} rule has an invalid number") from None


def _opt_float(v: Any) -> float | None:
    return None if v is None else float(v)


# ── Legacy ``filters`` mapping (SRD-SCR-015.007) ─────────────────────────────

_LEGACY_DEFAULTS: dict[str, dict[str, Any]] = {
    "volatility": {"enabled": True, "min_atr_pct": 0.01},
    "rsi": {"enabled": True, "min": 30, "max": 70, "period": 14},
    "range": {"enabled": True, "min_price": 5.0, "max_price": 5000.0},
    "breakout": {"enabled": True, "lookback": 10},
    "volume": {"enabled": True, "min_volume_ratio": 1.0, "ma_period": 10},
    "rs_index": {"enabled": False, "rs_min_percentile": 70.0, "rs_slope_days": 63},
}


def _rules_from_legacy(filters: Mapping[str, Any]) -> list[Rule]:
    def section(name: str) -> dict[str, Any]:
        merged = dict(_LEGACY_DEFAULTS[name])
        merged.update(filters.get(name, {}) or {})
        return merged

    v, r, p = section("volatility"), section("rsi"), section("range")
    b, vo, rs = section("breakout"), section("volume"), section("rs_index")
    return [
        Rule("atr_pct", Condition.AT_LEAST, float(v["min_atr_pct"]) * 100.0,
             params={"period": 14.0}, enabled=bool(v["enabled"])),
        Rule("rsi", Condition.BETWEEN, float(r["min"]), float(r["max"]),
             params={"period": float(r["period"])}, enabled=bool(r["enabled"])),
        Rule("price", Condition.BETWEEN, float(p["min_price"]), float(p["max_price"]),
             enabled=bool(p["enabled"])),
        Rule("breakout", Condition.IS_TRUE,
             params={"lookback": float(b["lookback"])}, enabled=bool(b["enabled"])),
        Rule("volume_ratio", Condition.AT_LEAST, float(vo["min_volume_ratio"]),
             params={"period": float(vo["ma_period"])}, enabled=bool(vo["enabled"])),
        Rule("rs_index", Condition.AT_LEAST, float(rs["rs_min_percentile"]),
             params={"slope_days": float(rs["rs_slope_days"])}, enabled=bool(rs["enabled"])),
    ]


# ── Summary text (SRD-SCR-015.015) ────────────────────────────────────────────

def rule_label(rule: Rule) -> str:
    """Short name of the rule's indicator, e.g. ``RSI`` or ``EMA(50)``."""
    return get_spec(rule.indicator_id).short


def params_summary(rule: Rule) -> str:
    """Parameter values in catalogue order, e.g. ``12 · 26 · 9``."""
    spec = get_spec(rule.indicator_id)
    return " · ".join(_num(rule.params.get(p.key, p.default)) for p in spec.params)


def settings_summary(rule: Rule) -> str:
    """Settings-column text: ``period 14`` for one parameter, ``12 · 26 · 9`` for several."""
    return format_param_values(get_spec(rule.indicator_id).params, rule.params)


def format_param_values(params: Sequence[ParamSpec], values: Mapping[str, float]) -> str:
    """Labelled text for one parameter (``period 14``), values joined for several, else ``""``."""
    if len(params) == 1:
        p = params[0]
        return p.display.format(_num(values.get(p.key, p.default)))
    return " · ".join(_num(values.get(p.key, p.default)) for p in params)


def rule_summary(rule: Rule) -> str:
    """One short label for a rule, e.g. ``RSI 30–70 (14)`` or ``Price > EMA(50)``."""
    spec = get_spec(rule.indicator_id)
    subject, unit, cond = spec.short, spec.unit, rule.condition
    if spec.id == "price" and cond is Condition.BETWEEN:
        text = _fmt_range(unit, rule.value, rule.to)
    elif cond is Condition.BETWEEN:
        text = f"{subject} {_fmt_range(unit, rule.value, rule.to)}"
    elif cond is Condition.AT_LEAST:
        text = f"{subject} ≥ {_fmt(unit, rule.value)}"
    elif cond is Condition.AT_MOST:
        text = f"{subject} ≤ {_fmt(unit, rule.value)}"
    elif cond is Condition.CROSSES_ABOVE:
        text = f"{subject} ↑ signal"
    elif cond is Condition.CROSSES_BELOW:
        text = f"{subject} ↓ signal"
    elif cond is Condition.PRICE_ABOVE:
        text = f"Price > {subject}"
    elif cond is Condition.PRICE_BELOW:
        text = f"Price < {subject}"
    else:
        text = f"{subject} {params_summary(rule)}".strip()
    if spec.id == "rs_index" and rule.params.get("slope_days", 0) > 0:
        text += f" sl{int(rule.params['slope_days'])}"
    if spec.summary_params and spec.params:
        text += f" ({params_summary(rule)})"
    return text


def config_summary(config: Mapping[str, Any]) -> str:
    """Details-column text for an indicator config; ``""`` if it cannot be read."""
    try:
        rules = rules_from_config(config)
    except IndicatorRuleError:
        return ""
    return _SEP.join(rule_summary(r) for r in rules if r.enabled)


def _num(v: float | None) -> str:
    if v is None:
        return "—"
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _fmt(unit: str, v: float | None) -> str:
    if v is None:
        return "—"
    if unit == "$":
        return _money(v)
    if unit == "$B":
        return f"${_num(v)}B"
    if unit in ("%", "×"):
        return f"{v:.1f}{unit}"
    return _num(v)


def _fmt_range(unit: str, lo: float | None, hi: float | None) -> str:
    if unit == "$":
        return f"{_money(lo)}–{_money(hi)}"
    if unit == "$B":
        return f"${_num(lo)}–{_num(hi)}B"
    if unit in ("%", "×"):
        return f"{_num(lo)}–{_num(hi)}{unit}"
    return f"{_num(lo)}–{_num(hi)}"


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"${v:.0f}" if v < 1000 else f"${v / 1000:.0f}K"
