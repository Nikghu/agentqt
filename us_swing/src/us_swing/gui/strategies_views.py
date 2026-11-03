"""
Module: MD-GUI-032.002.M02 — Strategies grouped list and table
Parent SRD: SRD-GUI-032.003

Two views of the same strategy rows.  The grouped list puts strategies under
Running, Stopped and Disabled headers.  The table shows one row per strategy;
the shared detail widget opens in a full-width child row under the clicked
row (SRD-GUI-032.004, .005, .008).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.execution_watchlist import _GroupRow
from us_swing.gui.icons import mark_danger, set_icon
from us_swing.gui.strategy_pnl_chart import money
from us_swing.gui.theme import C

RUNNING, STOPPED, DISABLED = "Running", "Stopped", "Disabled"
GROUPS = (RUNNING, STOPPED, DISABLED)
LIVE = ("RUNNING", "SQUARING_OFF")
COLUMNS = ("", "Strategy", "Status", "Dir", "Mode", "Type", "Entry window", "Per trade",
           "Trades", "Win %", "Total P&L", "Today", "Open", "")
COL_CHECK, COL_NAME, COL_STATUS, COL_DIR = 0, 1, 2, 3
COL_TOTAL, COL_TODAY, COL_BUTTON = 10, 11, 13
_RIGHT = (7, 8, 9, 10, 11, 12)
_WIDGET_COLUMNS = {COL_CHECK: 36, COL_STATUS: 120, COL_BUTTON: 110}
_MONO = '"IBM Plex Mono", Consolas, monospace'
_DASH = "–"


@dataclass(frozen=True, slots=True)
class StrategyRow:
    """What both views show for one strategy."""

    name: str
    status: str
    group: str
    side: str
    mode: str
    trade_type: str
    window: str
    per_trade: int
    trades: int
    win_rate: float | None
    total: float
    today: float
    open_count: int


def group_of(status: str, mode: str) -> str:
    """Running when live, Disabled when its mode is disabled, else Stopped."""
    if status in LIVE:
        return RUNNING
    return DISABLED if mode.lower() == "disabled" else STOPPED


def pill_text(status: str) -> str:
    return status.replace("_", " ")


def status_colour(status: str) -> str:
    colours: dict[str, str] = {"RUNNING": C.GREEN, "SQUARING_OFF": C.ORANGE}
    return colours.get(status, str(C.MUTED))


def strategy_rows(
    configs: Sequence[Any],
    status_of: Callable[[Any], str],
    pnl_of: Callable[[str], Any],
    open_of: Callable[[str], int],
) -> list[StrategyRow]:
    """Rows for ``configs``, Running first, then Stopped, then Disabled."""
    rows: list[StrategyRow] = []
    for cfg in configs:
        status = status_of(cfg)
        pnl = pnl_of(cfg.name)
        rows.append(StrategyRow(
            name=cfg.name,
            status=status,
            group=group_of(status, cfg.mode),
            side="Short" if cfg.direction == "SHORT" else "Long",
            mode=cfg.mode.capitalize(),
            trade_type=cfg.trade_type,
            window=f"{cfg.start_time} – {cfg.end_time}",
            per_trade=cfg.per_trade_pct,
            trades=pnl.trades,
            win_rate=pnl.win_rate if pnl.trades else None,
            total=pnl.total,
            today=pnl.today,
            open_count=open_of(cfg.name),
        ))
    return sorted(rows, key=lambda r: GROUPS.index(r.group))


def _money_or_dash(value: float) -> str:
    return money(value) if value else _DASH


def _pnl_colour(value: float) -> str:
    return C.GREEN if value > 0 else C.RED if value < 0 else str(C.MUTED)


def _side_colour(side: str) -> str:
    return str(C.RED if side == "Short" else C.GREEN)


class _GroupedItem(QWidget):
    """Grouped-list row: name and P&L, then a direction · mode · type line."""

    def __init__(self, row: StrategyRow) -> None:
        super().__init__()
        self.setObjectName("preset_item")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name = QLabel(row.name)
        name.setStyleSheet(f"font-family:{_MONO}; font-weight:bold; background:transparent;")
        pnl = QLabel(_money_or_dash(row.total))
        pnl.setStyleSheet(
            f"font-family:{_MONO}; color:{_pnl_colour(row.total)}; background:transparent;"
        )
        top = QHBoxLayout()
        top.addWidget(name, 1)
        top.addWidget(pnl)
        parts = [f"<b style='color:{_side_colour(row.side)}'>{row.side.upper()}</b>",
                 row.mode, row.trade_type, f"{row.trades} trades"]
        if row.open_count:
            parts.append(f"<span style='color:{C.GREEN}'>{row.open_count} open</span>")
        line = QLabel(" · ".join(parts))
        line.setTextFormat(Qt.TextFormat.RichText)
        line.setObjectName("view_key")
        body = QVBoxLayout(self)
        body.setContentsMargins(10, 7, 10, 7)
        body.setSpacing(2)
        body.addLayout(top)
        body.addWidget(line)


class GroupedList(QTreeWidget):
    """Strategies under Running, Stopped and Disabled headers (SRD-GUI-032.003)."""

    picked = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("strategy_groups")
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setVerticalScrollMode(QTreeWidget.ScrollMode.ScrollPerPixel)
        self.group_counts: dict[str, int] = {}
        self.itemClicked.connect(self._on_click)

    def fill(self, rows: Sequence[StrategyRow], selected: str | None) -> None:
        self.clear()
        self.group_counts = {}
        colours = {RUNNING: C.GREEN, STOPPED: C.TEAL, DISABLED: C.RED}
        for group in GROUPS:
            members = [r for r in rows if r.group == group]
            if not members:
                continue
            self.group_counts[group] = len(members)
            head = QTreeWidgetItem(self)
            head.setFlags(Qt.ItemFlag.ItemIsEnabled)
            head.setSizeHint(0, QSize(0, 30))
            self.setItemWidget(head, 0, _GroupRow(group, len(members), colours[group]))
            for row in members:
                item = QTreeWidgetItem(self)
                item.setData(0, Qt.ItemDataRole.UserRole, row.name)
                widget = _GroupedItem(row)
                item.setSizeHint(0, QSize(0, widget.sizeHint().height() + 8))
                self.setItemWidget(item, 0, widget)
                if row.name == selected:
                    self.setCurrentItem(item)

    def names(self) -> list[str]:
        items = (self.topLevelItem(i) for i in range(self.topLevelItemCount()))
        return [str(n) for it in items if it is not None
                and (n := it.data(0, Qt.ItemDataRole.UserRole))]

    def _on_click(self, item: QTreeWidgetItem, _column: int) -> None:
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if name:
            self.picked.emit(str(name))


class StrategyTable(QTreeWidget):
    """One row per strategy; the detail opens in a row under it (SRD-GUI-032.004/.005)."""

    row_clicked = pyqtSignal(str)
    run_clicked = pyqtSignal(str)
    checked_changed = pyqtSignal(list)

    def __init__(self, stash: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("strategy_table")
        self.setColumnCount(len(COLUMNS))
        self.setHeaderLabels(list(COLUMNS))
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setItemsExpandable(False)
        self.setExpandsOnDoubleClick(False)
        self.setUniformRowHeights(False)
        self.setVerticalScrollMode(QTreeWidget.ScrollMode.ScrollPerPixel)
        header = self.header()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
            for col, width in _WIDGET_COLUMNS.items():
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                header.resizeSection(col, width)
        self._stash = stash
        self._items: dict[str, QTreeWidgetItem] = {}
        self._checks: dict[str, QCheckBox] = {}
        self._detail: QWidget | None = None
        self.open_name: str | None = None
        self.itemClicked.connect(self._on_click)

    def fill(self, rows: Sequence[StrategyRow]) -> None:
        open_name, detail = self.open_name, self._detail
        checked = set(self.checked_names())
        self.close_detail()
        self.clear()
        self._items, self._checks = {}, {}
        for row in rows:
            self._add_row(row, row.name in checked)
        if open_name is not None and detail is not None:
            self.open_detail(open_name, detail)
        self.checked_changed.emit(self.checked_names())

    def _add_row(self, row: StrategyRow, checked: bool) -> None:
        item = QTreeWidgetItem(self)
        item.setData(0, Qt.ItemDataRole.UserRole, row.name)
        win = _DASH if row.win_rate is None else f"{row.win_rate * 100:.0f}"
        texts = {COL_NAME: row.name, COL_DIR: row.side.upper(), 4: row.mode,
                 5: row.trade_type, 6: row.window, 7: f"{row.per_trade} %",
                 8: str(row.trades), 9: win, COL_TOTAL: _money_or_dash(row.total),
                 COL_TODAY: _money_or_dash(row.today), 12: str(row.open_count)}
        for col, text in texts.items():
            item.setText(col, text)
            if col in _RIGHT:
                item.setTextAlignment(col, Qt.AlignmentFlag.AlignRight
                                      | Qt.AlignmentFlag.AlignVCenter)
        bold = QFont(_MONO.split(",")[0].strip('"'))
        bold.setBold(True)
        item.setFont(COL_NAME, bold)
        item.setFont(COL_DIR, bold)
        item.setForeground(COL_DIR, QColor(_side_colour(row.side)))
        item.setForeground(COL_TOTAL, QColor(_pnl_colour(row.total)))
        item.setForeground(COL_TODAY, QColor(_pnl_colour(row.today)))
        item.setSizeHint(COL_NAME, QSize(0, C.BTN_H + 10))

        check = QCheckBox()
        check.setAccessibleName(f"Select {row.name}")
        check.setChecked(checked)
        check.toggled.connect(lambda _on: self.checked_changed.emit(self.checked_names()))
        self.setItemWidget(item, COL_CHECK, _centred(check))
        self._checks[row.name] = check

        pill = QLabel(pill_text(row.status))
        colour = status_colour(row.status)
        pill.setStyleSheet(
            f"color:{colour}; border:1px solid {colour}; border-radius:8px;"
            f" padding:1px 8px; font-size:7.5pt; font-weight:bold;"
        )
        self.setItemWidget(item, COL_STATUS, _centred(
            pill, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        self.setItemWidget(item, COL_BUTTON, _centred(self._run_button(row)))
        self._items[row.name] = item

    def _run_button(self, row: StrategyRow) -> QPushButton:
        if row.status in LIVE:
            btn = QPushButton("Stop")
            set_icon(btn, "square-x", "danger")
            mark_danger(btn)
        elif row.group == DISABLED:
            btn = QPushButton("Enable")
            btn.setToolTip("Open the strategy to change its mode")
        else:
            btn = QPushButton("Start")
            set_icon(btn, "play", "go")
        name = row.name
        btn.clicked.connect(lambda: self.run_clicked.emit(name))
        return btn

    def open_detail(self, name: str, widget: QWidget) -> None:
        """Show ``widget`` in a full-width row under ``name``."""
        self.close_detail()
        item = self._items.get(name)
        if item is None:
            return
        holder = QFrame()
        holder.setObjectName("inline_detail")
        box = QVBoxLayout(holder)
        box.setContentsMargins(3, 0, 0, 1)
        box.addWidget(widget)
        widget.show()
        child = QTreeWidgetItem(item)
        child.setFlags(Qt.ItemFlag.ItemIsEnabled)
        child.setFirstColumnSpanned(True)
        child.setSizeHint(0, QSize(0, holder.sizeHint().height()))
        self.setItemWidget(child, 0, holder)
        item.setExpanded(True)
        self.setCurrentItem(item)
        self._detail, self.open_name = widget, name

    def close_detail(self) -> None:
        """Move the detail widget back to the stash, then drop the child row."""
        if self._detail is not None:
            self._detail.setParent(self._stash)
            item = self._items.get(self.open_name or "")
            if item is not None:
                item.takeChildren()
        self._detail, self.open_name = None, None

    def names(self) -> list[str]:
        return list(self._items)

    def checked_names(self) -> list[str]:
        return [name for name, box in self._checks.items() if box.isChecked()]

    def _on_click(self, item: QTreeWidgetItem, _column: int) -> None:
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if name:
            self.row_clicked.emit(str(name))


def _centred(widget: QWidget,
             align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter) -> QWidget:
    holder = QWidget()
    holder.setStyleSheet("background:transparent;")
    box = QHBoxLayout(holder)
    box.setContentsMargins(6, 0, 6, 0)
    box.addWidget(widget, 0, align)
    return holder
