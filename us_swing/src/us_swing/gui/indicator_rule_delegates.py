"""
Module: MD-GUI-015.009.M03 — Indicator Rule Delegates
Parent SRD: SRD-GUI-015.009
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from PyQt6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QRect,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QMouseEvent, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from us_swing.core.indicator_rules import IndicatorSpec
from us_swing.gui.indicator_rule_model import RuleRole, SpecRole
from us_swing.gui.theme import C


@runtime_checkable
class RuleRowsModel(Protocol):
    """Row operations the toggle and remove delegates need (indicator or pattern table)."""

    def set_enabled(self, row: int, enabled: bool) -> None: ...
    def remove_row(self, row: int) -> None: ...

_SWITCH_W = 32
_SWITCH_H = 16
_KNOB_PAD = 2
_REMOVE_SIZE = 20

_COMBO_QSS = f"""
    QComboBox {{
        background: {C.INPUT};
        color: {C.TEXT};
        border: 1px solid {C.OVERLAY2};
        border-radius: 4px;
        padding: 0 6px;
        outline: none;
    }}
    QComboBox:focus {{
        border: 1px solid {C.BLUE};
        outline: none;
    }}
"""

_SPIN_QSS = f"""
    QDoubleSpinBox {{
        background: {C.INPUT};
        color: {C.TEXT};
        border: 1px solid {C.OVERLAY2};
        border-radius: 4px;
        padding: 0 4px;
        outline: none;
    }}
    QDoubleSpinBox:focus {{
        border: 1px solid {C.BLUE};
        outline: none;
    }}
