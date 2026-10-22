"""Unit tests: MD-SCR-015.001.M23 — core/indicator_rules/_catalogue.py
Refs: UT-SCR-015.001–.003, .013–.014 (M23)
"""
from __future__ import annotations

import pytest

from us_swing.core.indicator_rules import (
    CATALOGUE,
    Category,
    IndicatorRuleError,
    ParamSpec,
    get_spec,
    rules_from_config,
)

_RELEASE_1 = [
    "price", "atr_pct", "rsi", "breakout", "volume_ratio", "rvol_1d", "rs_index",
    "ema_20", "ema_50", "ema_100", "ema_200", "price_ema_20", "price_ema_50",
    "price_ema_100", "macd", "macd_hist", "macd_signal", "ppo", "ppo_hist",
    "ppo_signal", "market_cap",
]
_INTRADAY = ["rvol_3m", "rvol_5m", "rvol_10m", "stvol_3m", "stvol_5m", "stvol_10m"]


def test_ids_unique_and_available_entries_computable() -> None:
    """UT-SCR-015.001.M23.T01: ids unique; available entries have compute or context."""
    ids = [s.id for s in CATALOGUE]
    assert len(ids) == len(set(ids))
    for spec in CATALOGUE:
        if spec.available:
            assert spec.compute is not None or spec.context != "none", spec.id


def test_unknown_id_rejected() -> None:
    """UT-SCR-015.001.M23.T02: unknown id raises IndicatorRuleError."""
    with pytest.raises(IndicatorRuleError):
        get_spec("nope")


def test_param_defaults_inside_ranges() -> None:
    """UT-SCR-015.002.M23.T01: every ParamSpec default lies within min–max."""
    for spec in CATALOGUE:
        for p in spec.params:
            assert p.min <= p.default <= p.max, f"{spec.id}.{p.key}"


def test_param_default_outside_range_refused() -> None:
    """UT-SCR-015.002.M23.T02: out-of-range default raises ValueError."""
    with pytest.raises(ValueError):
        ParamSpec("period", "Period", "int", 0, 1, 5)


def test_category_order_matches_fo() -> None:
    """UT-SCR-015.003.M23.T01: Category order is Price … Others."""
    assert [c.value for c in Category] == [
        "Price", "Momentum", "Trend", "Volatility", "Volume",
        "Relative strength", "Fundamentals", "Dividends", "Others",
    ]


def test_unknown_category_refused() -> None:
    """UT-SCR-015.003.M23.T02: unknown category raises ValueError."""
    with pytest.raises(ValueError):
        Category("Crypto")


def test_release_1_indicators_available() -> None:
    """UT-SCR-015.013.M23.T01: all 21 release-1 indicators exist and are available."""
    assert len(_RELEASE_1) == 21
    for indicator_id in _RELEASE_1:
        assert get_spec(indicator_id).available, indicator_id


def test_no_dividends_or_others_entries() -> None:
    """UT-SCR-015.013.M23.T02: release 1 has no Dividends or Others entries."""
    assert not [s for s in CATALOGUE if s.category in (Category.DIVIDENDS, Category.OTHERS)]


def test_intraday_entries_unavailable() -> None:
    """UT-SCR-015.014.M23.T01: intraday entries are unavailable with a reason."""
    for indicator_id in _INTRADAY:
        spec = get_spec(indicator_id)
        assert spec.available is False
        assert spec.unavailable_reason == "needs intraday data"


def test_rule_on_unavailable_indicator_refused() -> None:
    """UT-SCR-015.014.M23.T02: a rule on rvol_5m is refused on load."""
    cfg = {"schema": 2, "rules": [{"indicator_id": "rvol_5m", "condition": "at_least",
                                   "value": 2.0}]}
    with pytest.raises(IndicatorRuleError):
        rules_from_config(cfg)
