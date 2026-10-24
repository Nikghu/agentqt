"""Tests for chart drawings (FO-GUI-026, MD-GUI-026.012.M04)."""
from __future__ import annotations

import json
import logging

import pytest
import sqlalchemy as sa

from us_swing.gui.chart_drawings import ChartBridge, Drawing, DrawingStore, drawing_from_json

_TREND = Drawing("trend", ((1_700_000_000.0, 120.5), (1_700_864_000.0, 131.25)), "#f0a63a")
_HLINE = Drawing("hline", ((1_700_000_000.0, 125.0),), "#f0a63a")


@pytest.fixture()
def store() -> DrawingStore:
    return DrawingStore(sa.create_engine("sqlite://"))


def test_save_and_load(store):
    """UT-GUI-026.012.M04.T01: Save and load drawings."""
    saved = [store.save(1, "NVDA", "1d", d) for d in (_TREND, _HLINE)]
    assert all(d.id is not None for d in saved)
    loaded = store.load(1, "NVDA", "1d")
    assert loaded == saved
    assert loaded[0].points == _TREND.points and loaded[0].to_js()["points"][1] == {
        "time": 1_700_864_000.0, "price": 131.25}


def test_other_chart_sees_none(store):
    """UT-GUI-026.012.M04.T02: Other symbol, timeframe or user sees none."""
    store.save(1, "NVDA", "1d", _TREND)
    assert store.load(1, "NVDA", "1w") == []
    assert store.load(1, "AMD", "1d") == []
    assert store.load(2, "NVDA", "1d") == []


def test_delete_all_clears_one_chart(store):
    """UT-GUI-026.012.M04.T03: Delete all clears one chart only."""
    store.save(1, "NVDA", "1d", _TREND)
    store.save(1, "NVDA", "1d", _HLINE)
    kept = store.save(1, "NVDA", "1w", _TREND)
    assert store.delete_all(1, "NVDA", "1d") == 2
    assert store.load(1, "NVDA", "1d") == []
    assert store.load(1, "NVDA", "1w") == [kept]


def test_bridge_ignores_bad_json(qtbot, caplog):
    """UT-GUI-026.012.M04.T04: Bridge ignores bad JSON."""
    bridge = ChartBridge()
    with caplog.at_level(logging.WARNING), qtbot.assertNotEmitted(bridge.drawing_added):
        bridge.add_drawing("not json")
        bridge.add_drawing(json.dumps({"kind": "trend", "points": [{"time": 1, "price": 2}]}))
        bridge.add_drawing(json.dumps({"kind": "circle", "points": []}))
    assert caplog.text.count("[Charts] A drawing from the chart could not be read") == 3


def test_bridge_emits_valid_drawing(qtbot):
    """UT-GUI-026.011.M04.T05: Bridge turns page JSON into a drawing."""
    bridge = ChartBridge()
    payload = json.dumps({"kind": "rect", "points": [{"time": 10, "price": 1.5},
                                                     {"time": 20, "price": 2.5}]})
    with qtbot.waitSignal(bridge.drawing_added) as blocker:
        bridge.add_drawing(payload)
    assert blocker.args[0] == Drawing("rect", ((10.0, 1.5), (20.0, 2.5)))
    assert drawing_from_json(json.dumps({"kind": "hline", "points": [
        {"time": 1, "price": float("nan")}]})) is None