"""


def _paint_cell_background(
    painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
) -> None:
    """Draw the default cell background (selection, hover) without its text."""
    blank = QStyleOptionViewItem(option)
    blank.text = ""
    style = option.widget.style() if option.widget is not None else QApplication.style()
    if style is not None:
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, blank, painter, option.widget)


def _is_left_release(event: QEvent | None) -> bool:
    return (
        isinstance(event, QMouseEvent)
        and event.type() == QEvent.Type.MouseButtonRelease
        and event.button() == Qt.MouseButton.LeftButton
    )


class ToggleSwitchDelegate(QStyledItemDelegate):
    """Paints an on/off pill; a click inside the pill flips the rule's enabled flag."""

    @staticmethod
    def switch_rect(rect: QRect) -> QRect:
        """Return the pill rectangle centred in a cell rectangle."""
        return QRect(
            rect.left() + (rect.width() - _SWITCH_W) // 2,
            rect.top() + (rect.height() - _SWITCH_H) // 2,
            _SWITCH_W,
            _SWITCH_H,
        )

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if painter is None:
            return
        rule = index.data(RuleRole)
        if rule is None:
            super().paint(painter, option, index)
            return
        _paint_cell_background(painter, option, index)
        pill = self.switch_rect(option.rect)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(C.BLUE if rule.enabled else C.OVERLAY2))
        painter.drawRoundedRect(pill, _SWITCH_H / 2, _SWITCH_H / 2)
        knob = _SWITCH_H - 2 * _KNOB_PAD
        knob_x = pill.right() + 1 - _KNOB_PAD - knob if rule.enabled else pill.left() + _KNOB_PAD
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRect(knob_x, pill.top() + _KNOB_PAD, knob, knob))
        painter.restore()

    def editorEvent(
        self,
        event: QEvent | None,
        model: QAbstractItemModel | None,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if _is_left_release(event) and isinstance(model, RuleRowsModel):
            assert isinstance(event, QMouseEvent)
            if self.switch_rect(option.rect).contains(event.position().toPoint()):
                rule = index.data(RuleRole)
                if rule is not None:
                    model.set_enabled(index.row(), not rule.enabled)
                return True
        return False


class ConditionComboDelegate(QStyledItemDelegate):
    """Combo box listing the conditions allowed for the row's indicator."""

    def createEditor(
        self, parent: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        combo = QComboBox(parent)
        combo.setObjectName("rule_condition_combo")
        combo.setStyleSheet(_COMBO_QSS)
        spec: IndicatorSpec = index.data(SpecRole)
        for cond in spec.conditions:
            combo.addItem(cond.label, cond)
        # combo → activated → delegate → _commit_and_close
        combo.activated.connect(lambda _i, c=combo: self._commit_and_close(c))
        return combo

    def _commit_and_close(self, editor: QComboBox) -> None:
        self.commitData.emit(editor)
        self.closeEditor.emit(editor)

    def setEditorData(self, editor: QWidget | None, index: QModelIndex) -> None:
        if isinstance(editor, QComboBox):
            pos = editor.findData(index.data(Qt.ItemDataRole.EditRole))
            editor.setCurrentIndex(max(pos, 0))

    def setModelData(
        self, editor: QWidget | None, model: QAbstractItemModel | None, index: QModelIndex
    ) -> None:
        if model is None:
            return
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentData(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(
        self, editor: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if editor is None:
            return
        editor.setGeometry(option.rect)


class NumberSpinDelegate(QStyledItemDelegate):
    """Double spin box for the Value and To cells, bounded by the indicator's range."""

    def createEditor(
        self, parent: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        spec: IndicatorSpec = index.data(SpecRole)
        spin = QDoubleSpinBox(parent)
        spin.setObjectName("rule_value_spin")
        spin.setStyleSheet(_SPIN_QSS)
        spin.setRange(spec.value_min, spec.value_max)
        spin.setDecimals(2)
        span = spec.value_max - spec.value_min
        spin.setSingleStep(1.0 if span >= 10 else 0.1)
        if spec.unit:
            spin.setSuffix(spec.unit)
        return spin

    def setEditorData(self, editor: QWidget | None, index: QModelIndex) -> None:
        value = index.data(Qt.ItemDataRole.EditRole)
        if isinstance(editor, QDoubleSpinBox) and value is not None:
            editor.setValue(float(value))

    def setModelData(
        self, editor: QWidget | None, model: QAbstractItemModel | None, index: QModelIndex
    ) -> None:
        if model is None:
            return
        if isinstance(editor, QDoubleSpinBox):
            editor.interpretText()
            model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(
        self, editor: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if editor is None:
            return
        editor.setGeometry(option.rect)


class SettingsDelegate(QStyledItemDelegate):
    """Shows the parameter summary; a click asks the dialog to open the params editor."""

    edit_requested = pyqtSignal(int)  # row

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if painter is None:
            return
        rule = index.data(RuleRole)
        if rule is None:
            super().paint(painter, option, index)
            return
        _paint_cell_background(painter, option, index)
        text = index.data(Qt.ItemDataRole.DisplayRole) or "—"
        if len(index.data(SpecRole).params) > 1:
            text += "  ▾"
        painter.save()
        painter.setPen(QColor(C.SUBTEXT if rule.enabled else C.MUTED))
        painter.drawText(
            option.rect.adjusted(8, 0, -8, 0),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            text,
        )
        painter.restore()

    def editorEvent(
        self,
        event: QEvent | None,
        model: QAbstractItemModel | None,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if _is_left_release(event):
            spec = index.data(SpecRole)
            if spec is not None and spec.params:
                self.edit_requested.emit(index.row())
                return True
        return False


class RemoveButtonDelegate(QStyledItemDelegate):
    """Paints a remove glyph; a click inside it removes the row."""

    @staticmethod
    def remove_rect(rect: QRect) -> QRect:
        """Return the button rectangle centred in a cell rectangle."""
        return QRect(
            rect.left() + (rect.width() - _REMOVE_SIZE) // 2,
            rect.top() + (rect.height() - _REMOVE_SIZE) // 2,
            _REMOVE_SIZE,
            _REMOVE_SIZE,
        )

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if painter is None:
            return
        _paint_cell_background(painter, option, index)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.save()
        painter.setPen(QColor(C.RED if hovered else C.SUBTEXT))
        painter.drawText(
            self.remove_rect(option.rect), int(Qt.AlignmentFlag.AlignCenter), "✕"
        )
        painter.restore()

    def editorEvent(
        self,
        event: QEvent | None,
        model: QAbstractItemModel | None,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if _is_left_release(event) and isinstance(model, RuleRowsModel):
            assert isinstance(event, QMouseEvent)
            if self.remove_rect(option.rect).contains(event.position().toPoint()):
                row = index.row()
                # Timer owned by the model so it never fires after the model is gone
                timer = QTimer(model)
                timer.setSingleShot(True)
                # timer → timeout → model → remove the clicked row
                timer.timeout.connect(lambda: model.remove_row(row))
                timer.timeout.connect(timer.deleteLater)
                timer.start(0)
                return True
        return False

