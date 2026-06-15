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
    QPoint,
    QRect,
    QSize,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QColor, QCursor, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from us_swing.execution.strategy_engine import Action, StrategyEntered
from us_swing.execution.trade_cycle import (
    CycleAborted,
    CycleClosed,
    CycleClosing,
    CycleOpened,
    CycleUpdated,
    InvariantViolation,
    RiskUpdated,
)
from us_swing.gui.active_cycles_model import _STATE_BG, Col, _ActiveCyclesModel, _Row
from us_swing.gui.risk_editor_widget import _RiskEditorWidget
from us_swing.gui.theme import C

if TYPE_CHECKING:
    from us_swing.execution.pending_signal_store import PendingSignalStore
    from us_swing.execution.strategy_engine import TradeSignal
    from us_swing.execution.trade_cycle import TradeCycleCommand, TradeCycleQuery

log = logging.getLogger(__name__)

_ACTIONS_W = 88
_NUM_W = 32
_BTN_W = 26
_BTN_H = 22
_BTN_GAP = 4
_PILL_H = 18
_PILL_W = 84
_STATE_W = 165


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
        if index.column() != Col.STATE:
            super().paint(painter, option, index)
            return

        row_data = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(row_data, _Row) or row_data.kind == "editor":
            super().paint(painter, option, index)
            return

        # Default cell background (alternating / hover) without the cell text —
        # the state pill and action buttons are drawn on top.
        style = option.widget.style() if option.widget is not None else QApplication.style()
        blank = QStyleOptionViewItem(option)
        blank.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, blank, painter, option.widget)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        state = row_data.state
        cb_on = self._cb_provider()

        # State pill on the left of the cell.
        pill_color = _STATE_BG.get(state)
        if pill_color:
            pill = QRect(
                option.rect.left() + 6,
                option.rect.top() + (option.rect.height() - _PILL_H) // 2,
                _PILL_W,
                _PILL_H,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(pill_color))
            painter.drawRoundedRect(pill, 4, 4)
            painter.setPen(QColor(C.BG))
            painter.drawText(pill, int(Qt.AlignmentFlag.AlignCenter), state)

        # Action buttons on the right of the same cell.
        key = (index.row(), index.column())
        buttons: list[tuple[str, str, str]] = []  # (id, glyph, accent_hex)
        if state == "PENDING":
            is_exit = row_data.signal is not None and row_data.signal.action == Action.EXIT
            if cb_on:
                exec_accent = C.MUTED
            else:
                exec_accent = C.RED if is_exit else C.GREEN
            buttons.append(("execute", "▶", exec_accent))
            buttons.append(("dismiss", "✕", C.MUTED))
        elif state == "OPEN":
            buttons.append(("edit",  "✎", C.BLUE))
            buttons.append(("close", "■", C.RED))

        if buttons:
            rects = self._layout_buttons(option.rect, len(buttons))
            self._hit_rects[key] = [(b[0], r) for b, r in zip(buttons, rects)]
            for (bid, glyph, accent), rect in zip(buttons, rects):
                disabled = bid == "execute" and cb_on
                self._draw_button(painter, rect, glyph, accent, disabled)
        else:
            self._hit_rects[key] = []

        painter.restore()

    def _draw_button(
        self,
        p: QPainter,
        rect: QRect,
        glyph: str,
        accent_hex: str,
        disabled: bool,
    ) -> None:
        fg = QColor(C.MUTED) if disabled else QColor(accent_hex)
        pen = QPen(fg)
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 4, 4)
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), glyph)

    def _layout_buttons(self, cell: QRect, n: int) -> list[QRect]:
        out: list[QRect] = []
        if n == 0:
            return out
        total = n * _BTN_W + (n - 1) * _BTN_GAP
        x = cell.right() - 6 - total
        y = cell.top() + (cell.height() - _BTN_H) // 2
        for _ in range(n):
            out.append(QRect(x, y, _BTN_W, _BTN_H))
            x += _BTN_W + _BTN_GAP
        return out

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        if index.column() == Col.STATE:
            return QSize(_STATE_W, _BTN_H + 8)
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
        if index.column() != Col.STATE:
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
            and index.column() == Col.STATE
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


