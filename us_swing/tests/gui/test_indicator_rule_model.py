"""
Module: MD-GUI-015.008.M02 / MD-GUI-015.009.M03 / MD-GUI-015.002.M01 test cases (FO-GUI-015)
Parent SRD: SRD-GUI-015.008

Unit tests for RuleTableModel, the rule-table delegates and the frameless dialog base.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
)
from pytestqt.qtbot import QtBot

import us_swing.gui.indicator_library_model as library_mod
import us_swing.gui.indicator_params_dialog as params_mod
import us_swing.gui.indicator_rule_delegates as delegates_mod
import us_swing.gui.indicator_rule_model as model_mod
import us_swing.gui.indicator_rules_dialog as dialog_mod
from us_swing.core.indicator_rules import Condition, IndicatorRuleError, Rule, get_spec
from us_swing.gui.frameless_dialog import FramelessDialog
from us_swing.gui.indicator_rule_delegates import (
    ConditionComboDelegate,
    NumberSpinDelegate,
    RemoveButtonDelegate,
    ToggleSwitchDelegate,
)
from us_swing.gui.indicator_rule_model import (
    COL_CONDITION,
    COL_INDICATOR,
    COL_ON,
    COL_REMOVE,
    COL_TO,
    COL_VALUE,
    RuleRole,
    RuleTableModel,
)
from us_swing.gui.theme import C


@pytest.fixture
def model() -> RuleTableModel:
    return RuleTableModel()


@pytest.fixture
def table(qtbot: QtBot, model: RuleTableModel) -> QTableView:
    view = QTableView()
    view.setModel(model)
    view.setItemDelegateForColumn(COL_ON, ToggleSwitchDelegate(view))
    view.setItemDelegateForColumn(COL_REMOVE, RemoveButtonDelegate(view))
    qtbot.addWidget(view)
    return view


def _release(pos: QPointF) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _click_cell(view: QTableView, row: int, col: int, corner: bool = False) -> None:
    index = view.model().index(row, col)
    rect = view.visualRect(index)
    delegate = view.itemDelegateForColumn(col)
    option = QStyleOptionViewItem()
    option.rect = rect
    point = rect.topLeft() if corner else rect.center()
    delegate.editorEvent(_release(QPointF(point)), view.model(), option, index)


def test_table_has_seven_columns(model: RuleTableModel) -> None:
    """UT-GUI-015.008.M02.T01: empty model exposes the 7 expected headers."""
    headers = [
        model.headerData(i, Qt.Orientation.Horizontal) for i in range(model.columnCount())
    ]
    assert headers == ["On", "Indicator", "Condition", "Value", "To", "Settings", ""]
    assert model.rowCount() == 0


def test_add_rule_appends_and_signals(qtbot: QtBot, model: RuleTableModel) -> None:
    """UT-GUI-015.008.M02.T02: add_rule appends the default rule, emitting rules_changed once."""
    emitted: list[int] = []
    model.rules_changed.connect(lambda: emitted.append(1))
    row = model.add_rule("rsi")
    assert row == 0
    assert len(emitted) == 1
    assert model.rowCount() == 1
    assert model.rules()[0].indicator_id == "rsi"


def test_add_unknown_indicator_raises(model: RuleTableModel) -> None:
    """UT-GUI-015.008.M02.T03: unknown indicator raises and adds no row."""
    with pytest.raises(IndicatorRuleError):
        model.add_rule("nope")
    assert model.rowCount() == 0


def test_to_cell_editable_for_between(model: RuleTableModel) -> None:
    """UT-GUI-015.009.M02.T01: To cell is editable for a between rule."""
    model.set_rules([Rule("rsi", Condition.BETWEEN, 30.0, 70.0)])
    assert model.flags(model.index(0, COL_TO)) & Qt.ItemFlag.ItemIsEditable


def test_to_cell_locked_for_at_least(model: RuleTableModel) -> None:
    """UT-GUI-015.009.M02.T02: To cell is not editable and shows a dash for at least."""
    model.set_rules([Rule("atr_pct", Condition.AT_LEAST, 1.0)])
    index = model.index(0, COL_TO)
    assert not model.flags(index) & Qt.ItemFlag.ItemIsEditable
    assert model.data(index) == "—"


def test_switching_to_between_fills_to(model: RuleTableModel) -> None:
    """UT-GUI-015.009.M02.T03: at least to between fills To with the spec maximum."""
    model.set_rules([Rule("atr_pct", Condition.AT_LEAST, 1.0)])
    model.set_condition(0, Condition.BETWEEN)
    rule = model.rules()[0]
    assert rule.condition is Condition.BETWEEN
    assert rule.to == get_spec("atr_pct").value_max


def test_disabled_row_is_dimmed(model: RuleTableModel) -> None:
    """UT-GUI-015.012.M02.T01: set_enabled(False) dims the row and clears the flag."""
    model.set_rules([Rule("rsi", Condition.BETWEEN, 30.0, 70.0)])
    model.set_enabled(0, False)
    assert model.rules()[0].enabled is False
    colour = model.data(model.index(0, COL_INDICATOR), Qt.ItemDataRole.ForegroundRole)
    assert colour == QColor(C.MUTED)


def test_remove_bad_row_does_nothing(qtbot: QtBot, model: RuleTableModel) -> None:
    """UT-GUI-015.012.M02.T02: remove_row on a bad index keeps the row and emits nothing."""
    model.set_rules([Rule("rsi", Condition.BETWEEN, 30.0, 70.0)])
    with qtbot.assertNotEmitted(model.rules_changed):
        model.remove_row(9)
    assert model.rowCount() == 1


def test_condition_combo_lists_allowed_conditions(qtbot: QtBot, model: RuleTableModel) -> None:
    """UT-GUI-015.009.M03.T01: MACD condition combo has 4 items, crosses above first."""
    model.set_rules([Rule("macd", Condition.CROSSES_ABOVE)])
    editor = ConditionComboDelegate().createEditor(
        None, QStyleOptionViewItem(), model.index(0, COL_CONDITION)
    )
    qtbot.addWidget(editor)
    assert isinstance(editor, QComboBox)
    assert editor.count() == 4
    assert editor.itemData(0) is Condition.CROSSES_ABOVE


def test_value_spin_uses_spec_range_and_unit(qtbot: QtBot, model: RuleTableModel) -> None:
    """UT-GUI-015.010.M03.T01: value spinbox takes the spec range and unit suffix."""
    spec = get_spec("atr_pct")
    model.set_rules([Rule("atr_pct", Condition.AT_LEAST, 1.0)])
    editor = NumberSpinDelegate().createEditor(
        None, QStyleOptionViewItem(), model.index(0, COL_VALUE)
    )
    qtbot.addWidget(editor)
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.minimum() == spec.value_min
    assert editor.maximum() == spec.value_max
    assert editor.suffix() == "%"


def test_value_above_max_is_clamped(qtbot: QtBot, model: RuleTableModel) -> None:
    """UT-GUI-015.010.M03.T02: typing 999 into an RSI editor commits 100."""
    model.set_rules([Rule("rsi", Condition.AT_LEAST, 30.0)])
    index = model.index(0, COL_VALUE)
    delegate = NumberSpinDelegate()
    editor = delegate.createEditor(None, QStyleOptionViewItem(), index)
    qtbot.addWidget(editor)
    assert isinstance(editor, QDoubleSpinBox)
    editor.setValue(999.0)
    delegate.setModelData(editor, model, index)
    assert model.rules()[0].value == 100.0


def test_click_switch_toggles_enabled(table: QTableView, model: RuleTableModel) -> None:
    """UT-GUI-015.012.M03.T01: clicking the pill centre flips the rule's enabled flag."""
    model.set_rules([Rule("rsi", Condition.BETWEEN, 30.0, 70.0)])
    rect = table.visualRect(model.index(0, COL_ON))
    assert rect.contains(ToggleSwitchDelegate.switch_rect(rect))
    _click_cell(table, 0, COL_ON)
    assert model.index(0, COL_ON).data(RuleRole).enabled is False


