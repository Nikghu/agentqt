"""
Module: MD-GUI-015.001.M06 — Indicator Rules Dialog
Parent SRD: SRD-GUI-015.001
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from PyQt6.QtCore import QModelIndex, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.indicator_rules import (
    CATALOGUE,
    IndicatorRuleError,
    Rule,
    get_spec,
    rules_from_config,
    rules_to_config,
)
from us_swing.gui.frameless_dialog import FramelessDialog
from us_swing.gui.indicator_library_model import (
    MIME_INDICATOR,
    LibraryFilterProxy,
    LibraryTreeModel,
    LibraryTreeView,
)
from us_swing.gui.indicator_params_dialog import IndicatorParamsDialog
from us_swing.gui.indicator_rule_delegates import (
    ConditionComboDelegate,
    NumberSpinDelegate,
    RemoveButtonDelegate,
    SettingsDelegate,
    ToggleSwitchDelegate,
)
from us_swing.gui.indicator_rule_model import (
    COL_CONDITION,
    COL_INDICATOR,
    COL_ON,
    COL_REMOVE,
    COL_SETTINGS,
    COL_TO,
    COL_VALUE,
    RuleRole,
    RuleTableModel,
)
from us_swing.gui.theme import C

log = logging.getLogger(__name__)

_COLUMN_WIDTHS = {
    COL_ON: 48,
    COL_CONDITION: 140,
    COL_VALUE: 76,
    COL_TO: 76,
    COL_SETTINGS: 110,
    COL_REMOVE: 32,
}

_SEARCH_QSS = f"""
    QLineEdit {{
        background: {C.INPUT};
        color: {C.TEXT};
        border: 1px solid {C.OVERLAY2};
        border-radius: 4px;
        padding: 0 8px;
        outline: none;
    }}
    QLineEdit:focus {{
        border: 1px solid {C.BLUE};
        outline: none;
    }}
