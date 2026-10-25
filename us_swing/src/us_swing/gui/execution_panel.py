"""
Module: MD-GUI-004.001.M01 — ExecutionPanel
Parent SRD: SRD-GUI-004.001
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    QPoint,
    QSettings,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QMouseEvent
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.active_cycles_panel import ActiveCyclesPanel
from us_swing.gui.app_service import AppService, _IntradayCandleWorker
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui._types import TradeSignal
from us_swing.gui.execution_header import ExecutionHeader
from us_swing.gui.execution_watchlist import WatchlistPane
from us_swing.gui.strategies_pane import StrategiesPane
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
from us_swing.gui.icons import mark_danger, set_icon
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
        set_icon(clear_btn, "eraser", "danger")
        clear_btn.setFixedWidth(130)
        clear_btn.clicked.connect(self._clear_old_data)
        refresh_btn = QPushButton("Refresh")
        set_icon(refresh_btn, "refresh-cw", "info")
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
CHARTS_HIDDEN_KEY = "charts_hidden"


class _IntradayChartPane(QWidget):
    """Shows two intraday TradingView charts (3m and 15m) side by side.

    SRD-GUI-024.008 — the hidden / shown state (toggled from the page
    header) is remembered in ``settings``.
    """

    charts_toggled = pyqtSignal(bool)  # True = hidden

    def __init__(
        self,
        svc: AppService,
        parent: QWidget | None = None,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self._svc = svc
        self._current_symbol = ""
        self._settings = settings or QSettings("USSwing", "ExecutionPanel")

        # One in-flight candle read per timeframe; a request that arrives while
        # a read is running is held in _pending and run when the current one
        # finishes (latest request wins — older pending requests are dropped).
        self._workers: dict[str, _IntradayCandleWorker | None] = {"3m": None, "15m": None}
        self._pending: dict[str, tuple[str, str]] = {}   # tf -> (symbol, mode)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

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
        self.charts_hidden = False
        self.set_charts_hidden(bool(self._settings.value(CHARTS_HIDDEN_KEY, False, type=bool)))

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
        self._request_candles("3m",  symbol, "render")
        self._request_candles("15m", symbol, "render")

    def _on_live_bar(self, symbol: str) -> None:
        """Push fresh candle data to the chart without reloading the page."""
        if symbol == self._current_symbol and self._current_symbol:
            self._request_candles("3m",  symbol, "update")
            self._request_candles("15m", symbol, "update")

    def _refresh_current(self) -> None:
        """Periodic fallback data refresh — preserves zoom via JS injection."""
        if self._current_symbol:
            self._request_candles("3m",  self._current_symbol, "update")
            self._request_candles("15m", self._current_symbol, "update")

    def _request_candles(self, tf: str, symbol: str, mode: str) -> None:
        """Dispatch an off-thread candle read so the GUI thread never blocks.

        ``mode`` is ``"render"`` (full page load on symbol change) or
        ``"update"`` (JS data injection on live bar / timer). While a read for
        *tf* is already running the request is held in ``_pending`` and run
        when that read finishes; a pending full render is never downgraded to
        an update for the same symbol.
        """
        if self._workers.get(tf) is not None:
            prev = self._pending.get(tf)
            if prev is not None and prev[0] == symbol and prev[1] == "render" and mode == "update":
                return
            self._pending[tf] = (symbol, mode)
            return
        self._start_worker(tf, symbol, mode)

    def _start_worker(self, tf: str, symbol: str, mode: str) -> None:
        worker = _IntradayCandleWorker(self._svc, symbol, tf)
        worker.done.connect(
            lambda s, t, candles, m=mode: self._on_candles_ready(s, t, candles, m)
        )
        worker.finished.connect(lambda t=tf: self._on_worker_finished(t))
        self._workers[tf] = worker
        worker.start()

    def _on_worker_finished(self, tf: str) -> None:
        self._workers[tf] = None
        pending = self._pending.pop(tf, None)
        if pending is not None:
            symbol, mode = pending
            self._start_worker(tf, symbol, mode)

    def _on_candles_ready(self, symbol: str, tf: str, candles: list[dict], mode: str) -> None:
        if symbol != self._current_symbol:
            return   # user switched symbols while the read was in flight
        web = self._web_3m if tf == "3m" else self._web_15m
        if mode == "render":
            self._render(tf, web, symbol, candles)
        else:
            self._update_data(tf, web, candles)

    def _render(self, tf: str, web: QWebEngineView, symbol: str, candles: list[dict]) -> None:
        """Full page load — only called when the selected symbol changes."""
        volume_data = self._to_volume_data(candles)
        tz = self._svc.get_system_config().market_timezone
        web.setHtml(_build_chart_html(candles, volume_data, symbol, tf, show_reset_menu=True, timezone=tz), QUrl("about:blank"))

    def _update_data(self, tf: str, web: QWebEngineView, candles: list[dict]) -> None:
        """Inject updated candle data into the live chart page via JS."""
        page = web.page()
        if page is None:
            return
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

    def set_charts_hidden(self, hidden: bool) -> None:
        """Hide or show the charts and remember it (SRD-GUI-024.008)."""
        self.charts_hidden = hidden
        self._settings.setValue(CHARTS_HIDDEN_KEY, hidden)
        self.charts_toggled.emit(hidden)

    def _apply_splitter_style(self) -> None:
        ct = active_palette()
        self._splitter.setStyleSheet(f"QSplitter::handle {{ background:{ct.OVERLAY}; }}")

    def refresh_theme(self, _theme_id: str = "") -> None:
        """Re-apply Qt styles and re-render chart HTML for the active theme."""
        self._apply_splitter_style()
        if self._current_symbol:
            self._request_candles("3m",  self._current_symbol, "render")
            self._request_candles("15m", self._current_symbol, "render")
        else:
            self._show_placeholder()




_TAB_NAMES = ("Active trades", "Strategies", "Closed today")
_GAP_HANDLE_QSS = "QSplitter::handle { background: transparent; }"


# ── Execution Panel ───────────────────────────────────────────────────────────

class ExecutionPanel(QWidget):
    """
    FO-GUI-004 Execution Panel, laid out as the FO-GUI-024 workspace.
    Top: page header.  Left card: grouped watchlist — click a symbol to load
    its charts.  Right column: tab card (Active trades / Strategies / Closed
    today) above the 3m and 15m charts, which can be hidden.
    """

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = demo
        self._cb_active = False

        # Cards on the gutter with a GAP between them, like the Screener (SRD-GUI-023.002).
        gutter(self)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(GAP)

        # ── Page header (SRD-GUI-024.001) ──────────────────────────────────────
        self._header = ExecutionHeader(demo)
        head_box = QWidget()
        head_col = QVBoxLayout(head_box)
        head_col.setContentsMargins(0, 0, 0, 0)
        head_col.setSpacing(0)
        head_col.addWidget(self._header)

        # ── Circuit breaker banner (hidden by default) ─────────────────────────
        self._cb_banner = QLabel(
            "⚠  Circuit Breaker ACTIVE — daily loss limit reached. "
            "New entries are disabled."
        )
        self._cb_banner.setObjectName("cb_banner")
        self._cb_banner.setVisible(False)
        self._cb_banner.setWordWrap(True)
        head_col.addWidget(self._cb_banner)
        main.addWidget(card(head_box))
        # Circuit breaker lives on AppService (toggled from the page header, SRD-GUI-027.009).
        demo.circuit_breaker_changed.connect(self.on_circuit_breaker)

        # ── Chart pane (created first so we can wire the signal) ───────────────
        self._chart_pane = _IntradayChartPane(demo)

        # ── Horizontal split: watchlist card | right column ────────────────────
        h_splitter = gutter(QSplitter(Qt.Orientation.Horizontal))
        h_splitter.setHandleWidth(GAP)
        h_splitter.setStyleSheet(_GAP_HANDLE_QSS)
        self._h_splitter = h_splitter

        self._selected_symbol: str = ""
        self._left_pane = WatchlistPane(demo)
        self._left_pane.symbol_selected.connect(self._on_symbol_selected)
        demo.candle_readiness_updated.connect(self._on_candle_data_ready)

        h_splitter.addWidget(card(self._left_pane))
        h_splitter.addWidget(self._build_right_pane(demo))
        h_splitter.setSizes([250, 950])
        h_splitter.setCollapsible(0, False)
        h_splitter.setCollapsible(1, False)

        main.addWidget(h_splitter, 1)

        # ── Seed the chart with the highest-score stock if data already exists ──
        top = self._left_pane.get_top_symbol()
        if top:
            self._on_symbol_selected(top)

    def _build_right_pane(self, demo: AppService) -> QWidget:
        """Right column: tab card on top, intraday charts below (SRD-GUI-024.008)."""
        self._v_splitter = gutter(QSplitter(Qt.Orientation.Vertical))
        self._v_splitter.setHandleWidth(GAP)
        self._v_splitter.setStyleSheet(_GAP_HANDLE_QSS)

        self._bottom_tabs = self._build_bottom_tabs(demo)
        self._v_splitter.addWidget(card(self._bottom_tabs))
        self._chart_card = card(self._chart_pane)
        self._v_splitter.addWidget(self._chart_card)
        self._v_splitter.setStretchFactor(0, 3)
        self._v_splitter.setStretchFactor(1, 2)
        self._v_splitter.setCollapsible(0, False)
        self._v_splitter.setCollapsible(1, False)
        self._chart_pane.charts_toggled.connect(self._on_charts_toggled)
        self._header.charts_btn.clicked.connect(
            lambda: self._chart_pane.set_charts_hidden(not self._chart_pane.charts_hidden)
        )
        self._on_charts_toggled(self._chart_pane.charts_hidden)
        return self._v_splitter

    def _on_charts_toggled(self, hidden: bool) -> None:
        """Hidden: the chart card goes away; shown: 3 : 2 split."""
        self._chart_card.setVisible(not hidden)
        self._header.show_charts_state(hidden)
        if not hidden:
            total = max(self._v_splitter.height(), 500)
            self._v_splitter.setSizes([total * 3 // 5, total * 2 // 5])

    def _build_bottom_tabs(self, demo: AppService) -> QWidget:
        """Tab card: Active trades | Strategies | Closed today (SRD-GUI-024.003)."""
        self._tab_bar = QTabBar()
        self._tab_bar.setObjectName("exec_tabs")
        self._tab_bar.setDrawBase(False)
        self._tab_bar.setExpanding(False)
        for label in _TAB_NAMES:
            self._tab_bar.addTab(label)

        self._tab_stack = QStackedWidget()
        self._tab_stack.addWidget(self._build_active_trades_pane(demo))
        self._strategy_pane = StrategiesPane(demo)
        self._tab_stack.addWidget(self._strategy_pane)
        # Retained off-screen for the dormant legacy signals view's status text.
        self._status_lbl = QLabel()

        self._active_trades_panel.counts_changed.connect(self._on_trade_counts)
        self._strategy_pane.count_changed.connect(lambda n: self._set_tab_count(1, n))
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._on_tab_changed(0)
        self._set_tab_count(1, self._strategy_pane.list.count())

        card = QWidget()
        box = QVBoxLayout(card)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(14, 0, 14, 0)
        bar_row.addWidget(self._tab_bar)
        bar_row.addStretch(1)
        box.addLayout(bar_row)
        box.addWidget(self._tab_stack, 1)
        return card

    def _set_tab_count(self, index: int, count: int) -> None:
        self._tab_bar.setTabText(index, f"{_TAB_NAMES[index]} · {count}")

    def _on_trade_counts(self, active: int, closed: int) -> None:
        self._set_tab_count(0, active)
        self._set_tab_count(2, closed)

    def _on_tab_changed(self, index: int) -> None:
        self._tab_stack.setCurrentIndex(1 if index == 1 else 0)
        if index != 1:
            self._active_trades_panel.set_row_filter("closed" if index == 2 else "active")

    def _build_active_trades_pane(self, demo: AppService) -> QWidget:
        """SRD-GUI-014.001 — Active Trades pane wrapping `ActiveCyclesPanel`."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        def _exit_by_cycle_id(cycle_id: int, reason: str) -> None:
            demo.force_exit_cycle(cycle_id, reason)

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
            set_icon(diag_btn, "database", "info")
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
        set_icon(btn, "log-out", "danger", 13)
        mark_danger(btn)
        btn.setStyleSheet(_cell_btn_ss(ct.RED, ct.RED))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(lambda _, p=pos: self._on_table_force_exit(p))
        return btn

    # ── Slots ─────────────────────────────────────────────────────────────────

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
        """Delegate chart refresh for the active theme."""
        self._chart_pane.refresh_theme()
