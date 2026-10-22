"""
Module: MD-GUI-015.003.M04 / MD-GUI-015.011.M05 test cases (FO-GUI-015)
Parent SRD: SRD-GUI-015.003

Unit tests for LibraryTreeModel, LibraryFilterProxy, LibraryTreeView and IndicatorParamsDialog.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDoubleSpinBox, QPushButton, QSpinBox
from pytestqt.qtbot import QtBot

from us_swing.core.indicator_rules import get_spec
from us_swing.gui.indicator_library_model import (
    InUseRole,
    LibraryFilterProxy,
    LibraryTreeModel,
    LibraryTreeView,
)
from us_swing.gui.indicator_params_dialog import IndicatorParamsDialog


@pytest.fixture
def tree_model() -> LibraryTreeModel:
    return LibraryTreeModel()


@pytest.fixture
def proxy(tree_model: LibraryTreeModel) -> LibraryFilterProxy:
    p = LibraryFilterProxy()
    p.setSourceModel(tree_model)
    return p


def _category_texts(model: LibraryTreeModel) -> list[str]:
    return [str(model.index(r, 0).data()) for r in range(model.rowCount())]


def test_categories_in_enum_order_and_empty_hidden(tree_model: LibraryTreeModel) -> None:
    """UT-GUI-015.003.M04.T01: empty categories hidden; Price comes first."""
    texts = _category_texts(tree_model)
    assert texts[0].startswith("PRICE")
    assert not any(t.startswith(("DIVIDENDS", "OTHERS")) for t in texts)


def test_category_shows_used_over_total(tree_model: LibraryTreeModel) -> None:
    """UT-GUI-015.003.M04.T02: set_usage updates the Momentum category to '1 / 7'."""
    tree_model.set_usage({"rsi": 1})
    momentum = next(t for t in _category_texts(tree_model) if t.startswith("MOMENTUM"))
    assert momentum.endswith("1 / 7")


def test_category_rows_not_selectable_or_draggable(tree_model: LibraryTreeModel) -> None:
    """UT-GUI-015.003.M04.T03: category rows lack the selectable and drag flags."""
    row = next(
        r for r, t in enumerate(_category_texts(tree_model)) if t.startswith("MOMENTUM")
    )
    flags = tree_model.flags(tree_model.index(row, 0))
    assert not flags & Qt.ItemFlag.ItemIsSelectable
    assert not flags & Qt.ItemFlag.ItemIsDragEnabled


def test_search_keeps_matches_and_parent(proxy: LibraryFilterProxy) -> None:
    """UT-GUI-015.004.M04.T01: filter 'macd' keeps 3 items under Momentum."""
    proxy.setFilterFixedString("macd")
    assert proxy.rowCount() == 1
    momentum = proxy.index(0, 0)
    assert str(momentum.data()).startswith("MOMENTUM")
    assert proxy.rowCount(momentum) == 3


def test_search_without_match_empties_tree(proxy: LibraryFilterProxy) -> None:
    """UT-GUI-015.004.M04.T02: filter 'zzz' leaves the proxy empty."""
    proxy.setFilterFixedString("zzz")
    assert proxy.rowCount() == 0


def test_in_use_tag_follows_usage(tree_model: LibraryTreeModel) -> None:
    """UT-GUI-015.005.M04.T01: InUseRole is True while used, False once cleared."""
    item = tree_model.find_item("ema_50")
    assert item is not None
    tree_model.set_usage({"ema_50": 1})
    assert item.data(InUseRole) is True
    tree_model.set_usage({})
    assert item.data(InUseRole) is False


def test_unused_indicator_has_no_tag(tree_model: LibraryTreeModel) -> None:
    """UT-GUI-015.005.M04.T02: other indicators stay untagged when only RSI is used."""
    tree_model.set_usage({"rsi": 1})
    item = tree_model.find_item("macd")
    assert item is not None
    assert item.data(InUseRole) is False


def test_unavailable_item_disabled_with_reason(tree_model: LibraryTreeModel) -> None:
    """UT-GUI-015.006.M04.T01: rvol_5m is disabled and its tooltip names the reason."""
    item = tree_model.find_item("rvol_5m")
    assert item is not None
    assert not item.isEnabled()
    assert "needs intraday data" in item.toolTip()


def test_double_click_unavailable_emits_nothing(
    qtbot: QtBot, tree_model: LibraryTreeModel
) -> None:
    """UT-GUI-015.006.M04.T02: double-clicking rvol_5m does not emit indicator_activated."""
    view = LibraryTreeView()
    view.setModel(tree_model)
    qtbot.addWidget(view)
    item = tree_model.find_item("rvol_5m")
    assert item is not None
    with qtbot.assertNotEmitted(view.indicator_activated):
        view.doubleClicked.emit(item.index())


def test_params_dialog_one_spinbox_per_param(qtbot: QtBot) -> None:
    """UT-GUI-015.011.M05.T01: MACD dialog has fast/slow/signal spinboxes with spec ranges."""
    spec = get_spec("macd")
    dlg = IndicatorParamsDialog(spec, {})
    qtbot.addWidget(dlg)
    for param in spec.params:
        spin = dlg.findChild((QSpinBox, QDoubleSpinBox), f"param_{param.key}")
        assert spin is not None
        assert spin.minimum() == param.min
        assert spin.maximum() == param.max
    assert {"fast", "slow", "signal"} <= {p.key for p in spec.params}
    dlg.findChild(QSpinBox, "param_fast").setValue(8)
    assert dlg.get_params()["fast"] == 8.0


def test_params_dialog_reset_restores_defaults(qtbot: QtBot) -> None:
    """UT-GUI-015.011.M05.T02: Reset puts the fast period back to 12."""
    dlg = IndicatorParamsDialog(get_spec("macd"), {})
    qtbot.addWidget(dlg)
    dlg.findChild(QSpinBox, "param_fast").setValue(5)
    assert dlg.get_params()["fast"] == 5.0
    dlg.findChild(QPushButton, "param_reset_btn").click()
    assert dlg.get_params()["fast"] == 12.0

