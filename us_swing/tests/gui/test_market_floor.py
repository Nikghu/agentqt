"""Tests for the Market Floor frame (MD-GUI-034.001/.004/.008/.010)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from us_swing.gui import main_window
from us_swing.gui.desk_control import DeskPoller
from us_swing.gui.floor_layouts import LayoutStore, default_layout
from us_swing.gui.floor_sample import SAMPLE_TAG, SampleFloorData
from us_swing.gui.market_floor import MarketFloorWorkspace


def test_nav_items_order() -> None:
    """UT-GUI-034.001.M01.T01: Market Floor and AI Desk follow the first five pages."""
    labels = [label for _icon, label in main_window._NAV_ITEMS]
    assert labels == [
        "Dashboard", "Screener", "Execution", "Charts", "Backtest", "Market Floor", "AI Desk",
    ]
    assert {5, 6} <= main_window._WIDE_PAGES


def test_tabs_and_feed_fold_kept(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.004.M04.T01: five tabs in order; feed stays folded after a rebuild."""
    path = tmp_path / "layouts.json"
    first = MarketFloorWorkspace(DeskPoller(tmp_path), store=LayoutStore(path))
    qtbot.addWidget(first)
    assert first.tab_names() == [
        "Overview", "Ideas", "Sectors", "Regime & Breadth", "News & Calendar",
    ]
    assert first.tabs.tabText(3) == "Regime && Breadth"
    assert first.tabs.tabText(4) == "News && Calendar"
    assert not first.feed.is_folded()
    first.feed.set_folded(True)
    second = MarketFloorWorkspace(DeskPoller(tmp_path), store=LayoutStore(path))
    qtbot.addWidget(second)
    assert second.feed.is_folded()


def test_sample_tag_everywhere(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.010.M03.T01: sample products and every panel show Sample data."""
    data = SampleFloorData()
    assert data.products() and all(p.sample for p in data.products())
    page = MarketFloorWorkspace(DeskPoller(tmp_path), data, LayoutStore(tmp_path / "l.json"))
    qtbot.addWidget(page)
    panels = page.panel_cards()
    assert panels
    for panel in panels:
        texts = [lbl.text() for lbl in panel.findChildren(QLabel)]
        assert SAMPLE_TAG in texts


def test_layout_round_trip(tmp_path: Path) -> None:
    """UT-GUI-034.008.M07.T01: a saved layout and the last name survive a reopen."""
    path = tmp_path / "layouts.json"
    store = LayoutStore(path)
    tabs = default_layout()
    tabs["Overview"] = tabs["Overview"][:1]
    store.save("Swing", tabs)
    store.set_last("Swing")
    again = LayoutStore(path)
    assert again.last() == "Swing"
    assert "Swing" in again.names()
    assert again.load("Swing") == tabs


def test_broken_file_gives_default(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-GUI-034.008.M07.T02: bad JSON falls back to the default layout with a warning."""
    path = tmp_path / "layouts.json"
    path.write_text("{not json", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        store = LayoutStore(path)
    assert store.load(store.last()) == default_layout()
    assert any("[Floor]" in rec.message for rec in caplog.records)


def test_wrong_shape_file_gives_defaults(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """UT-GUI-034.008.M07.T03: valid JSON with a wrong shape never raises; defaults are used."""
    path = tmp_path / "layouts.json"
    bad_panel = {"id": "p1", "product": "ideas.top", "view": "table", "x": 0, "y": 0, "h": 2}
    path.write_text(
        json.dumps({"layouts": {"Default": None, "Odd": {"tabs": {
            "Overview": {"panels": [bad_panel, 5]}, "Ideas": []}}}}),
        encoding="utf-8",
    )
    with caplog.at_level(logging.WARNING):
        store = LayoutStore(path)
        assert store.load("Default") == default_layout()
        assert store.load("Odd") == default_layout()
    assert any("[Floor]" in rec.message for rec in caplog.records)


def test_broken_file_is_backed_up(tmp_path: Path) -> None:
    """UT-GUI-034.008.M07.T04: an unreadable file is renamed to .bak before a save."""
    path = tmp_path / "layouts.json"
    path.write_text("{not json", encoding="utf-8")
    store = LayoutStore(path)
    store.set_last("Default")
    assert (tmp_path / "layouts.json.bak").read_text(encoding="utf-8") == "{not json"


def test_bad_panel_shows_missing_card(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.004.M04.T02: a panel naming an unknown product shows a Missing product card."""
    path = tmp_path / "layouts.json"
    store = LayoutStore(path)
    tabs = default_layout()
    tabs["Overview"] = [{"id": "p1", "product": "nope", "view": "table", "filters": {},
                         "link": "", "x": 0, "y": 0, "w": 4, "h": 4}]
    store.save("Default", tabs)
    page = MarketFloorWorkspace(DeskPoller(tmp_path), store=LayoutStore(path))
    qtbot.addWidget(page)
    texts = [lbl.text() for p in page.panel_cards() for lbl in p.findChildren(QLabel)]
    assert "Missing product" in texts
