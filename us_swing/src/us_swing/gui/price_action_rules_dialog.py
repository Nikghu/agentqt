"""
Module: MD-GUI-016.001.M08 — Price Action Rules Dialog
Parent SRD: SRD-GUI-016.001
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from PyQt6.QtCore import QModelIndex, Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.price_patterns import (
    DEFAULT_THRESHOLD,
    PATTERNS,
    PatternCategory,
    PatternRule,
    PatternRuleError,
    get_pattern,
    pattern_rules_from_config,
    pattern_rules_to_config,
)
from us_swing.gui.frameless_dialog import FramelessDialog
from us_swing.gui.indicator_library_model import (
    LibraryFilterProxy,
    LibraryTreeModel,
    LibraryTreeView,
)
from us_swing.gui.indicator_params_dialog import IndicatorParamsDialog
from us_swing.gui.indicator_rule_delegates import (
    RemoveButtonDelegate,
    SettingsDelegate,
    ToggleSwitchDelegate,
)
from us_swing.gui.indicator_rule_model import RuleRole
from us_swing.gui.indicator_rules_dialog import RuleTableView
from us_swing.gui.pattern_rule_model import (
    COL_ON,
    COL_PATTERN,
    COL_REMOVE,
    COL_SETTINGS,
    PatternRuleTableModel,
)
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C

log = logging.getLogger(__name__)

_COLUMN_WIDTHS = {COL_ON: 48, COL_SETTINGS: 150, COL_REMOVE: 32}

_INPUT_QSS = f"""
    QLineEdit, QSpinBox {{
        background: {C.INPUT};
        color: {C.TEXT};
        border: 1px solid {C.OVERLAY2};
        border-radius: 4px;
        padding: 0 8px;
        outline: none;
    }}
    QLineEdit:focus, QSpinBox:focus {{
        border: 1px solid {C.BLUE};
        outline: none;
    }}
