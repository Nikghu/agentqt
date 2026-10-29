"""Tests for MD-BKT-002.001.M01 — backtest/spec.py."""
from __future__ import annotations

import json

from us_swing.backtest.spec import AccountSpec, RunPlan, StrategySpec

_EXAMPLE = {
    "schema": 1,
    "name": "Momentum vs Pullback, Tech",
    "period": {"from": "2026-01-02", "to": "2026-10-28"},
    "universe": {"mode": "sector", "sectors": ["Information Technology"],
                 "add": ["PLTR"], "remove": ["INTC"]},
    "screener": {"preset_id": "abc-momentum", "top_n": 5, "ai_ranking": False},
    "strategies": [
        {"id": "st-orb", "allocation_pct": 60, "per_trade_pct": 50},
        {"id": "st-vwap", "allocation_pct": 40, "per_trade_pct": 100},
    ],
    "account": {"capital": [2000, 5000], "grow_with_pnl": False,
                "max_daily_loss_pct": 2.0, "when_full": "first_signal"},
    "costs": {"per_order": 1.0, "slippage_bps": 5},
}


def test_plan_json_round_trip() -> None:
    """UT-BKT-002.001.M01.T01: A plan saved and loaded again is equal."""
    plan = RunPlan.from_dict(_EXAMPLE)

    again = RunPlan.from_json(plan.to_json())

    assert again == plan
    data = json.loads(plan.to_json())
    assert data["account"]["capital"] == [2000.0, 5000.0]
    assert data["strategies"][0]["allocation_pct"] == 60.0


def test_unknown_keys_and_missing_parts() -> None:
    """UT-BKT-002.001.M01.T02: Extra keys are ignored and missing parts use defaults."""
    data = {k: v for k, v in _EXAMPLE.items() if k != "costs"}
    data["extra"] = {"x": 1}

    plan = RunPlan.from_dict(data)

    assert plan.costs.per_order == 1.0
    assert plan.costs.slippage_bps == 5.0


def test_good_plan_is_valid() -> None:
    """UT-BKT-002.002.M01.T01: The example plan has no errors."""
    assert RunPlan.from_dict(_EXAMPLE).validate() == []


def test_bad_values_listed() -> None:
    """UT-BKT-002.002.M01.T02: Each bad value gives one plain message."""
    data = json.loads(json.dumps(_EXAMPLE))
    data["schema"] = 2
    data["period"] = {"from": "2026-05-01", "to": "2026-01-01"}
    data["universe"]["sectors"] = []
    data["account"]["capital"] = 0

    errors = RunPlan.from_dict(data).validate()

    assert errors == [
        "Plan version 2 is not supported",
        "Start date is after the end date",
        "Pick at least one sector",
        "Capital must be more than zero",
    ]


def test_variant_grid() -> None:
    """UT-BKT-002.003.M01.T01: Capital × per-trade lists give 4 variants in order."""
    plan = RunPlan.from_dict(_EXAMPLE)
    plan = RunPlan(
        name=plan.name, period=plan.period, screener=plan.screener,
        strategies=(StrategySpec("st-orb", (60.0,), (50.0, 100.0)),),
        account=AccountSpec(capital=(2000.0, 5000.0)),
    )

    variants = plan.variants()

    assert [(v.capital, v.strategies[0][2]) for v in variants] == [
        (2000.0, 50.0), (2000.0, 100.0), (5000.0, 50.0), (5000.0, 100.0),
    ]


def test_over_64_variants() -> None:
    """UT-BKT-002.003.M01.T02: More than 64 variants is a validation error."""
    data = json.loads(json.dumps(_EXAMPLE))
    data["account"]["capital"] = list(range(1000, 1065))

    errors = RunPlan.from_dict(data).validate()

    assert errors == ["65 variants is more than the limit of 64"]
