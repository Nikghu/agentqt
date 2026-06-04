"""
Module: MD-GUI-004.001.M01 — ExecutionPanel
Parent SRD: SRD-GUI-004.001
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPoint,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.data.models import FilteredStockEntry
from us_swing.gui.active_cycles_panel import ActiveCyclesPanel
from us_swing.gui.app_service import AppService
from us_swing.gui._types import TradeSignal
from us_swing.gui.chart_panel import _build_html as _build_chart_html
from us_swing.gui.pending_signals_table_model import (
    COL_ACTION   as PS_COL_ACTION,
    COL_CURRENT  as PS_COL_CURRENT,
    COL_ENTRY    as PS_COL_ENTRY,
    COL_PNL      as PS_COL_PNL,
    COL_QTY      as PS_COL_QTY,
    COL_SIDE     as PS_COL_SIDE,
    COL_STATUS   as PS_COL_STATUS,
    COL_STOP     as PS_COL_STOP,
    COL_STRATEGY as PS_COL_STRATEGY,
    COL_SYMBOL   as PS_COL_SYMBOL,
    COL_TARGET   as PS_COL_TARGET,
    KIND_EXITED,
    KIND_PENDING_ENTRY,
    KIND_RUNNING,
    PendingSignalsTableModel,
)
from us_swing.gui.strategy_builder_dialog import (
    StrategyBuilderDialog,
    StrategyConfig,
    load_strategies,
    save_strategies,
)
from us_swing.gui.strategy_table_model import (
    COL_CAPITAL,
    COL_DELETE,
    COL_EDIT,
    COL_END,
    COL_END_DATE,
    COL_MODE,
    COL_NAME,
    COL_RESET,
    COL_RUN,
    COL_SCOPE,
    COL_START,
    COL_START_DATE,
    COL_STATUS,
    COL_STOPLOSS,
    COL_STOPLOSS_TYPE,
    COL_TARGET,
    COL_TARGET_TYPE,
    COL_TRADE_TYPE,
    StatusBadgeDelegate,
    StrategyTableModel,
)
from us_swing.gui.theme import C, active_palette, colors


# ── Temporary diagnostics flag — set False to hide the DB Info button ────────

_SHOW_DB_DIAGNOSTICS: bool = True
_INTRADAY_DB_PATH: Path = Path.home() / ".usswing" / "candles.db"

def _cell_btn_ss(border: str, fg: str) -> str:
    return (
        f"QPushButton {{ background: transparent; border: 1px solid {border};"
        f" border-radius: 3px; color: {fg}; font-size: 8pt;"
        f" min-height: {C.BTN_H_SM}px; max-height: {C.BTN_H_SM}px; outline: none; }}"
        f"QPushButton:hover {{ background: {fg}22; border-color: {fg}; }}"
        f"QPushButton:focus {{ outline: none; }}"
    )

_CELL_ICON_BTN_SS = (
    "QPushButton {{ background: transparent; border: 1px solid transparent;"
    " border-radius: 4px; outline: none; }}"
    "QPushButton:hover {{ background: {hover_bg}; border: 1px solid {fg}; }}"
    "QPushButton:focus {{ outline: none; }}"
)


def _cell_icon(kind: str, color_hex: str) -> QIcon:
    """Draw a 14×14 icon for table cell buttons: pencil, trash-can, play triangle, or stop square."""
    SIZE = 14
    pm = QPixmap(SIZE, SIZE)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color_hex)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(c)

    if kind == "edit":
        # Pencil body — diagonal filled polygon
        path = QPainterPath()
        path.moveTo(10.5, 1.5)
        path.lineTo(12.5, 3.5)
        path.lineTo(4.5, 11.5)
        path.lineTo(1.5, 12.5)
        path.lineTo(2.5, 9.5)
        path.closeSubpath()
        painter.drawPath(path)
        # Eraser cap — small semi-transparent rect at the top
        painter.setBrush(QColor(c.red(), c.green(), c.blue(), 170))
        painter.drawRect(9, 1, 4, 2)
    elif kind == "run":
        # Play triangle — pointing right, centered
        path = QPainterPath()
        path.moveTo(3.0, 1.5)
        path.lineTo(12.0, 7.0)
        path.lineTo(3.0, 12.5)
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "stop":
        # Stop square — filled rounded rect, centered
        painter.drawRoundedRect(2, 2, 10, 10, 2, 2)
    elif kind == "reset":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(c, 1.6))
        painter.drawArc(2, 2, 10, 10, 60 * 16, 260 * 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        head = QPainterPath()
        head.moveTo(11.5, 5.0)
        head.lineTo(13.5, 2.0)
        head.lineTo(9.5, 2.5)
        head.closeSubpath()
        painter.drawPath(head)
    else:
        # Trash handle
        painter.drawRoundedRect(5, 1, 4, 2, 1, 1)
        # Lid bar
        painter.drawRoundedRect(1, 3, 12, 2, 1, 1)
        # Body
        painter.drawRoundedRect(2, 6, 10, 7, 1, 1)
        # Ribs (dark cutouts to simulate vertical lines)
        painter.setBrush(QColor(0, 0, 0, 110))
        painter.drawRect(5, 7, 1, 5)
        painter.drawRect(8, 7, 1, 5)

    painter.end()
    return QIcon(pm)


# ── Strategy Table Pane ───────────────────────────────────────────────────────

class _StrategyTablePane(QWidget):
    """Strategy Builder tab — all configured strategies with inline edit and delete."""

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = demo
        self._configs: list[StrategyConfig] = load_strategies()
        demo.strategy_status_changed.connect(self._on_engine_status)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 6, 0, 0)
        root.setSpacing(6)

        # ── Model + proxy ──────────────────────────────────────────────────────
        self._model = StrategyTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)

        # ── View ───────────────────────────────────────────────────────────────
        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSortingEnabled(True)
        self._view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setAlternatingRowColors(True)
        self._view.setShowGrid(False)
        self._view.setWordWrap(False)
        self._view.setItemDelegateForColumn(COL_STATUS, StatusBadgeDelegate(self._view))
        self._view.setStyleSheet(
            f"QTableCornerButton::section {{ background: {C.BG}; border: none; }}"
        )

        vh = self._view.verticalHeader()
        if vh:
            vh.setVisible(True)
            vh.setDefaultSectionSize(28)
            vh.setMinimumWidth(32)

        hh = self._view.horizontalHeader()
        if hh:
            hh.setStretchLastSection(False)
            for col, width, mode in [
                (COL_STATUS,      110, QHeaderView.ResizeMode.Interactive),
                (COL_RUN,          42, QHeaderView.ResizeMode.Fixed),
                (COL_NAME,        130, QHeaderView.ResizeMode.Interactive),
                (COL_EDIT,         42, QHeaderView.ResizeMode.Fixed),
                (COL_DELETE,       62, QHeaderView.ResizeMode.Fixed),
                (COL_RESET,        42, QHeaderView.ResizeMode.Fixed),
                (COL_SCOPE,        90, QHeaderView.ResizeMode.Interactive),
                (COL_MODE,         70, QHeaderView.ResizeMode.Interactive),
                (COL_CAPITAL,      60, QHeaderView.ResizeMode.Interactive),
                (COL_START,        55, QHeaderView.ResizeMode.Interactive),
                (COL_END,          55, QHeaderView.ResizeMode.Interactive),
                (COL_TRADE_TYPE,   80, QHeaderView.ResizeMode.Interactive),
                (COL_START_DATE,   90, QHeaderView.ResizeMode.Interactive),
                (COL_END_DATE,     90, QHeaderView.ResizeMode.Interactive),
                (COL_TARGET,        60, QHeaderView.ResizeMode.Interactive),
                (COL_TARGET_TYPE,   70, QHeaderView.ResizeMode.Interactive),
                (COL_STOPLOSS,      60, QHeaderView.ResizeMode.Interactive),
                (COL_STOPLOSS_TYPE, 70, QHeaderView.ResizeMode.Stretch),
            ]:
                hh.setSectionResizeMode(col, mode)
                if mode != QHeaderView.ResizeMode.Stretch:
                    hh.resizeSection(col, width)

        # Label the vertical-header corner cell as the row-number column.
        corner = self._view.findChild(QAbstractButton)
        if corner is not None:
            corner.setText("#")

        self._proxy.layoutChanged.connect(lambda: self._reinject_row_widgets())
        root.addWidget(self._view, 1)

        add_btn = QPushButton("+ Add Strategy")
        add_btn.setFixedHeight(C.BTN_H)
        add_btn.setFixedWidth(130)
        add_btn.clicked.connect(self._on_add)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(add_btn)
        root.addLayout(btn_row)

        self._refresh_table()

    # ── Data helpers ──────────────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        running_override = self._demo.get_strategies_with_open_cycles()
        self._model.load(self._configs, running_override=running_override)
        self._reinject_row_widgets()

    def _reinject_row_widgets(self) -> None:
        ct = active_palette()
        for proxy_row in range(self._proxy.rowCount()):
            src_row = self._proxy.mapToSource(self._proxy.index(proxy_row, 0)).row()
            cfg = self._configs[src_row]
            # Use the effective state (same source as the STATUS badge) so the
            # Play/Stop icon never disagrees with the badge.
            state = self._model.status_for(cfg)
            is_live = state in ("RUNNING", "SQUARING_OFF")
            self._view.setIndexWidget(
                self._proxy.index(proxy_row, COL_RUN),
                self._make_run_btn(
                    "■" if is_live else "▶",
                    ct.RED if is_live else ct.GREEN,
                    lambda _, r=src_row: self._on_run(r),
                ),
            )
            self._view.setIndexWidget(
                self._proxy.index(proxy_row, COL_EDIT),
                self._make_cell_btn("edit", ct.BLUE, lambda _, r=src_row: self._on_edit(r)),
            )
            self._view.setIndexWidget(
                self._proxy.index(proxy_row, COL_DELETE),
                self._make_cell_btn("delete", ct.RED, lambda _, r=src_row: self._on_delete(r)),
            )
            self._view.setIndexWidget(
                self._proxy.index(proxy_row, COL_RESET),
                self._make_cell_btn("reset", ct.ORANGE, lambda _, r=src_row: self._on_reset(r)),
            )

    @staticmethod
    def _make_run_btn(icon_char: str, color: str, slot: Any) -> QPushButton:
        ct = active_palette()
        kind = "run" if icon_char == "▶" else "stop"
        btn = QPushButton()
        btn.setIcon(_cell_icon(kind, color))
        btn.setIconSize(QSize(14, 14))
        btn.setToolTip("Start strategy" if kind == "run" else "Stop strategy")
        btn.setStyleSheet(_CELL_ICON_BTN_SS.format(fg=color, hover_bg=ct.OVERLAY))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(slot)
        return btn

    @staticmethod
    def _make_cell_btn(kind: str, color: str, slot: Any) -> QPushButton:
        ct = active_palette()
        btn = QPushButton()
        btn.setIcon(_cell_icon(kind, color))
        btn.setIconSize(QSize(14, 14))
        tip = {"edit": "Edit", "delete": "Delete", "reset": "Reset rex counters"}.get(kind, kind.title())
        btn.setToolTip(tip)
        btn.setStyleSheet(_CELL_ICON_BTN_SS.format(fg=color, hover_bg=ct.OVERLAY))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(slot)
        return btn

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_add(self) -> None:
        existing_names = {c.name for c in self._configs}
        dlg = StrategyBuilderDialog(self, existing_names=existing_names)
        dlg.strategy_saved.connect(self._append_config)
        dlg.exec()

    def _on_edit(self, src_row: int) -> None:
        if src_row < 0 or src_row >= len(self._configs):
            return
        original = self._configs[src_row]
        existing_names = {c.name for c in self._configs}
        dlg = StrategyBuilderDialog(self, existing=original, existing_names=existing_names)

        def _on_saved(cfg: StrategyConfig) -> None:
            self._configs[src_row] = cfg
            save_strategies(self._configs)
            self._demo.reload_strategy_registry()
            self._refresh_table()

        dlg.strategy_saved.connect(_on_saved)
        dlg.exec()

    def _on_delete(self, src_row: int) -> None:
        if src_row < 0 or src_row >= len(self._configs):
            return
        cfg = self._configs[src_row]
        ret = QMessageBox.question(
            self,
            "Delete Strategy",
            f"Delete strategy '{cfg.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._configs.pop(src_row)
            save_strategies(self._configs)
            repo = getattr(self._demo, "rex_counters", None)
            if repo is not None:
                try:
                    repo.reset(cfg.name)
                except Exception:
                    pass
            self._refresh_table()

    def _on_reset(self, src_row: int) -> None:
        if src_row < 0 or src_row >= len(self._configs):
            return
        cfg = self._configs[src_row]
        repo = getattr(self._demo, "rex_counters", None)
        if repo is None:
            QMessageBox.warning(
                self,
                "Reset unavailable",
                "Rex counter repository is not initialized — restart the app and try again.",
            )
            return
        ret = QMessageBox.question(
            self,
            "Reset Strategy",
            f"Reset rex counters for '{cfg.name}'?\n\n"
            "This clears the per-stock re-entry budget so the strategy can take fresh entries.\n"
            "Open positions are NOT affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = repo.reset(cfg.name)
        except Exception as exc:
            QMessageBox.critical(self, "Reset failed", f"Could not reset counters:\n{exc}")
            return
        QMessageBox.information(
            self,
            "Reset complete",
            f"Cleared {deleted} rex counter row(s) for '{cfg.name}'.",
        )

    def _append_config(self, cfg: StrategyConfig) -> None:
        self._configs.append(cfg)
        save_strategies(self._configs)
        self._refresh_table()

    def _on_run(self, src_row: int) -> None:
        """Play/Stop toggle.

        Play (STOPPED → RUNNING): arms evaluation immediately.

        Stop (RUNNING → STOPPED or SQUARING_OFF):
        - With no open cycles: transitions to STOPPED immediately.
        - With one or more open cycles: transitions to SQUARING_OFF; the
          engine emits forced EXITs for each open cycle and auto-transitions
          to STOPPED when the last cycle closes (FO-EXE-013 AC#3).

        Stop while SQUARING_OFF: forces STOPPED once no open cycles remain
        (or the cycle ledger is absent), so a strategy can never be locked
        into the squaring-off badge; stays SQUARING_OFF while cycles remain.
        """
        if src_row < 0 or src_row >= len(self._configs):
            return
        cfg = self._configs[src_row]
        # Effective state (badge source) so a Stop icon always performs a stop,
        # even when RUNNING is forced by an open cycle.
        current = self._model.status_for(cfg)

        if current == "STOPPED":
            new_state = "RUNNING"
        elif current == "SQUARING_OFF":
            if self._demo.get_open_symbols_for_strategy(cfg.name):
                return
            new_state = "STOPPED"
        else:
            open_syms = self._demo.get_open_symbols_for_strategy(cfg.name)
            new_state = "SQUARING_OFF" if open_syms else "STOPPED"

        cfg.run_state = new_state
        save_strategies(self._configs)
        self._notify_engine_run_state(cfg.name, new_state)
        self._demo.reload_strategy_registry()
        self._refresh_table()

    def _notify_engine_run_state(self, strategy_id: str, new_state: str) -> None:
        engine = getattr(self._demo, "_strategy_engine", None)
        if engine is None:
            return
        try:
            from us_swing.execution import ExecutionEnums
            engine.set_run_state(strategy_id, ExecutionEnums.StrategyRunState(new_state))
        except Exception:
            pass

    def _on_engine_status(self, strategy_name: str, new_status: str) -> None:
        """A strategy entered or exited a position.

        The RUNNING badge is derived live from open cycles in
        ``_refresh_table`` (via ``running_override``), so we only refresh
        here. ``run_state`` must never be overwritten with the legacy
        ``"Active"`` / ``"Running"`` vocabulary — those are not valid
        ``StrategyRunState`` values and corrupt the persisted column.
        """
        self._refresh_table()


# ── Diagnostics title bar ─────────────────────────────────────────────────────

class _DiagTitleBar(QWidget):
    """Minimal drag+close title bar for the candle DB diagnostics dialog."""

    _BTN = (
        "QPushButton {{ background: transparent; color: {fg}; border: none;"
        " font-size: 14px; min-width: 32px; max-width: 32px;"
        " min-height: 28px; max-height: 28px; border-radius: 4px; }}"
        "QPushButton:hover {{ background: {hover}; }}"
    )

    def __init__(self, title: str, window: QDialog) -> None:
        super().__init__(window)
        self._win = window
        self._drag = QPoint()
        self.setObjectName("title_bar")
        self.setFixedHeight(40)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 4, 0)
        row.setSpacing(0)

        lbl = QLabel(title)
        lbl.setObjectName("top_brand")
        row.addWidget(lbl)
        row.addStretch()

        cls_btn = QPushButton("✕")
        cls_btn.setStyleSheet(self._BTN.format(fg=C.SUBTEXT, hover="#c0392b"))
        cls_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cls_btn.clicked.connect(window.close)
        row.addWidget(cls_btn)

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # type: ignore[override]
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self._win.frameGeometry().topLeft()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:  # type: ignore[override]
        if ev.buttons() & Qt.MouseButton.LeftButton and not self._drag.isNull():
            self._win.move(ev.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(ev)


# ── Candle DB diagnostics dialog ──────────────────────────────────────────────

class _CandleDbDiagDialog(QDialog):
    """Temporary diagnostic — per-symbol intraday candle DB row counts and date ranges."""

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self.setWindowTitle("Candle DB Info")
        self.setMinimumSize(860, 520)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)

        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(_DiagTitleBar("Candle DB — Intraday Stats", self))

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 12, 16, 16)
        bl.setSpacing(10)

        self._summary = QLabel("")
        self._summary.setStyleSheet(f"color: {C.MUTED}; font-size: 9pt;")
        bl.addWidget(self._summary)

        self._tbl = QTableWidget()
        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setWordWrap(False)
        self._tbl.setShowGrid(False)
        vh = self._tbl.verticalHeader()
        if vh:
            vh.setVisible(False)
        bl.addWidget(self._tbl, 1)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("Clear Old Data")
        clear_btn.setObjectName("danger_btn")
        clear_btn.setFixedWidth(130)
        clear_btn.clicked.connect(self._clear_old_data)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(90)
        refresh_btn.clicked.connect(self._load)
        btn_row.addStretch()
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(refresh_btn)
        bl.addLayout(btn_row)

        root.addWidget(body, 1)
        self._load()

    def _load(self) -> None:
        if not _INTRADAY_DB_PATH.exists():
            self._summary.setText(f"No candle database found at {_INTRADAY_DB_PATH}")
            self._tbl.setRowCount(0)
            return
        try:
            conn = sqlite3.connect(str(_INTRADAY_DB_PATH))
            data = self._query(conn)
            conn.close()
            self._populate(data)
        except Exception as exc:
            self._summary.setText(f"Error reading DB: {exc}")

    @staticmethod
    def _query(
        conn: sqlite3.Connection,
    ) -> dict[str, dict[str, tuple[int, str | None, str | None]]]:
        result: dict[str, dict[str, tuple[int, str | None, str | None]]] = {}
        for tf, tbl in (("1m", "price_1m"), ("3m", "price_3m"), ("15m", "price_15m")):
            try:
                rows = conn.execute(
                    f"SELECT symbol, COUNT(*), MIN(datetime), MAX(datetime)"  # noqa: S608
                    f" FROM {tbl} GROUP BY symbol ORDER BY symbol"
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for symbol, count, first, last in rows:
                result.setdefault(symbol, {})[tf] = (int(count), first, last)
        return result

    def _populate(
        self, data: dict[str, dict[str, tuple[int, str | None, str | None]]]
    ) -> None:
        total_1m = sum(v.get("1m", (0,))[0] for v in data.values())
        total_3m = sum(v.get("3m", (0,))[0] for v in data.values())
        total_15m = sum(v.get("15m", (0,))[0] for v in data.values())
        self._summary.setText(
            f"{len(data)} symbol(s)  —  "
            f"1m: {total_1m:,} rows  |  3m: {total_3m:,} rows  |  15m: {total_15m:,} rows"
        )

        headers = ["Symbol", "1m rows", "3m rows", "15m rows", "First bar (1m)", "Last bar (1m)"]
        self._tbl.setColumnCount(len(headers))
        self._tbl.setHorizontalHeaderLabels(headers)
        self._tbl.setRowCount(len(data))

        for row_i, (symbol, tfs) in enumerate(sorted(data.items())):
            r1m = tfs.get("1m", (0, None, None))
            r3m = tfs.get("3m", (0, None, None))
            r15m = tfs.get("15m", (0, None, None))
            first = (r1m[1] or "")[:16]
            last = (r1m[2] or "")[:16]

            vals = [symbol, str(r1m[0]), str(r3m[0]), str(r15m[0]), first, last]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                align = (
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    if col == 0
                    else Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                )
                item.setTextAlignment(int(align))
                if col == 0:
                    item.setForeground(QColor(C.BLUE))
                self._tbl.setItem(row_i, col, item)

        hdr = self._tbl.horizontalHeader()
        if hdr:
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            hdr.resizeSection(0, 80)
            for c in range(1, len(headers)):
                hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)

    def _clear_old_data(self) -> None:
        """Delete intraday candle rows for symbols not in the watch list or open positions."""
        keep: set[str] = {e.symbol for e in self._svc.get_latest_screener_results()}
        keep |= {p.symbol for p in self._svc.get_positions()}

        if not _INTRADAY_DB_PATH.exists():
            QMessageBox.information(self, "Candle DB", "No database found.")
            return

        try:
            conn = sqlite3.connect(str(_INTRADAY_DB_PATH))
            data = self._query(conn)
            conn.close()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not read DB: {exc}")
            return

        all_syms = set(data.keys())
        delete_syms = all_syms - keep
        keep_in_db = all_syms & keep

        if not delete_syms:
            QMessageBox.information(
                self, "Candle DB",
                "Nothing to delete — all symbols are already in the watch list or open positions.",
            )
            return

        ret = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete intraday candle data for {len(delete_syms)} symbol(s)?\n\n"
            f"Keep:    {len(keep_in_db)} symbol(s)  (watch list + open positions)\n"
            f"Delete:  {len(delete_syms)} symbol(s)\n\n"
            f"This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        try:
            conn = sqlite3.connect(str(_INTRADAY_DB_PATH))
            placeholders = ",".join("?" * len(delete_syms))
            syms = list(delete_syms)
            for tbl in ("price_1m", "price_3m", "price_15m"):
                try:
                    conn.execute(
                        f"DELETE FROM {tbl} WHERE symbol IN ({placeholders})",  # noqa: S608
                        syms,
                    )
                except sqlite3.OperationalError:
                    pass
            conn.commit()
            conn.close()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Delete failed: {exc}")
            return

        self._load()


# ── Intraday chart pane (3m + 15m side by side) ───────────────────────────────

_CHART_REFRESH_MS: int = 90_000  # periodic fallback re-render interval

class _IntradayChartPane(QWidget):
    """Shows two intraday TradingView charts (3m and 15m) side by side."""

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._current_symbol = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._hdr = QLabel("Select a stock to view intraday charts")
        self._apply_hdr_style(active=False)
        root.addWidget(self._hdr)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(2)
        self._apply_splitter_style()

        self._web_3m = QWebEngineView()
        self._web_3m.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._web_15m = QWebEngineView()
        self._web_15m.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._splitter.addWidget(self._web_3m)
        self._splitter.addWidget(self._web_15m)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)

        root.addWidget(self._splitter, 1)
        self._show_placeholder()

        # Qt auto-disconnects this when the widget is destroyed (QObject lifetime rule).
        svc.live_bar_data_updated.connect(self._on_live_bar)

        # Fallback timer: re-render every 90 s regardless of signal (covers
        # yfinance polling mode where candle_closed fires per-symbol but may
        # not match _current_symbol on every tick).
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(_CHART_REFRESH_MS)
        self._refresh_timer.timeout.connect(self._refresh_current)
        self._refresh_timer.start()

    def load_symbol(self, symbol: str) -> None:
        if symbol == self._current_symbol:
            return
        self._current_symbol = symbol
        self._hdr.setText(f"{symbol}  —  Intraday")
        self._apply_hdr_style(active=True)
        self._render("3m",  self._web_3m,  symbol)
        self._render("15m", self._web_15m, symbol)

    def _on_live_bar(self, symbol: str) -> None:
        """Push fresh candle data to the chart without reloading the page."""
        if symbol == self._current_symbol and self._current_symbol:
            self._update_data("3m",  self._web_3m,  symbol)
            self._update_data("15m", self._web_15m, symbol)

    def _refresh_current(self) -> None:
        """Periodic fallback data refresh — preserves zoom via JS injection."""
        if self._current_symbol:
            self._update_data("3m",  self._web_3m,  self._current_symbol)
            self._update_data("15m", self._web_15m, self._current_symbol)

    def _render(self, tf: str, web: QWebEngineView, symbol: str) -> None:
        """Full page load — only called when the selected symbol changes."""
        candles = self._svc.get_intraday_candles_for_symbol(symbol, tf)
        volume_data = self._to_volume_data(candles)
        tz = self._svc.get_system_config().market_timezone
        web.setHtml(_build_chart_html(candles, volume_data, symbol, tf, show_reset_menu=True, timezone=tz), QUrl("about:blank"))

    def _update_data(self, tf: str, web: QWebEngineView, symbol: str) -> None:
        """Inject updated candle data into the live chart page via JS."""
        page = web.page()
        if page is None:
            return
        candles = self._svc.get_intraday_candles_for_symbol(symbol, tf)
        volume_data = self._to_volume_data(candles)
        candle_json = json.dumps(candles)
        volume_json = json.dumps(volume_data)
        page.runJavaScript(
            f"if(window.updateChartData){{window.updateChartData({candle_json},{volume_json});}}"
        )

    @staticmethod
    def _to_volume_data(candles: list[dict]) -> list[dict]:
        _tc = colors()
        _vol_up = _tc["candle_up_volume"]
        _vol_dn = _tc["candle_down_volume"]
        return [
            {
                "time":  c["time"],
                "value": c["volume"],
                "color": _vol_up if c["close"] >= c["open"] else _vol_dn,
            }
            for c in candles
        ]

    def _show_placeholder(self) -> None:
        ct = active_palette()
        for label, web in [("3m", self._web_3m), ("15m", self._web_15m)]:
            html = (
                f'<!DOCTYPE html><html><body style="margin:0;background:{ct.BG};'
                f'display:flex;align-items:center;justify-content:center;'
                f'height:100vh;font-family:monospace;">'
                f'<div style="text-align:center;color:{ct.OVERLAY2};">'
                f'<div style="font-size:28px;margin-bottom:8px;">📊</div>'
                f'<div style="font-size:11px;color:{ct.MUTED};">{label.upper()}</div>'
                f'</div></body></html>'
            )
            web.setHtml(html)

    def _apply_hdr_style(self, *, active: bool) -> None:
        ct = active_palette()
        if active:
            self._hdr.setStyleSheet(
                f"color:{ct.TEXT}; font-size:9pt; font-weight:bold; padding:4px 10px;"
                f"background:{ct.SURFACE}; border-bottom:1px solid {ct.OVERLAY};"
            )
        else:
            self._hdr.setStyleSheet(
                f"color:{ct.MUTED}; font-size:8pt; padding:4px 10px;"
                f"background:{ct.SURFACE}; border-bottom:1px solid {ct.OVERLAY};"
            )

    def _apply_splitter_style(self) -> None:
        ct = active_palette()
        self._splitter.setStyleSheet(f"QSplitter::handle {{ background:{ct.OVERLAY}; }}")

    def refresh_theme(self, _theme_id: str = "") -> None:
        """Re-apply Qt styles and re-render chart HTML for the active theme."""
        self._apply_splitter_style()
        active = bool(self._current_symbol)
        self._apply_hdr_style(active=active)
        if active:
            self._render("3m",  self._web_3m,  self._current_symbol)
            self._render("15m", self._web_15m, self._current_symbol)
        else:
            self._show_placeholder()




# ── Filtered Stocks table model ───────────────────────────────────────────────

_COL_SYMBOL   = 0
_COL_SCORE    = 1
_COL_RUN      = 2
_COL_STYLE    = 3
_COL_SCREENER = 4


class _FilteredStocksModel(QAbstractTableModel):
    """Table model for the filtered stocks left pane."""

    HEADERS = ["Symbol", "Score", "Run", "Style", "Screener"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[FilteredStockEntry] = []
        self._readiness: dict[str, bool | None] = {}

    def load(self, entries: list[FilteredStockEntry]) -> None:
        self.beginResetModel()
        self._rows = entries
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        entry = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == _COL_SYMBOL:
                return entry.symbol
            if col == _COL_SCORE:
                return f"{entry.score:.3f}"
            if col == _COL_STYLE:
                return ", ".join(entry.trading_styles) if entry.trading_styles else "—"
            if col == _COL_SCREENER:
                return entry.screener_name
            if col == _COL_RUN:
                return "Auto" if entry.run_type == "scheduled" else "Manual"

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == _COL_SYMBOL:
                return QColor(C.BLUE)
            if col == _COL_SCORE:
                if entry.score >= 0.70:
                    return QColor(C.GREEN)
                if entry.score >= 0.40:
                    return QColor(C.YELLOW)
                return QColor(C.RED)
            if col == _COL_RUN:
                return QColor(C.TEAL) if entry.run_type == "scheduled" else QColor(C.BLUE)

        if role == Qt.ItemDataRole.BackgroundRole:
            if self._readiness.get(entry.symbol) is False:
                return QColor(180, 60, 60, 70)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (_COL_SCORE, _COL_RUN):
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def set_candle_readiness(self, report: dict[str, bool | None]) -> None:
        self._readiness.update(report)
        if self._rows:
            top_left = self.createIndex(0, 0)
            bot_right = self.createIndex(len(self._rows) - 1, len(self.HEADERS) - 1)
            self.dataChanged.emit(top_left, bot_right, [Qt.ItemDataRole.BackgroundRole])


# ── Filtered Stocks left pane ─────────────────────────────────────────────────

class _FilteredStocksPane(QWidget):
    """Left panel showing the most recent screener output across all presets."""

    symbol_selected = pyqtSignal(str)  # emitted on row click or auto-select

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(180)
        self._all_entries: list[FilteredStockEntry] = []

        self._current_date = ""

        # ── Header ─────────────────────────────────────────────────────────────
        hdr_lbl = QLabel("FILTERED STOCKS")
        hdr_lbl.setStyleSheet(
            f"color: {C.MUTED}; font-size: 7pt; font-weight: bold; letter-spacing: 2px;"
        )
        _meta_qss = f"color: {C.MUTED}; font-size: 8pt;"
        self._date_lbl = QLabel("")
        self._date_lbl.setStyleSheet(_meta_qss)
        self._time_lbl = QLabel("")
        self._time_lbl.setStyleSheet(_meta_qss)
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(_meta_qss)

        self._date_time_sep = QLabel(" - ")
        self._date_time_sep.setStyleSheet(_meta_qss)
        self._time_count_sep = QLabel(" - ")
        self._time_count_sep.setStyleSheet(_meta_qss)

        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 0, 0, 0)
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()
        hdr_row.addWidget(self._date_lbl)
        hdr_row.addWidget(self._date_time_sep)
        hdr_row.addWidget(self._time_lbl)
        hdr_row.addWidget(self._time_count_sep)
        hdr_row.addWidget(self._count_lbl)

        # ── Table ──────────────────────────────────────────────────────────────
        self._model = _FilteredStocksModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(_COL_SCORE, Qt.SortOrder.DescendingOrder)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        v_hdr = self._table.verticalHeader()
        assert v_hdr is not None
        v_hdr.setVisible(False)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)

        hdrs = self._table.horizontalHeader()
        assert hdrs is not None
        hdrs.setSectionResizeMode(_COL_SYMBOL,   QHeaderView.ResizeMode.Interactive)
        hdrs.resizeSection(_COL_SYMBOL, 75)
        hdrs.setSectionResizeMode(_COL_SCORE,    QHeaderView.ResizeMode.Interactive)
        hdrs.resizeSection(_COL_SCORE, 52)
        hdrs.setSectionResizeMode(_COL_RUN,      QHeaderView.ResizeMode.Interactive)
        hdrs.resizeSection(_COL_RUN, 58)
        hdrs.setSectionResizeMode(_COL_STYLE,    QHeaderView.ResizeMode.Interactive)
        hdrs.resizeSection(_COL_STYLE, 65)
        hdrs.setSectionResizeMode(_COL_SCREENER, QHeaderView.ResizeMode.Stretch)

        # ── Empty state label ─────────────────────────────────────────────────
        self._empty_lbl = QLabel("No screener results yet.\nRun a preset in the Screener tab.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 9pt; padding: 20px;")
        self._empty_lbl.setWordWrap(True)

        # Stack table and empty label — show one at a time
        self._table.setVisible(False)
        self._empty_lbl.setVisible(True)

        # ── Layout ─────────────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 6, 0)
        root.setSpacing(6)
        root.addLayout(hdr_row)
        root.addWidget(self._table, 1)
        root.addWidget(self._empty_lbl, 1)

        # ── Selection signal ───────────────────────────────────────────────────
        sel_model = self._table.selectionModel()
        assert sel_model is not None
        sel_model.currentChanged.connect(self._on_current_changed)

        # ── Wire up to service ─────────────────────────────────────────────────
        svc.screener_results_updated.connect(self._on_updated)
        svc.candle_readiness_updated.connect(self._on_candle_readiness)
        self._on_updated(svc.get_latest_screener_results())

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        src = self._proxy.mapToSource(current)
        if not src.isValid() or src.row() >= len(self._model._rows):
            return
        self.symbol_selected.emit(self._model._rows[src.row()].symbol)

    def get_top_symbol(self) -> str | None:
        """Return the symbol of the highest-score row, or None if empty."""
        idx = self._proxy.index(0, 0)
        if not idx.isValid():
            return None
        src = self._proxy.mapToSource(idx)
        if not src.isValid() or src.row() >= len(self._model._rows):
            return None
        return self._model._rows[src.row()].symbol

    def _on_updated(self, entries: list[FilteredStockEntry]) -> None:
        self._all_entries = entries
        dates = sorted({e.date for e in entries}, reverse=True)
        if not dates:
            self._current_date = ""
            self._date_lbl.setText("")
            self._time_lbl.setText("")
            self._count_lbl.setText("")
            self._date_time_sep.setVisible(False)
            self._time_count_sep.setVisible(False)
            self._table.setVisible(False)
            self._empty_lbl.setVisible(True)
            return
        self._current_date = dates[0]
        self._date_lbl.setText(
            datetime.strptime(self._current_date, "%Y-%m-%d").strftime("%d %b %Y")
        )
        latest_time = max(
            (e.time for e in entries if e.date == self._current_date and e.time),
            default="",
        )
        self._time_lbl.setText(latest_time)
        self._time_lbl.setVisible(bool(latest_time))
        self._date_time_sep.setVisible(bool(latest_time))
        self._time_count_sep.setVisible(True)
        self._filter_by_date()

    def _filter_by_date(self) -> None:
        self._model.load(self._all_entries)
        count = len(self._all_entries)
        self._count_lbl.setText(f"{count} Stock{'s' if count != 1 else ''}")
        self._table.setVisible(count > 0)
        self._empty_lbl.setVisible(count == 0)
        if count > 0:
            top = self._proxy.index(0, 0)
            if top.isValid():
                self._table.setCurrentIndex(top)

    def _on_candle_readiness(self, report: dict[str, bool | None]) -> None:
        self._model.set_candle_readiness(report)


# ── Execution Panel ───────────────────────────────────────────────────────────

class ExecutionPanel(QWidget):
    """
    FO-GUI-004 Execution Panel.
    Left pane: filtered stocks — click any row to load intraday charts.
    Right pane top: 3m and 15m TradingView charts for the selected stock.
    Right pane bottom: pending signals with qty override and execute controls.
    """

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = demo
        self._cb_active = False

        main = QVBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        # ── Header row ─────────────────────────────────────────────────────────
        title = QLabel("Trade Execution")
        title.setStyleSheet(f"color: {C.BLUE}; font-size: 12pt; font-weight: bold;")

        admin_badge = QLabel("🔐 ADMIN")
        admin_badge.setStyleSheet(
            f"color:{C.YELLOW}; background:{C.YELLOW}18; border:1px solid {C.YELLOW}55;"
            f"border-radius:5px; padding:1px 7px; font-size:7pt; font-weight:bold;"
        )

        exec_for_lbl = QLabel("Execute for:")
        exec_for_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        self._exec_user_combo = QComboBox()
        self._exec_user_combo.setMinimumWidth(140)
        self._exec_user_combo.setStyleSheet("QComboBox { outline: none; } QComboBox:focus { outline: none; }")
        self._exec_user_combo.addItem("🌐  All / Broadcast", None)
        for u in demo.get_users():
            flag = "🔴" if u.mode == "live" else "🔵"
            self._exec_user_combo.addItem(f"{flag}  {u.username}  ({u.mode.upper()})", u.user_id)
        demo.viewing_changed.connect(self._on_scope_changed)

        hdr = QHBoxLayout()
        hdr.addWidget(title)
        hdr.addWidget(admin_badge)
        hdr.addStretch()
        hdr.addWidget(exec_for_lbl)
        hdr.addWidget(self._exec_user_combo)
        main.addLayout(hdr)

        # ── Circuit breaker banner (hidden by default) ─────────────────────────
        self._cb_banner = QLabel(
            "⚠  Circuit Breaker ACTIVE — daily loss limit reached. "
            "New entries are disabled."
        )
        self._cb_banner.setObjectName("cb_banner")
        self._cb_banner.setVisible(False)
        self._cb_banner.setWordWrap(True)
        main.addWidget(self._cb_banner)
        # Circuit breaker now lives on AppService (toggled from Settings → System).
        demo.circuit_breaker_changed.connect(self.on_circuit_breaker)

        # ── Chart pane (created first so we can wire the signal) ───────────────
        self._chart_pane = _IntradayChartPane(demo)

        # ── Horizontal split: filtered stocks | right pane ─────────────────────
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setHandleWidth(2)
        h_splitter.setStyleSheet(f"QSplitter::handle {{ background: {active_palette().OVERLAY}; }}")
        self._h_splitter = h_splitter

        self._selected_symbol: str = ""
        self._left_pane = _FilteredStocksPane(demo)
        self._left_pane.symbol_selected.connect(self._on_symbol_selected)
        demo.candle_readiness_updated.connect(self._on_candle_data_ready)

        h_splitter.addWidget(self._left_pane)
        h_splitter.addWidget(self._build_right_pane(demo))
        h_splitter.setSizes([260, 900])
        h_splitter.setCollapsible(0, False)
        h_splitter.setCollapsible(1, False)

        main.addWidget(h_splitter, 1)

        # ── Seed the chart with the highest-score stock if data already exists ──
        top = self._left_pane.get_top_symbol()
        if top:
            self._on_symbol_selected(top)

    def _build_right_pane(self, demo: AppService) -> QWidget:
        """Build the right side: intraday charts (top) + tabbed bottom pane."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(6, 0, 0, 0)
        layout.setSpacing(0)

        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.setHandleWidth(2)
        self._v_splitter.setStyleSheet(f"QSplitter::handle {{ background: {active_palette().OVERLAY}; }}")

        self._v_splitter.addWidget(self._chart_pane)
        self._bottom_tabs = self._build_bottom_tabs(demo)
        self._v_splitter.addWidget(self._bottom_tabs)
        self._v_splitter.setSizes([380, 260])
        self._v_splitter.setCollapsible(0, False)
        self._v_splitter.setCollapsible(1, False)

        layout.addWidget(self._v_splitter, 1)
        return pane

    @staticmethod
    def _tab_qss() -> str:
        ct = active_palette()
        return (
            f"QTabBar::tab {{"
            f"  background: {ct.SURFACE}; color: {ct.MUTED};"
            f"  padding: 6px 16px; border: 1px solid {ct.OVERLAY}; border-bottom: none;"
            f"  border-top-left-radius: 4px; border-top-right-radius: 4px;"
            f"  margin-right: 2px; font-size: 9pt;"
            f"}}"
            f"QTabBar::tab:selected {{"
            f"  background: {ct.BG}; color: {ct.TEXT};"
            f"  border-bottom: 2px solid {ct.TEXT}; font-weight: bold;"
            f"}}"
            f"QTabBar::tab:hover:!selected {{ background: {ct.OVERLAY}; }}"
            f"QTabWidget::pane {{ border: 1px solid {ct.OVERLAY}; background: {ct.BG}; }}"
        )

    def _build_bottom_tabs(self, demo: AppService) -> QTabWidget:
        """Tabbed bottom pane: Active Trades | Strategy Builder."""
        tabs = QTabWidget()
        tabs.setStyleSheet(self._tab_qss())
        tabs.addTab(self._build_active_trades_pane(demo), "📈  Active Trades")
        tabs.addTab(self._build_strategy_tab(demo), "🛠  Strategy Builder")
        return tabs

    def _build_strategy_tab(self, demo: AppService) -> QWidget:
        """Strategy Builder pane. (Candle DB + circuit-breaker live in Settings → System.)"""
        self._strategy_pane = _StrategyTablePane(demo)
        # Retained off-screen for the dormant legacy signals view's status text.
        self._status_lbl = QLabel()
        return self._strategy_pane

    def _build_active_trades_pane(self, demo: AppService) -> QWidget:
        """SRD-GUI-014.001 — Active Trades pane wrapping `ActiveCyclesPanel`."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        def _exit_by_cycle_id(cycle_id: int, reason: str) -> None:
            cycle_query = getattr(demo, "cycle_query", None)
            if cycle_query is None:
                return
            snap = cycle_query.cycle(cycle_id)
            if snap is None:
                return
            demo.force_exit_position(snap.strategy_id, snap.symbol)

        self._active_trades_panel = ActiveCyclesPanel(
            cycle_query=demo.cycle_query,
            cycle_cmd=demo.cycle_cmd,
            pending_store=demo.pending_store,
            app_service=demo,
            exit_executor=_exit_by_cycle_id,
            execute_executor=demo.execute_signal,
            parent=pane,
        )
        layout.addWidget(self._active_trades_panel, 1)

        return pane

    def _build_signals_pane(self, demo: AppService) -> QWidget:
        """Build the signals sub-pane: unified pending + running table, status, demo button."""
        ct = active_palette()
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        hdr = QLabel("PENDING SIGNALS & ACTIVE POSITIONS")
        hdr.setStyleSheet(
            f"color: {C.MUTED}; font-size: 7pt; font-weight: bold; letter-spacing: 2px;"
        )
        layout.addWidget(hdr)

        # ── Unified table view ────────────────────────────────────────────────
        self._signals_model = PendingSignalsTableModel(self)
        self._signals_view = QTableView()
        self._signals_view.setModel(self._signals_model)
        self._signals_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._signals_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._signals_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._signals_view.setAlternatingRowColors(True)
        self._signals_view.setShowGrid(False)
        self._signals_view.setWordWrap(False)
        self._signals_view.setStyleSheet(
            f"QTableCornerButton::section {{ background: {ct.BG}; border: none; }}"
        )

        vh = self._signals_view.verticalHeader()
        if vh:
            vh.setVisible(False)
            vh.setDefaultSectionSize(C.BTN_H_SM + 4)

        hh = self._signals_view.horizontalHeader()
        if hh:
            hh.setStretchLastSection(False)
            for col, width, mode in [
                (PS_COL_STATUS,    110, QHeaderView.ResizeMode.Interactive),
                (PS_COL_STRATEGY,  120, QHeaderView.ResizeMode.Interactive),
                (PS_COL_SYMBOL,     70, QHeaderView.ResizeMode.Interactive),
                (PS_COL_SIDE,       55, QHeaderView.ResizeMode.Interactive),
                (PS_COL_ENTRY,      70, QHeaderView.ResizeMode.Interactive),
                (PS_COL_STOP,       70, QHeaderView.ResizeMode.Interactive),
                (PS_COL_TARGET,     70, QHeaderView.ResizeMode.Interactive),
                (PS_COL_CURRENT,    70, QHeaderView.ResizeMode.Interactive),
                (PS_COL_PNL,        80, QHeaderView.ResizeMode.Interactive),
                (PS_COL_QTY,        55, QHeaderView.ResizeMode.Interactive),
                (PS_COL_ACTION,    110, QHeaderView.ResizeMode.Fixed),
            ]:
                hh.setSectionResizeMode(col, mode)
                hh.resizeSection(col, width)

        layout.addWidget(self._signals_view, 1)

        # ── Empty-state overlay label (shown when table is empty) ─────────────
        self._signals_empty_lbl = QLabel("No pending signals or open positions.")
        self._signals_empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._signals_empty_lbl.setStyleSheet(f"color: {C.MUTED}; padding: 12px;")
        layout.addWidget(self._signals_empty_lbl)

        # ── Status line + demo CB toggle ──────────────────────────────────────
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 9pt;")
        layout.addWidget(self._status_lbl)

        self._cb_toggle = QPushButton("Demo: Toggle Circuit Breaker")
        self._cb_toggle.setObjectName("danger_btn")
        self._cb_toggle.setFixedWidth(240)
        self._cb_toggle.clicked.connect(self._toggle_cb)
        cb_row = QHBoxLayout()
        cb_row.addStretch()
        if _SHOW_DB_DIAGNOSTICS:
            diag_btn = QPushButton("Candle DB")
            diag_btn.setFixedWidth(100)
            diag_btn.clicked.connect(lambda: _CandleDbDiagDialog(self._demo, self).exec())
            cb_row.addWidget(diag_btn)
        cb_row.addWidget(self._cb_toggle)
        layout.addLayout(cb_row)

        demo.pending_signals_updated.connect(self._refresh_signals_pane)
        demo.positions_updated.connect(self._refresh_signals_pane)
        self._refresh_signals_pane()

        return pane

    def _refresh_signals_pane(self) -> None:
        """Reload pending + running + today's exited rows into the model."""
        pending = self._demo.get_pending_signals()
        running = self._demo.get_active_strategy_positions()
        exited  = self._demo.get_recent_closed_cycles()
        self._signals_model.load(
            pending, running, self._demo.get_latest_close, exited=exited
        )
        self._inject_action_buttons()
        total = len(pending) + len(running) + len(exited)
        self._signals_view.setVisible(total > 0)
        self._signals_empty_lbl.setVisible(total == 0)
        self._status_lbl.setText(
            f"{len(pending)} pending · {len(running)} running · "
            f"{len(exited)} exited today"
        )
        self._status_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 9pt;")

    def _inject_action_buttons(self) -> None:
        """Place an Execute / Force Exit button into each row's Action column.

        EXITED rows show no button — they're informational only and roll off
        in the next day's pre-open cleanup.
        """
        for row_idx in range(self._signals_model.rowCount()):
            r = self._signals_model.row_at(row_idx)
            if r is None:
                continue
            idx = self._signals_model.index(row_idx, PS_COL_ACTION)
            if r.kind == KIND_EXITED:
                self._signals_view.setIndexWidget(idx, None)
                continue
            if r.kind == KIND_RUNNING:
                btn = self._make_force_exit_btn(r.payload)
            else:
                btn = self._make_pending_action_btn(r)
                if self._cb_active and r.kind == KIND_PENDING_ENTRY:
                    btn.setEnabled(False)
            self._signals_view.setIndexWidget(idx, btn)

    def _make_pending_action_btn(self, row: Any) -> QPushButton:
        ct = active_palette()
        fg = ct.GREEN if row.side == "BUY" else ct.RED
        btn = QPushButton(f"Execute {row.side}")
        btn.setStyleSheet(_cell_btn_ss(fg, fg))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(lambda _, payload=row.payload: self._on_table_execute(payload))
        return btn

    def _make_force_exit_btn(self, pos: Any) -> QPushButton:
        ct = active_palette()
        btn = QPushButton("Force Exit")
        btn.setStyleSheet(_cell_btn_ss(ct.RED, ct.RED))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(lambda _, p=pos: self._on_table_force_exit(p))
        return btn

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_scope_changed(self) -> None:
        """Sync the Execute-for combo with the admin viewing scope."""
        uid = self._demo.get_viewing_uid()
        for i in range(self._exec_user_combo.count()):
            if self._exec_user_combo.itemData(i) == uid:
                self._exec_user_combo.setCurrentIndex(i)
                break

    def _on_table_execute(self, signal: TradeSignal) -> None:
        """User clicked Execute on a pending row — confirm and submit."""
        qty = max(1, signal.recommended_qty)
        mode = self._demo.get_active_user().mode.upper()
        msg = (
            f"Submit <b>{signal.side}</b> order for <b>{signal.symbol}</b>?<br><br>"
            f"Qty: {qty}&nbsp;&nbsp; Entry: {signal.entry_price:.2f}"
            f"&nbsp;&nbsp; Mode: {mode}"
        )
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Confirm Order")
        dlg.setIcon(QMessageBox.Icon.Question)
        dlg.setText(msg)
        dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dlg.setDefaultButton(QMessageBox.StandardButton.Yes)
        if dlg.exec() != QMessageBox.StandardButton.Yes:
            return
        order_id = self._demo.execute_signal(signal, qty)
        self._status_lbl.setText(
            f"✔  Order #{order_id} submitted for {signal.symbol} × {qty}"
        )
        self._status_lbl.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")

    def _on_table_force_exit(self, pos: Any) -> None:
        """User clicked Force Exit on a running row — confirm and submit market exit."""
        last = self._demo.get_latest_close(pos.symbol, "3m")
        cur_str = f"{last:.2f}" if last is not None else "market"
        msg = (
            f"Manually exit <b>{pos.symbol}</b> from strategy "
            f"<b>{pos.strategy_id}</b>?<br><br>"
            f"Qty: {pos.quantity}&nbsp;&nbsp; Entry: {pos.average_price:.2f}"
            f"&nbsp;&nbsp; Exit @ {cur_str}"
        )
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Confirm Force Exit")
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setText(msg)
        dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dlg.setDefaultButton(QMessageBox.StandardButton.No)
        if dlg.exec() != QMessageBox.StandardButton.Yes:
            return
        order_id = self._demo.force_exit_position(pos.strategy_id, pos.symbol)
        if order_id is None:
            self._status_lbl.setText(f"⚠  No open cycle found for {pos.symbol}")
            self._status_lbl.setStyleSheet(f"color: {C.ORANGE}; font-size: 9pt;")
            return
        self._status_lbl.setText(
            f"✔  Force exit submitted for {pos.symbol} × {pos.quantity}"
        )
        self._status_lbl.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")

    def _on_symbol_selected(self, symbol: str) -> None:
        self._selected_symbol = symbol
        self._chart_pane.load_symbol(symbol)

    def _on_candle_data_ready(self, _: dict[str, bool | None]) -> None:
        if self._selected_symbol:
            self._chart_pane.load_symbol(self._selected_symbol)

    def on_circuit_breaker(self, active: bool) -> None:
        """Disable pending-entry buttons in the signals table and show banner."""
        self._cb_active = active
        self._cb_banner.setVisible(active)
        # Legacy signals pane is dormant; ActiveCyclesPanel handles its own delegate state.
        if hasattr(self, "_signals_view"):
            self._inject_action_buttons()
        if active:
            self._demo.log_message.emit("WARNING", "Circuit breaker activated — entries disabled")

    def refresh_theme(self, _theme_id: str = "") -> None:
        """Re-apply splitter styles and delegate chart refresh for the active theme."""
        ct = active_palette()
        self._h_splitter.setStyleSheet(f"QSplitter::handle {{ background: {ct.OVERLAY}; }}")
        self._v_splitter.setStyleSheet(f"QSplitter::handle {{ background: {ct.OVERLAY}; }}")
        self._bottom_tabs.setStyleSheet(self._tab_qss())
        self._chart_pane.refresh_theme()
