"""
Module: MD-SCR-015.009.M26 — core/indicator_rules/_evaluate.py
Parent SRD: SRD-SCR-015.009

Evaluates one rule against one symbol's bar arrays.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from us_swing.core.indicator_rules._catalogue import Condition, get_spec
from us_swing.core.indicator_rules._rules import Rule
from us_swing.core.indicator_rules._ta import BarArrays, FloatArray


@dataclass(frozen=True, slots=True)
class RuleContext:
    """Cross-symbol data some rules need: RS ranks, market caps and benchmark bars."""

    rs_ranks: Mapping[str, float] = field(default_factory=dict)
    market_caps: Mapping[str, float] = field(default_factory=dict)
    benchmark: BarArrays | None = None


def evaluate_rule(
    rule: Rule, symbol: str, arrays: BarArrays, ctx: RuleContext
) -> tuple[bool, float | None]:
    """Return ``(passed, last_value)``; missing data or too few bars fail the rule."""
    spec = get_spec(rule.indicator_id)
    params = {
        p.key: min(max(float(rule.params.get(p.key, p.default)), p.min), p.max)
        for p in spec.params
    }

    if spec.context == "rs":
        rank = ctx.rs_ranks.get(symbol)
        if rank is None:
            return False, None
        slope_days = int(params.get("slope_days", 0))
        slope_ok = slope_days <= 0 or (
            ctx.benchmark is not None
            and rs_slope_up(arrays.close, ctx.benchmark.close, slope_days)
        )
        return _compare(rule, rank, arrays) and slope_ok, rank

    if spec.context == "market_cap":
        cap = ctx.market_caps.get(symbol)
        if cap is None:
            return False, None
        billions = cap / 1e9
        return _compare(rule, billions, arrays), billions

    if spec.compute is None or len(arrays.close) == 0:
        return False, None
    series = spec.compute(arrays, params)
    last = _last(series.value)
    if last is None:
        return False, None
    if rule.condition in (Condition.CROSSES_ABOVE, Condition.CROSSES_BELOW):
        if series.reference is None:
            return False, last
        return _crossed(rule.condition, series.value, series.reference), last
    return _compare(rule, last, arrays), last


def rs_slope_up(close: FloatArray, bench_close: FloatArray, slope_days: int) -> bool:
    """True if the stock/benchmark ratio rose over ``slope_days`` bars.

    Too little history counts as rising, as in the original RS filter.
    """
    n = min(len(close), len(bench_close))
    if n < slope_days + 1:
        return True
    b_now, b_prev = bench_close[-1], bench_close[-slope_days - 1]
    if b_now == 0 or b_prev == 0:
        return True
    return bool(close[-1] / b_now > close[-slope_days - 1] / b_prev)


def _compare(rule: Rule, v: float, arrays: BarArrays) -> bool:
    cond = rule.condition
    if cond is Condition.AT_LEAST:
        return rule.value is not None and v >= rule.value
    if cond is Condition.AT_MOST:
        return rule.value is not None and v <= rule.value
    if cond is Condition.BETWEEN:
        return rule.value is not None and rule.to is not None and rule.value <= v <= rule.to
    if cond is Condition.PRICE_ABOVE:
        return bool(arrays.close[-1] > v)
    if cond is Condition.PRICE_BELOW:
        return bool(arrays.close[-1] < v)
    if cond is Condition.IS_TRUE:
        return v == 1.0
    return False


def _crossed(cond: Condition, value: FloatArray, ref: FloatArray) -> bool:
    if len(value) < 2 or len(ref) < 2:
        return False
    v0, v1, r0, r1 = value[-2], value[-1], ref[-2], ref[-1]
    if np.isnan([v0, v1, r0, r1]).any():
        return False
    if cond is Condition.CROSSES_ABOVE:
        return bool(v0 <= r0 and v1 > r1)
    return bool(v0 >= r0 and v1 < r1)


def _last(series: FloatArray) -> float | None:
    if len(series) == 0:
        return None
    v = float(series[-1])
    return None if math.isnan(v) else v
