"""
Module: MD-GUI-004.002 — PendingSignalsTableModel
Parent SRD: SRD-GUI-014 (Execution Panel — Pending Signals & Active Positions)

Unified table model that surfaces two row sources in a single Qt view:

1. **Pending signals** from ``PendingSignalStore`` — manual-mode strategy
   signals awaiting user execute/dismiss.
2. **Running positions** from the ``trade_cycles`` ledger via
   ``TradeCycleService.open_cycles()`` — paper trades currently in flight,
   shown with live unrealized PnL until exit.

Each row stays visible from pending-entry → running → exit so the user can
follow a stock's lifecycle in one place.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from us_swing.data.models import OpenPosition, TradeSignal
from us_swing.gui.theme import C

# ── Column constants ──────────────────────────────────────────────────────────

COL_STATUS   = 0
COL_STRATEGY = 1
COL_SYMBOL   = 2
COL_SIDE     = 3
COL_ENTRY    = 4
COL_STOP     = 5
COL_TARGET   = 6
COL_CURRENT  = 7
COL_PNL      = 8
COL_QTY      = 9
COL_ACTION   = 10

HEADERS = (
    "Status", "Strategy", "Symbol", "Side", "Entry",
    "Stop", "Target", "Current", "PnL", "Qty", "Action",
)


# ── Row kinds + status labels ────────────────────────────────────────────────

KIND_PENDING_ENTRY = "pending_entry"
KIND_PENDING_EXIT  = "pending_exit"
KIND_RUNNING       = "running"
KIND_EXITED        = "exited"

_STATUS_LABEL: dict[str, str] = {
    KIND_PENDING_ENTRY: "PENDING ENTRY",
    KIND_PENDING_EXIT:  "PENDING EXIT",
    KIND_RUNNING:       "RUNNING",
    KIND_EXITED:        "EXITED",
}


@dataclass(slots=True)
class _Row:
    kind:     str
    strategy: str
    symbol:   str
    side:     str
    entry:    float
    stop:     float
    target:   float
    current:  float | None
    pnl:      float | None
    qty:      int
    payload:  object   # original TradeSignal or OpenPosition

    @property
    def status_label(self) -> str:
        return _STATUS_LABEL.get(self.kind, self.kind)


# ── Model ─────────────────────────────────────────────────────────────────────

class PendingSignalsTableModel(QAbstractTableModel):
    """Read-only model — rebuilt via ``load()`` whenever upstream state changes."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._rows: list[_Row] = []

    def load(
        self,
        pending:      list[TradeSignal],
        running:      list[OpenPosition],
        price_lookup: Callable[[str], float | None],
        exited:       list[Any] | None = None,
    ) -> None:
        """Rebuild rows from pending signals, running positions, and today's exits.

        *exited* is a list of ``CycleRecord``s (closed today) — kept opaque
        here to avoid importing from the execution package.  They render as
        an EXITED row with realized PnL and no action button.
        """
        rows: list[_Row] = []
        for sig in pending:
            kind = KIND_PENDING_ENTRY if sig.side == "BUY" else KIND_PENDING_EXIT
            rows.append(_Row(
                kind     = kind,
                strategy = sig.strategy_id,
                symbol   = sig.symbol,
                side     = sig.side,
                entry    = float(sig.entry_price or 0.0),
                stop     = float(sig.stop_loss or 0.0),
                target   = float(sig.target_price or 0.0),
                current  = None,
                pnl      = None,
                qty      = int(sig.recommended_qty or 0),
                payload  = sig,
            ))
        for pos in running:
            cur = price_lookup(pos.symbol)
            pnl = (cur - pos.average_price) * pos.quantity if cur is not None else None
            rows.append(_Row(
                kind     = KIND_RUNNING,
                strategy = pos.strategy_id,
                symbol   = pos.symbol,
                side     = "LONG",
                entry    = float(pos.average_price),
                stop     = float(pos.stop_loss),
                target   = float(pos.target_price),
                current  = cur,
                pnl      = pnl,
                qty      = int(pos.quantity),
                payload  = pos,
            ))
        for c in (exited or []):
            # c is a trade_cycle.CycleSnapshot — field names differ from the
            # legacy CycleRecord (strategy_id vs strategy, entry_qty vs qty,
            # realized_pnl_usd vs pnl).
            rows.append(_Row(
                kind     = KIND_EXITED,
                strategy = c.strategy_id,
                symbol   = c.symbol,
                side     = "LONG",
                entry    = float(c.entry_price),
                stop     = float(c.hard_stop_loss or 0.0),
                target   = float(c.target_price or 0.0),
                current  = float(c.exit_price) if c.exit_price is not None else None,
                pnl      = float(c.realized_pnl_usd) if c.realized_pnl_usd is not None else None,
                qty      = int(c.entry_qty),
                payload  = c,
            ))

        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    # ── Qt model overrides ───────────────────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(
        self,
        section:     int,
        orientation: Qt.Orientation,
        role:        int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        r = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_STATUS:
                return r.status_label
            if col == COL_STRATEGY:
                return r.strategy or "—"
            if col == COL_SYMBOL:
                return r.symbol
            if col == COL_SIDE:
                return r.side
            if col == COL_ENTRY:
                return f"{r.entry:.2f}" if r.entry else "—"
            if col == COL_STOP:
                return f"{r.stop:.2f}" if r.stop else "—"
            if col == COL_TARGET:
                return f"{r.target:.2f}" if r.target else "—"
            if col == COL_CURRENT:
                return f"{r.current:.2f}" if r.current is not None else "—"
            if col == COL_PNL:
                if r.pnl is None:
                    return "—"
                sign = "+" if r.pnl >= 0 else ""
                return f"{sign}{r.pnl:.2f}"
            if col == COL_QTY:
                return str(r.qty) if r.qty else "—"
            if col == COL_ACTION:
                return ""

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == COL_STATUS:
                if r.kind == KIND_RUNNING:
                    return QColor(C.GREEN)
                if r.kind == KIND_PENDING_ENTRY:
                    return QColor(C.YELLOW)
                if r.kind == KIND_PENDING_EXIT:
                    return QColor(C.ORANGE)
                if r.kind == KIND_EXITED:
                    return QColor(C.MUTED)
            if col == COL_SYMBOL:
                return QColor(C.MUTED if r.kind == KIND_EXITED else C.BLUE)
            if col == COL_SIDE:
                if r.side == "BUY":
                    return QColor(C.GREEN)
                if r.side == "SELL":
                    return QColor(C.RED)
                return QColor(C.MUTED if r.kind == KIND_EXITED else C.TEAL)
            if col == COL_PNL and r.pnl is not None:
                return QColor(C.GREEN if r.pnl >= 0 else C.RED)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (COL_ENTRY, COL_STOP, COL_TARGET, COL_CURRENT, COL_PNL, COL_QTY):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            if col == COL_STATUS:
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        return None

    # ── Helpers ──────────────────────────────────────────────────────────────

    def row_at(self, row: int) -> _Row | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    @property
    def rows(self) -> list[_Row]:
        return list(self._rows)
