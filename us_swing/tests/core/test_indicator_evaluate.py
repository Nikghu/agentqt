"""Unit tests: MD-SCR-015.009.M26 — core/indicator_rules/_evaluate.py
Refs: UT-SCR-015.009.M26.T01–T06
"""
from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pytest

from us_swing.core.indicator_rules import (
    Condition,
    Rule,
    RuleContext,
    Series,
    evaluate_rule,
)
from us_swing.core.indicator_rules import _catalogue

from .conftest import arrays_from_close, seeded_arrays

_CTX = RuleContext()


def _set_compute(monkeypatch: pytest.MonkeyPatch, indicator_id: str, fn: Any) -> None:
    patched = dataclasses.replace(_catalogue.get_spec(indicator_id), compute=fn)
    monkeypatch.setitem(_catalogue._BY_ID, indicator_id, patched)


def _const(value: float) -> Any:
    return lambda a, p: Series(np.full(len(a.close), value))


@pytest.mark.parametrize("rsi_value", [30.0, 70.0])
def test_between_is_inclusive(monkeypatch: pytest.MonkeyPatch, rsi_value: float) -> None:
    """UT-SCR-015.009.M26.T01: RSI exactly at 30 or 70 passes 30–70."""
    _set_compute(monkeypatch, "rsi", _const(rsi_value))
    rule = Rule("rsi", Condition.BETWEEN, 30.0, 70.0)
    assert evaluate_rule(rule, "X", seeded_arrays(30), _CTX) == (True, rsi_value)


def test_value_outside_band_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-SCR-015.009.M26.T02: RSI 75 fails 30–70."""
    _set_compute(monkeypatch, "rsi", _const(75.0))
    rule = Rule("rsi", Condition.BETWEEN, 30.0, 70.0)
    assert evaluate_rule(rule, "X", seeded_arrays(30), _CTX) == (False, 75.0)


def _cross_fn(value: list[float], ref: list[float]) -> Any:
    return lambda a, p: Series(np.asarray(value), np.asarray(ref))


def test_cross_above_on_last_bar(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-SCR-015.009.M26.T03: MACD below signal at −2, above at −1 → pass."""
    _set_compute(monkeypatch, "macd", _cross_fn([0.0, -1.0, 1.0], [0.0, 0.0, 0.0]))
    rule = Rule("macd", Condition.CROSSES_ABOVE)
    assert evaluate_rule(rule, "X", arrays_from_close([1, 2, 3]), _CTX)[0] is True


def test_older_cross_does_not_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-SCR-015.009.M26.T04: crossed at −3, above since → fail."""
    _set_compute(monkeypatch, "macd", _cross_fn([-1.0, 1.0, 2.0, 3.0], [0.0] * 4))
    rule = Rule("macd", Condition.CROSSES_ABOVE)
    assert evaluate_rule(rule, "X", arrays_from_close([1, 2, 3, 4]), _CTX)[0] is False


def test_too_few_bars_fails() -> None:
    """UT-SCR-015.009.M26.T05: 10 bars cannot give EMA(50)."""
    rule = Rule("ema_50", Condition.PRICE_ABOVE)
    assert evaluate_rule(rule, "X", seeded_arrays(10), _CTX) == (False, None)


def test_price_above_ema() -> None:
    """UT-SCR-015.009.M26.T06: steadily rising closes sit above EMA(20)."""
    rule = Rule("ema_20", Condition.PRICE_ABOVE)
    closes = [100.0 + i for i in range(60)]
    passed, value = evaluate_rule(rule, "X", arrays_from_close(closes), _CTX)
    assert passed is True and value is not None and value < closes[-1]
