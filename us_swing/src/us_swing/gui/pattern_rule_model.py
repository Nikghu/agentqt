"""
Module: MD-GUI-016.004.M07 — Price Action Pattern Rule Table Model
Parent SRD: SRD-GUI-016.004
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

from us_swing.core.price_patterns import (
    PatternRule,
    default_pattern_rule,
    get_pattern,
    pattern_settings_summary,
)
from us_swing.gui.indicator_rule_model import RuleRole, SpecRole
from us_swing.gui.theme import C

COL_ON = 0
COL_PATTERN = 1
COL_SETTINGS = 2
COL_REMOVE = 3

_HEADERS = ("On", "Pattern", "Settings", "")


class PatternRuleTableModel(QAbstractTableModel):
    """Holds the dialog's ``PatternRule`` list; no screening logic."""

    rules_changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rules: list[PatternRule] = []

    # ── Public API ────────────────────────────────────────────────────────

    def set_rules(self, rules: list[PatternRule]) -> None:
        self.beginResetModel()
        self._rules = list(rules)
        self.endResetModel()
        self.rules_changed.emit()

    def rules(self) -> list[PatternRule]:
        return list(self._rules)

    def add_rule(self, pattern_id: str) -> int:
        """Append the default rule for a pattern and return its row.

        Raises:
            PatternRuleError: If the pattern id is unknown (no row is added).
        """
        rule = default_pattern_rule(get_pattern(pattern_id))
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
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rules):
            return None
        rule = self._rules[index.row()]
        spec = get_pattern(rule.pattern_id)
        col = index.column()

        if role == RuleRole:
            return rule
        if role == SpecRole:
            return spec
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor(C.TEXT if rule.enabled else C.MUTED)
        if role == Qt.ItemDataRole.ToolTipRole and col == COL_PATTERN:
            return spec.description
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if col == COL_PATTERN:
            return spec.name
        if col == COL_SETTINGS:
            return pattern_settings_summary(rule)
        return None
