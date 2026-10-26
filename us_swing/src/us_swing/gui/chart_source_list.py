"""
Module: MD-GUI-026.002.M02 — Chart source list
Parent SRD: SRD-GUI-026.002

Watchlist, Screener and Trades symbols beside the Charts chart, with a filter box.
Opens on the first non-empty tab in the order Trades, Screener, Watchlist (SRD-GUI-026.013).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.app_service import AppService
from us_swing.gui.screener_views import ChipGroup
from us_swing.gui.theme import active_palette

TABS: tuple[tuple[str, str], ...] = (
    ("Watchlist", "watchlist"), ("Screener", "screener"), ("Trades", "trades"),
)
DEFAULT_ORDER = ("trades", "screener", "watchlist")
EMPTY_TEXT = {
    "watchlist": "Watchlist is empty",
    "screener": "No screener results yet",
    "trades": "No open trades",
}
_SYMBOL_ROLE = Qt.ItemDataRole.UserRole


@dataclass(frozen=True)
class SourceRow:
    """One symbol line: sub-line, last price and change % (None when unknown)."""

    symbol: str
    sub: str = ""
    last: float | None = None
    change_pct: float | None = None


def source_rows(svc: AppService, tab: str) -> list[SourceRow]:
    """Rows for ``tab``: watchlist, latest screener results by score, or open positions."""
    if tab == "watchlist":
        return [
            SourceRow(i.symbol, "", i.ltp or None, i.change_pct if i.ltp else None)
            for i in svc.get_watchlist_items()
        ]
    if tab == "screener":
        return [
            SourceRow(e.symbol,
                      "Manual pick" if e.run_type == "pick" else
                      f"{e.screener_name} · {e.score:.2f}")
            for e in sorted(svc.get_latest_screener_results(), key=lambda e: -e.score)
        ]
    rows = []
    for p in svc.get_positions():
        if p.quantity <= 0:
            continue
        side = "Short" if p.direction == "SHORT" else "Long"
        rows.append(SourceRow(p.symbol, f"{side} {p.quantity} sh",
                              p.current_price or None, p.pnl_pct if p.current_price else None))
    return rows


def filter_rows(rows: Iterable[SourceRow], text: str) -> list[SourceRow]:
    """Keep rows whose symbol contains ``text`` (case-insensitive)."""
    needle = text.strip().upper()
    return [r for r in rows if needle in r.symbol.upper()]


class _RowWidget(QWidget):
    """Symbol and sub-line on the left, last price and change on the right."""

    def __init__(self, row: SourceRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # The list paints the row (hover, selection); labels must not paint their own box.
        self.setStyleSheet("QLabel { background: transparent; }")
        ct: Any = active_palette()
        line = QHBoxLayout(self)
        line.setContentsMargins(10, 5, 10, 5)
        left = QVBoxLayout()
        left.setSpacing(0)
        symbol = QLabel(row.symbol)
        symbol.setStyleSheet("font-weight:600;")
        left.addWidget(symbol)
        sub = QLabel(row.sub)
        sub.setStyleSheet(f"color:{ct.SUBTEXT}; font-size:8pt;")
        left.addWidget(sub)
        line.addLayout(left, 1)
        right = QVBoxLayout()
        right.setSpacing(0)
        last = QLabel("" if row.last is None else f"{row.last:,.2f}")
        last.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(last)
        change = QLabel("" if row.change_pct is None else f"{row.change_pct:+.2f}%")
        change.setAlignment(Qt.AlignmentFlag.AlignRight)
        colour = ct.RED if (row.change_pct or 0.0) < 0 else ct.GREEN
        change.setStyleSheet(f"color:{colour}; font-size:8pt;")
        right.addWidget(change)
        line.addLayout(right)
        last.setVisible(row.last is not None)
        change.setVisible(row.change_pct is not None)


class SourceList(QWidget):
    """Tabs, filter and symbol list; clicking a row emits ``symbol_selected``."""

    symbol_selected = pyqtSignal(str)

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._rows: list[SourceRow] = []
        self.user_chose = False   # set once the user clicks a tab or a row
        self._selected = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        self.tabs = ChipGroup(list(TABS))
        self.tabs.changed.connect(self._on_tab)
        root.addWidget(self.tabs)

        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("Filter")
        self.filter_box.setClearButtonEnabled(True)
        self.filter_box.textChanged.connect(self._fill)
        root.addWidget(self.filter_box)

        self.list = QListWidget()
        self.list.setObjectName("chart_source_list")
        self.list.itemClicked.connect(self._on_item)
        root.addWidget(self.list, 1)
        self.empty_lbl = QLabel()
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setWordWrap(True)
        root.addWidget(self.empty_lbl, 1)

        svc.watchlist_updated.connect(lambda: self._refresh_if("watchlist"))
        svc.positions_updated.connect(lambda: self._refresh_if("trades"))
        svc.screener_results_updated.connect(lambda _e: self._refresh_if("screener"))
        self.refresh()

    @property
    def tab(self) -> str:
        return self.tabs.value or "watchlist"

    def refresh(self) -> None:
        """Reload the rows of the current tab."""
        self._rows = source_rows(self._svc, self.tab)
        self._fill()

    def pick_default(self) -> str | None:
        """Show the first non-empty tab in ``DEFAULT_ORDER``; return its first symbol."""
        for tab in DEFAULT_ORDER:
            rows = source_rows(self._svc, tab)
            if rows:
                if tab != self.tab:   # the current tab already refreshes on its own signal
                    for button, (_label, value) in zip(self.tabs.buttons, TABS):
                        button.setChecked(value == tab)
                    self._rows = rows
                    self._fill()
                return rows[0].symbol
        return None

    def select_symbol(self, symbol: str) -> bool:
        """Highlight ``symbol`` when it is in the list; returns whether it was found."""
        self._selected = symbol
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item is not None and item.data(_SYMBOL_ROLE) == symbol:
                self.list.setCurrentItem(item)
                return True
        self.list.clearSelection()
        self.list.setCurrentItem(None)
        return False

    def visible_symbols(self) -> list[str]:
        return [str(self.list.item(i).data(_SYMBOL_ROLE))  # type: ignore[union-attr]
                for i in range(self.list.count())]

    def _refresh_if(self, tab: str) -> None:
        if self.tab == tab:
            self.refresh()

    def _on_tab(self) -> None:
        self.user_chose = True
        self.refresh()

    def _fill(self) -> None:
        self.list.clear()
        rows = filter_rows(self._rows, self.filter_box.text())
        for row in rows:
            item = QListWidgetItem()
            item.setData(_SYMBOL_ROLE, row.symbol)
            widget = _RowWidget(row)
            item.setSizeHint(widget.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)
        has_rows = bool(rows)
        self.list.setVisible(has_rows)
        self.empty_lbl.setVisible(not has_rows)
        self.empty_lbl.setText(EMPTY_TEXT[self.tab] if not self._rows else "No match")
        ct: Any = active_palette()
        self.empty_lbl.setStyleSheet(f"color:{ct.SUBTEXT};")
        if self._selected:
            self.select_symbol(self._selected)

    def _on_item(self, item: QListWidgetItem) -> None:
        symbol = str(item.data(_SYMBOL_ROLE))
        self._selected = symbol
        self.user_chose = True
        self.symbol_selected.emit(symbol)
