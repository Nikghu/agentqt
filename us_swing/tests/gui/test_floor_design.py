"""Tests for the Market Floor design match: header, painted views, tiles data and layouts."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QTableWidget
from pytestqt.qtbot import QtBot

from us_swing.core.desk_contract import ProductDescriptor
from us_swing.core.desk_floor import DeskFloorData
from us_swing.gui.desk_control import DeskBar, DeskPoller
from us_swing.gui.floor_charts import (
    HeatMapView,
    LineView,
    RotationView,
    ScoreDelegate,
    SideDelegate,
    TilesView,
    heat_colour,
)
from us_swing.gui.floor_grid_model import PanelSpec
from us_swing.gui.floor_layouts import DEFAULT_NAME, VERSION, LayoutStore, default_layout
from us_swing.gui.floor_panel import PanelFrame, table_body
from us_swing.gui.floor_sample import SampleFloorData
from us_swing.gui.market_floor import MarketFloorWorkspace
from us_swing.gui.theme import C

_DAYS = ("2026-11-02", "2026-11-03", "2026-11-04")


def _write_desk(home: Path) -> None:
    from us_swing.market.store import (
        BreadthRow,
        IdeaRow,
        MarketStore,
        RegimeRow,
        SectorRow,
    )

    store = MarketStore(home)
    regimes = [
        RegimeRow(day, regime, "Normal", 10.0, 0.2, 500.0, 490.0, 480.0, 16.6, 18.8, "Calm", 20,
                  "n", "2026-11-05T00:00:00")
        for day, regime in zip(_DAYS, ("Choppy", "Uptrend", "Uptrend"), strict=True)
    ]
    breadths = [BreadthRow(day, 500, 60.0, 50.0 + i, 50.0, 38, 7, 300, 200)
                for i, day in enumerate(_DAYS)]
    store.write_days(regimes, breadths)
    sectors = [SectorRow(_DAYS[-1], name, 100.0, rel, 0.0, 0.0, rank, 101.0, 100.5, "Leading", 50)
               for rank, (name, rel) in enumerate((("Technology", 0.043),
                                                   ("Energy", -0.02)), start=1)]
    store.write_sector_days(sectors, [])
    ideas = [IdeaRow(_DAYS[-1], side, sym, "list", 1, 80.0, "Technology", "Flag", 10.0, 9.0)
             for side, sym in (("long", "NVDA"), ("long", "AAPL"), ("short", "XOM"))]
    store.write_idea_days([_DAYS[-1]], [], ideas, [])
    store.close()


def _page(qtbot: QtBot, tmp_path: Path, data: object | None = None) -> MarketFloorWorkspace:
    page = MarketFloorWorkspace(DeskPoller(tmp_path), data,  # type: ignore[arg-type]
                                LayoutStore(tmp_path / "l.json"))
    qtbot.addWidget(page)
    return page


def test_chips_from_desk(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.045.M28.T01: regime, fear, VIX and above 50-day chips come from desk.db."""
    _write_desk(tmp_path)
    page = _page(qtbot, tmp_path, DeskFloorData(SampleFloorData(), tmp_path))
    chips = page.chip_texts()
    assert chips[:4] == ["Uptrend trend", "Fear: Calm", "VIX 16.6 · contango",
                         "Above 50-day 52%"]


