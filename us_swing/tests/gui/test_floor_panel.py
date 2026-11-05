"""Tests for Market Floor panels, link groups and the grid widget (MD-GUI-034.005/.006)."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QLabel, QTableWidget
from pytestqt.qtbot import QtBot

from us_swing.gui.floor_dialogs import ANY, CatalogDialog, PanelSettingsDialog
from us_swing.gui.floor_grid import PanelGrid
from us_swing.gui.floor_grid_model import GridModel, PanelSpec
from us_swing.gui.floor_panel import LinkBus, PanelFrame
from us_swing.gui.floor_sample import SampleFloorData

_DATA = SampleFloorData()
_PRODUCTS = {p.id: p for p in _DATA.products()}


def _frame(bus: LinkBus | None, link: str | None, pid: str = "p1") -> PanelFrame:
    spec = PanelSpec(pid, "ideas.top", "table", {}, link)
    return PanelFrame(spec, _PRODUCTS["ideas.top"], _DATA, bus)


def _selected_symbol(frame: PanelFrame) -> str:
    table = frame.findChild(QTableWidget)
    assert table is not None
    rows = table.selectionModel().selectedRows()  # type: ignore[union-attr]
    return table.item(rows[0].row(), 0).text() if rows else ""  # type: ignore[union-attr]


def _click_symbol(frame: PanelFrame, symbol: str) -> None:
    table = frame.findChild(QTableWidget)
    assert table is not None
    for r in range(table.rowCount()):
        if table.item(r, 0).text() == symbol:  # type: ignore[union-attr]
            table.cellClicked.emit(r, 0)
            return
    raise AssertionError(symbol)


def test_view_switch(qtbot: QtBot) -> None:
    """UT-GUI-034.006.M06.T01: table, then card, then chart placeholder."""
    frame = _frame(None, None)
    qtbot.addWidget(frame)
    assert frame.findChild(QTableWidget) is not None
    frame.set_view("card")
    assert frame.findChild(QTableWidget) is None
    assert any("Symbol:" in lbl.text() for lbl in frame.findChildren(QLabel))
    frame.set_view("chart")
    frame.set_symbol("AAPL")
    texts = [lbl.text() for lbl in frame.findChildren(QLabel)]
    assert "Chart comes later" in texts and "AAPL" in texts


def test_link_group_updates_same_group(qtbot: QtBot) -> None:
    """UT-GUI-034.007.M06.T01: click AAPL in group A; other A panels follow, B does not."""
    bus = LinkBus()
    sender, mate, other = _frame(bus, "A", "p1"), _frame(bus, "A", "p2"), _frame(bus, "B", "p3")
    for frame in (sender, mate, other):
        qtbot.addWidget(frame)
    echoes: list[str] = []
    sender.set_symbol = echoes.append  # type: ignore[method-assign,assignment]
    _click_symbol(sender, "AAPL")
    assert _selected_symbol(mate) == "AAPL"
    assert _selected_symbol(other) == ""
    assert echoes == []


def test_no_group_publishes_nothing(qtbot: QtBot) -> None:
    """UT-GUI-034.007.M06.T02: a panel without a group sends nothing."""
    bus = LinkBus()
    loner, mate = _frame(bus, None, "p1"), _frame(bus, "A", "p2")
    for frame in (loner, mate):
        qtbot.addWidget(frame)
    seen: list[tuple[str, str]] = []
    bus.symbol_selected.connect(lambda g, s, _o: seen.append((g, s)))
    with qtbot.waitSignal(loner.symbol_clicked):
        _click_symbol(loner, "AAPL")
    assert seen == []
    assert _selected_symbol(mate) == ""


def test_missing_product_frame(qtbot: QtBot) -> None:
    """UT-GUI-034.006.M06.T02: an unknown product shows a Missing product card."""
    frame = PanelFrame(PanelSpec("p1", "nope"), None, _DATA)
    qtbot.addWidget(frame)
    assert "Missing product" in [lbl.text() for lbl in frame.findChildren(QLabel)]


def test_dialogs_return_choices(qtbot: QtBot) -> None:
    """UT-GUI-034.006.M06.T03: catalog returns the product; settings returns view/filters/link."""
    catalog = CatalogDialog(_DATA.products())
    qtbot.addWidget(catalog)
    catalog.list.setCurrentRow(1)
    assert catalog.chosen() == _DATA.products()[1]
    dialog = PanelSettingsDialog(_PRODUCTS["ideas.top"], "table", {"side": "long"}, None)
    qtbot.addWidget(dialog)
    assert dialog.result_settings() == ("table", {"side": "long"}, None)
    dialog.view_combo.setCurrentText("card")
    dialog.filter_combos["side"].setCurrentText(ANY)
    dialog.link_combo.setCurrentText("B")
    assert dialog.result_settings() == ("card", {}, "B")


def test_grid_drag_only_in_edit_mode(qtbot: QtBot) -> None:
    """UT-GUI-034.005.M05.T08: dragging a title bar moves a panel only in edit mode."""
    model = GridModel([PanelSpec("p1", "ideas.top", x=0, y=0, w=4, h=4)])
    grid = PanelGrid(lambda spec: PanelFrame(spec, _PRODUCTS["ideas.top"], _DATA))
    qtbot.addWidget(grid)
    grid.resize(1200, 600)
    grid.set_model(model)
    grid.show()
    frame = grid.frames()[0]
    changes: list[int] = []
    grid.layout_changed.connect(lambda: changes.append(1))
    bar = frame.title_bar
    start = QPoint(40, 5)
    far = start + QPoint(grid.width() // 12 * 3, 0)
    qtbot.mousePress(bar, Qt.MouseButton.LeftButton, pos=start)  # type: ignore[no-untyped-call]
    qtbot.mouseMove(bar, far)  # type: ignore[no-untyped-call]
    qtbot.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=far)  # type: ignore[no-untyped-call]
    assert model.panels[0].x == 0 and not changes
    grid.set_edit(True)
    qtbot.mousePress(bar, Qt.MouseButton.LeftButton, pos=start)  # type: ignore[no-untyped-call]
    qtbot.mouseMove(bar, far)  # type: ignore[no-untyped-call]
    qtbot.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=start)  # type: ignore[no-untyped-call]
    assert model.panels[0].x == 3 and changes


def test_drag_needs_left_button_and_clears_on_edit_off(qtbot: QtBot) -> None:
    """UT-GUI-034.005.M05.T09: a right-click does not drag; leaving edit mode ends a drag."""
    model = GridModel([PanelSpec("p1", "ideas.top", x=0, y=0, w=4, h=4)])
    grid = PanelGrid(lambda spec: PanelFrame(spec, _PRODUCTS["ideas.top"], _DATA))
    qtbot.addWidget(grid)
    grid.resize(1200, 600)
    grid.set_model(model)
    grid.show()
    grid.set_edit(True)
    bar = grid.frames()[0].title_bar
    start = QPoint(40, 5)
    qtbot.mousePress(bar, Qt.MouseButton.RightButton, pos=start)  # type: ignore[no-untyped-call]
    assert grid._drag is None
    qtbot.mousePress(bar, Qt.MouseButton.LeftButton, pos=start)  # type: ignore[no-untyped-call]
    assert grid._drag is not None
    qtbot.mouseMove(bar, start + QPoint(300, 0))
    grid.set_edit(False)
    assert grid._drag is None and not grid._ghost.isVisible()
    assert grid.frames()[0].geometry().x() == 0
    qtbot.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=start)
    assert model.panels[0].x == 0
