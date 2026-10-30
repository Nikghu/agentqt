"""
Module: MD-GUI-031.053.M07 — Backtest trade list
Parent SRD: SRD-GUI-031.053

Every trade of the run: Trade #, LONG/SHORT pill, times, prices, P&L, P&L %, qty,
duration and exit reason, with All / Wins / Losses / LONG / SHORT chips.
Clicking a row asks the workspace to open that trade's day in the Inspector.
"""
from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.screener_views import ChipGroup
from us_swing.gui.theme import C

HEADERS = ["Trade #", "Type", "Symbol", "Strategy", "Entry time", "Exit time", "Entry price",
           "Exit price", "P&L", "P&L %", "Qty", "Duration (hrs)", "Exit reason"]
FILTERS = [("All", "all"), ("Wins", "wins"), ("Losses", "losses"), ("LONG", "LONG"),
           ("SHORT", "SHORT")]
_ET = "America/New_York"
_TIME = "%Y-%m-%d %H:%M:%S"


def numbered(trades: pd.DataFrame) -> pd.DataFrame:
    """Trades in entry order with ``number``, ``pnl_pct``, ``hours`` and ET ``day`` columns."""
    out = trades.sort_values("entry_ts", kind="stable").reset_index(drop=True)
    entry = pd.DatetimeIndex(pd.to_datetime(out["entry_ts"], utc=True))
    exit_ = pd.DatetimeIndex(pd.to_datetime(out["exit_ts"], utc=True))
    cost = (out["entry_px"].astype(float) * out["qty"].astype(float)).replace(0.0, float("nan"))
    return out.assign(
        number=range(1, len(out) + 1),
        pnl_pct=out["net_pnl"].astype(float) / cost * 100.0,
        hours=(exit_ - entry).total_seconds() / 3600.0,
        day=entry.tz_convert(_ET).date,
    )


def keep(trades: pd.DataFrame, which: str) -> pd.DataFrame:
    """Rows for one filter chip: all, wins, losses, LONG or SHORT."""
    if which == "wins":
        return trades[trades["net_pnl"] > 0]
    if which == "losses":
        return trades[trades["net_pnl"] <= 0]
    if which in ("LONG", "SHORT"):
        return trades[trades["direction"].astype(str).str.upper() == which]
    return trades


def _times(values: pd.Series) -> list[str]:
    return list(pd.DatetimeIndex(pd.to_datetime(values, utc=True)).tz_convert(_ET).strftime(_TIME))


class TradeList(QWidget):
    """SRD-GUI-031.053 — the Trade list panel of the Detail Report."""

    trade_clicked = pyqtSignal(object)  # pd.Series of the trade, with its ET ``day``

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all = numbered(pd.DataFrame(columns=[
            "strategy", "symbol", "direction", "entry_ts", "entry_px", "qty", "exit_ts",
            "exit_px", "exit_reason", "net_pnl"]))
        self._rows = self._all
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        top = QHBoxLayout()
        self.summary = QLabel("")
        self.summary.setObjectName("details_key")
        self.chips = ChipGroup([(label, value) for label, value in FILTERS])
        self.chips.setFixedWidth(360)
        self.chips.changed.connect(self._render)
        top.addWidget(self.summary, 1)
        top.addWidget(self.chips)
        body.addLayout(top)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.table.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellClicked.connect(self._on_clicked)
        body.addWidget(self.table, 1)

    def set_trades(self, trades: pd.DataFrame) -> None:
        """Show every trade of the selected variant."""
        self._all = numbered(trades)
        self._render()

    def _render(self) -> None:
        rows = keep(self._all, self.chips.value or "all")
        self._rows = rows.reset_index(drop=True)
        self.summary.setText(f"{len(rows)} of {len(self._all)} trades · net P&L "
                             f"{_usd(float(rows['net_pnl'].sum()))}")
        self.table.setRowCount(len(rows))
        cells = [
            [str(n) for n in rows["number"]], list(rows["direction"].astype(str).str.upper()),
            list(rows["symbol"]), list(rows["strategy"]),
            _times(rows["entry_ts"]), _times(rows["exit_ts"]),
            [f"{v:,.2f}" for v in rows["entry_px"]], [f"{v:,.2f}" for v in rows["exit_px"]],
            [_usd(float(v)) for v in rows["net_pnl"]], [f"{v:+.2f}%" for v in rows["pnl_pct"]],
            [str(v) for v in rows["qty"]], [f"{v:.2f}" for v in rows["hours"]],
            list(rows["exit_reason"]),
        ]
        for col, values in enumerate(cells):
            for row, value in enumerate(values):
                self.table.setItem(row, col, self._item(col, str(value), rows, row))
        self.table.resizeColumnsToContents()

    def _item(self, col: int, text: str, rows: pd.DataFrame, row: int) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if col == 1:
            colour = QColor(C.TEAL if text == "LONG" else C.BLUE)
            item.setForeground(colour)
            back = QColor(colour)
            back.setAlpha(40)
            item.setBackground(back)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        elif col in (8, 9):
            pnl = float(rows["net_pnl"].iloc[row])
            item.setForeground(QColor(C.GREEN if pnl > 0 else C.RED))
        return item

    def _on_clicked(self, row: int, _col: int) -> None:
        if row < len(self._rows):
            self.trade_clicked.emit(self._rows.iloc[row])


def _usd(value: float) -> str:
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"
