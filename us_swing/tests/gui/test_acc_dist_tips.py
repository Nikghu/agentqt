"""Tests for the Acc / Dist settings tips (MD-SCR-017.017.M34).

Refs: UT-SCR-017.017.M34.T01–T03 (FO-SCR-015)
"""
from __future__ import annotations

import pytest

from us_swing.gui.acc_dist_tips import LABELS, TABS, summary, tab_intro, tip
from us_swing.screener.screeners.acc_dist import SETTINGS, read_config


@pytest.mark.parametrize("mode", ["accumulation", "distribution"])
def test_every_setting_has_a_tip_on_a_tab(mode: str) -> None:
    """UT-SCR-017.017.M34.T01: Every setting sits on one tab and has a tip in both modes."""
    cfg = read_config({"mode": mode})
    on_tabs = [k for spec in TABS for row in spec.rows for k in row if k]
    assert sorted(on_tabs) == sorted([*SETTINGS, "mode", "move_rule"])
    assert set(LABELS) == set(on_tabs)
    for key in on_tabs:
        info = tip(key, cfg)
        assert info.title and info.text and info.example
    assert all(tab_intro(i, cfg) for i in range(len(TABS)))


def test_tips_follow_mode_and_values() -> None:
    """UT-SCR-017.017.M34.T02: Tips change with the mode and use the current values."""
    dist = read_config({"mode": "distribution", "zone_pct": 25.0})
    acc = read_config({"mode": "accumulation", "zone_pct": 25.0})
    assert "$95.00" in tip("zone_pct", dist).example
    assert "$85.00" in tip("zone_pct", acc).example
    assert tip("min_ud_ratio", dist).title == "Not used now"
    assert tip("max_ud_ratio", acc).title == "Not used now"
    assert tip("high_factor", acc).title != tip("high_factor", dist).title


def test_summary_reflects_switches() -> None:
    """UT-SCR-017.017.M34.T03: The plain-words summary drops switched-off zones."""
    on = summary(read_config({"mode": "distribution"}))
    off = summary(read_config({"mode": "distribution", "location_filter": False,
                               "close_position": False}))
    assert "distribution" in on and "range" in on and "close in the" in on
    assert "range" not in off and "of the day" not in off
