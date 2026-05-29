"""
Module: MD-GUI-014.001.M02 — _ActiveCyclesModel
Parent SRD: SRD-GUI-014.002, .004, .009, .011, .013

Unified table model for both PENDING signals (from FO-EXE-011's
PendingSignalStore) and live cycle rows (from FO-EXE-012's
TradeCycleQuery).  Incremental on_* slots are wired from the panel; the
model itself touches no thread primitives.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt
from PyQt6.QtGui import QColor

from us_swing.gui.theme import C

if TYPE_CHECKING:
    from us_swing.execution.pending_signal_store import PendingSignalStore
    from us_swing.execution.strategy_engine import RexCounterRepository, TradeSignal
    from us_swing.execution.trade_cycle import CycleSnapshot, TradeCycleQuery


class Col(IntEnum):
    NUM       = 0
    USER      = 1
    STATE     = 2
    TIME      = 3
    SYMBOL    = 4
    STRATEGY  = 5
    QTY       = 6
    ENTRY     = 7
    LTP       = 8
    PNL_USD   = 9
    PNL_PCT   = 10
    HARD_STOP = 11
    TARGET    = 12
    TRAIL     = 13
    REX       = 14
    ACTIONS   = 15


_HEADERS: dict[int, str] = {
    Col.NUM:       "#",
    Col.USER:      "User",
    Col.STATE:     "State",
    Col.TIME:      "Time",
    Col.SYMBOL:    "Symbol",
    Col.STRATEGY:  "Strategy",
    Col.QTY:       "Qty",
    Col.ENTRY:     "Entry $",
    Col.LTP:       "LTP",
    Col.PNL_USD:   "PnL $",
    Col.PNL_PCT:   "PnL %",
    Col.HARD_STOP: "Hard Stop",
    Col.TARGET:    "Target",
    Col.TRAIL:     "Trail",
    Col.REX:       "Rex",
    Col.ACTIONS:   "",
}


_STATE_BG: dict[str, str] = {
    "PENDING":   C.ORANGE,
    "OPENING":   C.BLUE,
    "OPEN":      C.GREEN,
    "CLOSING":   C.ORANGE,
    "DISMISSED": C.MUTED,
}


@dataclass
class _Row:
    kind:            str
    key:             str
    state:           str
    time:            str          = ""
    symbol:          str          = ""
    strategy:        str          = ""
    qty:             int          = 0
    entry_price:     float | None = None
    ltp:             float | None = None
    pnl_usd:         float | None = None
    pnl_pct:         float | None = None
    hard_stop:       float | None = None
    target:          float | None = None
    trail:           float | None = None
    user_id:         int          = 0
    signal:          TradeSignal | None = None
    cycle_id:        int | None   = None
    parent_cycle_id: int | None   = None
    rex_remaining:   int | None   = None


def _now_hms() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


class _ActiveCyclesModel(QAbstractTableModel):
    def __init__(
        self,
        query: TradeCycleQuery,
        pending_store: PendingSignalStore,
        parent: QObject | None = None,
        rex_counters: RexCounterRepository | None = None,
        user_name_provider: Callable[[int], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._query = query
        self._pending = pending_store
        self._rex_counters = rex_counters
        self._user_name_provider = user_name_provider or (lambda uid: "")
        self._rows: list[_Row] = []
        self._by_key: dict[str, int] = {}
        self._scope_user_id: int | None = None  # None = All Users

    # ── Bulk refresh ─────────────────────────────────────────────────────

    def refresh(self) -> None:
        self.beginResetModel()
        self._rows = [
            r for r in (
                [self._row_from_pending(s) for s in self._pending.list()] +
                [self._row_from_snap(c) for c in self._query.open_cycles()]
            )
            if self._in_scope(r)
        ]
        self._rebuild_index()
        self.endResetModel()

    # ── Incremental on_* slots (called from panel bridge) ────────────────

    def on_pending_added(self, signal: TradeSignal) -> None:
        row = self._row_from_pending(signal)
        if not self._in_scope(row):
            return
        self._insert_row(row)

    def on_pending_removed(self, signal_id: str) -> None:
        self._remove_row(signal_id)

    def on_pending_dismissed(self, signal_id: str) -> None:
        self.set_row_state(signal_id, "DISMISSED")

    def on_cycle_opened(self, snap: CycleSnapshot) -> None:
        row = self._row_from_snap(snap)
        if not self._in_scope(row):
            return
        self._insert_row(row)

    def on_cycle_updated(self, snap: CycleSnapshot) -> None:
        idx = self._by_key.get(f"cycle:{snap.cycle_id}")
        if idx is None:
            return
        row = self._rows[idx]
        changed: list[int] = []
        if row.ltp != snap.current_price:
            row.ltp = snap.current_price
            changed.append(Col.LTP)
        if row.pnl_usd != snap.current_pnl_usd:
            row.pnl_usd = snap.current_pnl_usd
            changed.append(Col.PNL_USD)
        if row.pnl_pct != snap.current_pnl_pct:
            row.pnl_pct = snap.current_pnl_pct
            changed.append(Col.PNL_PCT)
        if row.trail != snap.trailing_stop_level:
            row.trail = snap.trailing_stop_level
            changed.append(Col.TRAIL)
        if row.hard_stop != snap.hard_stop_loss:
            row.hard_stop = snap.hard_stop_loss
            changed.append(Col.HARD_STOP)
        if row.target != snap.target_price:
            row.target = snap.target_price
            changed.append(Col.TARGET)
        if not changed:
            return
        self.dataChanged.emit(
            self.index(idx, min(changed)),
            self.index(idx, max(changed)),
        )

    def on_cycle_state(self, snap: CycleSnapshot) -> None:
        idx = self._by_key.get(f"cycle:{snap.cycle_id}")
        if idx is None:
            return
        row = self._rows[idx]
        if row.state == snap.state:
            return
        row.state = snap.state
        self.dataChanged.emit(
            self.index(idx, Col.STATE),
            self.index(idx, Col.ACTIONS),
        )

    def on_cycle_closed(self, snap: CycleSnapshot) -> None:
        self._remove_row(f"cycle:{snap.cycle_id}")

    def on_cycle_aborted(self, snap: CycleSnapshot) -> None:
        self._remove_row(f"cycle:{snap.cycle_id}")

    # ── Optimistic state flips (called by panel after user click) ────────

    def set_row_state(self, key: str, new_state: str) -> None:
        idx = self._by_key.get(key)
        if idx is None:
            return
        row = self._rows[idx]
        if row.state == new_state:
            return
        row.state = new_state
        self.dataChanged.emit(
            self.index(idx, Col.STATE),
            self.index(idx, Col.ACTIONS),
        )

    # ── Editor row management ────────────────────────────────────────────

    def insert_editor_row(self, cycle_id: int) -> int | None:
        parent_idx = self._by_key.get(f"cycle:{cycle_id}")
        if parent_idx is None:
            return None
        editor = _Row(
            kind="editor",
            key=f"editor:{cycle_id}",
            state="",
            parent_cycle_id=cycle_id,
        )
        pos = parent_idx + 1
        self.beginInsertRows(QModelIndex(), pos, pos)
        self._rows.insert(pos, editor)
        self._rebuild_index()
        self.endInsertRows()
        return pos

    def remove_editor_row(self, cycle_id: int) -> None:
        self._remove_row(f"editor:{cycle_id}")

    # ── Scope ────────────────────────────────────────────────────────────

    def set_scope(self, user_id: int | None) -> None:
        if self._scope_user_id == user_id:
            return
        self._scope_user_id = user_id
        self.refresh()

    @property
    def scope_user_id(self) -> int | None:
        return self._scope_user_id

    def _in_scope(self, row: _Row) -> bool:
        if self._scope_user_id is None:
            return True
        return row.user_id == self._scope_user_id

    # ── Internal helpers ─────────────────────────────────────────────────

    def _insert_row(self, row: _Row) -> None:
        if row.key in self._by_key:
            return
        n = len(self._rows)
        self.beginInsertRows(QModelIndex(), n, n)
        self._rows.append(row)
        self._by_key[row.key] = n
        self.endInsertRows()

    def _remove_row(self, key: str) -> None:
        idx = self._by_key.get(key)
        if idx is None:
            return
        self.beginRemoveRows(QModelIndex(), idx, idx)
        del self._rows[idx]
        self._rebuild_index()
        self.endRemoveRows()

    def _rebuild_index(self) -> None:
        self._by_key = {r.key: i for i, r in enumerate(self._rows)}

    def _row_from_pending(self, signal: TradeSignal) -> _Row:
        return _Row(
            kind="pending",
            key=signal.signal_id,
            state="PENDING",
            time=_now_hms(),
            symbol=signal.symbol,
            strategy=signal.strategy_id,
            qty=signal.qty_recommended or 1,
            entry_price=signal.entry_price,
            hard_stop=signal.stop_loss,
            target=signal.target,
            user_id=signal.user_id,
            signal=signal,
            rex_remaining=self._fetch_rex(signal.strategy_id, signal.symbol),
        )

    def _row_from_snap(self, snap: CycleSnapshot) -> _Row:
        return _Row(
            kind="cycle",
            key=f"cycle:{snap.cycle_id}",
            state=snap.state,
            time=snap.entry_time[-8:] if snap.entry_time else "",
            symbol=snap.symbol,
            strategy=snap.strategy_id,
            qty=snap.entry_qty,
            entry_price=snap.entry_price,
            ltp=snap.current_price,
            pnl_usd=snap.current_pnl_usd,
            pnl_pct=snap.current_pnl_pct,
            hard_stop=snap.hard_stop_loss,
            target=snap.target_price,
            trail=snap.trailing_stop_level,
            user_id=snap.user_id,
            cycle_id=snap.cycle_id,
            rex_remaining=self._fetch_rex(snap.strategy_id, snap.symbol),
        )

    def _fetch_rex(self, strategy_id: str, symbol: str) -> int | None:
        if self._rex_counters is None or not strategy_id or not symbol:
            return None
        try:
            return self._rex_counters.get(strategy_id, symbol)
        except Exception:
            return None

    def on_strategy_entered(self, strategy_id: str, symbol: str) -> None:
        """Refresh the cached rex_remaining for any row matching (strategy, symbol)."""
        new_value = self._fetch_rex(strategy_id, symbol)
        for idx, row in enumerate(self._rows):
            if row.strategy == strategy_id and row.symbol == symbol:
                row.rex_remaining = new_value
                cell = self.index(idx, Col.REX)
                self.dataChanged.emit(cell, cell, [Qt.ItemDataRole.DisplayRole,
                                                   Qt.ItemDataRole.ForegroundRole,
                                                   Qt.ItemDataRole.ToolTipRole])

    # ── Qt model API ─────────────────────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(Col)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        return _HEADERS.get(section, "")

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        r = index.row()
        c = index.column()
        if r < 0 or r >= len(self._rows):
            return None
        row = self._rows[r]
        if role == Qt.ItemDataRole.UserRole:
            return row
        if role == int(Qt.ItemDataRole.UserRole) + 1:
            return row.state
        if row.kind == "editor":
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            if c == Col.NUM:
                return str(r + 1)
            return self._display(row, c)
        if role == Qt.ItemDataRole.BackgroundRole:
            return self._background(row, c)
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground(row, c)
        if role == Qt.ItemDataRole.ToolTipRole:
            if c == Col.REX and row.rex_remaining is not None and row.rex_remaining < 0:
                return "Rex limit reached — Reset Strategy to re-enable entries"
        return None

    def _display(self, row: _Row, col: int) -> Any:
        if col == Col.USER:
            if not row.user_id:
                return ""
            name = self._user_name_provider(row.user_id)
            return name if name else str(row.user_id)
        if col == Col.STATE:
            return row.state
        if col == Col.TIME:
            return row.time
        if col == Col.SYMBOL:
            return row.symbol
        if col == Col.STRATEGY:
            return row.strategy
        if col == Col.QTY:
            return str(row.qty)
        if col == Col.ENTRY:
            return self._fmt_money(row.entry_price)
        if col == Col.LTP:
            return self._fmt_money(row.ltp)
        if col == Col.PNL_USD:
            return self._fmt_pnl_usd(row.pnl_usd)
        if col == Col.PNL_PCT:
            return self._fmt_pnl_pct(row.pnl_pct)
        if col == Col.HARD_STOP:
            return self._fmt_money(row.hard_stop)
        if col == Col.TARGET:
            return self._fmt_money(row.target)
        if col == Col.TRAIL:
            return self._fmt_money(row.trail)
        if col == Col.REX:
            return "—" if row.rex_remaining is None else str(row.rex_remaining)
        return ""

    @staticmethod
    def _fmt_money(v: float | None) -> str:
        return "—" if v is None else f"${v:.2f}"

    @staticmethod
    def _fmt_pnl_usd(v: float | None) -> str:
        if v is None:
            return "—"
        sign = "+" if v >= 0 else "-"
        return f"{sign}${abs(v):.2f}"

    @staticmethod
    def _fmt_pnl_pct(v: float | None) -> str:
        if v is None:
            return "—"
        sign = "+" if v >= 0 else "-"
        return f"{sign}{abs(v):.2f}%"

    def _background(self, row: _Row, col: int) -> QColor | None:
        if col == Col.STATE:
            hex_code = _STATE_BG.get(row.state)
            return QColor(hex_code) if hex_code else None
        if col in (Col.PNL_USD, Col.PNL_PCT):
            v = row.pnl_usd if col == Col.PNL_USD else row.pnl_pct
            if v is None:
                return None
            return QColor(C.PNL_POS_BG) if v >= 0 else QColor(C.PNL_NEG_BG)
        return None

    def _foreground(self, row: _Row, col: int) -> QColor | None:
        if col == Col.STATE:
            return QColor(C.BG)
        if col == Col.REX:
            if row.rex_remaining is not None and row.rex_remaining < 0:
                return QColor(C.MUTED)
            return None
        if col in (Col.PNL_USD, Col.PNL_PCT):
            v = row.pnl_usd if col == Col.PNL_USD else row.pnl_pct
            if v is None:
                return None
            return QColor(C.GREEN) if v >= 0 else QColor(C.RED)
        return None


__all__ = ["Col"]
