"""
Module: MD-GUI-031.053.M07 — Backtest trade list
Parent SRD: SRD-GUI-031.053

Every trade of the run as an Entry row and an Exit row in time order, with the free
capital left after each row (SRD-GUI-031.089), and All / Wins / Losses / LONG / SHORT chips.
Clicking a row asks the workspace to open that trade's day in the Inspector. A breakdown
row click can narrow the list to one group's trades (SRD-GUI-031.066).
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

from us_swing.core.dates import DATE_FMT
from us_swing.gui.screener_views import ChipGroup
from us_swing.gui.theme import C

HEADERS = ["Trade #", "Trade", "Type", "Symbol", "Strategy", "Time", "Price", "Qty", "P&L",
           "P&L %", "Allocated capital", "Available capital", "Duration (days)", "Exit reason"]
FILTERS = [("All", "all"), ("Wins", "wins"), ("Losses", "losses"), ("LONG", "LONG"),
           ("SHORT", "SHORT")]
IDLE_SHARE = 0.8  # Available capital above this share of start capital is shaded red
_ET = "America/New_York"
_TIME = f"{DATE_FMT} %H:%M:%S"


def numbered(trades: pd.DataFrame) -> pd.DataFrame:
    """Trades in entry order with ``number``, ``pnl_pct``, ``hours``, ``days``, ``alloc``
    and ET ``day``."""
    out = trades.sort_values("entry_ts", kind="stable").reset_index(drop=True)
    entry = pd.DatetimeIndex(pd.to_datetime(out["entry_ts"], utc=True))
    exit_ = pd.DatetimeIndex(pd.to_datetime(out["exit_ts"], utc=True))
    alloc = out["entry_px"].astype(float) * out["qty"].astype(float)
    hours = (exit_ - entry).total_seconds() / 3600.0
    return out.assign(
        number=range(1, len(out) + 1),
        pnl_pct=out["net_pnl"].astype(float) / alloc.replace(0.0, float("nan")) * 100.0,
        hours=hours,
        days=hours / 24.0,
        alloc=alloc,
        day=entry.tz_convert(_ET).date,
    )


def events(trades: pd.DataFrame, capital: float | None) -> pd.DataFrame:
    """One Entry and one Exit row per numbered trade in time order, with ``event``, ``time``,
    ``price`` and ``avail``: free capital after the row (an exit at the same time comes first,
    as in the engine). ``avail`` is NaN when ``capital`` is not known."""
    entry = trades.assign(event="Entry", time=pd.to_datetime(trades["entry_ts"], utc=True),
                          price=trades["entry_px"], _first=1)
    exit_ = trades.assign(event="Exit", time=pd.to_datetime(trades["exit_ts"], utc=True),
                          price=trades["exit_px"], _first=0)
    out = (pd.concat([entry, exit_], ignore_index=True)
           .sort_values(["time", "_first", "number"], kind="stable")
           .drop(columns="_first").reset_index(drop=True))
    change = out["alloc"].where(out["event"] == "Exit", -out["alloc"]).astype(float)
    start = float("nan") if capital is None else capital
    return out.assign(avail=start + change.cumsum())


def keep(trades: pd.DataFrame, which: str) -> pd.DataFrame:
    """Rows for one filter chip: all, wins, losses, LONG or SHORT."""
    if which == "wins":
        return trades[trades["net_pnl"] > 0]
    if which == "losses":
        return trades[trades["net_pnl"] <= 0]
    if which in ("LONG", "SHORT"):
        return trades[trades["direction"].astype(str).str.upper() == which]
    return trades


def trade_keys(trades: pd.DataFrame) -> list[tuple[str, int]]:
    """(symbol, entry time in ns) per trade; the same trade gives the same key everywhere."""
    entry = pd.DatetimeIndex(pd.to_datetime(trades["entry_ts"], utc=True))
    return list(zip(trades["symbol"].astype(str), [int(ts.value) for ts in entry], strict=True))


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
        self._capital: float | None = None
        self._events = events(self._all, None)
        self._rows = self._events
        self._group = ""
        self._keys: set[tuple[str, int]] | None = None
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

    def set_trades(self, trades: pd.DataFrame, capital: float | None = None) -> None:
        """Show every trade of the selected variant; ``capital`` is its start capital."""
        self._all = numbered(trades)
        self._capital = capital
        self._events = events(self._all, capital)
        self._group, self._keys = "", None
        self._render()

    def set_group_filter(self, label: str, keys: set[tuple[str, int]] | None) -> None:
        """Keep only the trades in ``keys`` (a breakdown group), or all when ``keys`` is None."""
        self._group, self._keys = (label, keys) if keys is not None else ("", None)
        self._render()

    def _render(self) -> None:
        rows = self._all
        if self._keys is not None:
            rows = rows[[key in self._keys for key in trade_keys(rows)]]
        rows = keep(rows, self.chips.value or "all")
        shown = self._events[self._events["number"].isin(rows["number"])]
        self._rows = shown.reset_index(drop=True)
        group = f"{self._group} · " if self._group else ""
        self.summary.setText(f"{group}{len(rows)} of {len(self._all)} trades · net P&L "
                             f"{_usd(float(rows['net_pnl'].sum()))}")
        self.table.setRowCount(len(shown))
        exits = list(shown["event"] == "Exit")

        def on_exit(values: list[str]) -> list[str]:
            return [v if out else "" for v, out in zip(values, exits, strict=True)]

        cells = [
            [str(n) for n in shown["number"]], list(shown["event"]),
            list(shown["direction"].astype(str).str.upper()),
            list(shown["symbol"]), list(shown["strategy"]), _times(shown["time"]),
            [f"{v:,.2f}" for v in shown["price"]], [str(v) for v in shown["qty"]],
            on_exit([_usd(float(v)) for v in shown["net_pnl"]]),
            on_exit([f"{v:+.2f}%" for v in shown["pnl_pct"]]),
            [_usd(float(v)) for v in shown["alloc"]],
            ["—" if pd.isna(v) else _usd(float(v)) for v in shown["avail"]],
            on_exit([f"{v:.1f}" for v in shown["days"]]),
            on_exit([str(v) for v in shown["exit_reason"]]),
        ]
        for col, values in enumerate(cells):
            for row, value in enumerate(values):
                self.table.setItem(row, col, self._item(col, str(value), shown, row))
        self.table.resizeColumnsToContents()

    def _item(self, col: int, text: str, rows: pd.DataFrame, row: int) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if col == 2:
            colour = QColor(C.TEAL if text == "LONG" else C.BLUE)
            item.setForeground(colour)
            back = QColor(colour)
            back.setAlpha(40)
            item.setBackground(back)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        elif col in (8, 9):
            pnl = float(rows["net_pnl"].iloc[row])
            item.setForeground(QColor(C.GREEN if pnl > 0 else C.RED))
        elif col == 11 and self._capital and (
                float(rows["avail"].iloc[row]) > IDLE_SHARE * self._capital):
            back = QColor(C.RED)
            back.setAlpha(40)
            item.setBackground(back)
        return item

    def _on_clicked(self, row: int, _col: int) -> None:
        if row < len(self._rows):
            number = self._rows["number"].iloc[row]
            self.trade_clicked.emit(self._all[self._all["number"] == number].iloc[0])


def _usd(value: float) -> str:
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"