# ── Confirmation Dialog ──────────────────────────────────────────────────────


class _ConfirmDialog(QDialog):
    """Frameless, themed confirm dialog matching the app's design language.

    Replaces the native ``QMessageBox`` for trade actions. The first line of
    ``text`` is shown as the headline; the remaining lines render as muted
    detail. Returns ``True`` only when the primary button is pressed.
    """

    def __init__(
        self,
        title: str,
        text: str,
        *,
        confirm_text: str = "Confirm",
        accent: str | None = None,
        confirm_enabled: bool = True,
        warning: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        accent = accent or C.BLUE
        self._drag_pos = QPoint()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setMinimumWidth(380)

        headline, _, detail = text.partition("\n")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_title_bar(title))

        card = QFrame()
        card.setObjectName("confirm_card")
        card.setStyleSheet(
            f"#confirm_card {{ background: {C.BG}; "
            f"border-left: 3px solid {accent}; }}"
        )
        body = QVBoxLayout(card)
        body.setContentsMargins(22, 20, 22, 12)
        body.setSpacing(8)

        head_lbl = QLabel(headline)
        head_lbl.setWordWrap(True)
        head_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: 11pt; font-weight: 600; background: transparent;"
        )
        body.addWidget(head_lbl)

        if detail.strip():
            detail_lbl = QLabel(detail.strip())
            detail_lbl.setWordWrap(True)
            detail_lbl.setStyleSheet(
                f"color: {C.MUTED}; font-size: 9pt; background: transparent;"
            )
            body.addWidget(detail_lbl)

        root.addWidget(card, 1)
        root.addWidget(self._build_button_row(confirm_text, accent, confirm_enabled))

        if warning:
            root.addWidget(self._build_warning_banner(warning))

    def _build_title_bar(self, title: str) -> QWidget:
        bar = QWidget()
        bar.setObjectName("title_bar")
        bar.setFixedHeight(38)
        bar.setStyleSheet(f"#title_bar {{ background: {C.SURFACE}; }}")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 6, 0)
        row.setSpacing(0)

        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {C.SUBTEXT}; font-size: 9pt; font-weight: bold; "
            f"letter-spacing: 1px; background: transparent;"
        )
        row.addWidget(lbl)
        row.addStretch()

        close = QPushButton("✕")
        close.setFixedSize(30, 26)
        close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.SUBTEXT}; border: none;"
            f" padding: 0; font-size: 13px; font-weight: bold; min-height: 26px;"
            f" max-height: 26px; border-radius: 4px; outline: none; }}"
            f"QPushButton:hover {{ background: #c0392b; color: #ffffff; }}"
        )
        close.clicked.connect(self.reject)
        row.addWidget(close)
        return bar

    def _build_button_row(
        self, confirm_text: str, accent: str, confirm_enabled: bool = True
    ) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet(f"background: {C.BG};")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(22, 4, 22, 18)
        row.setSpacing(10)
        row.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel.setFixedWidth(96)
        cancel.setStyleSheet(
            f"QPushButton {{ background: {C.OVERLAY}; color: {C.TEXT}; border: none;"
            f" border-radius: 5px; font-size: 9pt; outline: none; }}"
            f"QPushButton:hover {{ background: {C.OVERLAY2}; }}"
            f"QPushButton:focus {{ outline: none; }}"
        )
        cancel.clicked.connect(self.reject)

        confirm = QPushButton(confirm_text)
        confirm.setFixedWidth(118)
        confirm.setEnabled(confirm_enabled)
        if confirm_enabled:
            confirm.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            confirm.setDefault(True)
            confirm.setStyleSheet(
                f"QPushButton {{ background: {accent}; color: {C.SURFACE}; border: none;"
                f" border-radius: 5px; font-size: 9pt; font-weight: bold; outline: none; }}"
                f"QPushButton:hover {{ background: {accent}; color: {C.BG}; }}"
                f"QPushButton:focus {{ outline: none; }}"
            )
            confirm.clicked.connect(self.accept)
        else:
            confirm.setStyleSheet(
                f"QPushButton {{ background: {C.OVERLAY}; color: {C.MUTED}; border: none;"
                f" border-radius: 5px; font-size: 9pt; font-weight: bold; outline: none; }}"
            )

        row.addWidget(cancel)
        row.addWidget(confirm)
        return wrap

    def _build_warning_banner(self, warning: str) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet(f"background: {C.BG};")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(22, 0, 22, 14)
        row.setSpacing(6)

        icon = QLabel("⚠")
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        icon.setStyleSheet(
            f"color: {C.RED}; font-size: 9pt; background: transparent;"
        )

        text = QLabel(warning)
        text.setWordWrap(True)
        text.setStyleSheet(
            f"color: {C.MUTED}; font-size: 8pt; background: transparent;"
        )

        row.addWidget(icon)
        row.addWidget(text, 1)
        return wrap

    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        if ev is not None and ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent | None) -> None:
        if (
            ev is not None
            and ev.buttons() & Qt.MouseButton.LeftButton
            and not self._drag_pos.isNull()
        ):
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(ev)


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
    dispatches a manual close through `ExecutionEngine.exit_position`, and
    an `execute_executor(signal, qty) -> int` callable that submits a
    pending entry through the single broker-submit path and returns the
    order id (negative on failure).
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
        execute_executor: Callable[[TradeSignal, int], int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cycle_query = cycle_query
        self._cycle_cmd = cycle_cmd
        self._pending = pending_store
        self._app = app_service
        self._exit_executor = exit_executor
        self._execute_executor = execute_executor

        self._expanded_cycle_id: int | None = None
        self._editor: _RiskEditorWidget | None = None

        # ── Widgets ──────────────────────────────────────────────────────
        self._model = _ActiveCyclesModel(
            cycle_query,
            pending_store,
            parent=self,
            rex_counters=getattr(app_service, "rex_counters", None),
            user_name_provider=self._lookup_user_name,
            tz_provider=self._market_timezone,
        )
        self._table = QTableView(self)
        self._table.setModel(self._model)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionMode(QTableView.SelectionMode.NoSelection)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(int(Col.NUM), QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(int(Col.STATE), QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(int(Col.NUM), _NUM_W)
        self._table.setColumnWidth(int(Col.STATE), _STATE_W)
        # ACTIONS column is now empty — its buttons render inside the STATE cell.
        self._table.setColumnHidden(int(Col.ACTIONS), True)
        self._table.setMouseTracking(True)

        self._delegate = _RowActionsDelegate(
            cb_state_provider=lambda: bool(getattr(self._app, "circuit_breaker_active", False)),
            parent=self,
        )
        self._table.setItemDelegateForColumn(Col.STATE, self._delegate)

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
        self._pending.pending_signal_dismissed.connect(self._model.on_pending_dismissed)
        self._pending.pending_signal_executed.connect(self._model.on_pending_removed)

        if hasattr(self._app, "pending_tick"):
            self._app.pending_tick.connect(self._model.on_pending_tick)

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

        # Initial scope + refresh. refresh() is called explicitly because
        # set_scope() is a no-op when the scope is unchanged (e.g. None→None),
        # which would otherwise leave open cycles surviving from a prior
        # session unloaded on startup.
        self._model.set_scope(getattr(self._app, "viewing_uid", None))
        self._model.refresh()
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
        is_exit = sig.action == Action.EXIT
        verb = "Sell" if is_exit else "Buy"
        text = (
            f"Submit {verb} {qty} × {sig.symbol} @ MKT?\n"
            f"Entry at live market   ·   "
            f"Stop ${sig.stop_loss or 0.0:.2f}   ·   "
            f"Target ${sig.target or 0.0:.2f}"
        )
        # A BUY needs free margin; a SELL frees capital and is never blocked.
        confirm_enabled, warning = self._affordability(sig, qty) if not is_exit else (True, None)
        if not self._confirm(
            "EXECUTE SIGNAL",
            text,
            confirm_text=f"{verb} {sig.symbol}",
            accent=C.RED if is_exit else C.GREEN,
            confirm_enabled=confirm_enabled,
            warning=warning,
        ):
            return
        # Route through the single broker-submit path; the pending row is
        # removed via pending_signal_executed and the cycle row is inserted
        # by the authoritative CycleOpened event — never faked locally.
        order_id = self._execute_executor(sig, qty)
        if order_id < 0:
            log.warning("[Execution] Order submission failed for %s", sig.symbol)

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
            f"Close position — Sell {snap.entry_qty} × {snap.symbol} @ MKT?\n"
            f"Entry ${snap.entry_price:.2f}   ·   Current ~${ltp:.2f}   ·   "
            f"Est. P&L: {sign}${abs(pnl):.2f}"
        )
        if not self._confirm(
            "CLOSE POSITION",
            text,
            confirm_text="Close Position",
            accent=C.RED,
        ):
            return
        # No optimistic flip: the CLOSING/CLOSED row state is driven by the
        # authoritative CycleClosing/CycleClosed events.  A failed or no-op
        # exit therefore leaves the row OPEN (correct) instead of stranding
        # it in CLOSING.
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
        # Always show the owner in Active Trades, even when scoped to one user.
        self._table.setColumnHidden(int(Col.USER), False)

    # ── Empty state ──────────────────────────────────────────────────────

    @pyqtSlot()
    def _refresh_empty_state(self) -> None:
        empty = self._model.rowCount() == 0
        self._table.setVisible(not empty)
        self._empty_label.setVisible(empty)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _lookup_user_name(self, user_id: int) -> str:
        if not user_id:
            return ""
        getter = getattr(self._app, "get_user_by_id", None)
        if getter is None:
            return ""
        try:
            profile = getter(user_id)
        except Exception:
            return ""
        if profile is None:
            return ""
        return str(getattr(profile, "display_name", "") or getattr(profile, "username", ""))

    def _market_timezone(self) -> str:
        getter = getattr(self._app, "get_system_config", None)
        if getter is None:
            return "US/Eastern"
        try:
            return str(getter().market_timezone)
        except Exception:
            return "US/Eastern"

    def _confirm(
        self,
        title: str,
        text: str,
        *,
        confirm_text: str = "Confirm",
        accent: str | None = None,
        confirm_enabled: bool = True,
        warning: str | None = None,
    ) -> bool:
        dlg = _ConfirmDialog(
            title, text, confirm_text=confirm_text, accent=accent,
            confirm_enabled=confirm_enabled, warning=warning, parent=self,
        )
        return dlg.exec() == QDialog.DialogCode.Accepted

    def _affordability(self, sig: TradeSignal, qty: int) -> tuple[bool, str | None]:
        """Block the BUY confirm when global Margin Available can't cover it.

        Margin Available is the real free cash across all strategies; a manual
        entry can override the per-strategy Capital Max but never the global
        ceiling (SRD-EXE-017.022). Returns (confirm_enabled, warning_text).
        """
        margin_fn = getattr(self._app, "margin_available", None)
        if margin_fn is None or qty <= 0:
            return True, None
        price = getattr(self._app, "_market_price_for", lambda _s: None)(sig.symbol)
        if not price or price <= 0:
            price = sig.entry_price or 0.0
        if price <= 0:
            return True, None
        margin = float(margin_fn())
        needed = qty * price
        if needed <= margin:
            return True, None
        return False, (
            f"Insufficient buying power for {qty} × {sig.symbol} — "
            f"needs ${needed:,.2f}, you have ${margin:,.2f}"
        )

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
