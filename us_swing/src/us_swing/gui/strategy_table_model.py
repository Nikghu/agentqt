"""
Module: MD-GUI-004.001.M02 — Strategy Table Model and Status Badge Delegate
Parent SRD: SRD-GUI-004.001
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem, QStyledItemDelegate, QWidget

from us_swing.gui.strategy_builder_dialog import StrategyConfig
from us_swing.gui.theme import C

COL_STATUS        = 0
COL_RUN           = 1
COL_NAME          = 2
COL_EDIT          = 3
COL_DELETE        = 4
COL_RESET         = 5
COL_SCOPE         = 6
COL_MODE          = 7
COL_CAPITAL       = 8
COL_START         = 9
COL_END           = 10
COL_TRADE_TYPE    = 11
COL_START_DATE    = 12
COL_END_DATE      = 13
COL_TARGET        = 14
COL_TARGET_TYPE   = 15
COL_STOPLOSS      = 16
COL_STOPLOSS_TYPE = 17

COLUMNS: list[str] = [
    "Status", "Run", "Name", "Edit", "Delete", "Reset", "Scope", "Mode", "Capital",
    "Start", "End", "Trade Type", "Start Date", "End Date",
    "Target", "Target Type", "Stop Loss", "StopLoss Type",
]

STATUS_COLORS: dict[str, str] = {
    "STOPPED":      C.MUTED,
    "RUNNING":      C.TEAL,
    "SQUARING_OFF": C.ORANGE,
}


def _run_state(cfg: StrategyConfig) -> str:
    """Read ``run_state`` from the strategy signal dict, falling back to legacy ``Status``."""
    sig = cfg.strategy_signal
    raw = sig.get("run_state")
    if isinstance(raw, str) and raw:
        return raw
    legacy = sig.get("Status", "Inactive")
    if legacy in ("Active", "Running"):
        return "RUNNING"
    return "STOPPED"


class StrategyTableModel(QAbstractTableModel):
    """Read-only table model backing the strategy executor QTableView."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[StrategyConfig] = []
        self._running_override: set[str] = set()

    def load(
        self,
        configs: list[StrategyConfig],
        running_override: set[str] | None = None,
    ) -> None:
        """Reload rows.

        *running_override* — strategy names whose Status column should
        visually render as ``Running`` regardless of the cfg value.  Used
        on boot to surface restored open positions without mutating the
        underlying ``StrategyConfig`` (which would mislead the play/stop
        button into thinking the strategy is armed).
        """
        self.beginResetModel()
        self._rows = list(configs)
        self._running_override = set(running_override or set())
        self.endResetModel()

    def status_for(self, cfg: StrategyConfig) -> str:
        """Return the visual status — overridden to ``RUNNING`` if the
        strategy has open positions, otherwise the raw ``run_state`` value."""
        if cfg.name in self._running_override:
            return "RUNNING"
        return _run_state(cfg)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return COLUMNS[section]
            if orientation == Qt.Orientation.Vertical:
                return str(section + 1)
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        cfg = self._rows[index.row()]
        col = index.column()

        if col in (COL_RUN, COL_EDIT, COL_DELETE, COL_RESET):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_STATUS:
                return self.status_for(cfg)
            return _cell_text(cfg, col)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == COL_NAME:
                return QColor(C.BLUE)
            if col == COL_STATUS:
                return QColor(STATUS_COLORS.get(self.status_for(cfg), C.MUTED))
        return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col == COL_NAME:
                return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

        return None

    def config_at(self, row: int) -> StrategyConfig:
        return self._rows[row]


def _cell_text(cfg: StrategyConfig, col: int) -> str:
    status: str = _run_state(cfg)
    if col == COL_NAME:
        return cfg.name
    if col == COL_SCOPE:
        return {
            "all": "All S&P 500",
            "include": f"Include ({len(cfg.symbols_include)})",
            "exclude": f"Exclude ({len(cfg.symbols_exclude)})",
        }.get(cfg.symbol_mode, cfg.symbol_mode)
    if col == COL_MODE:
        return cfg.mode.capitalize()
    if col == COL_CAPITAL:
        return f"{cfg.capital_max} %"
    if col == COL_START:
        return cfg.start_time
    if col == COL_END:
        return cfg.end_time
    if col == COL_TRADE_TYPE:
        return cfg.trade_type
    if col == COL_START_DATE:
        return cfg.start_date
    if col == COL_END_DATE:
        return cfg.end_date
    if col == COL_TARGET:
        return f"{cfg.target_value:.1f}%" if cfg.target_enabled else "—"
    if col == COL_TARGET_TYPE:
        return cfg.target_type.capitalize() if cfg.target_enabled else "—"
    if col == COL_STOPLOSS:
        return f"{cfg.stoploss_value:.1f}%" if cfg.stoploss_enabled else "—"
    if col == COL_STOPLOSS_TYPE:
        return cfg.stoploss_type.capitalize() if cfg.stoploss_enabled else "—"
    if col == COL_STATUS:
        return status
    return ""


class StatusBadgeDelegate(QStyledItemDelegate):
    """Draws the Status column as a rounded pill badge keyed to STATUS_COLORS."""

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        if painter is None:
            return
        if index.column() != COL_STATUS:
            super().paint(painter, option, index)
            return

        status: str = str(index.data(Qt.ItemDataRole.DisplayRole) or "STOPPED")
        color = QColor(STATUS_COLORS.get(status, C.MUTED))

        painter.save()

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        pill_w = min(option.rect.width() - 16, 90)
        pill_h = 18
        pill_x = option.rect.x() + (option.rect.width() - pill_w) // 2
        pill_y = option.rect.y() + (option.rect.height() - pill_h) // 2
        pill = QRectF(pill_x, pill_y, pill_w, pill_h)

        bg = QColor(color)
        bg.setAlpha(45)
        border = QColor(color)
        border.setAlpha(140)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(bg)
        painter.setPen(border)
        painter.drawRoundedRect(pill, 9.0, 9.0)

        f = QFont(option.font)
        f.setPointSize(8)
        painter.setFont(f)
        painter.setPen(color)
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, status)

        painter.restore()