def test_no_chips_on_sample(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.045.M28.T02: sample data gives no chips."""
    page = _page(qtbot, tmp_path, SampleFloorData())
    assert page.chip_texts() == []


def test_edit_only_buttons(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.046.M28.T01: edit tools show only in edit mode; no desk bar on the Floor."""
    page = _page(qtbot, tmp_path)
    buttons = (page.add_btn, page.reset_btn, page.save_as_btn, page.delete_btn)
    assert all(b.isHidden() for b in buttons)
    assert not page.edit_btn.isHidden() and not page.fold_btn.isHidden()
    page.edit_btn.setChecked(True)
    assert not any(b.isHidden() for b in buttons)
    page.edit_btn.setChecked(False)
    assert all(b.isHidden() for b in buttons)
    assert page.findChildren(DeskBar) == []


def test_fold_and_reset_tab(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.046.M28.T02: Fold feed folds the feed; Reset tab brings back default panels."""
    page = _page(qtbot, tmp_path)
    page.fold_btn.click()
    assert page.feed.is_folded() and page.fold_btn.text() == "Show feed"
    page.fold_btn.click()
    assert not page.feed.is_folded() and page.fold_btn.text() == "Fold feed"
    page.remove_panel("Overview", "p1")
    assert len(page.grid("Overview").model.panels) == 4
    page._confirm = lambda *_a, **_k: False
    page.reset_tab()
    assert len(page.grid("Overview").model.panels) == 4
    page._confirm = lambda *_a, **_k: True
    page.reset_tab()
    assert [p.product for p in page.grid("Overview").model.panels] == [
        d["product"] for d in default_layout()["Overview"]
    ]


def test_real_tiles_and_history(tmp_path: Path) -> None:
    """UT-GUI-034.047.M29.T01: five tiles with the regime day count; history oldest first."""
    _write_desk(tmp_path)
    data = DeskFloorData(SampleFloorData(), tmp_path)
    tiles = data.rows("market.tiles", {})
    assert [t["title"] for t in tiles] == [
        "Regime", "Above 50-day", "New highs · lows", "Ideas", "Leading sector"]
    assert tiles[0]["value"] == "Uptrend" and tiles[0]["note"] == "trend · day 2"
    assert tiles[2]["value"] == "38 · 7"
    assert tiles[3]["value"] == "2 L · 1 S"
    assert tiles[4]["value"] == "Technology" and tiles[4]["note"].startswith("+4.3%")
    history = data.rows("breadth.history", {})
    assert [h["date"] for h in history] == list(_DAYS)
    assert next(p for p in data.products() if p.id == "market.tiles").sample is False


def test_tiles_view(qtbot: QtBot) -> None:
    """UT-GUI-034.047.M27.T01: the tiles view shows one tile per row with its value."""
    rows = SampleFloorData().rows("market.tiles", {})
    view = TilesView(rows)
    qtbot.addWidget(view)
    values = [lbl.text() for lbl in view.findChildren(QLabel, "tile_value")]
    assert len(values) == 5 and values[0] == "Uptrend"


def test_heat_colour() -> None:
    """UT-GUI-034.048.M27.T01: above SPY leans green, below leans red, zero is the surface."""
    up, down, flat = heat_colour(4.0), heat_colour(-4.0), heat_colour(0.0)
    surface = QColor(C.SURFACE)
    assert up.green() > surface.green() and up.green() > up.red()
    assert down.red() > surface.red() and down.red() > down.green()
    assert flat == surface


def test_views_paint_and_empty(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.049.M27.T01: painted views draw with rows; an empty product shows a note."""
    data = SampleFloorData()
    for view in (LineView(data.rows("breadth.history", {})),
                 RotationView(data.rows("sectors.rrg", {})),
                 HeatMapView(data.rows("sectors.rank", {}))):
        qtbot.addWidget(view)
        view.resize(400, 240)
        assert not view.grab().isNull()
    assert len(HeatMapView(data.rows("sectors.rank", {})).cells()) == 7
    empty = ProductDescriptor("breadth.history", "Empty", "line", ("line",), ("date", "value"))
    frame = PanelFrame(PanelSpec("p1", "breadth.history", "line"), empty, SampleFloorData(),
                       None)
    qtbot.addWidget(frame)
    frame._data = _EmptyData()  # type: ignore[assignment]
    frame.set_view("line")
    assert "No data yet" in [lbl.text() for lbl in frame.findChildren(QLabel)]


class _EmptyData(SampleFloorData):
    def rows(self, product_id: str, filters: object) -> list[dict[str, object]]:  # type: ignore[override]
        return []


def test_rotation_mapping(qtbot: QtBot) -> None:
    """UT-GUI-034.050.M27.T01: a strong sector sits top right, a weak one bottom left."""
    view = RotationView([{"sector": "A", "rs_ratio": "102", "rs_momentum": "101"},
                         {"sector": "B", "rs_ratio": "98", "rs_momentum": "99"}])
    qtbot.addWidget(view)
    view.resize(300, 300)
    centre = view.plot_rect().center()
    strong, weak = view.to_screen(102, 101), view.to_screen(98, 99)
    assert strong.x() > centre.x() and strong.y() < centre.y()
    assert weak.x() < centre.x() and weak.y() > centre.y()


def test_idea_delegates(qtbot: QtBot) -> None:
    """UT-GUI-034.051.M27.T01: score and side delegates are set on idea tables only."""
    data = SampleFloorData()
    products = {p.id: p for p in data.products()}
    ideas = table_body(products["ideas.top"], data.rows("ideas.top", {}))
    news = table_body(products["news.latest"], data.rows("news.latest", {}))
    for table in (ideas, news):
        qtbot.addWidget(table)
    cols = products["ideas.top"].columns
    assert isinstance(ideas.itemDelegateForColumn(cols.index("score")), ScoreDelegate)
    assert isinstance(ideas.itemDelegateForColumn(cols.index("side")), SideDelegate)
    assert all(news.itemDelegateForColumn(c) is None for c in range(news.columnCount()))
    ideas.resize(500, 300)
    assert not ideas.grab().isNull() and isinstance(ideas, QTableWidget)


def test_default_refresh_once(tmp_path: Path) -> None:
    """UT-GUI-034.052.M30.T01: a version 1 file gets the new Default; Swing is kept."""
    path = tmp_path / "layouts.json"
    old = {"panels": [{"id": "p1", "product": "regime.today", "view": "card", "filters": {},
                       "link": "", "x": 0, "y": 0, "w": 4, "h": 6}]}
    path.write_text(json.dumps({
        "version": 1, "last": "Swing", "feed_folded": False,
        "layouts": {DEFAULT_NAME: {"tabs": {"Overview": old}},
                    "Swing": {"tabs": {"Overview": old}}},
    }), encoding="utf-8")
    store = LayoutStore(path)
    assert store.load(DEFAULT_NAME)["Overview"] == default_layout()["Overview"]
    assert store.load("Swing")["Overview"] == old["panels"]
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["version"] == VERSION == 2
    assert (tmp_path / "layouts.json.v1.bak").exists()
    store.save(DEFAULT_NAME, {"Overview": old["panels"]})
    assert LayoutStore(path).load(DEFAULT_NAME)["Overview"] == old["panels"]


def test_gone_view_falls_back(qtbot: QtBot) -> None:
    """UT-GUI-034.052.M30.T02: a sector panel saved as chart opens as a heat map."""
    data = SampleFloorData()
    product = next(p for p in data.products() if p.id == "sectors.rank")
    frame = PanelFrame(PanelSpec("p1", "sectors.rank", "chart"), product, data, None)
    qtbot.addWidget(frame)
    assert frame.spec.view == "heatmap"
    assert frame.findChildren(HeatMapView)
