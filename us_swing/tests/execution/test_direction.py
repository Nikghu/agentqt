"""
Module: MD-EXE-018.003.M04 — execution/direction.py tests
Parent SRD: SRD-EXE-018.003, SRD-EXE-018.004
"""
from __future__ import annotations

import pytest

from us_swing.broker.broker import OrderSide
from us_swing.execution.direction import order_side, risk_levels


def test_long_side_mapping() -> None:
    """UT-EXE-018.003.M04.T01: LONG enters with BUY and exits with SELL."""
    assert order_side("LONG", True) is OrderSide.BUY
    assert order_side("LONG", False) is OrderSide.SELL


def test_short_side_mapping() -> None:
    """UT-EXE-018.003.M04.T02: SHORT enters with SELL and exits with BUY."""
    assert order_side("SHORT", True) is OrderSide.SELL
    assert order_side("SHORT", False) is OrderSide.BUY


def test_long_risk_levels() -> None:
    """UT-EXE-018.004.M04.T03: LONG stop sits below and target above the price."""
    stop, target = risk_levels("LONG", 100.0, True, 2.0, True, 4.0)
    assert stop == pytest.approx(98.0)
    assert target == pytest.approx(104.0)


def test_short_risk_levels_flip() -> None:
    """UT-EXE-018.004.M04.T04: SHORT stop sits above and target below the price."""
    stop, target = risk_levels("SHORT", 100.0, True, 2.0, True, 4.0)
    assert stop == pytest.approx(102.0)
    assert target == pytest.approx(96.0)


def test_disabled_levels_return_none() -> None:
    """UT-EXE-018.004.M04.T05: disabled stop and target return None."""
    assert risk_levels("SHORT", 100.0, False, 2.0, False, 4.0) == (None, None)
