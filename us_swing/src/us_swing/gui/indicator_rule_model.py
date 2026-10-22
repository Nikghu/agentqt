"""
Module: MD-GUI-015.008.M02 — Indicator Rule Table Model
Parent SRD: SRD-GUI-015.008
"""
from __future__ import annotations

import dataclasses
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor

from us_swing.core.indicator_rules import (
    Condition,
    IndicatorSpec,
    Rule,
    default_rule,
    get_spec,
    settings_summary,
)
from us_swing.gui.theme import C

COL_ON = 0
COL_INDICATOR = 1
COL_CONDITION = 2
COL_VALUE = 3
COL_TO = 4
COL_SETTINGS = 5
COL_REMOVE = 6

RuleRole = Qt.ItemDataRole.UserRole + 1
SpecRole = Qt.ItemDataRole.UserRole + 2

_HEADERS = ("On", "Indicator", "Condition", "Value", "To", "Settings", "")
_DASH = "—"


def _format_number(spec: IndicatorSpec, value: float | None) -> str:
    """Value/To cell text: ``$5,000``, ``1.0%``, ``1.0×``, ``$10B`` or ``30``."""
    if value is None:
        return _DASH
    if spec.unit == "$":
        text = f"{value:,.2f}"
        return f"${text[:-3] if text.endswith('.00') else text}"
    if spec.unit == "$B":
        return f"${value:,g}B"
    if spec.unit in ("%", "×"):
        return f"{value:.1f}{spec.unit}"
    return f"{value:g}"


class RuleTableModel(QAbstractTableModel):
    """Holds the dialog's ``Rule`` list; no screening logic."""

    rules_changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rules: list[Rule] = []

    # ── Public API ────────────────────────────────────────────────────────

    def set_rules(self, rules: list[Rule]) -> None:
        self.beginResetModel()
        self._rules = list(rules)
        self.endResetModel()
        self.rules_changed.emit()

    def rules(self) -> list[Rule]:
        return list(self._rules)

    def add_rule(self, indicator_id: str) -> int:
        """Append the default rule for an indicator and return its row.

        Raises:
            IndicatorRuleError: If the indicator id is unknown (no row is added).
        """
        rule = default_rule(get_spec(indicator_id))
        row = len(self._rules)
        self.beginInsertRows(QModelIndex(), row, row)
        self._rules.append(rule)
        self.endInsertRows()
        self.rules_changed.emit()
        return row

    def remove_row(self, row: int) -> None:
        if not 0 <= row < len(self._rules):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._rules[row]
        self.endRemoveRows()
        self.rules_changed.emit()

    def set_enabled(self, row: int, enabled: bool) -> None:
        self.update_rule(row, enabled=enabled)

    def update_rule(self, row: int, **changes: Any) -> None:
        """Replace the rule at ``row`` with a copy carrying ``changes``."""
        if not 0 <= row < len(self._rules):
            return
        old = self._rules[row]
        new = dataclasses.replace(old, **changes)
        if new == old:
            return
        self._rules[row] = new
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(_HEADERS) - 1))
        self.rules_changed.emit()

    def set_condition(self, row: int, condition: Condition) -> None:
        """Change a row's condition, adjusting Value and To to suit it."""
        if not 0 <= row < len(self._rules):
            return
        rule = self._rules[row]
        spec = get_spec(rule.indicator_id)
        value = rule.value
        if condition.needs_value and value is None:
            value = spec.default_value
        to: float | None = None
        if condition.needs_to:
            default_to = spec.default_to if spec.default_to is not None else spec.value_max
            to = rule.to if rule.to is not None else default_to
        self.update_rule(row, condition=condition, value=value, to=to)

    # ── QAbstractTableModel ───────────────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rules)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(_HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _HEADERS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        rule = self._rules[index.row()]
        col = index.column()
        if col == COL_CONDITION or (
            col == COL_VALUE and rule.condition.needs_value
        ) or (col == COL_TO and rule.condition.needs_to):
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rules):
            return None
        rule = self._rules[index.row()]
        spec = get_spec(rule.indicator_id)
        col = index.column()

        if role == RuleRole:
            return rule
        if role == SpecRole:
            return spec
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor(C.TEXT if rule.enabled else C.MUTED)
        if role == Qt.ItemDataRole.ToolTipRole and col == COL_INDICATOR:
            return spec.description
        if role == Qt.ItemDataRole.EditRole:
            if col == COL_CONDITION:
                return rule.condition
            if col == COL_VALUE:
                return rule.value
            if col == COL_TO:
                return rule.to
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole and col in (COL_VALUE, COL_TO):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if col == COL_INDICATOR:
            return spec.name
        if col == COL_CONDITION:
            return rule.condition.label
        if col == COL_VALUE:
            return _format_number(spec, rule.value) if rule.condition.needs_value else _DASH
        if col == COL_TO:
            return _format_number(spec, rule.to) if rule.condition.needs_to else _DASH
        if col == COL_SETTINGS:
            return settings_summary(rule)
        return None

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        row = index.row()
        col = index.column()
        if not self.flags(index) & Qt.ItemFlag.ItemIsEditable:
            return False
        if col == COL_CONDITION and isinstance(value, Condition):
            self.set_condition(row, value)
            return True
        if col == COL_VALUE:
            self.update_rule(row, value=float(value))
            return True
        if col == COL_TO:
            self.update_rule(row, to=float(value))
            return True
        return False
