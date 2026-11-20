"""Tests for watchlist row selection and right-click Delete (SRD-GUI-019.004)."""
from __future__ import annotations

from typing import Any

import pytest
from PyQt6.QtCore import QPoint

from us_swing.data.models import WatchlistItem
from us_swing.gui import dashboard_panel
from us_swing.gui.dashboard_panel import _WatchlistTab
from tests.gui.test_watchlist_suggestions import _StubService


class _ListService(_StubService):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[WatchlistItem] = []
        self.removed: list[str] = []

    def get_watchlist_items(self) -> list[WatchlistItem]:
        return self.items

    def remove_from_watchlist(self, symbol: str) -> None:
        self.removed.append(symbol)


@pytest.fixture()
def tab(qtbot: Any) -> tuple[_WatchlistTab, _ListService]:
    svc = _ListService()
    svc.items = [WatchlistItem("AAPL", ltp=100.0), WatchlistItem("NVDA", ltp=50.0)]
    widget = _WatchlistTab(svc)  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    widget.reload()
    return widget, svc


def test_selection_kept_on_price_update(tab: Any) -> None:
    """UT-GUI-019.004.M02.T04: a selected row stays selected when prices update."""
    widget, svc = tab
    widget.table_view.selectRow(1)

    svc.items = [WatchlistItem("AAPL", ltp=101.0), WatchlistItem("NVDA", ltp=51.0)]
    widget.reload()

    rows = widget.table_view.selectionModel().selectedRows()
    assert [r.row() for r in rows] == [1]
    assert widget._remove_btn.isEnabled()
    assert widget._model.data(widget._model.index(1, 1)) is not None


def test_right_click_delete_removes_symbol(tab: Any, monkeypatch: Any) -> None:
    """UT-GUI-019.004.M02.T05: right-click Delete removes the stock under the mouse."""
    widget, svc = tab
    widget.show()

    def _pick_first(menu: Any, *_: Any) -> None:
        menu.actions()[0].trigger()

    monkeypatch.setattr(dashboard_panel.QMenu, "exec", _pick_first)
    view = widget.table_view
    pos = view.visualRect(widget._model.index(1, 0)).center()

    widget._show_row_menu(pos)

    assert svc.removed == ["NVDA"]


def test_right_click_on_empty_area_shows_no_menu(tab: Any, monkeypatch: Any) -> None:
    """UT-GUI-019.004.M02.T06: right-click below the last row does nothing."""
    widget, svc = tab
    widget.show()
    shown: list[Any] = []
    monkeypatch.setattr(dashboard_panel.QMenu, "exec", lambda m, *_: shown.append(m))

    widget._show_row_menu(QPoint(5, 5000))

    assert shown == []
    assert svc.removed == []
