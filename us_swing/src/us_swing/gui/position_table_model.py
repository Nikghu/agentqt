"""
Module: MD-GUI-002.001.M02 — position_table_model.py
Parent SRD: SRD-GUI-002.001, SRD-GUI-002.002

QAbstractTableModel implementations for positions and trade history.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from us_swing.gui._types import OpenPosition, TradeRecord
from us_swing.gui.theme import C


class PositionTableModel(QAbstractTableModel):
    """
    Model: [User] | Symbol | Qty | Avg Entry | Current | Unrealised P&L | Stop | Target | State
    The User column is optional — shown only in admin All-Users scope.
    SRD-GUI-002.001, SRD-GUI-002.002
    """

    _BASE_COLS = ["Symbol", "Qty", "Avg Entry", "Current", "P&L ($)", "P&L %", "Stop", "Target", "State"]
    _USER_COL  = ["User"]

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._rows: list[OpenPosition] = []
        self._show_user: bool = False
        self._user_labels: dict[int, str] = {}
        self._highlighted_row: int = -1
        self._exchange_unavailable: set[str] = set()

    @property
    def COLUMNS(self) -> list[str]:
        return self._USER_COL + self._BASE_COLS if self._show_user else self._BASE_COLS

    def set_show_user(self, show: bool, user_labels: dict[int, str] | None = None) -> None:
        """Toggle the prepended User column.  user_labels maps user_id → username."""
        self.beginResetModel()
        self._show_user  = show
        self._user_labels = user_labels or {}
        self.endResetModel()

    def set_exchange_unavailable(self, symbols: set[str]) -> None:
        """Mark symbols whose contracts are not available on US exchanges."""
        self.beginResetModel()
        self._exchange_unavailable = symbols
        self.endResetModel()

    def refresh(self, positions: list[OpenPosition]) -> None:
        self.beginResetModel()
        self._rows = positions
        self._highlighted_row = -1
        self.endResetModel()

    def set_highlighted_row(self, row: int) -> None:
        """Mark a row as highlighted (red font). Pass -1 to clear."""
        old = self._highlighted_row
        self._highlighted_row = row
        # Notify view to repaint affected rows
        if old >= 0 and old < len(self._rows):
            self.dataChanged.emit(
                self.index(old, 0), self.index(old, self.columnCount() - 1)
            )
        if row >= 0 and row < len(self._rows):
            self.dataChanged.emit(
                self.index(row, 0), self.index(row, self.columnCount() - 1)
            )

    # ── QAbstractTableModel interface ─────────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        pos = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(pos, col)

        if role == Qt.ItemDataRole.BackgroundRole:
            if index.row() == self._highlighted_row:
                return QColor("#3a0a0a")
            return self._background(pos, col)

        if role == Qt.ItemDataRole.ForegroundRole:
            if index.row() == self._highlighted_row:
                return QColor(C.RED)
            if pos.symbol in self._exchange_unavailable:
                return QColor(C.MUTED)
            return self._foreground(pos, col)

        if role == Qt.ItemDataRole.ToolTipRole:
            if pos.symbol in self._exchange_unavailable:
                return "Not available on US exchanges — candle data unavailable."
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            # right-align numeric columns (shift by 1 when user col visible)
            shift = 1 if self._show_user else 0
            if col in [shift + c for c in (1, 2, 3, 4, 5, 6, 7)]:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter

        return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _display(self, pos: OpenPosition, col: int) -> str:
        if self._show_user:
            if col == 0:
                return self._user_labels.get(pos.user_id, f"#{pos.user_id}")
            col -= 1  # shift to base column index
        match col:
            case 0: return pos.symbol
            case 1: return str(pos.quantity)
            case 2: return f"${pos.average_price:,.2f}"
            case 3: return f"${pos.current_price:,.2f}"
            case 4:
                pnl = pos.unrealised_pnl
                return f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
            case 5:
                pct = pos.pnl_pct
                return f"{pct:+.2f}%"
            case 6: return f"${pos.stop_loss:,.2f}"
            case 7: return f"${pos.target_price:,.2f}"
            case 8: return pos.state
        return ""

    def _background(self, pos: OpenPosition, col: int) -> QColor | None:
        base_col = (col - 1) if self._show_user else col
        if base_col == 4:
            return QColor(C.PNL_POS_BG) if pos.unrealised_pnl >= 0 else QColor(C.PNL_NEG_BG)
        if base_col == 8:
            state_bg = {
                "NEW":           "#2a2a2a",
                "PARTIAL_ENTRY": "#332b00",
                "OPEN":          "#1a3326",
                "PARTIAL_EXIT":  "#332500",
                "CLOSED":        "#1a1a1a",
            }
            return QColor(state_bg.get(pos.state, C.SURFACE))
        return None

    def _foreground(self, pos: OpenPosition, col: int) -> QColor | None:
        base_col = (col - 1) if self._show_user else col
        if base_col == 4:
            return QColor(C.GREEN) if pos.unrealised_pnl >= 0 else QColor(C.RED)
        if base_col == 5:
            return QColor(C.GREEN) if pos.pnl_pct >= 0 else QColor(C.RED)
        if base_col == 8:
            state_fg = {
                "NEW":           C.STATE_NEW,
                "PARTIAL_ENTRY": C.STATE_PARTIAL_ENTRY,
                "OPEN":          C.STATE_OPEN,
                "PARTIAL_EXIT":  C.STATE_PARTIAL_EXIT,
                "CLOSED":        C.STATE_CLOSED,
            }
            return QColor(state_fg.get(pos.state, C.TEXT))
        return None


# ─────────────────────────────────────────────────────────────────────────────

class TradeHistoryModel(QAbstractTableModel):
    """
    Model: [User] | Time | Symbol | Side | Qty | Entry | Exit | P&L | Strategy | Mode
    The User column is optional — shown only in admin All-Users scope.
    SRD-GUI-002.004
    """

    _BASE_COLS = ["Date & Time", "Symbol", "Side", "Qty", "Entry", "Exit", "P&L", "Strategy", "Mode"]
    _USER_COL  = ["User"]

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._rows: list[TradeRecord] = []
        self._show_user: bool = False
        self._user_labels: dict[int, str] = {}

    @property
    def COLUMNS(self) -> list[str]:
        return self._USER_COL + self._BASE_COLS if self._show_user else self._BASE_COLS

    def set_show_user(self, show: bool, user_labels: dict[int, str] | None = None) -> None:
        """Toggle the prepended User column. user_labels maps user_id → username."""
        self.beginResetModel()
        self._show_user   = show
        self._user_labels = user_labels or {}
        self.endResetModel()

    def refresh(self, trades: list[TradeRecord]) -> None:
        self.beginResetModel()
        self._rows = sorted(trades, key=lambda t: t.entry_time, reverse=True)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        t = self._rows[index.row()]
        col = index.column()
        base_col = (col - 1) if self._show_user else col

        if role == Qt.ItemDataRole.DisplayRole:
            if self._show_user and col == 0:
                return self._user_labels.get(t.user_id, f"#{t.user_id}")
            match base_col:
                case 0: return t.entry_time.strftime("%m/%d  %H:%M")
                case 1: return t.symbol
                case 2: return t.side
                case 3: return str(t.quantity)
                case 4: return f"${t.entry_price:.2f}"
                case 5: return f"${t.exit_price:.2f}" if t.exit_price else "—"
                case 6:
                    if t.pnl is None:
                        return "—"
                    return f"+${t.pnl:,.2f}" if t.pnl >= 0 else f"-${abs(t.pnl):,.2f}"
                case 7: return t.strategy_id
                case 8: return t.mode.upper()
            return ""

        if role == Qt.ItemDataRole.BackgroundRole:
            if base_col == 6 and t.pnl is not None:
                return QColor(C.PNL_POS_BG) if t.pnl >= 0 else QColor(C.PNL_NEG_BG)
            return None

        if role == Qt.ItemDataRole.ForegroundRole:
            if base_col == 6 and t.pnl is not None:
                return QColor(C.GREEN) if t.pnl >= 0 else QColor(C.RED)
            if base_col == 2:
                return QColor(C.GREEN) if t.side == "BUY" else QColor(C.RED)
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            shift = 1 if self._show_user else 0
            if col in [shift + c for c in (3, 4, 5, 6)]:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter

        return None
