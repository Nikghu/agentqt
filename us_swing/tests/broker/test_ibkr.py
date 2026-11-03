"""Tests for MD-INF-009.005.M01 — IBKR order building (SRD-INF-009.008)."""
from __future__ import annotations

from us_swing.broker.ibkr import build_ib_order


def test_market_order_uses_adaptive_algo() -> None:
    """UT-INF-009.005.M01.T01: MARKET request builds an Adaptive (Normal) MKT order."""
    order = build_ib_order("BUY", 10, "MARKET", None)

    assert order.orderType == "MKT"
    assert order.algoStrategy == "Adaptive"
    assert [(p.tag, p.value) for p in order.algoParams] == [("adaptivePriority", "Normal")]
    assert order.tif == "DAY"


def test_limit_order_has_no_algo() -> None:
    """UT-INF-009.005.M01.T02: LIMIT request builds a plain LMT order with no algo."""
    order = build_ib_order("SELL", 5, "LIMIT", 48.5)

    assert order.orderType == "LMT"
    assert order.lmtPrice == 48.5
    assert order.algoStrategy == ""
    assert order.algoParams == []
    assert order.tif == "DAY"
