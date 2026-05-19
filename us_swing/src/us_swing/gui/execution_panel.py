"""
Module: MD-GUI-004 — execution_panel.py
FO-GUI-004 Execution Panel: pending signals + override qty + execute entry.
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
    QSortFilterProxyModel,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QMouseEvent
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.data.models import FilteredStockEntry
from us_swing.gui.app_service import AppService
from us_swing.gui._types import TradeSignal
from us_swing.gui.chart_panel import _build_html as _build_chart_html
from us_swing.gui.theme import C, active_palette, colors


# ── Temporary diagnostics flag — set False to hide the DB Info button ────────

_SHOW_DB_DIAGNOSTICS: bool = True
_INTRADAY_DB_PATH: Path = Path.home() / ".usswing" / "candles.db"


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


# ── Single signal row ─────────────────────────────────────────────────────────

class _SignalRow(QFrame):
    """One row in the signal list: symbol label, stats, quantity override, execute."""

    execute_requested = pyqtSignal(object, int)  # (TradeSignal, qty)

    def __init__(self, signal: TradeSignal, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._signal   = signal
        self._mode     = mode
        self._original_qty = signal.recommended_qty

        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet(f"QFrame {{ border: 1px solid {C.OVERLAY}; border-radius: 6px; }}")

        # ── Labels ─────────────────────────────────────────────────────────────
        sym = QLabel(signal.symbol)
        sym.setStyleSheet(f"color: {C.BLUE}; font-size: 13pt; font-weight: bold; border: none;")

        strat = QLabel(signal.strategy_id)
        strat.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt; border: none;")

        status_badge = QLabel("⬤  READY")
        status_badge.setStyleSheet(f"color: {C.GREEN}; font-weight: bold; font-size: 9pt; border: none;")

        price_lbl = QLabel(f"Entry: {signal.entry_price:.2f}")
        stop_lbl  = QLabel(f"Stop: {signal.stop_loss:.2f}")
        tgt_lbl   = QLabel(f"Target: {signal.target_price:.2f}")
        rr_val    = (signal.target_price - signal.entry_price) / (signal.entry_price - signal.stop_loss)
        rr_lbl    = QLabel(f"R/R: {rr_val:.1f}×")
        for lbl in (price_lbl, stop_lbl, tgt_lbl, rr_lbl):
            lbl.setStyleSheet(f"color: {C.TEXT}; font-size: 9pt; border: none;")
        rr_lbl.setStyleSheet(f"color: {C.YELLOW}; font-weight: bold; font-size: 9pt; border: none;")

        # Info column
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.addWidget(sym)
        info_col.addWidget(strat)
        info_col.addWidget(status_badge)

        # Price column
        price_col = QVBoxLayout()
        price_col.setSpacing(2)
        price_col.addWidget(price_lbl)
        price_col.addWidget(stop_lbl)
        price_col.addWidget(tgt_lbl)
        price_col.addWidget(rr_lbl)

        # Quantity column
        rec_lbl = QLabel("Rec. Qty")
        rec_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt; border: none;")
        self._spin = QSpinBox()
        self._spin.setRange(1, 10_000)
        self._spin.setValue(signal.recommended_qty)
        self._spin.setFixedWidth(90)
        self._override_lbl = QLabel("")
        self._override_lbl.setStyleSheet(f"color: {C.ORANGE}; font-size: 8pt; border: none;")
        self._spin.valueChanged.connect(self._on_qty_changed)

        qty_col = QVBoxLayout()
        qty_col.setSpacing(2)
        qty_col.addWidget(rec_lbl)
        qty_col.addWidget(self._spin)
        qty_col.addWidget(self._override_lbl)

        # Execute button
        self._exec_btn = QPushButton(f"Execute  {signal.side}")
        self._exec_btn.setObjectName("buy_btn")
        self._exec_btn.setMinimumWidth(120)
        self._exec_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._exec_btn.clicked.connect(self._on_execute)

        # Row layout
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(24)
        row.addLayout(info_col)
        row.addLayout(price_col)
        row.addStretch()
        row.addLayout(qty_col)
        row.addWidget(self._exec_btn)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_qty_changed(self, value: int) -> None:
        if value != self._original_qty:
            self._override_lbl.setText("(overridden)")
        else:
            self._override_lbl.setText("")

    def _on_execute(self) -> None:
        qty    = self._spin.value()
        symbol = self._signal.symbol
        price  = self._signal.entry_price
        mode   = self._mode.upper()
        target_lbl = self._get_target_user_label()
        executing_for = f"<br><span style='color:{C.YELLOW}; font-size:8pt;'>🔐 Admin · Executing for: {target_lbl}</span>" if target_lbl else ""
        msg    = (
            f"Submit <b>{self._signal.side}</b> order for <b>{symbol}</b>?<br><br>"
            f"Qty: {qty}&nbsp;&nbsp; Entry: {price:.2f}&nbsp;&nbsp; Mode: {mode}"
            f"{executing_for}"
        )
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Confirm Order")
        dlg.setIcon(QMessageBox.Icon.Question)
        dlg.setText(msg)
        dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dlg.setDefaultButton(QMessageBox.StandardButton.Yes)
        ret = dlg.exec()
        if ret == QMessageBox.StandardButton.Yes:
            self.execute_requested.emit(self._signal, qty)
            self.setEnabled(False)
            self._exec_btn.setText("✔  Submitted")
            self._exec_btn.setStyleSheet(f"color: {C.MUTED};")

    def _get_target_user_label(self) -> str:
        """Return the label of the target user selected in the Execution panel combo."""
        w = self.parent()
        while w is not None:
            if isinstance(w, ExecutionPanel):
                idx = w._exec_user_combo.currentIndex()
                return w._exec_user_combo.itemText(idx)
            w = w.parent()
        return ""

    def set_circuit_breaker(self, active: bool) -> None:
        self._exec_btn.setEnabled(not active)

    def refresh_mode(self, mode: str) -> None:
        self._mode = mode


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
        self._date_lbl = QLabel("")
        self._date_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt;")
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt;")

        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 0, 0, 0)
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()
        hdr_row.addWidget(self._date_lbl)
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
            self._count_lbl.setText("")
            self._table.setVisible(False)
            self._empty_lbl.setVisible(True)
            return
        self._current_date = dates[0]
        formatted = datetime.strptime(self._current_date, "%Y-%m-%d").strftime("%d %b %Y")
        self._date_lbl.setText(formatted)
        self._filter_by_date()

    def _filter_by_date(self) -> None:
        visible = [e for e in self._all_entries if e.date == self._current_date]
        self._model.load(visible)
        count = len(visible)
        self._count_lbl.setText(f"{count} stock{'s' if count != 1 else ''}")
        self._table.setVisible(count > 0)
        self._empty_lbl.setVisible(count == 0)
        if count > 0:
            # Auto-select the highest-score row (proxy row 0 — sorted desc by score)
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
        """Build the right side: intraday charts (top) + pending signals (bottom)."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(6, 0, 0, 0)
        layout.setSpacing(0)

        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.setHandleWidth(2)
        self._v_splitter.setStyleSheet(f"QSplitter::handle {{ background: {active_palette().OVERLAY}; }}")

        self._v_splitter.addWidget(self._chart_pane)
        self._v_splitter.addWidget(self._build_signals_pane(demo))
        self._v_splitter.setSizes([380, 200])
        self._v_splitter.setCollapsible(0, False)
        self._v_splitter.setCollapsible(1, False)

        layout.addWidget(self._v_splitter, 1)
        return pane

    def _build_signals_pane(self, demo: AppService) -> QWidget:
        """Build the signals sub-pane: pending signals scroll area + status + demo button."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        # Pending signals group
        group = QGroupBox("Pending Signals")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(10)

        signals = demo.get_pending_signals()
        self._signal_rows: list[_SignalRow] = []
        if signals:
            mode = demo.get_active_user().mode
            for sig in signals:
                row = _SignalRow(sig, mode)
                row.execute_requested.connect(self._on_execute)
                self._signal_rows.append(row)
                group_layout.addWidget(row)
        else:
            no_sig = QLabel("No pending signals at this time.")
            no_sig.setStyleSheet(f"color: {C.MUTED}; padding: 20px;")
            no_sig.setAlignment(Qt.AlignmentFlag.AlignCenter)
            group_layout.addWidget(no_sig)

        scroll = QScrollArea()
        scroll.setWidget(group)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {C.BG}; }}")
        layout.addWidget(scroll, 1)

        # Status line
        self._status_lbl = QLabel(f"{len(signals)} signal(s) pending — review and execute above")
        self._status_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 9pt;")
        layout.addWidget(self._status_lbl)

        # Demo CB toggle + optional diagnostics button
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

        return pane

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_scope_changed(self) -> None:
        """Sync the Execute-for combo with the admin viewing scope."""
        uid = self._demo.get_viewing_uid()
        for i in range(self._exec_user_combo.count()):
            if self._exec_user_combo.itemData(i) == uid:
                self._exec_user_combo.setCurrentIndex(i)
                break

    def _on_execute(self, signal: TradeSignal, qty: int) -> None:
        order_id = self._demo.execute_signal(signal, qty)
        self._status_lbl.setText(
            f"✔  Order #{order_id} submitted for {signal.symbol} × {qty}  —  "
            f"check Log Viewer for details"
        )
        self._status_lbl.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")

    def _toggle_cb(self) -> None:
        self._cb_active = not self._cb_active
        self.on_circuit_breaker(self._cb_active)

    def _on_symbol_selected(self, symbol: str) -> None:
        self._selected_symbol = symbol
        self._chart_pane.load_symbol(symbol)

    def _on_candle_data_ready(self, _: dict[str, bool | None]) -> None:
        if self._selected_symbol:
            self._chart_pane.load_symbol(self._selected_symbol)

    def on_circuit_breaker(self, active: bool) -> None:
        """Enable/disable all entry buttons and show banner."""
        self._cb_active = active
        self._cb_banner.setVisible(active)
        for row in self._signal_rows:
            row.set_circuit_breaker(active)
        if active:
            self._demo.log_message.emit("WARNING", "Circuit breaker activated — entries disabled")

    def refresh_theme(self, _theme_id: str = "") -> None:
        """Re-apply splitter styles and delegate chart refresh for the active theme."""
        ct = active_palette()
        self._h_splitter.setStyleSheet(f"QSplitter::handle {{ background: {ct.OVERLAY}; }}")
        self._v_splitter.setStyleSheet(f"QSplitter::handle {{ background: {ct.OVERLAY}; }}")
        self._chart_pane.refresh_theme()
