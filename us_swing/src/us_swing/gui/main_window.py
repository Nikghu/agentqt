"""
Module: MD-GUI-000 — main_window.py
QMainWindow: Frameless terminal UI — compact top bar with horizontal nav.

Layout:
  ┌──────────────────────────────────────────────────────────────────────┐
  │ ◈ US SWING  │ Dashboard  Screener  Execution  Settings │ NYSE● │ 👤 trader PAPER │ P&L │ ─ □ ✕ │
  ├──────────────────────────────────────────────────────────────────────┤
  │  CONTENT  (QStackedWidget — fills remainder)                          │
  ├──────────────────────────────────────────────────────────────────────┤
  │  STATUS BAR                                                            │
  └──────────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import logging
import math

from PyQt6.QtCore import QPoint, QPointF, QRectF, QSettings, QTimer, Qt

_log = logging.getLogger(__name__)
from PyQt6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.data.models import ConnectionStatus
from us_swing.gui.app_service import AppService
from us_swing.gui.chart_panel import CandleChartPanel
from us_swing.gui.dashboard_panel import DashboardPanel
from us_swing.gui.execution_panel import ExecutionPanel
from us_swing.gui.screener_panel import ScreenerPanel
from us_swing.gui.settings_panel import SettingsPanel
from us_swing.gui.system_store import load_system_config
from us_swing.gui.theme import C, load_theme_id


# ── Horizontal nav tab button ──────────────────────────────────────────────────

class _TabBtn(QPushButton):
    """Compact horizontal nav tab — icon + label, underline when active."""

    def __init__(self, icon: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(f"{icon}  {label}", parent)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setObjectName("tab_btn")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(38)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)



# ── Feed connect toggle ────────────────────────────────────────────────────────

class _FeedToggle(QPushButton):
    """
    Pill-shaped feed connect/disconnect toggle with animated LED indicator.

    Three states
    ────────────
    IDLE        gray pill  — "Connect Feed"
    CONNECTING  amber pill — "Connecting…" (LED breathes)
    CONNECTED   green pill — "Live Feed"   (LED glows)
    """

    IDLE       = "idle"
    CONNECTING = "connecting"
    CONNECTED  = "connected"

    # (bg, border, led, text) hex per state
    _COL: dict[str, tuple[str, str, str, str]] = {
        IDLE:       ("#181824", "#45475a", "#565870", "#7f849c"),
        CONNECTING: ("#1e1505", "#c8860a", "#f5a623", "#f5a623"),
        CONNECTED:  ("#071810", "#1a7840", "#2dbd6e", "#2dbd6e"),
    }
    _LABEL: dict[str, str] = {
        IDLE:       "Connect",
        CONNECTING: "Connecting…",
        CONNECTED:  "Live Feed",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state      = self.IDLE
        self._led_alpha  = 1.0
        self._pulse_phi  = 0.0
        self._hovered    = False

        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(40)
        self._pulse_timer.timeout.connect(self._tick)

        self.setFixedSize(100, 28)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("")   # opt out of global QSS entirely

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        self._state = state
        if state == self.CONNECTING:
            self._pulse_phi = 0.0
            self._pulse_timer.start()
            self.setEnabled(False)
        else:
            self._pulse_timer.stop()
            self._led_alpha = 1.0
            self.setEnabled(True)
        self.update()

    # ── Events ─────────────────────────────────────────────────────────────────

    def enterEvent(self, event: object) -> None:  # type: ignore[override]
        self._hovered = True
        self.update()

    def leaveEvent(self, event: object) -> None:  # type: ignore[override]
        self._hovered = False
        self.update()

    def _tick(self) -> None:
        self._pulse_phi = (self._pulse_phi + 0.16) % (2 * math.pi)
        self._led_alpha = 0.20 + 0.80 * (0.5 + 0.5 * math.sin(self._pulse_phi))
        self.update()

    # ── Paint ──────────────────────────────────────────────────────────────────

    def paintEvent(self, event: object) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        r = h / 2.0

        bg_h, bd_h, led_h, txt_h = self._COL[self._state]
        bg  = QColor(bg_h)
        bd  = QColor(bd_h)
        led = QColor(led_h)
        txt = QColor(txt_h)

        if self._hovered and self._state == self.IDLE:
            if load_theme_id() == "vscode":
                bd  = QColor("#9d9d9d")
                txt = QColor("#d4d4d4")
            else:
                bd  = QColor("#6e7aff")
                txt = QColor("#b0b8ff")

        # ── Pill shell ─────────────────────────────────────────────────────
        shell = QPainterPath()
        shell.addRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)
        p.fillPath(shell, bg)
        p.setPen(QPen(bd, 1.0))
        p.drawPath(shell)

        # ── LED ────────────────────────────────────────────────────────────
        led_r  = 4.0
        led_cx = r          # horizontally centred in the left "cap"
        led_cy = h / 2.0

        if self._state == self.CONNECTED:
            # soft outer glow ring
            glow = QColor(led_h)
            glow.setAlphaF(0.22)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QPointF(led_cx, led_cy), led_r + 3.0, led_r + 3.0)

        core = QColor(led)
        core.setAlphaF(self._led_alpha)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(core)
        p.drawEllipse(QPointF(led_cx, led_cy), led_r, led_r)

        # ── Label ──────────────────────────────────────────────────────────
        font = QFont("Segoe UI", 8)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(txt)
        tx = led_cx + led_r + 8.0
        p.drawText(
            QRectF(tx, 0.0, w - tx - 8.0, h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._LABEL[self._state],
        )

        p.end()


# ── Draggable top bar ──────────────────────────────────────────────────────────

class _TitleBar(QWidget):
    """
    Single compact top bar:
      brand | nav tabs | market pills | user/mode | P&L | win controls
    Supports window drag on the non-interactive regions.
    """

    def __init__(self, svc: AppService, window: QMainWindow,
                 panels: list[QWidget], stack: QStackedWidget,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._win         = window
        self._drag_pos    = QPoint()
        self._maximised   = False
        self._restore_geom = window.geometry()

        self.setObjectName("title_bar")
        self.setFixedHeight(40)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 0, 0)
        row.setSpacing(0)

        # ── Brand ───────────────────────────────────────────────────────
        brand = QLabel("Swing Trading Terminal")
        brand.setObjectName("top_brand")
        row.addWidget(brand)

        _vdiv(row)

        # ── Nav tabs ─────────────────────────────────────────────────────
        nav_items = [
            ("📊", "Dashboard"),
            ("🔍", "Screener"),
            ("⚡", "Execution"),
            ("📈", "Chart"),
            ("⚙",  "Settings"),
        ]
        self._tabs: list[_TabBtn] = []
        for (icon, label), panel in zip(nav_items, panels):
            btn = _TabBtn(icon, label)
            self._tabs.append(btn)
            row.addWidget(btn)
            btn.clicked.connect(lambda _c, p=panel: stack.setCurrentWidget(p))

        row.addStretch(1)          # push remaining right

        self._svc = svc

        # ── Connect / Disconnect feed toggle ──────────────────────────────
        row.addSpacing(8)
        self._feed_btn = _FeedToggle(self)
        self._feed_btn.clicked.connect(self._on_feed_btn_clicked)
        row.addWidget(self._feed_btn)
        svc.feed_status_changed.connect(self._on_feed_status_changed)
        row.addSpacing(8)

        _vdiv(row)

        # ── Window controls (dialog-style flat buttons) ───────────────────
        _wc = (
            "QPushButton {{ background: transparent; color: {fg}; border: none;"
            " font-size: 14px; min-width: 32px; max-width: 32px;"
            " min-height: 28px; max-height: 28px; border-radius: 4px; }}"
            "QPushButton:hover {{ background: {hover}; color: white; }}"
        )
        self._btn_min = QPushButton("−")
        self._btn_min.setStyleSheet(_wc.format(fg=C.SUBTEXT, hover=C.OVERLAY2))
        self._btn_min.setToolTip("Minimize")
        self._btn_min.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_min.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._btn_max = QPushButton("□")
        self._btn_max.setStyleSheet(_wc.format(fg=C.SUBTEXT, hover=C.OVERLAY2))
        self._btn_max.setToolTip("Maximize")
        self._btn_max.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_max.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._btn_cls = QPushButton("✕")
        self._btn_cls.setStyleSheet(_wc.format(fg=C.SUBTEXT, hover="#c0392b"))
        self._btn_cls.setToolTip("Close")
        self._btn_cls.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_cls.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._btn_min.clicked.connect(window.showMinimized)
        self._btn_max.clicked.connect(self._toggle_max)
        self._btn_cls.clicked.connect(window.close)

        win_frame = QWidget()
        win_frame.setFixedHeight(38)
        wf = QHBoxLayout(win_frame)
        wf.setContentsMargins(4, 0, 8, 0)
        wf.setSpacing(2)
        wf.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        for b in (self._btn_min, self._btn_max, self._btn_cls):
            wf.addWidget(b, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(win_frame, alignment=Qt.AlignmentFlag.AlignVCenter)
    def _on_feed_btn_clicked(self) -> None:
        status = self._svc.connection_status
        if status == ConnectionStatus.CONNECTED:
            from PyQt6.QtWidgets import QMessageBox
            ret = QMessageBox.question(
                self, "Disconnect Feed",
                "Disconnect data feed?\nPosition prices will stop updating.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.Yes:
                self._svc.disconnect_feed()
        elif status != ConnectionStatus.RECONNECTING:
            self._svc.connect_feed()

    def _on_feed_status_changed(self, status_str: str) -> None:
        if status_str == "connected":
            self._feed_btn.set_state(_FeedToggle.CONNECTED)
        elif status_str == "reconnecting":
            self._feed_btn.set_state(_FeedToggle.CONNECTING)
        else:
            self._feed_btn.set_state(_FeedToggle.IDLE)
    # ── Drag to move ──────────────────────────────────────────────────────────

    def mousePressEvent(self, ev):  # type: ignore[override]
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self._win.frameGeometry().topLeft()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):  # type: ignore[override]
        if ev.buttons() & Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self._win.move(ev.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(ev)

    def mouseDoubleClickEvent(self, ev):  # type: ignore[override]
        if ev.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()
        super().mouseDoubleClickEvent(ev)

    def _toggle_max(self) -> None:
        if self._maximised:
            self._win.setGeometry(self._restore_geom)
            self._btn_max.setText("□")
            self._btn_max.setToolTip("Maximize")
            self._maximised = False
        else:
            self._restore_geom = self._win.geometry()
            screen = self._win.screen() or QApplication.primaryScreen()
            self._win.setGeometry(screen.availableGeometry())
            self._btn_max.setText("❐")
            self._btn_max.setToolTip("Restore")
            self._maximised = True

    # ── Data refresh ──────────────────────────────────────────────────────────


# ── Admin Context Bar ─────────────────────────────────────────────────────────────

class _AdminContextBar(QWidget):
    """
    A slim info strip (28px) below the accent line showing the active admin scope:
      • All Users: aggregate count, total equity, combined P&L, total positions
      • Specific user: name, mode, IBKR ID, risk settings, equity
    """

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = svc
        self.setObjectName("admin_ctx_bar")
        self.setFixedHeight(28)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(0)

        # ── Market Watch (leftmost) ────────────────────────────────────────────
        mw_hdr = QLabel("MARKET WATCH")
        mw_hdr.setStyleSheet(
            f"color:{C.MUTED}; font-size:7pt; letter-spacing:1px;"
            f" font-weight:bold; padding-right:10px;"
        )
        row.addWidget(mw_hdr)

        self._mw_cells: list[dict] = []
        for _ in range(3):
            name_lbl = QLabel("–")
            name_lbl.setStyleSheet(
                f"color:{C.MUTED}; font-size:7pt; font-weight:bold; padding-right:4px;"
            )
            ltp_lbl = QLabel("–")
            ltp_lbl.setStyleSheet(
                f"color:{C.TEXT}; font-size:8pt; font-weight:bold; padding-right:3px;"
            )
            chg_lbl = QLabel("–")
            chg_lbl.setStyleSheet(
                f"color:{C.MUTED}; font-size:8pt; padding-right:18px;"
            )
            row.addWidget(name_lbl)
            row.addWidget(ltp_lbl)
            row.addWidget(chg_lbl)
            self._mw_cells.append({"name": name_lbl, "ltp": ltp_lbl, "chg": chg_lbl})

        _mw_sep = QLabel("│")
        _mw_sep.setStyleSheet(f"color:{C.OVERLAY2}; padding: 0 8px;")
        row.addWidget(_mw_sep)

        # ── Scope icon + items ───────────────────────────────────────────────
        self._scope_icon = QLabel()
        self._scope_icon.setStyleSheet(f"color:{C.YELLOW}; font-size:8pt; font-weight:bold; padding-right:6px;")
        row.addWidget(self._scope_icon)

        self._items: dict[str, QLabel] = {}
        self._dividers: list[QLabel] = []

        for key in ("scope", "risk", "mode", "ibkr"):
            if self._items:  # divider before each (except first)
                d = QLabel("·")
                d.setStyleSheet(f"color:{C.OVERLAY2}; padding: 0 10px;")
                row.addWidget(d)
                self._dividers.append(d)
            lbl = QLabel()
            lbl.setStyleSheet(f"color:{C.TEXT}; font-size:8pt;")
            row.addWidget(lbl)
            self._items[key] = lbl

        row.addStretch()

        svc.viewing_changed.connect(self.refresh)
        svc.positions_updated.connect(self.refresh)
        svc.account_updated.connect(self.refresh)
        svc.market_watch_updated.connect(self._refresh_mw)
        self._refresh_mw()
        self.refresh()

    def _refresh_mw(self) -> None:
        items = self._demo.get_market_watch()
        for i, cell in enumerate(self._mw_cells):
            if i < len(items):
                it = items[i]
                color = C.GREEN if it.change_pct >= 0 else C.RED
                sign  = "+" if it.change_pct >= 0 else ""
                cell["name"].setText(it.display_name)
                cell["ltp"].setText(f"${it.ltp:,.2f}" if it.ltp else "–")
                cell["chg"].setText(f"{sign}{it.change_pct:.2f}%" if it.ltp else "–")
                cell["chg"].setStyleSheet(
                    f"color:{color}; font-size:8pt; padding-right:16px;"
                )
            else:
                cell["name"].setText("–")
                cell["ltp"].setText("–")
                cell["chg"].setText("–")

    def refresh(self) -> None:
        uid   = self._demo.get_viewing_uid()
        users = self._demo.get_users()

        if uid is None:
            self._scope_icon.setText("🌐")
            self._items["scope"].setText(
                f"<b style='color:{C.YELLOW}'>ALL USERS</b>"
                f"  <span style='color:{C.MUTED};font-size:7pt'>{len(users)} accounts</span>"
            )
            for k in ("risk", "mode", "ibkr"):
                self._items[k].hide()
        else:
            u = self._demo.get_user_by_id(uid)
            if not u:
                return
            mode_clr = C.RED if u.mode == "live" else C.BLUE
            self._scope_icon.setText("👤")
            self._items["scope"].setText(f"<b style='color:{C.BLUE}'>{u.username}</b>")
            self._items["risk"].setText(
                f"<span style='color:{C.MUTED}'>Risk/Trade</span>  <b>{u.risk_config.risk_per_trade_pct:.1f}%</b>"
            )
            self._items["mode"].setText(f"<b style='color:{mode_clr}'>{u.mode.upper()}</b>")
            self._items["ibkr"].setText(
                f"<span style='color:{C.MUTED}'>IBKR</span>  <b>#{u.ibkr_client_id}</b>"
            )
            for k in ("risk", "mode", "ibkr"):
                self._items[k].show()

        for lbl in self._items.values():
            lbl.setTextFormat(Qt.TextFormat.RichText)


# ── Main Window ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """FO-GUI-001 Main Window — frameless, horizontal-nav terminal style."""

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = svc
        self._feed_retry_timer: QTimer | None = None
        self._feed_retry_count = 0
        self._feed_retry_max = 10
        self._db_info: object | None = None
        self._auto_fill_worker: object | None = None
        self._auto_fill_timer: QTimer | None = None
        self._auto_fill_retries = 0
        self._auto_fill_max_retries = 10
        self._auto_fill_username = ""
        self._auto_fill_password = ""

        # Remove OS window chrome
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowTitle("US Swing Terminal")

        # ── Panels ─────────────────────────────────────────────────────────────
        self._dashboard_panel  = DashboardPanel(svc)
        self._screener_panel   = ScreenerPanel(svc)
        self._execution_panel  = ExecutionPanel(svc)
        self._chart_panel      = CandleChartPanel(svc)
        self._settings_panel   = SettingsPanel(svc)
        panels = [
            self._dashboard_panel, self._screener_panel, self._execution_panel,
            self._chart_panel, self._settings_panel,
        ]

        self._settings_panel.theme_changed.connect(self._chart_panel.refresh_theme)
        self._settings_panel.theme_changed.connect(self._execution_panel.refresh_theme)

        # ── Stacked content ────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        for p in panels:
            self._stack.addWidget(p)

        # ── Title bar (with nav + win controls) ────────────────────────────────
        self._title_bar = _TitleBar(svc, self, panels, self._stack)

        # Activate first tab
        self._title_bar._tabs[0].setChecked(True)
        self._stack.setCurrentIndex(0)

        # ── Blue accent underline below title bar ──────────────────────────────
        accent = QFrame()
        accent.setFrameShape(QFrame.Shape.HLine)
        accent.setObjectName("accent_line")
        # ── Admin context bar ─────────────────────────────────────────────────────
        self._admin_ctx_bar = _AdminContextBar(svc)
        # ── Status bar widgets ─────────────────────────────────────────────────
        self._status = self.statusBar()
        self._status.setSizeGripEnabled(False)
        _sb_qss      = "background:transparent;color:#ffffff;font-weight:bold;padding:0 8px;"
        _sb_qss_sm   = "background:transparent;color:#ffffff;font-weight:bold;padding:0 8px;font-size:8pt;"
        _sb_pill_qss = "background:transparent;color:#ffffff;font-weight:bold;padding:0 10px;font-size:8pt;"
        self._sb_conn    = QLabel("●  Internet: Checking…")
        self._sb_conn.setStyleSheet(_sb_qss)
        self._sb_session = QLabel("SESSION: LIVE READ-ONLY")
        self._sb_session.setStyleSheet(_sb_qss_sm)
        self._sb_exe     = QLabel("EXE: DISABLED")
        self._sb_exe.setStyleSheet(_sb_qss_sm)
        for w in (self._sb_conn, _sep(), self._sb_session, _sep(), self._sb_exe):
            self._status.addWidget(w)
        # NYSE / NASDAQ market status — right side of status bar
        self._sb_nyse   = QLabel("⬤  NYSE")
        self._sb_nasdaq = QLabel("⬤  NASDAQ")
        for pill in (self._sb_nyse, self._sb_nasdaq):
            pill.setStyleSheet(_sb_pill_qss)
            self._status.addPermanentWidget(pill)

        # ── Root widget ────────────────────────────────────────────────────────
        root = QWidget()
        root.setObjectName("root_widget")
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._title_bar)
        rl.addWidget(accent)
        rl.addWidget(self._admin_ctx_bar)
        rl.addWidget(self._stack, 1)
        self.setCentralWidget(root)

        # ── Signals ─────────────────────────────────────────────────────────────
        svc.account_updated.connect(self._refresh_status)
        svc.positions_updated.connect(self._refresh_status)
        svc.viewing_changed.connect(self._refresh_status)
        svc.internet_status_changed.connect(self._on_internet_status_changed)
        svc.market_status_updated.connect(self._on_market_status)
        svc.candle_db_status_changed.connect(self._on_db_status_updated)
        self._refresh_status()
        self._on_market_status()

        # Auto-connect feed and auto-fill TWS credentials if scheduler is enabled
        if load_system_config().scheduler_enabled:
            self._start_feed_auto_connect()
            self._maybe_start_auto_fill_tws()

        # Wire screener watchlist signal
        self._screener_panel.watchlist_add_requested.connect(self._on_watchlist_add)

        # ── Geometry ────────────────────────────────────────────────────────────
        settings = QSettings("USSwing", "MainWindow")
        geom = settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            w, h = 1_180, 740
            self.setGeometry(
                (screen.width()  - w) // 2,
                (screen.height() - h) // 2,
                w, h,
            )

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _refresh_status(self) -> None:
        pass

    def _on_internet_status_changed(self, online: bool) -> None:
        """Update the status-bar internet pill when connectivity flips."""
        if online:
            self._sb_conn.setText("●  Internet: Online")
        else:
            self._sb_conn.setText("●  Internet: Offline")

    def _on_market_status(self) -> None:
        """Update NYSE / NASDAQ status bar pills from AppService market status."""
        _tip_map = {
            "open":        "Regular Trading Hours  09:30 – 16:00 ET",
            "pre_market":  "Pre-Market Session  04:00 – 09:30 ET",
            "after_hours": "After-Hours Session  16:00 – 20:00 ET",
            "closed":      "Market Closed",
        }
        status = self._demo.get_market_status()
        for pill, key in ((self._sb_nyse, "nyse"), (self._sb_nasdaq, "nasdaq")):
            s = status.get(key, "closed")
            pill.setToolTip(_tip_map.get(s, ""))

    def _on_db_status_updated(self, info: object) -> None:
        """Store latest database info for use during auto-connect."""
        self._db_info = info

    def on_circuit_breaker(self, active: bool) -> None:
        self._execution_panel.on_circuit_breaker(active)

    def _on_watchlist_add(self, symbol: str) -> None:
        """Screener 'Add to Watchlist' — forward to dashboard for now."""
        self._dashboard_panel.on_watchlist_add(symbol)

    def _start_feed_auto_connect(self) -> None:
        """Start scheduler auto-connect: react immediately via signal, retry every 60s if needed."""
        self._feed_retry_count = 0
        self._demo.log_message.emit("INFO", "Feed auto-connect started (scheduler mode).")
        self._demo.feed_status_changed.connect(self._on_scheduler_feed_status)
        self._demo.connect_feed()
        self._schedule_next_retry()

    def _on_scheduler_feed_status(self, status: str) -> None:
        """Fires immediately when feed status changes during auto-connect."""
        if status != "connected":
            return
        self._demo.feed_status_changed.disconnect(self._on_scheduler_feed_status)
        if self._feed_retry_timer is not None:
            self._feed_retry_timer.stop()
            self._feed_retry_timer = None
        self._demo.log_message.emit("INFO", "Feed auto-connect succeeded.")
        self._trigger_fill_delta_if_partial()

    def _schedule_next_retry(self) -> None:
        """Schedule a retry attempt in 60 seconds."""
        if self._feed_retry_timer is not None:
            self._feed_retry_timer.stop()
        self._feed_retry_timer = QTimer(self)
        self._feed_retry_timer.timeout.connect(self._on_feed_retry_tick)
        self._feed_retry_timer.setSingleShot(True)
        self._feed_retry_timer.start(60_000)

    def _on_feed_retry_tick(self) -> None:
        """Retry feed connection every 60 seconds (up to 10 attempts)."""
        self._feed_retry_count += 1
        if self._feed_retry_count < self._feed_retry_max:
            self._demo.log_message.emit(
                "INFO",
                f"Feed reconnect attempt {self._feed_retry_count + 1}/{self._feed_retry_max}."
            )
            self._demo.connect_feed()
            self._schedule_next_retry()
        else:
            self._demo.log_message.emit(
                "WARNING",
                f"Feed auto-connect failed after {self._feed_retry_max} attempts."
            )
            self._demo.feed_status_changed.disconnect(self._on_scheduler_feed_status)
            if self._feed_retry_timer is not None:
                self._feed_retry_timer.stop()
                self._feed_retry_timer = None

    def _trigger_fill_delta_if_partial(self) -> None:
        """Trigger fill delta if the database status is PARTIAL."""
        from us_swing.gui.app_service import CandleDbStatus, CandleDbInfo
        if isinstance(self._db_info, CandleDbInfo):
            if self._db_info.status == CandleDbStatus.PARTIAL:
                self._demo.log_message.emit("INFO", "Database status is PARTIAL. Starting fill delta.")
                self._settings_panel.trigger_fill_delta()

    # ── TWS auto-fill on startup ───────────────────────────────────────────────

    def _maybe_start_auto_fill_tws(self) -> None:
        """If Auto Fill Credential is enabled, load stored credentials and schedule the first fill attempt."""
        from us_swing.gui.scheduler_store import load_scheduler_config
        from us_swing.gui.scheduler_dialog import load_ibkr_password
        sched_cfg = load_scheduler_config()
        if not sched_cfg or not sched_cfg.auto_login or not sched_cfg.ibkr_username:
            return
        pwd = load_ibkr_password(sched_cfg.ibkr_username)
        if not pwd:
            self._demo.log_message.emit(
                "WARNING",
                "Auto Fill: no stored IBKR password — open Windows Task Scheduler dialog and save credentials.",
            )
            return
        self._auto_fill_username = sched_cfg.ibkr_username
        self._auto_fill_password = pwd
        self._auto_fill_retries = 0
        self._demo.log_message.emit("INFO", "Auto Fill: waiting 30 s for TWS login form…")
        # Create the timer once; _on_auto_fill_done reuses it via start() to avoid leaking instances.
        self._auto_fill_timer = QTimer(self)
        self._auto_fill_timer.setSingleShot(True)
        self._auto_fill_timer.timeout.connect(self._attempt_auto_fill_tws)
        self._auto_fill_timer.start(30_000)

    def _attempt_auto_fill_tws(self) -> None:
        """Spawn a FillWorker to type IBKR credentials into the TWS login window."""
        if self._demo.connection_status is ConnectionStatus.CONNECTED:
            self._demo.log_message.emit("INFO", "Auto Fill: Feed already connected — skipping credential fill.")
            self._auto_fill_username = ""
            self._auto_fill_password = ""
            return
        from us_swing.gui.scheduler_dialog import FillWorker
        worker = self._auto_fill_worker
        if worker is not None and hasattr(worker, "isRunning") and worker.isRunning():  # type: ignore[union-attr]
            return
        self._auto_fill_retries += 1
        self._demo.log_message.emit(
            "INFO",
            f"Auto Fill: attempt {self._auto_fill_retries}/{self._auto_fill_max_retries}…",
        )
        w = FillWorker(self._auto_fill_username, self._auto_fill_password, self)
        w.done.connect(self._on_auto_fill_done)
        w.start()
        self._auto_fill_worker = w

    def _on_auto_fill_done(self, error: str) -> None:
        """Handle fill result: log success or schedule retry on TWS-not-found."""
        if not error:
            self._auto_fill_username = ""
            self._auto_fill_password = ""  # wipe from memory after use
            self._auto_fill_worker = None
            self._demo.log_message.emit(
                "INFO", "Auto Fill: credentials typed — approve the 2FA prompt on your phone."
            )
            return
        if self._auto_fill_retries < self._auto_fill_max_retries:
            self._demo.log_message.emit("INFO", "Auto Fill: TWS login form not ready — retrying in 30 s.")
            if self._auto_fill_timer is not None:
                self._auto_fill_timer.start(30_000)
        else:
            self._demo.log_message.emit(
                "WARNING",
                f"Auto Fill: gave up after {self._auto_fill_max_retries} attempts — TWS login form never appeared.",
            )

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def closeEvent(self, event: object) -> None:  # type: ignore[override]
        if self._feed_retry_timer is not None:
            self._feed_retry_timer.stop()
        if self._auto_fill_timer is not None:
            self._auto_fill_timer.stop()
        worker = self._auto_fill_worker
        if worker is not None and hasattr(worker, "isRunning") and worker.isRunning():  # type: ignore[union-attr]
            worker.quit()   # type: ignore[union-attr]
            worker.wait(6000)  # type: ignore[union-attr]
        self._demo._stop_live_bar_worker()
        settings = QSettings("USSwing", "MainWindow")
        settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)  # type: ignore[arg-type]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sep() -> QLabel:
    lbl = QLabel("│")
    lbl.setStyleSheet(f"background:transparent;color:{C.OVERLAY2};padding:0 2px;")
    return lbl


def _vdiv(layout: QHBoxLayout) -> None:
    """Insert a subtle vertical divider into a horizontal layout."""
    d = QFrame()
    d.setFrameShape(QFrame.Shape.VLine)
    d.setFixedHeight(20)
    d.setStyleSheet(f"color:{C.OVERLAY2};margin:0 6px;")
    layout.addWidget(d)