"""


class RuleTableView(QTableView):
    """Rule table that accepts indicators dragged from the library."""

    indicator_dropped = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        viewport = self.viewport()
        if viewport is not None:
            viewport.setAcceptDrops(True)
        self.setDropIndicatorShown(False)

    @staticmethod
    def _has_indicator(event: QDragEnterEvent | QDragMoveEvent | QDropEvent) -> bool:
        mime = event.mimeData()
        return mime is not None and mime.hasFormat(MIME_INDICATOR)

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        if event is None:
            return
        if self._has_indicator(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent | None) -> None:
        if event is None:
            return
        if self._has_indicator(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent | None) -> None:
        if event is None or not self._has_indicator(event):
            return
        mime = event.mimeData()
        assert mime is not None
        raw = mime.data(MIME_INDICATOR).data().decode("utf-8")
        event.acceptProposedAction()
        self.indicator_dropped.emit(raw)


class IndicatorRulesDialog(FramelessDialog):
    """Library of indicators plus an editable list of screening rules."""

    def __init__(self, config: dict[str, Any] | None, parent: QWidget | None = None) -> None:
        super().__init__("Indicator Filters", min_width=960, min_height=600, parent=parent)
        self.setObjectName("indicator_rules_dialog")
        self._benchmark = str((config or {}).get("benchmark_symbol", "SPY"))

        self.tree_model = LibraryTreeModel(self)
        self._proxy = LibraryFilterProxy(self)
        self._proxy.setSourceModel(self.tree_model)
        self._model = RuleTableModel(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_library_pane())
        splitter.addWidget(self._build_rules_pane())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 710])
        self.content_layout().addWidget(splitter, 1)
        self.content_layout().addLayout(self._build_footer())

        # rules_changed → dialog → _refresh (keeps header and in-use tags current)
        self._unloaded_config: dict[str, Any] | None = None
        self._model.rules_changed.connect(self._refresh)
        self._load(config)
        # model → rules_changed → dialog → forget the unreadable saved config once edited
        self._model.rules_changed.connect(self._forget_unloaded_config)
        self.tree.expandAll()

    # ── Public API ────────────────────────────────────────────────────────

    def rules(self) -> list[Rule]:
        return self._model.rules()

    def get_config(self) -> dict[str, Any]:
        """Return the saved-config dict for the current rule list.

        If the saved rules could not be read and the user changed nothing, the
        original config is returned so pressing OK does not erase it.
        """
        if self._unloaded_config is not None:
            return dict(self._unloaded_config)
        return rules_to_config(self._model.rules(), self._benchmark)

    # ── Construction ──────────────────────────────────────────────────────

    def _build_library_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(8)

        self.search = QLineEdit()
        self.search.setObjectName("rule_search")
        self.search.setPlaceholderText(f"Search {len(CATALOGUE)} indicators")
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet(_SEARCH_QSS)
        lay.addWidget(self.search)

        self.tree = LibraryTreeView()
        self.tree.setObjectName("rule_library_tree")
        self.tree.setModel(self._proxy)
        lay.addWidget(self.tree, 1)

        # search → textChanged → dialog → _on_search
        self.search.textChanged.connect(self._on_search)
        # tree → indicator_activated → dialog → _add_indicator
        self.tree.indicator_activated.connect(self._add_indicator)
        return pane

    def _build_rules_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(8, 0, 0, 0)
        lay.setSpacing(8)

        self.header = QLabel()
        self.header.setObjectName("rule_header")
        self.header.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 11px;")
        lay.addWidget(self.header)

        self.table = RuleTableView()
        self.table.setObjectName("rule_table")
        self.table.setModel(self._model)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        v_header = self.table.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(C.INPUT_H)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.DoubleClicked
        )
        self.table.setMouseTracking(True)
        table_viewport = self.table.viewport()
        if table_viewport is not None:
            table_viewport.setMouseTracking(True)

        hdr = self.table.horizontalHeader()
        if hdr is not None:
            hdr.setSectionResizeMode(COL_INDICATOR, QHeaderView.ResizeMode.Stretch)
            for col, _width in _COLUMN_WIDTHS.items():
                hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        for col, width in _COLUMN_WIDTHS.items():
            self.table.setColumnWidth(col, width)

        self._settings_delegate = SettingsDelegate(self.table)
        number_delegate = NumberSpinDelegate(self.table)
        self.table.setItemDelegateForColumn(COL_ON, ToggleSwitchDelegate(self.table))
        self.table.setItemDelegateForColumn(COL_CONDITION, ConditionComboDelegate(self.table))
        self.table.setItemDelegateForColumn(COL_VALUE, number_delegate)
        self.table.setItemDelegateForColumn(COL_TO, number_delegate)
        self.table.setItemDelegateForColumn(COL_SETTINGS, self._settings_delegate)
        self.table.setItemDelegateForColumn(COL_REMOVE, RemoveButtonDelegate(self.table))
        lay.addWidget(self.table, 1)

        # table → indicator_dropped → dialog → _add_indicator
        self.table.indicator_dropped.connect(self._add_indicator)
        # settings delegate → edit_requested → dialog → _on_edit_requested
        self._settings_delegate.edit_requested.connect(self._on_edit_requested)
        return pane

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        hint = QLabel("Double-click an indicator to add a row")
        hint.setStyleSheet(f"color: {C.MUTED}; font-size: 11px;")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("rule_cancel_btn")
        ok_btn = QPushButton("✔  OK")
        ok_btn.setObjectName("btn_green")
        ok_btn.setDefault(True)
        self.ok_btn = ok_btn
        for btn in (cancel_btn, ok_btn):
            btn.setFixedWidth(80)
            btn.setStyleSheet("QPushButton { outline: none; }")
        row.addWidget(hint)
        row.addStretch()
        row.addWidget(cancel_btn)
        row.addWidget(ok_btn)

        # cancel_btn → clicked → dialog → reject
        cancel_btn.clicked.connect(self.reject)
        # ok_btn → clicked → dialog → accept
        ok_btn.clicked.connect(self.accept)
        return row

    # ── Behaviour ─────────────────────────────────────────────────────────

    def _load(self, config: dict[str, Any] | None) -> None:
        try:
            rules = rules_from_config(config or {})
        except IndicatorRuleError:
            log.warning(
                "[Screener] Saved indicator rules could not be loaded — "
                "starting with an empty list; the saved rules are kept unless you edit them"
            )
            self._unloaded_config = dict(config or {})
            rules = []
        self._model.set_rules(rules)

    def _forget_unloaded_config(self) -> None:
        self._unloaded_config = None

    def _on_search(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)
        if text:
            self.tree.expandAll()

    def _add_indicator(self, indicator_id: str) -> None:
        try:
            spec = get_spec(indicator_id)
        except IndicatorRuleError:
            log.warning("[Screener] Unknown indicator cannot be added to the rule list")
            return
        if not spec.available:
            return
        row = self._model.add_rule(indicator_id)
        self.table.scrollTo(self._model.index(row, COL_INDICATOR))

    def _on_edit_requested(self, row: int) -> None:
        # Open the panel after the table's mouse handler has returned
        QTimer.singleShot(0, lambda: self._edit_params(row))

    def _edit_params(self, row: int) -> None:
        index: QModelIndex = self._model.index(row, COL_INDICATOR)
        rule: Rule | None = index.data(RuleRole)
        if rule is None:
            return
        dlg = IndicatorParamsDialog(get_spec(rule.indicator_id), rule.params, parent=self)
        viewport = self.table.viewport()
        if viewport is not None:
            cell = self.table.visualRect(self._model.index(row, COL_SETTINGS))
            dlg.place_under(viewport.mapToGlobal(cell.bottomRight()))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._model.update_rule(row, params=dlg.get_params())

    def _refresh(self) -> None:
        rules = self._model.rules()
        self.tree_model.set_usage(Counter(r.indicator_id for r in rules))
        enabled = sum(1 for r in rules if r.enabled)
        self.header.setText(f"{len(rules)} rules · {enabled} on · match all")
