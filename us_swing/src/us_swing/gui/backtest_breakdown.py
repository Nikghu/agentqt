"""
Module: MD-GUI-031.062.M12 — Backtest breakdown
Parent SRD: SRD-GUI-031.062, SRD-GUI-031.063, SRD-GUI-031.064, SRD-GUI-031.065,
            SRD-GUI-031.066

Breakdown of one report's trades by a chip-picked group: natural order for ordered groups,
readable names, win rate meter, zero-line P&L bar, an All trades total, small groups greyed,
Stock collapsed to best / worst with search and a minimum-trades filter. Clicking a row asks
the Trade list to show only that group's trades.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd
from PyQt6.QtCore import QModelIndex, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.backtest.steps.report import HOLD_BUCKETS, Report, breakdown
from us_swing.gui.backtest_trade_list import trade_keys
from us_swing.gui.screener_views import ChipGroup
from us_swing.gui.theme import C

CHIPS = (("exit_reason", "Exit reason"), ("hour", "Entry hour"), ("weekday", "Weekday"),
         ("hold", "Hold time"), ("rank", "Rank"), ("sector", "Sector"), ("symbol", "Stock"),
         ("strategy", "Strategy"), ("score_bucket", "Score"))
HEADERS = ["Group", "Trades", "Win rate", "Avg P&L", "Net P&L", "Loss ◂ 0 ▸ Gain"]
ORDERED = frozenset({"hour", "weekday", "hold", "rank", "score_bucket"})
MIN_TRADES = 5
COLLAPSE_ABOVE = 10
TOTAL = "All trades"
_EXIT_NAMES = {"stop": "Stop loss", "strategy": "Strategy exit", "end_of_test": "End of test"}
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_WIN_COL, _BAR_COL = 2, 5
_VALUE = Qt.ItemDataRole.UserRole
_KIND = Qt.ItemDataRole.UserRole + 1


@dataclass(frozen=True)
class Row:
    """One breakdown row; ``trades == 0`` marks an empty slot."""

    key: str
    label: str
    trades: int
    net: float
    win: float
    avg: float


def group_label(by: str, value: str) -> str:
    """Readable name for a group value; exit reasons get plain words."""
    if by == "exit_reason":
        return _EXIT_NAMES.get(value, value.replace("_", " ").capitalize())
    return value


def _slots(by: str, values: Sequence[str]) -> list[str]:
    if by == "hour":
        hours = [int(v[:2]) for v in values]
        return [f"{h:02d}:00" for h in range(min(hours), max(hours) + 1)]
    if by == "weekday":
        return [d for i, d in enumerate(_WEEKDAYS) if i < 5 or d in values]
    if by == "hold":
        return [name for _limit, name in HOLD_BUCKETS]
    if by == "rank":
        return [str(r) for r in range(1, max(int(v) for v in values) + 1)]
    return sorted(values, key=lambda v: float(v.split("–")[0]))


def rows(frame: pd.DataFrame, by: str) -> list[Row]:
    """Breakdown rows: natural order with empty slots for ordered groups, else best first."""
    data = {str(g): Row(str(g), group_label(by, str(g)), int(n), float(p), float(w), float(a))
            for g, n, p, w, a in frame.itertuples(index=False)}
    if by not in ORDERED or not data:
        return list(data.values())
    return [data.get(key) or Row(key, group_label(by, key), 0, 0.0, 0.0, 0.0)
            for key in _slots(by, list(data))]


def visible(all_rows: Sequence[Row], query: str, min_trades: int,
            show_all: bool) -> list[Row | None]:
    """Rows after search and minimum trades; long lists keep best 5 and worst 5 (None = gap)."""
    text = query.strip().upper()
    kept = [r for r in all_rows if r.trades >= min_trades and text in r.key.upper()]
    if show_all or text or len(kept) <= COLLAPSE_ABOVE:
        return list(kept)
    return [*kept[:5], None, *kept[-5:]]


class _CellDelegate(QStyledItemDelegate):
    """Win rate meter beside the text and the zero-line P&L bar."""

    def paint(self, painter: QPainter | None, option: QStyleOptionViewItem,
              index: QModelIndex) -> None:
        super().paint(painter, option, index)
        kind, value = index.data(_KIND), index.data(_VALUE)
        if painter is None or kind is None or value is None:
            return
        rect: QRect = option.rect
        dim = bool(index.data(Qt.ItemDataRole.ToolTipRole))
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        if kind == "win":
            track = QRect(rect.right() - 52, rect.center().y() - 2, 44, 5)
            painter.setBrush(QColor(C.OVERLAY))
            painter.drawRoundedRect(track, 2, 2)
            fill = QColor(C.BLUE)
            fill.setAlphaF(0.4 if dim else 1.0)
            painter.setBrush(fill)
            painter.drawRoundedRect(QRect(track.left(), track.top(),
                                          round(44 * float(value)), 5), 2, 2)
        else:
            mid = rect.center().x()
            half = rect.width() // 2 - 8
            painter.setBrush(QColor(C.OVERLAY2))
            painter.drawRect(mid, rect.top() + 4, 1, rect.height() - 8)
            width = round(half * min(1.0, abs(float(value))))
            colour = QColor(C.GREEN if value >= 0 else C.RED)
            colour.setAlphaF(0.4 if dim else 1.0)
            painter.setBrush(colour)
            left = mid + 1 if value >= 0 else mid - width
            painter.drawRoundedRect(QRect(left, rect.center().y() - 5, width, 10), 2, 2)
        painter.restore()


def _money(value: float) -> str:
    return f"{'-' if value < 0 else '+'}${abs(value):,.2f}"


class BreakdownView(QWidget):
    """SRD-GUI-031.062–.066 — breakdown chips, table and Trade list filter."""

    group_selected = pyqtSignal(str, object)  # label ("" clears), set of trade keys or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._report: Report | None = None
        self._rows: list[Row] = []
        self._shown: list[Row | None] = []
        self._show_all = False
        self._selected = ""
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        self.chips = ChipGroup([(name, key) for key, name in CHIPS])
        self.chips.changed.connect(self._on_chip)
        body.addWidget(self.chips)
        tools = QHBoxLayout()
        self.note = QLabel("")
        self.note.setObjectName("details_key")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search stock")
        self.search.setFixedWidth(150)
        self.search.setStyleSheet("QLineEdit { outline: none; } QLineEdit:focus { outline: none; }")
        self.search.textChanged.connect(self._render)
        self.min_trades = QSpinBox()
        self.min_trades.setRange(1, 99)
        self.min_trades.setPrefix("Min trades: ")
        self.min_trades.setFixedWidth(130)
        self.min_trades.valueChanged.connect(self._render)
        tools.addWidget(self.note, 1)
        tools.addWidget(self.search)
        tools.addWidget(self.min_trades)
        body.addLayout(tools)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.table.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setItemDelegate(_CellDelegate(self.table))
        self.table.cellClicked.connect(self._on_clicked)
        body.addWidget(self.table, 1)
        self._mono = QFont("IBM Plex Mono")
        self._mono.setStyleHint(QFont.StyleHint.Monospace)
        self._show_tools(False)

    @property
    def by(self) -> str:
        return str(self.chips.value)

    def set_report(self, report: Report | None) -> None:
        """Show ``report``'s breakdown; chips get group counts and single groups turn off."""
        self._report = report
        self._selected = ""
        for button, (key, name) in zip(self.chips.buttons, CHIPS, strict=True):
            count = 0 if report is None else int(report.trades[key].nunique())
            button.setText(f"{name} {count}" if count else name)
            button.setEnabled(count > 1)
            button.setToolTip("" if count > 1 else f"Only one {name.lower()} in this run")
        if not self.chips.buttons[self._checked_index()].isEnabled():
            first = next((b for b in self.chips.buttons if b.isEnabled()), None)
            if first is not None:
                first.setChecked(True)
        self._on_chip()

    def _checked_index(self) -> int:
        return next(i for i, (key, _n) in enumerate(CHIPS) if key == self.by)

    def _show_tools(self, show: bool) -> None:
        self.search.setVisible(show)
        self.min_trades.setVisible(show)

    def _on_chip(self) -> None:
        self._show_all = False
        self._show_tools(self.by == "symbol")
        if self._selected:
            self._selected = ""
            self.group_selected.emit("", None)
        rep = self._report
        self._rows = [] if rep is None or rep.trades.empty else rows(
            breakdown(rep.trades, self.by), self.by)
        self._render()

    def _render(self) -> None:
        symbol = self.by == "symbol"
        self._shown = (visible(self._rows, self.search.text(), self.min_trades.value(),
                               self._show_all) if symbol else list(self._rows))
        self.note.setText(self._note())
        total = self._total()
        nets = [abs(r.net) for r in self._rows] + ([abs(total.net)] if total else [])
        scale = max(nets, default=0.0) or 1.0
        table = self.table
        table.clearSpans()
        table.setRowCount(len(self._shown) + (1 if total else 0))
        for i, row in enumerate(self._shown):
            if row is None:
                self._gap_row(i)
            elif row.trades == 0:
                self._empty_row(i, row)
            else:
                self._fill_row(i, row, scale)
        if total is not None:
            self._fill_row(len(self._shown), total, scale, bold=True)
        table.resizeColumnsToContents()
        table.setColumnWidth(_BAR_COL, max(table.columnWidth(_BAR_COL), 180))
        table.setColumnWidth(_WIN_COL, table.columnWidth(_WIN_COL) + 60)

    def _note(self) -> str:
        if not self._rows:
            return "No trades in this run"
        order = "time order" if self.by in ORDERED else "best net P&L first"
        groups = sum(1 for r in self._rows if r.trades)
        return f"{groups} groups · {order} · groups under {MIN_TRADES} trades are greyed"

    def _total(self) -> Row | None:
        rep = self._report
        if rep is None or rep.trades.empty:
            return None
        pnl = rep.trades["net_pnl"].astype(float)
        return Row("", TOTAL, len(pnl), float(pnl.sum()), float((pnl > 0).mean()),
                   float(pnl.mean()))

    def _item(self, text: str, colour: str | None = None, mono: bool = True) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if mono:
            item.setFont(self._mono)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if colour:
            item.setForeground(QColor(colour))
        return item

    def _fill_row(self, i: int, row: Row, scale: float, bold: bool = False) -> None:
        total = self._report.trades.shape[0] if self._report is not None else 0
        low = row.trades < MIN_TRADES and not bold
        tip = f"Only {row.trades} trade(s) — weak evidence" if low else ""
        name = self._item(f"{row.label}   n<{MIN_TRADES}" if low else row.label, mono=False)
        share = f"{row.trades}  {row.trades / total:.0%}" if total and not bold else str(row.trades)
        win = self._item(f"{row.win:.1%}")
        win.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        win.setData(_KIND, "win")
        win.setData(_VALUE, row.win)
        bar = QTableWidgetItem("")
        bar.setData(_KIND, "bar")
        bar.setData(_VALUE, row.net / scale)
        cells = [name, self._item(share), win, self._item(_money(row.avg), _pnl(row.avg)),
                 self._item(_money(row.net), _pnl(row.net)), bar]
        for col, item in enumerate(cells):
            if low:
                item.setForeground(QColor(C.MUTED))
                item.setToolTip(tip)
            if bold:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.table.setItem(i, col, item)

    def _empty_row(self, i: int, row: Row) -> None:
        self.table.setItem(i, 0, self._item(row.label, C.MUTED, mono=False))
        self.table.setItem(i, 1, self._item("No trades", C.MUTED, mono=False))
        self.table.setSpan(i, 1, 1, len(HEADERS) - 1)

    def _gap_row(self, i: int) -> None:
        hidden = sum(1 for r in self._rows if r.trades >= self.min_trades.value()) - 10
        item = self._item(f"··· {hidden} more stocks · click to show all", C.BLUE, mono=False)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(i, 0, item)
        self.table.setSpan(i, 0, 1, len(HEADERS))

    def _on_clicked(self, i: int, _col: int) -> None:
        if i >= len(self._shown):
            self._select("")
            return
        row = self._shown[i]
        if row is None:
            self._show_all = True
            self._render()
        elif row.trades:
            self._select("" if row.key == self._selected else row.key)

    def _select(self, key: str) -> None:
        """Tell the Trade list to keep one group's trades, or all when ``key`` is empty."""
        if key == self._selected:
            return
        self._selected = key
        rep = self._report
        if not key or rep is None:
            self.table.clearSelection()
            self.group_selected.emit("", None)
            return
        picked = rep.trades[rep.trades[self.by].astype(str) == key]
        label = f"{dict(CHIPS)[self.by]}: {group_label(self.by, key)}"
        self.group_selected.emit(label, set(trade_keys(picked)))


def _pnl(value: float) -> str | None:
    return C.GREEN if value > 0 else C.RED if value < 0 else None
