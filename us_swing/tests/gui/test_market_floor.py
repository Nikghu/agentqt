"""Tests for the Market Floor frame (MD-GUI-034.001/.004/.008/.010)."""
from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from us_swing.core.desk_contract import DeskState, DeskStatus, ProductDescriptor
from us_swing.core.desk_floor import DeskFloorData
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


def test_edit_add_save_as_rebuild(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.008.M07.T05: an edited layout saved as Swing returns after a rebuild."""
    path = tmp_path / "layouts.json"
    page = MarketFloorWorkspace(DeskPoller(tmp_path), store=LayoutStore(path))
    qtbot.addWidget(page)
    assert not page.add_btn.isEnabled()
    page.edit_btn.setChecked(True)
    assert page.add_btn.isEnabled() and page.grid("Overview").is_edit()
    before = len(page.grid("Overview").model.panels)
    spec = page.add_product("flow.leaders", "Overview")
    assert spec is not None
    frame = page.grid("Overview").frames()[0]
    page.apply_panel_settings(frame, "card", {}, "B")
    page.save_layout_as("Swing")
    again = MarketFloorWorkspace(DeskPoller(tmp_path), store=LayoutStore(path))
    qtbot.addWidget(again)
    assert again.layout_name() == "Swing"
    panels = again.grid("Overview").model.panels
    assert len(panels) == before + 1
    assert panels[0].view == "card" and panels[0].link == "B"
    assert panels[-1].product == "flow.leaders"
    assert again.grid("Ideas").model.to_list() == page.grid("Ideas").model.to_list()


def test_switch_and_delete_layout(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.008.M07.T06: switching reloads tabs; Default cannot be deleted."""
    store = LayoutStore(tmp_path / "layouts.json")
    page = MarketFloorWorkspace(DeskPoller(tmp_path), store=store)
    qtbot.addWidget(page)
    assert not page.delete_btn.isEnabled()
    page.remove_panel("Overview", "p1")
    page.save_layout_as("Swing")
    page.switch_layout("Default")
    page._confirm = lambda *_a, **_k: True
    assert len(page.grid("Overview").model.panels) == 4
    assert store.last() == "Default"
    page.layout_combo.setCurrentText("Swing")
    assert len(page.grid("Overview").model.panels) == 3 and page.delete_btn.isEnabled()
    page.delete_layout()
    assert page.layout_name() == "Default" and "Swing" not in store.names()
    assert not store.delete("Default")


def test_debounced_save(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.008.M07.T07: a change is written to the store after the save delay."""
    path = tmp_path / "layouts.json"
    page = MarketFloorWorkspace(DeskPoller(tmp_path), store=LayoutStore(path))
    qtbot.addWidget(page)
    page.remove_panel("Overview", "p1")
    qtbot.waitUntil(lambda: path.exists(), timeout=3000)
    assert len(LayoutStore(path).load("Default")["Overview"]) == 3


def test_emptied_tab_stays_empty(tmp_path: Path) -> None:
    """UT-GUI-034.008.M07.T08: an emptied tab is not refilled; a missing tab gets defaults."""
    path = tmp_path / "layouts.json"
    store = LayoutStore(path)
    tabs = default_layout()
    tabs["Ideas"] = []
    store.save("Default", tabs)
    again = LayoutStore(path).load("Default")
    assert again["Ideas"] == []
    assert again["Overview"] == default_layout()["Overview"]
    del tabs["Sectors"]
    store.save("Default", tabs)
    assert LayoutStore(path).load("Default")["Sectors"] == default_layout()["Sectors"]


def test_save_as_existing_name_needs_confirmation(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.008.M07.T09: Save as onto an existing name asks first and can be refused."""
    store = LayoutStore(tmp_path / "layouts.json")
    page = MarketFloorWorkspace(DeskPoller(tmp_path), store=store)
    qtbot.addWidget(page)
    page.save_layout_as("Swing")
    page.remove_panel("Overview", "p1")
    asked: list[str] = []

    def refuse(*_a: object, **_k: object) -> bool:
        asked.append("x")
        return False

    page._confirm = refuse
    page.save_layout_as("Default")
    assert asked and page.layout_name() == "Swing"
    assert len(store.load("Default")["Overview"]) == 4
    page._confirm = lambda *_a, **_k: True
    page.save_layout_as("Default")
    assert page.layout_name() == "Default" and len(store.load("Default")["Overview"]) == 3
    page._confirm = lambda *_a, **_k: False
    page.save_layout_as("Swing")
    page.layout_combo.setCurrentText("Swing")
    page.delete_layout()
    assert "Swing" in store.names()


def test_edit_button_text(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.004.M04.T03: the Edit button reads Done while editing."""
    page = MarketFloorWorkspace(DeskPoller(tmp_path), store=LayoutStore(tmp_path / "l.json"))
    qtbot.addWidget(page)
    page.edit_btn.setChecked(True)
    assert page.edit_btn.text() == "Done"
    page.edit_btn.setChecked(False)
    assert page.edit_btn.text() == "Edit"


def _write_market(home: Path) -> None:
    from us_swing.market.store import BreadthRow, MarketStore, RegimeRow

    store = MarketStore(home)
    regimes = [
        RegimeRow(day, regime, "Calm", 10.0, 0.2, 500.0, 490.0, 480.0, 14.0, 16.0,
                  "Low fear", 20, "n", "2026-11-05T00:00:00")
        for day, regime in (("2026-11-03", "Downtrend"), ("2026-11-04", "Uptrend"))
    ]
    breadths = [
        BreadthRow(day, 500, 60.0, 55.0, 50.0, 10, 5, 300, 200)
        for day in ("2026-11-03", "2026-11-04")
    ]
    store.write_days(regimes, breadths)
    store.close()


def _tags(page: MarketFloorWorkspace, title: str) -> list[bool]:
    out = []
    for panel in page.panel_cards():
        texts = [lbl.text() for lbl in panel.findChildren(QLabel)]
        if title in texts:
            out.append(SAMPLE_TAG in texts)
    return out


def test_real_regime_and_breadth(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.011.M10.T01: real regime and breadth rows lose the Sample tag."""
    _write_market(tmp_path)
    data = DeskFloorData(SampleFloorData(), tmp_path)
    regime = next(p for p in data.products() if p.id == "regime.today")
    assert regime.sample is False
    row = data.rows("regime.today", {})[0]
    assert row["regime"] == "Uptrend" and row["data_date"] == "2026-11-04"
    page = MarketFloorWorkspace(DeskPoller(tmp_path), data, LayoutStore(tmp_path / "l.json"))
    qtbot.addWidget(page)
    titles = {p.id: p.title for p in data.products()}
    for pid in ("regime.today", "breadth.daily"):
        tags = _tags(page, titles[pid])
        assert tags and not any(tags)
    other = next(p for p in data.products() if p.sample)
    assert other.title in {t for p in page.panel_cards() for t in
                           (lbl.text() for lbl in p.findChildren(QLabel))}
    assert all(_tags(page, other.title))
    assert any(SAMPLE_TAG in [lbl.text() for lbl in c.findChildren(QLabel)]
               for c in page.panel_cards())


def test_no_desk_db_gives_sample(tmp_path: Path) -> None:
    """UT-GUI-034.011.M10.T02: with no desk.db the sample regime row is shown."""
    data = DeskFloorData(SampleFloorData(), tmp_path)
    regime = next(p for p in data.products() if p.id == "regime.today")
    assert regime.sample is True
    assert data.rows("regime.today", {}) == SampleFloorData().rows("regime.today", {})


class _CountingData(DeskFloorData):
    reads = 0

    def products(self) -> Sequence[ProductDescriptor]:
        type(self).reads += 1
        return super().products()


def test_reload_after_run_ends(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.011.M10.T03: panels reload once when a Running desk stops running."""
    _CountingData.reads = 0
    data = _CountingData(SampleFloorData(), tmp_path)
    poller = DeskPoller(tmp_path)
    page = MarketFloorWorkspace(poller, data, LayoutStore(tmp_path / "l.json"))
    qtbot.addWidget(page)
    base = _CountingData.reads
    poller.status_changed.emit(DeskStatus(DeskState.RUNNING))
    assert _CountingData.reads == base
    poller.status_changed.emit(DeskStatus(DeskState.SLEEPING))
    assert _CountingData.reads == base + 1
    poller.status_changed.emit(DeskStatus(DeskState.SLEEPING))
    assert _CountingData.reads == base + 1
    assert page.panel_cards()


def _write_sectors(home: Path) -> None:
    from us_swing.market.store import MarketStore, SectorRow, StockRsRow

    store = MarketStore(home)
    sectors, stocks = [], []
    for day, top in (("2026-11-04", "Energy"), ("2026-11-05", "Technology")):
        for rank, sector in enumerate((top, "Utilities"), start=1):
            sectors.append(SectorRow(day, sector, 100.0, 0.02 / rank, 0.03, 0.05, rank,
                                     101.0 - rank, 100.5, "Leading", 60))
        stocks += [StockRsRow(day, "NVDA", "Technology", 0.9, 99, 1, 2),
                   StockRsRow(day, "AAPL", "Technology", 0.5, 70, 2, 2),
                   StockRsRow(day, "NEE", "Utilities", 0.7, 85, 1, 1)]
    store.write_sector_days(sectors, stocks)
    store.close()


def test_real_sectors_and_leaders(tmp_path: Path) -> None:
    """UT-GUI-034.012.M11.T01: latest sector and RS rows, in order, filterable, not sample."""
    _write_sectors(tmp_path)
    data = DeskFloorData(SampleFloorData(), tmp_path)
    products = {p.id: p for p in data.products()}
    for pid in ("sectors.rank", "sectors.rrg", "rs.leaders"):
        assert products[pid].sample is False
        assert "2026-11-05" in products[pid].title
    assert products["rs.leaders"].filters == {"sector": ("Technology", "Utilities")}
    ranks = data.rows("sectors.rank", {})
    assert [(r["rank"], r["sector"]) for r in ranks] == [(1, "Technology"), (2, "Utilities")]
    assert ranks[0]["rel_1m"] == "+2.0%"
    assert data.rows("sectors.rrg", {})[0] == {
        "sector": "Technology", "rs_ratio": "100.0", "rs_momentum": "100.5",
        "quadrant": "Leading"}
    leaders = data.rows("rs.leaders", {})
    assert [r["symbol"] for r in leaders] == ["NVDA", "NEE", "AAPL"]
    assert leaders[0]["sector_rank"] == "1 of 2"
    tech = data.rows("rs.leaders", {"sector": "Technology"})
    assert [r["symbol"] for r in tech] == ["NVDA", "AAPL"]


def test_no_sector_data_gives_sample(tmp_path: Path) -> None:
    """UT-GUI-034.012.M11.T02: with regime only, sector products stay sample; no RS leaders."""
    _write_market(tmp_path)
    data = DeskFloorData(SampleFloorData(), tmp_path)
    products = {p.id: p for p in data.products()}
    assert products["sectors.rank"].sample is True
    assert products["sectors.rrg"].sample is True
    assert "rs.leaders" not in products
    assert data.rows("sectors.rank", {}) == SampleFloorData().rows("sectors.rank", {})


def _write_ideas(home: Path) -> None:
    from us_swing.market.store import IdeaRow, MarketStore, ReasonRow

    store = MarketStore(home)
    ideas, reasons = [], []
    for day in ("2026-11-04", "2026-11-05"):
        ideas += [
            IdeaRow(day, "long", "TRV", "list", 1, 71.6, "Financials", "Flat base", 409.31, 353.8),
            IdeaRow(day, "long", "CAH", "watch", 1, 70.4, "Health Care", "Flat base", 262.3, 224.5),
            IdeaRow(day, "short", "NVDA", "list", 1, 72.9, "Information Technology",
                    "Lower highs", 199.68, 219.99),
        ]
        reasons += [ReasonRow(day, "long", "TRV", 1, "RS rating 90"),
                    ReasonRow(day, "long", "CAH", 1, "Earnings in 1 day")]
    store.write_idea_days([], [], ideas, reasons)
    store.close()


def test_real_idea_list(tmp_path: Path) -> None:
    """UT-GUI-034.013.M12.T01: latest ideas; side filter; list by default; Watch on request."""
    _write_ideas(tmp_path)
    data = DeskFloorData(SampleFloorData(), tmp_path)
    product = next(p for p in data.products() if p.id == "ideas.top")
    assert product.sample is False
    assert product.title == "Top ideas (2026-11-05)"
    assert product.filters == {"side": ("long", "short"), "status": ("list", "watch")}
    rows = data.rows("ideas.top", {})
    assert [r["symbol"] for r in rows] == ["NVDA", "TRV"]
    assert rows[1] == {"symbol": "TRV", "side": "long", "score": "72", "setup": "Flat base",
                       "sector": "Financials", "trigger": "409.31", "stop": "353.80",
                       "why": "RS rating 90"}
    assert [r["symbol"] for r in data.rows("ideas.top", {"side": "long"})] == ["TRV"]
    watch = data.rows("ideas.top", {"status": "watch"})
    assert [(r["symbol"], r["why"]) for r in watch] == [("CAH", "Earnings in 1 day")]


def test_no_ideas_gives_sample(tmp_path: Path) -> None:
    """UT-GUI-034.013.M12.T02: with sector rows only, the idea list stays sample data."""
    _write_sectors(tmp_path)
    data = DeskFloorData(SampleFloorData(), tmp_path)
    product = next(p for p in data.products() if p.id == "ideas.top")
    assert product.sample is True
    assert data.rows("ideas.top", {}) == SampleFloorData().rows("ideas.top", {})