"""


class PriceActionRulesDialog(FramelessDialog):
    """Library of price action patterns plus an editable list of pattern rules."""

    def __init__(self, config: dict[str, Any] | None, parent: QWidget | None = None) -> None:
        super().__init__("Price Action Patterns", min_width=860, min_height=560, parent=parent)
        self.setObjectName("price_action_rules_dialog")

        self.tree_model = LibraryTreeModel(self, entries=PATTERNS, categories=PatternCategory)
        self._proxy = LibraryFilterProxy(self)
        self._proxy.setSourceModel(self.tree_model)
        self._model = PatternRuleTableModel(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_library_pane())
        splitter.addWidget(self._build_rules_pane())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 610])
        self.content_layout().addWidget(splitter, 1)
        self.content_layout().addLayout(self._build_footer())

        # rules_changed → dialog → _refresh (keeps header and in-use tags current)
        self._unloaded_config: dict[str, Any] | None = None
        self._model.rules_changed.connect(self._refresh)
        self._load(config)
        # model / threshold edits → dialog → forget the unreadable saved config
        self._model.rules_changed.connect(self._forget_unloaded_config)
        self.threshold_spin.valueChanged.connect(self._forget_unloaded_config)
        self.tree.expandAll()

    # ── Public API ────────────────────────────────────────────────────────

    def rules(self) -> list[PatternRule]:
        return self._model.rules()

    def threshold(self) -> float:
        """Pass threshold as a fraction (0–1)."""
        return self.threshold_spin.value() / 100.0

    def get_config(self) -> dict[str, Any]:
        """Return the saved-config dict for the current rules and threshold.

        If the saved rules could not be read and the user changed nothing, the
        original config is returned so pressing OK does not erase it.
        """
        if self._unloaded_config is not None:
            return dict(self._unloaded_config)
        return pattern_rules_to_config(self._model.rules(), self.threshold())

    # ── Construction ──────────────────────────────────────────────────────

    def _build_library_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(8)

        self.search = QLineEdit()
        self.search.setObjectName("rule_search")
        self.search.setPlaceholderText(f"Search {len(PATTERNS)} patterns")
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet(_INPUT_QSS)
        lay.addWidget(self.search)

        self.tree = LibraryTreeView()
        self.tree.setObjectName("rule_library_tree")
        self.tree.setModel(self._proxy)
        lay.addWidget(self.tree, 1)

        # search → textChanged → dialog → _on_search
        self.search.textChanged.connect(self._on_search)
        # tree → indicator_activated → dialog → _add_pattern
        self.tree.indicator_activated.connect(self._add_pattern)
        return pane

    def _build_rules_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(8, 0, 0, 0)
        lay.setSpacing(8)
        lay.addLayout(self._build_header())

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
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMouseTracking(True)
        table_viewport = self.table.viewport()
        if table_viewport is not None:
            table_viewport.setMouseTracking(True)

        hdr = self.table.horizontalHeader()
        if hdr is not None:
            hdr.setSectionResizeMode(COL_PATTERN, QHeaderView.ResizeMode.Stretch)
            for col in _COLUMN_WIDTHS:
                hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        for col, width in _COLUMN_WIDTHS.items():
            self.table.setColumnWidth(col, width)

        self._settings_delegate = SettingsDelegate(self.table)
        self.table.setItemDelegateForColumn(COL_ON, ToggleSwitchDelegate(self.table))
        self.table.setItemDelegateForColumn(COL_SETTINGS, self._settings_delegate)
        self.table.setItemDelegateForColumn(COL_REMOVE, RemoveButtonDelegate(self.table))
        lay.addWidget(self.table, 1)

        # table → indicator_dropped → dialog → _add_pattern
        self.table.indicator_dropped.connect(self._add_pattern)
        # settings delegate → edit_requested → dialog → _on_edit_requested
        self._settings_delegate.edit_requested.connect(self._on_edit_requested)
        return pane

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        muted = f"color: {C.SUBTEXT}; font-size: 11px;"

        self.header = QLabel()
        self.header.setObjectName("rule_header")
        self.header.setStyleSheet(muted)

        self.threshold_spin = QSpinBox()
        self.threshold_spin.setObjectName("threshold_spin")
        self.threshold_spin.setRange(0, 100)
        self.threshold_spin.setSingleStep(5)
        self.threshold_spin.setSuffix(" %")
        self.threshold_spin.setFixedWidth(72)
        self.threshold_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.threshold_spin.setStyleSheet(_INPUT_QSS)

        pass_lbl = QLabel("Pass when ≥")
        match_lbl = QLabel("of patterns match")
        for lbl in (pass_lbl, match_lbl):
            lbl.setStyleSheet(muted)

        row.addWidget(self.header)
        row.addStretch()
        row.addWidget(pass_lbl)
        row.addWidget(self.threshold_spin)
        row.addWidget(match_lbl)
        return row

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        hint = QLabel("Double-click a pattern to add a row")
        hint.setStyleSheet(f"color: {C.MUTED}; font-size: 11px;")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("rule_cancel_btn")
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("btn_green")
        set_icon(ok_btn, "check", "add")
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
            rules, threshold = pattern_rules_from_config(config or {})
        except PatternRuleError:
            log.warning(
                "[Screener] Saved price action patterns could not be loaded and are kept "
                "unless you edit the list"
            )
            self._unloaded_config = dict(config or {})
            rules, threshold = [], DEFAULT_THRESHOLD
        self.threshold_spin.setValue(min(max(round(threshold * 100), 0), 100))
        self._model.set_rules(rules)

    def _forget_unloaded_config(self) -> None:
        self._unloaded_config = None

    def _on_search(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)
        if text:
            self.tree.expandAll()

    def _add_pattern(self, pattern_id: str) -> None:
        try:
            get_pattern(pattern_id)
        except PatternRuleError:
            log.warning("[Screener] Unknown price action pattern cannot be added to the list")
            return
        row = self._model.add_rule(pattern_id)
        self.table.scrollTo(self._model.index(row, COL_PATTERN))

    def _on_edit_requested(self, row: int) -> None:
        # Open the panel after the table's mouse handler has returned
        QTimer.singleShot(0, lambda: self._edit_params(row))

    def _edit_params(self, row: int) -> None:
        index: QModelIndex = self._model.index(row, COL_PATTERN)
        rule: PatternRule | None = index.data(RuleRole)
        if rule is None:
            return
        dlg = IndicatorParamsDialog(get_pattern(rule.pattern_id), rule.params, parent=self)
        viewport = self.table.viewport()
        if viewport is not None:
            cell = self.table.visualRect(self._model.index(row, COL_SETTINGS))
            dlg.place_under(viewport.mapToGlobal(cell.bottomRight()))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._model.update_rule(row, params=dlg.get_params())

    def _refresh(self) -> None:
        rules = self._model.rules()
        self.tree_model.set_usage(Counter(r.pattern_id for r in rules))
        enabled = sum(1 for r in rules if r.enabled)
        noun = "pattern" if len(rules) == 1 else "patterns"
        self.header.setText(f"{len(rules)} {noun} · {enabled} on")
