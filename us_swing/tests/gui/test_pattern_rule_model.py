"""
Module: MD-GUI-016.004.M07 / MD-GUI-015.009.M03 test cases (FO-GUI-016)
Parent SRD: SRD-GUI-016.004

Unit tests for PatternRuleTableModel and the shared toggle / remove delegates.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QStyleOptionViewItem, QTableView
from pytestqt.qtbot import QtBot

from us_swing.core.price_patterns import PatternRule, PatternRuleError
from us_swing.gui.indicator_rule_delegates import RemoveButtonDelegate, ToggleSwitchDelegate
from us_swing.gui.pattern_rule_model import (
    COL_ON,
    COL_PATTERN,
    COL_REMOVE,
    COL_SETTINGS,
    PatternRuleTableModel,
)
from us_swing.gui.theme import C


@pytest.fixture
def model() -> PatternRuleTableModel:
    return PatternRuleTableModel()


def _release(pos: QPointF) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _click(view: QTableView, row: int, col: int) -> bool:
    index = view.model().index(row, col)
    option = QStyleOptionViewItem()
    option.rect = view.visualRect(index)
    delegate = view.itemDelegateForColumn(col)
    return bool(
        delegate.editorEvent(_release(QPointF(option.rect.center())), view.model(), option, index)
    )


def test_columns_and_display_text(model: PatternRuleTableModel) -> None:
    """UT-GUI-016.004.M07.T01: 4 headers; pattern name and settings text shown."""
    model.set_rules([PatternRule("hammer", {"within": 1.0})])
    headers = [model.headerData(i, Qt.Orientation.Horizontal) for i in range(4)]
    assert headers == ["On", "Pattern", "Settings", ""]
    assert model.index(0, COL_PATTERN).data() == "Hammer"
    assert model.index(0, COL_SETTINGS).data() == "1-bar window"


def test_unknown_pattern_and_bad_remove(model: PatternRuleTableModel) -> None:
    """UT-GUI-016.004.M07.T02: unknown pattern raises; bad-row remove is a no-op."""
    with pytest.raises(PatternRuleError):
        model.add_rule("nope")
    model.add_rule("nr4")
    model.remove_row(9)
    assert model.rowCount() == 1


def test_disable_dims_row_and_signals(qtbot: QtBot, model: PatternRuleTableModel) -> None:
    """UT-GUI-016.008.M07.T01: disabling dims the row and emits rules_changed."""
    model.add_rule("doji")
    with qtbot.waitSignal(model.rules_changed, timeout=500):
        model.set_enabled(0, False)
    color = model.index(0, COL_PATTERN).data(Qt.ItemDataRole.ForegroundRole)
    assert color == QColor(C.MUTED)


def test_toggle_missing_row_does_nothing(qtbot: QtBot, model: PatternRuleTableModel) -> None:
    """UT-GUI-016.008.M07.T02: toggling a missing row changes nothing and emits nothing."""
    model.add_rule("doji")
    before = model.rules()
    with qtbot.assertNotEmitted(model.rules_changed):
        model.set_enabled(9, False)
    assert model.rules() == before


def test_delegates_act_on_pattern_model(qtbot: QtBot, model: PatternRuleTableModel) -> None:
    """UT-GUI-016.005.M03.T01: toggle and remove delegates work on the pattern model."""
    model.set_rules([PatternRule("hammer"), PatternRule("doji")])
    view = QTableView()
    view.setModel(model)
    view.setItemDelegateForColumn(COL_ON, ToggleSwitchDelegate(view))
    view.setItemDelegateForColumn(COL_REMOVE, RemoveButtonDelegate(view))
    qtbot.addWidget(view)
    view.show()
    assert _click(view, 0, COL_ON)
    assert model.rules()[0].enabled is False
    assert _click(view, 1, COL_REMOVE)
    qtbot.waitUntil(lambda: model.rowCount() == 1, timeout=1000)


def test_delegates_ignore_plain_model(qtbot: QtBot) -> None:
    """UT-GUI-016.005.M03.T02: delegates ignore a model without the rule-row API."""
    plain = QStandardItemModel(1, 4)
    plain.setItem(0, 0, QStandardItem("x"))
    view = QTableView()
    view.setModel(plain)
    view.setItemDelegateForColumn(0, ToggleSwitchDelegate(view))
    view.setItemDelegateForColumn(3, RemoveButtonDelegate(view))
    qtbot.addWidget(view)
    view.show()
    assert _click(view, 0, 0) is False
    assert _click(view, 0, 3) is False
    assert plain.rowCount() == 1
