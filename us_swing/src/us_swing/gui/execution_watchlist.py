"""
Module: MD-GUI-024.002.M02 — Execution watchlist
Parent SRD: SRD-GUI-024.002

Latest screener output grouped by source: manual picks first, then one group
per screener.  Rows show symbol, last 3m close and score.  Keeps the manual
pick input (SRD-GUI-004.010) and pick removal (SRD-GUI-004.011).
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QStringListModel, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QCompleter,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.data.models import FilteredStockEntry
from us_swing.gui.app_service import AppService
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C

COL_SYMBOL, COL_LTP, COL_SCORE = 0, 1, 2
MANUAL = "Manual"
_SYMBOL_ROLE = Qt.ItemDataRole.UserRole
_PICK_ROLE = Qt.ItemDataRole.UserRole + 1
_NOT_READY = QColor(180, 60, 60, 70)


def group_entries(
    entries: list[FilteredStockEntry],
) -> list[tuple[str, list[FilteredStockEntry]]]:
    """Manual picks first, then screener names A→Z; rows by score, highest first."""
    groups: dict[str, list[FilteredStockEntry]] = {}
    for e in entries:
        key = MANUAL if e.run_type == "pick" else e.screener_name or "Other"
        groups.setdefault(key, []).append(e)
    names = sorted(k for k in groups if k != MANUAL)
    if MANUAL in groups:
        names.insert(0, MANUAL)
    return [
        (name, groups[name] if name == MANUAL
         else sorted(groups[name], key=lambda e: e.score, reverse=True))
        for name in names
    ]


class _GroupRow(QWidget):
    """Group header: coloured name on the left, count on the right."""

    def __init__(self, name: str, count: int, colour: str) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 0, 8, 0)
        title = QLabel(name.replace("_", " "))
        title.setStyleSheet(f"color:{colour}; font-weight:bold; background:transparent;")
        num = QLabel(str(count))
        num.setStyleSheet(f"color:{C.SUBTEXT}; background:transparent;")
        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(num)


class WatchlistPane(QWidget):
    """Grouped watchlist (SRD-GUI-024.002)."""

    symbol_selected = pyqtSignal(str)

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(200)
        self._svc = svc
        self._readiness: dict[str, bool | None] = {}

        # ── Manual pick input (SRD-GUI-004.010) ────────────────────────────────
        self._pick_input = QLineEdit()
        self._pick_input.setPlaceholderText("Add symbol…")
        self._pick_input.returnPressed.connect(self._on_add_pick)
        # Suggestions match symbol or company name, e.g. "dell" → "DELL — Dell Technologies"
        self._pick_completer = QCompleter(self)
        self._pick_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._pick_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._pick_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._pick_completer.setMaxVisibleItems(12)
        popup = self._pick_completer.popup()
        assert popup is not None
        popup.setStyleSheet(
            f"QAbstractItemView {{ background:{C.SURFACE}; color:{C.TEXT};"
            f" border:1px solid {C.OVERLAY}; selection-background-color:{C.OVERLAY};"
            f" selection-color:{C.TEXT}; font-size:8pt; outline:none; }}"
        )
        self._pick_input.setCompleter(self._pick_completer)
        self._refresh_pick_suggestions()
        svc.sp500_updated.connect(self._refresh_pick_suggestions)
        add_btn = QPushButton()
        set_icon(add_btn, "plus", "add")
        add_btn.setToolTip("Add symbol")
        add_btn.setAccessibleName("Add symbol")
        add_btn.setFixedWidth(C.BTN_H + 4)
        add_btn.clicked.connect(self._on_add_pick)
        pick_row = QHBoxLayout()
        pick_row.setContentsMargins(10, 10, 10, 6)
        pick_row.setSpacing(6)
        pick_row.addWidget(self._pick_input, 1)
        pick_row.addWidget(add_btn)

        # ── Tree ───────────────────────────────────────────────────────────────
        self.tree = QTreeWidget()
        self.tree.setObjectName("exec_watch")
        self.tree.setColumnCount(3)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(0)
        self.tree.setItemsExpandable(False)
        self.tree.setUniformRowHeights(True)
        header = self.tree.header()
        assert header is not None
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_SYMBOL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_LTP, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_SCORE, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_LTP, 74)
        header.resizeSection(COL_SCORE, 60)
        self.tree.currentItemChanged.connect(self._on_current_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)

        self.empty_lbl = QLabel("No screener results yet.\nRun a preset in the Screener tab.")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 9pt; padding: 20px;")
        self.empty_lbl.setWordWrap(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(pick_row)
        root.addWidget(self.tree, 1)
        root.addWidget(self.empty_lbl, 1)

        svc.screener_results_updated.connect(self.load)
        svc.candle_readiness_updated.connect(self.set_candle_readiness)
        svc.live_bar_data_updated.connect(self._refresh_ltp)
        self.load(svc.get_latest_screener_results())

    # ── Loading ───────────────────────────────────────────────────────────────

    def load(self, entries: list[FilteredStockEntry]) -> None:
        """Rebuild the groups; keep the selected symbol when it is still listed."""
        current = self.current_symbol()
        self.tree.blockSignals(True)
        self.tree.clear()
        colours = [C.TEAL, C.BLUE, C.MAUVE, C.GREEN]
        screener_idx = 0
        for name, rows in group_entries(entries):
            if name == MANUAL:
                colour = C.SUBTEXT
            else:
                colour = colours[screener_idx % len(colours)]
                screener_idx += 1
            group = QTreeWidgetItem(self.tree)
            group.setFlags(Qt.ItemFlag.ItemIsEnabled)
            group.setFirstColumnSpanned(True)
            self.tree.setItemWidget(group, COL_SYMBOL, _GroupRow(name, len(rows), colour))
            for entry in rows:
                self._add_row(group, entry)
            group.setExpanded(True)
        self.tree.blockSignals(False)

        has_rows = bool(entries)
        self.tree.setVisible(has_rows)
        self.empty_lbl.setVisible(not has_rows)
        self._select(current or self.get_top_symbol())

    def _add_row(self, group: QTreeWidgetItem, entry: FilteredStockEntry) -> None:
        pick = entry.run_type == "pick"
        item = QTreeWidgetItem(group)
        item.setData(COL_SYMBOL, _SYMBOL_ROLE, entry.symbol)
        item.setData(COL_SYMBOL, _PICK_ROLE, pick)
        item.setText(COL_SYMBOL, entry.symbol)
        item.setText(COL_LTP, self._ltp_text(entry.symbol))
        item.setTextAlignment(COL_LTP, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setTextAlignment(
            COL_SCORE, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        if pick:
            item.setText(COL_SCORE, "✕")
            item.setForeground(COL_SCORE, QBrush(QColor(C.RED)))
            item.setToolTip(COL_SCORE, "Remove from watchlist")
        else:
            item.setText(COL_SCORE, f"{entry.score:.2f}")
            item.setForeground(COL_SCORE, QBrush(QColor(C.BLUE)))
        item.setForeground(COL_LTP, QBrush(QColor(C.SUBTEXT)))
        self._paint_readiness(item)

    def _ltp_text(self, symbol: str) -> str:
        price = self._svc.get_latest_close(symbol, "3m")
        return f"{price:,.2f}" if price is not None else "—"

    # ── Queries ───────────────────────────────────────────────────────────────

    def _symbol_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []
        for g in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(g)
            if group is None:
                continue
            items.extend(c for c in (group.child(i) for i in range(group.childCount())) if c)
        return items

    def get_top_symbol(self) -> str | None:
        """First symbol of the first group, or None when empty."""
        items = self._symbol_items()
        return str(items[0].data(COL_SYMBOL, _SYMBOL_ROLE)) if items else None

    def current_symbol(self) -> str | None:
        item = self.tree.currentItem()
        if item is None or item.parent() is None:
            return None
        return str(item.data(COL_SYMBOL, _SYMBOL_ROLE))

    def group_names(self) -> list[tuple[str, int]]:
        """(name, count) per group, in display order."""
        out: list[tuple[str, int]] = []
        for g in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(g)
            widget = self.tree.itemWidget(group, COL_SYMBOL) if group else None
            labels = widget.findChildren(QLabel) if widget else []
            if group is not None and labels:
                out.append((labels[0].text(), group.childCount()))
        return out

    def _select(self, symbol: str | None) -> None:
        for item in self._symbol_items():
            if item.data(COL_SYMBOL, _SYMBOL_ROLE) == symbol:
                self.tree.setCurrentItem(item)
                return

    # ── Readiness / live price ────────────────────────────────────────────────

    def set_candle_readiness(self, report: dict[str, bool | None]) -> None:
        self._readiness.update(report)
        for item in self._symbol_items():
            self._paint_readiness(item)

    def _paint_readiness(self, item: QTreeWidgetItem) -> None:
        not_ready = self._readiness.get(str(item.data(COL_SYMBOL, _SYMBOL_ROLE))) is False
        brush = QBrush(_NOT_READY) if not_ready else QBrush()
        for col in (COL_SYMBOL, COL_LTP, COL_SCORE):
            item.setBackground(col, brush)

    def _refresh_ltp(self, symbol: str) -> None:
        for item in self._symbol_items():
            if item.data(COL_SYMBOL, _SYMBOL_ROLE) == symbol:
                item.setText(COL_LTP, self._ltp_text(symbol))

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_current_changed(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        if current is not None and current.parent() is not None:
            self.symbol_selected.emit(str(current.data(COL_SYMBOL, _SYMBOL_ROLE)))

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if column == COL_SCORE and item.data(COL_SYMBOL, _PICK_ROLE):
            self._svc.remove_manual_pick(str(item.data(COL_SYMBOL, _SYMBOL_ROLE)))

    def _refresh_pick_suggestions(self) -> None:
        items = [f"{r.symbol} — {r.name}" for r in self._svc.get_sp500_universe()]
        self._pick_completer.setModel(QStringListModel(items, self._pick_completer))

    def _on_add_pick(self) -> None:
        symbol = self._pick_input.text().split(" — ")[0]
        error = self._svc.add_manual_pick(symbol)
        if error is None:
            self._pick_input.clear()
            return
        QToolTip.showText(
            self._pick_input.mapToGlobal(QPoint(0, self._pick_input.height())),
            error,
            self._pick_input,
        )