def test_click_remove_removes_row(qtbot: QtBot, table: QTableView, model: RuleTableModel) -> None:
    """UT-GUI-015.012.M03.T02: clicking the remove glyph drops the row (deferred)."""
    model.set_rules([Rule("rsi", Condition.BETWEEN, 30.0, 70.0)])
    rect = table.visualRect(model.index(0, COL_REMOVE))
    assert rect.contains(RemoveButtonDelegate.remove_rect(rect))
    _click_cell(table, 0, COL_REMOVE)
    qtbot.waitUntil(lambda: model.rowCount() == 0, timeout=1000)


def test_click_outside_switch_does_nothing(table: QTableView, model: RuleTableModel) -> None:
    """UT-GUI-015.012.M03.T03: clicking the cell corner leaves enabled unchanged."""
    model.set_rules([Rule("rsi", Condition.BETWEEN, 30.0, 70.0)])
    _click_cell(table, 0, COL_ON, corner=True)
    assert model.rules()[0].enabled is True


def test_inline_editors_suppress_focus_outline(qtbot: QtBot, model: RuleTableModel) -> None:
    """UT-GUI-015.015.M03.T01: condition and spin editors carry 'outline: none' styles."""
    model.set_rules([Rule("rsi", Condition.BETWEEN, 30.0, 70.0)])
    option = QStyleOptionViewItem()
    combo = ConditionComboDelegate().createEditor(None, option, model.index(0, COL_CONDITION))
    spin = NumberSpinDelegate().createEditor(None, option, model.index(0, COL_VALUE))
    qtbot.addWidget(combo)
    qtbot.addWidget(spin)
    assert "outline: none" in combo.styleSheet()
    assert "outline: none" in spin.styleSheet()


def test_new_gui_modules_have_no_fixed_heights() -> None:
    """UT-GUI-015.015.M03.T02: the 5 new GUI modules never call setFixedHeight/setFixedSize.

    ``frameless_dialog`` is excluded: it is moved unchanged and keeps the
    standard 38 px title bar.
    """
    modules = (model_mod, delegates_mod, library_mod, params_mod, dialog_mod)
    for mod in modules:
        source = Path(str(mod.__file__)).read_text(encoding="utf-8")
        assert "setFixedSize(" not in source, mod.__name__
        assert "setFixedHeight(" not in source, mod.__name__


def test_frameless_dialog_keeps_title_bar_and_layout(qtbot: QtBot) -> None:
    """UT-GUI-015.002.M01.T01: title label, 3 window buttons and a QVBoxLayout content area."""
    dlg = FramelessDialog("X")
    qtbot.addWidget(dlg)
    assert [lbl.text() for lbl in dlg._title_bar.findChildren(QLabel)] == ["X"]
    assert len(dlg._title_bar.findChildren(QPushButton)) == 3
    assert isinstance(dlg.content_layout(), QVBoxLayout)


def test_close_button_rejects(qtbot: QtBot) -> None:
    """UT-GUI-015.002.M01.T02: clicking the close button leaves the dialog rejected."""
    dlg = FramelessDialog("X")
    qtbot.addWidget(dlg)
    close_btn = next(b for b in dlg._title_bar.findChildren(QPushButton) if b.text() == "✕")
    dlg.open()
    close_btn.click()
    assert dlg.result() == QDialog.DialogCode.Rejected
