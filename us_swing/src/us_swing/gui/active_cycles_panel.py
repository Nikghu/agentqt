"""
Module: MD-GUI-014.001.M01 — ActiveCyclesPanel + _RowActionsDelegate
Parent SRD: SRD-GUI-014.001, .003-.006, .008-.012

Replaces the right pane of `_ExecutionPanel` with a unified PENDING /
OPENING / OPEN / CLOSING table. Subscribes to FO-EXE-011 pending-signal
signals and FO-EXE-012 TradeCycleEvent payloads via a Qt-queued bridge;
all business logic flows through the cycle Command surface and the
pending-signal store — the panel is a renderer + action emitter.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import (
    QEvent,
    QModelIndex,
    QRect,
    QSize,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QMessageBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from us_swing.execution.strategy_engine import StrategyEntered
from us_swing.execution.trade_cycle import (
    CycleAborted,
    CycleClosed,
    CycleClosing,
    CycleOpened,
    CycleUpdated,
    InvariantViolation,
    RiskUpdated,
)
from us_swing.gui.active_cycles_model import Col, _ActiveCyclesModel, _Row
from us_swing.gui.risk_editor_widget import _RiskEditorWidget
from us_swing.gui.theme import C

if TYPE_CHECKING:
    from us_swing.execution.pending_signal_store import PendingSignalStore
    from us_swing.execution.trade_cycle import TradeCycleCommand, TradeCycleQuery

log = logging.getLogger(__name__)

_ACTIONS_W = 200
_BTN_GAP = 6


# ── Row Actions Delegate ─────────────────────────────────────────────────────


class _RowActionsDelegate(QStyledItemDelegate):
    """Paints the per-row action button bar and routes clicks to signals."""

    execute_clicked   = pyqtSignal(str)  # signal_id
    dismiss_clicked   = pyqtSignal(str)  # signal_id
    edit_risk_clicked = pyqtSignal(int)  # cycle_id
    close_clicked     = pyqtSignal(int)  # cycle_id

    def __init__(
        self,
        cb_state_provider: Callable[[], bool],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cb_provider = cb_state_provider
        self._hit_rects: dict[tuple[int, int], list[tuple[str, QRect]]] = {}

    # ── Paint ────────────────────────────────────────────────────────────

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        if index.column() != Col.ACTIONS:
            super().paint(painter, option, index)
            return

        row_data = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(row_data, _Row):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cb_on = self._cb_provider()
        state = row_data.state

        if state in ("OPENING", "CLOSING"):
            self._draw_spinner(painter, option.rect, state)
            painter.restore()
            return

        buttons: list[tuple[str, str, str]] = []  # (id, label, accent_hex)
        if state == "PENDING":
            buttons.append(("execute", "Execute", C.GREEN if not cb_on else C.MUTED))
            buttons.append(("dismiss", "Dismiss", C.MUTED))
        elif state == "OPEN":
            buttons.append(("edit",  "Edit Risk", C.BLUE))
            buttons.append(("close", "Close",     C.RED))
        else:
            painter.restore()
            return

        rects = self._layout_buttons(option.rect, len(buttons))
        key = (index.row(), index.column())
        self._hit_rects[key] = [(b[0], r) for b, r in zip(buttons, rects)]

        for (bid, label, accent), rect in zip(buttons, rects):
            disabled = bid == "execute" and cb_on
            self._draw_button(painter, rect, label, accent, disabled)

        painter.restore()

    def _draw_button(
        self,
        p: QPainter,
        rect: QRect,
        label: str,
        accent_hex: str,
        disabled: bool,
    ) -> None:
        pen = QPen(QColor(accent_hex))
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 4, 4)
        p.setPen(QColor(C.MUTED if disabled else C.TEXT))
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), label)

    def _draw_spinner(self, p: QPainter, rect: QRect, state: str) -> None:
        p.setPen(QColor(C.MUTED))
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "…")
        _ = state  # spinner animation is owned by the panel timer

    def _layout_buttons(self, cell: QRect, n: int) -> list[QRect]:
        out: list[QRect] = []
        if n == 0:
            return out
        cell_w = max(cell.width() - 12, 0)
        # Two-button layout: 80 px + 60 px when both present; else single fills.
        widths = [80, 60] if n == 2 else [min(120, cell_w)]
        widths = widths[:n]
        total = sum(widths) + (n - 1) * _BTN_GAP
        x = cell.right() - 6 - total
        y = cell.top() + (cell.height() - C.BTN_H_SM) // 2
        for w in widths:
            out.append(QRect(x, y, w, C.BTN_H_SM))
            x += w + _BTN_GAP
        return out

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        if index.column() == Col.ACTIONS:
            return QSize(_ACTIONS_W, C.BTN_H_SM + 8)
        return super().sizeHint(option, index)

    # ── Click routing ────────────────────────────────────────────────────

    def editorEvent(
        self,
        event: QEvent,
        model: Any,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        if index.column() != Col.ACTIONS:
            return False
        if not isinstance(event, QMouseEvent):
            return False
        pos = event.pos()
        rects = self._hit_rects.get((index.row(), index.column()), [])
        for bid, rect in rects:
            if not rect.contains(pos):
                continue
            row = index.data(Qt.ItemDataRole.UserRole)
            if not isinstance(row, _Row):
                return False
            if bid == "execute":
                if self._cb_provider():
                    return True  # disabled — swallow click
                if row.signal is not None:
                    self.execute_clicked.emit(row.signal.signal_id)
            elif bid == "dismiss":
                if row.signal is not None:
                    self.dismiss_clicked.emit(row.signal.signal_id)
            elif bid == "edit":
                if row.cycle_id is not None:
                    self.edit_risk_clicked.emit(row.cycle_id)
            elif bid == "close":
                if row.cycle_id is not None:
                    self.close_clicked.emit(row.cycle_id)
            return True
        return False

    def helpEvent(
        self,
        event: QEvent,
        view: Any,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if (
            event.type() == QEvent.Type.ToolTip
            and self._cb_provider()
            and index.column() == Col.ACTIONS
        ):
            row = index.data(Qt.ItemDataRole.UserRole)
            if isinstance(row, _Row) and row.state == "PENDING":
                QToolTip.showText(
                    event.globalPos(),
                    "Circuit breaker active — no new entries",
                    view,
                )
                return True
        return super().helpEvent(event, view, option, index)


# ── Active Cycles Panel ──────────────────────────────────────────────────────


class ActiveCyclesPanel(QWidget):
    """Right-pane replacement for the Execution Panel's Pending Signals.

    The panel is constructed with three Protocol-typed dependencies plus
    a reference to an `AppService`-shaped object that exposes:
      - `circuit_breaker_active: bool` property
      - `circuit_breaker_changed(bool)` pyqtSignal
      - `viewing_uid: int | None` property
      - `viewing_changed` pyqtSignal
      - `event_bus` attribute exposing a `MonitoringEventBus.subscribe`
    Plus an `exit_executor(cycle_id, reason) -> None` callable that
    dispatches a manual close through `ExecutionEngine.exit_position`.
    """

    _bridge_event = pyqtSignal(object)

    def __init__(
        self,
        *,
        cycle_query: TradeCycleQuery,
        cycle_cmd: TradeCycleCommand,
        pending_store: PendingSignalStore,
        app_service: Any,
        exit_executor: Callable[[int, str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cycle_query = cycle_query
        self._cycle_cmd = cycle_cmd
        self._pending = pending_store
        self._app = app_service
        self._exit_executor = exit_executor

        self._expanded_cycle_id: int | None = None
        self._editor: _RiskEditorWidget | None = None

        # ── Widgets ──────────────────────────────────────────────────────
        self._model = _ActiveCyclesModel(
            cycle_query,
            pending_store,
            parent=self,
            rex_counters=getattr(app_service, "rex_counters", None),
        )
        self._table = QTableView(self)
        self._table.setModel(self._model)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionMode(QTableView.SelectionMode.NoSelection)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._table.setMouseTracking(True)

        self._delegate = _RowActionsDelegate(
            cb_state_provider=lambda: bool(getattr(self._app, "circuit_breaker_active", False)),
            parent=self,
        )
        self._table.setItemDelegateForColumn(Col.ACTIONS, self._delegate)

        self._empty_label = QLabel(
            "No active cycles — pending signals and open positions appear here",
            self,
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {C.MUTED}; padding: 24px;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._table)
        root.addWidget(self._empty_label)

        # ── Wiring ───────────────────────────────────────────────────────
        self._delegate.execute_clicked.connect(self._on_execute_clicked)
        self._delegate.dismiss_clicked.connect(self._on_dismiss_clicked)
        self._delegate.edit_risk_clicked.connect(self._on_edit_risk_clicked)
        self._delegate.close_clicked.connect(self._on_close_clicked)

        self._pending.pending_signal_added.connect(self._model.on_pending_added)
        self._pending.pending_signal_removed.connect(self._model.on_pending_removed)

        self._bridge_event.connect(self._dispatch_event, Qt.ConnectionType.QueuedConnection)
        stream = getattr(self._app, "event_stream", None)
        if stream is not None and hasattr(stream, "subscribe"):
            stream.subscribe(self._bridge_event.emit)

        if hasattr(self._app, "viewing_changed"):
            self._app.viewing_changed.connect(self._on_viewing_changed)
        if hasattr(self._app, "circuit_breaker_changed"):
            self._app.circuit_breaker_changed.connect(self._on_circuit_breaker_changed)

        self._model.modelReset.connect(self._refresh_empty_state)
        self._model.rowsInserted.connect(self._refresh_empty_state)
        self._model.rowsRemoved.connect(self._refresh_empty_state)

        # Initial scope + refresh
        self._model.set_scope(getattr(self._app, "viewing_uid", None))
        self._refresh_empty_state()
        self._refresh_user_column()

    # ── Event bridge (worker-thread → GUI-thread) ────────────────────────

    @pyqtSlot(object)
    def _dispatch_event(self, evt: Any) -> None:
        if isinstance(evt, CycleOpened):
            self._model.on_cycle_opened(evt.snapshot)
        elif isinstance(evt, CycleUpdated):
            self._model.on_cycle_updated(evt.snapshot)
        elif isinstance(evt, CycleClosing):
            snap = self._cycle_query.cycle(evt.cycle_id)
            if snap is not None:
                self._model.on_cycle_state(snap)
        elif isinstance(evt, CycleClosed):
            self._model.on_cycle_closed(evt.snapshot)
            if evt.cycle_id == self._expanded_cycle_id:
                self._collapse_editor()
                log.debug("[Panel] editor auto-dismissed for closed cycle %d",
                          evt.cycle_id)
        elif isinstance(evt, CycleAborted):
            snap = self._cycle_query.cycle(evt.cycle_id)
            if snap is not None:
                self._model.on_cycle_aborted(snap)
            if evt.cycle_id == self._expanded_cycle_id:
                self._collapse_editor()
        elif isinstance(evt, RiskUpdated):
            self._model.on_cycle_updated(evt.snapshot)
        elif isinstance(evt, StrategyEntered):
            self._model.on_strategy_entered(evt.strategy_id, evt.symbol)
        # else: unknown event types are intentionally ignored

    # ── Action handlers ──────────────────────────────────────────────────

    @pyqtSlot(str)
    def _on_execute_clicked(self, signal_id: str) -> None:
        sig = next((s for s in self._pending.list() if s.signal_id == signal_id), None)
        if sig is None:
            return
        qty = sig.qty_recommended or 0
        text = (
            f"Submit BUY {qty} × {sig.symbol} @ MKT?\n"
            f"Entry ~${sig.entry_price or 0.0:.2f}  ·  "
            f"Stop ${sig.stop_loss or 0.0:.2f}  ·  "
            f"Target ${sig.target or 0.0:.2f}"
        )
        if not self._confirm("Execute pending signal", text):
            return
        executed = self._pending.execute(signal_id)
        if executed is None:
            return
        self._model.set_row_state(signal_id, "OPENING")

    @pyqtSlot(str)
    def _on_dismiss_clicked(self, signal_id: str) -> None:
        self._pending.dismiss(signal_id)
        log.info("[Execution] User dismissed signal for %s", signal_id)

    @pyqtSlot(int)
    def _on_edit_risk_clicked(self, cycle_id: int) -> None:
        if self._expanded_cycle_id == cycle_id:
            self._collapse_editor()
            return
        if self._expanded_cycle_id is not None:
            self._collapse_editor()
        self._expand_editor(cycle_id)

    @pyqtSlot(int)
    def _on_close_clicked(self, cycle_id: int) -> None:
        snap = self._cycle_query.cycle(cycle_id)
        if snap is None:
            return
        ltp = snap.current_price if snap.current_price is not None else snap.entry_price
        pnl = snap.current_pnl_usd if snap.current_pnl_usd is not None else 0.0
        sign = "+" if pnl >= 0 else "-"
        text = (
            f"Close position?\n"
            f"Submit SELL {snap.entry_qty} × {snap.symbol} @ MKT\n"
            f"Entry ${snap.entry_price:.2f}  ·  Current ~${ltp:.2f}  ·  "
            f"Est. P&L: {sign}${abs(pnl):.2f}"
        )
        if not self._confirm("Close cycle", text):
            return
        self._model.set_row_state(f"cycle:{cycle_id}", "CLOSING")
        try:
            self._exit_executor(cycle_id, "manual")
        except Exception:
            log.exception("[Panel] exit_executor failed for cycle %d", cycle_id)

    # ── Editor expand / collapse ─────────────────────────────────────────

    def _expand_editor(self, cycle_id: int) -> None:
        snap = self._cycle_query.cycle(cycle_id)
        if snap is None:
            return
        editor_row = self._model.insert_editor_row(cycle_id)
        if editor_row is None:
            return
        editor = _RiskEditorWidget(snap, parent=self._table)
        editor.saved.connect(self._on_editor_saved)
        editor.cancelled.connect(self._on_editor_cancelled)
        self._table.setSpan(editor_row, 0, 1, len(Col))
        self._table.setIndexWidget(self._model.index(editor_row, 0), editor)
        self._table.setRowHeight(editor_row, 120)
        self._editor = editor
        self._expanded_cycle_id = cycle_id

    def _collapse_editor(self) -> None:
        if self._expanded_cycle_id is None:
            return
        cid = self._expanded_cycle_id
        self._model.remove_editor_row(cid)
        if self._editor is not None:
            self._editor.deleteLater()
        self._editor = None
        self._expanded_cycle_id = None

    @pyqtSlot(int, dict)
    def _on_editor_saved(self, cycle_id: int, fields: dict[str, Any]) -> None:
        try:
            self._cycle_cmd.update_risk(cycle_id, **fields)
        except InvariantViolation as exc:
            if self._editor is not None:
                self._editor.show_error(str(exc))
            return
        except Exception:
            log.exception("[Panel] update_risk crashed for cycle %d", cycle_id)
            return
        self._collapse_editor()

    @pyqtSlot(int)
    def _on_editor_cancelled(self, cycle_id: int) -> None:
        _ = cycle_id
        self._collapse_editor()

    # ── Scope + CB ───────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_viewing_changed(self) -> None:
        new_uid = getattr(self._app, "viewing_uid", None)
        self._model.set_scope(new_uid)
        self._refresh_user_column()

    @pyqtSlot(bool)
    def _on_circuit_breaker_changed(self, _active: bool) -> None:
        # Force a delegate repaint of the ACTIONS column for every PENDING row.
        for r in range(self._model.rowCount()):
            idx = self._model.index(r, int(Col.ACTIONS))
            self._table.update(idx)

    def _refresh_user_column(self) -> None:
        show_user = self._model.scope_user_id is None
        self._table.setColumnHidden(int(Col.USER), not show_user)

    # ── Empty state ──────────────────────────────────────────────────────

    @pyqtSlot()
    def _refresh_empty_state(self) -> None:
        empty = self._model.rowCount() == 0
        self._table.setVisible(not empty)
        self._empty_label.setVisible(empty)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _confirm(self, title: str, text: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    # ── Test helpers ─────────────────────────────────────────────────────

    @property
    def model(self) -> _ActiveCyclesModel:
        return self._model

    @property
    def delegate(self) -> _RowActionsDelegate:
        return self._delegate

    @property
    def expanded_cycle_id(self) -> int | None:
        return self._expanded_cycle_id

    # Used by smoke tests to drive the bridge synchronously.
    def _publish_test_event(self, evt: Any) -> None:
        self._bridge_event.emit(evt)


__all__ = ["ActiveCyclesPanel", "_RowActionsDelegate"]
