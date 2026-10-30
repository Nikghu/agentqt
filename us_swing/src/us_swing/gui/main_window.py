"""
Module: MD-GUI-000 — main_window.py
Shell: MD-GUI-018.005.M03 (Parent SRD: SRD-GUI-018.005)
Settings dialog wiring: MD-GUI-027.004.M03 (Parent SRD: SRD-GUI-027.004)
QMainWindow: Frameless terminal UI — title bar, left sidebar, stacked screens.

Layout:
  ┌──────────────────────────────────────────────────────────────────────┐
  │ logo  Swing Trading Terminal v  │  index prices           │ − □ ✕   │
  ├──────────┬───────────────────────────────────────────────────────────┤
  │ SIDEBAR  │  CONTENT  (QStackedWidget)        │ RIGHT PANEL │ STRIP │
  │ (200/56) ├───────────────────────────────────┴─────────────┤       │
  │          │  LIVE LOG (bottom panel, 0/180)                  │       │
  ├──────────┴─────────────────────────────────────────────────┴───────┤
  │  STATUS BAR                                                          │
  └──────────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QSettings,
    QTimer,
    Qt,
)
from PyQt6.QtGui import QCursor, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing import __version__
from us_swing.data.models import ConnectionStatus
from us_swing.gui.app_service import AppService
from us_swing.gui.backtest_workspace import BacktestWorkspace
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.chart_workspace import ChartWorkspace
from us_swing.gui.dashboard_panel import DashboardPanel
from us_swing.gui.execution_panel import ExecutionPanel
from us_swing.gui.screener_panel import ScreenerPanel
from us_swing.gui.settings_dialog import SettingsDialog
from us_swing.gui.settings_panel import SettingsPanel
from us_swing.gui.system_store import load_system_config
from us_swing.gui.icons import refresh_icons
from us_swing.gui.log_viewer_panel import LogViewerPanel
from us_swing.gui.reveal import RevealController
from us_swing.gui.side_panels import IconStrip, PositionDetails
from us_swing.gui.sidebar import FULL_WIDTH, MINI_WIDTH, Sidebar
from us_swing.gui.theme import C, active_palette

_log = logging.getLogger(__name__)


def _asset_path(name: str) -> Path:
    """Resolve a bundled asset, working both from source and a frozen exe.

    In a PyInstaller build the assets folder is unpacked under ``sys._MEIPASS``;
    from source it sits four levels up from this module (the package root).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / name
    return Path(__file__).parent.parent.parent.parent / "assets" / name


# ── Market Watch cell ─────────────────────────────────────────────────────────

class _MWCell(QLabel):
    """Single Market Watch entry — name highlights on hover like a nav tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._hovered = False
        self._name = ""
        self._ltp: float = 0.0
        self._change_pct: float = 0.0
        self._has_data = False

    def update_data(self, name: str, ltp: float, change_pct: float) -> None:
        self._name = name
        self._ltp = ltp
        self._change_pct = change_pct
        self._has_data = ltp > 0
        self._render()

    def enterEvent(self, event: object) -> None:
        self._hovered = True
        self._render()

    def leaveEvent(self, event: object) -> None:
        self._hovered = False
        self._render()

    def _render(self) -> None:
        _T = active_palette()
        name_color = _T.TEXT if self._hovered else _T.MUTED
        if self._has_data:
            color = _T.GREEN if self._change_pct >= 0 else _T.RED
            sign = "+" if self._change_pct >= 0 else ""
            self.setText(
                f"<span style='color:{name_color};font-size:8.5pt;font-weight:500'>{self._name}</span>"
                f"&nbsp;&nbsp;<span style='color:{_T.TEXT};font-size:9pt;font-family:IBM Plex Mono,Consolas,monospace;'>{self._ltp:,.2f}</span>"
                f"&nbsp;<span style='color:{color};font-size:8.5pt;font-family:IBM Plex Mono,Consolas,monospace;'>{sign}{self._change_pct:.2f}%</span>"
            )
        else:
            self.setText(
                f"<span style='color:{name_color};font-size:8.5pt;font-weight:500'>{self._name}</span>"
                f"&nbsp;&nbsp;<span style='color:{_T.OVERLAY2};font-size:9pt'>—</span>"
            )


# ── Draggable top bar ──────────────────────────────────────────────────────────

class _TitleBar(QWidget):
    """
    Single compact top bar:
      brand | nav tabs | market pills | user/mode | P&L | win controls
    Supports window drag on the non-interactive regions.
    """

    def __init__(self, svc: AppService, window: QMainWindow,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._win         = window
        self._svc         = svc
        self._drag_pos    = QPoint()
        self._maximised   = False
        self._restore_geom = window.geometry()

        self.setObjectName("title_bar")
        self.setFixedHeight(40)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 0, 0)
        row.setSpacing(0)

        # ── Logo ────────────────────────────────────────────────────────
        _logo_path = _asset_path("logo.png")
        logo = QLabel()
        logo.setFixedSize(24, 24)
        pix = QPixmap(str(_logo_path))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))
        row.addWidget(logo)
        row.addSpacing(6)

        # ── Brand ───────────────────────────────────────────────────────
        brand = QLabel("Swing Trading Terminal")
        brand.setObjectName("top_brand")
        row.addWidget(brand)

        version = QLabel(f"v{__version__}")
        version.setObjectName("top_version")
        version.setToolTip("Installed version")
        row.addWidget(version)

        _vdiv(row)

        # ── Market watch index prices ──────────────────────────────────────
        row.addStretch(1)
        self._mw_cells: list[_MWCell] = []
        self._mw_cell_divs: list[QLabel] = []
        self._mw_sym_names = dict(svc.get_mw_symbol_names())
        for sym in self._mw_sym_names:
            if self._mw_cells:
                div = QLabel("│")
                row.addWidget(div)
                self._mw_cell_divs.append(div)
            cell = _MWCell()
            cell.setObjectName(f"mw_{sym}")
            cell.update_data(self._mw_sym_names[sym], 0.0, 0.0)
            row.addWidget(cell)
            self._mw_cells.append(cell)
        self._apply_mw_styles()
        svc.market_watch_updated.connect(self._refresh_mw)
        self._refresh_mw()

        row.addStretch(1)          # push remaining right

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

    def _apply_mw_styles(self) -> None:
        _T = active_palette()
        for div in self._mw_cell_divs:
            div.setStyleSheet(f"color:{_T.OVERLAY2}; padding: 0 8px;")
        for cell in self._mw_cells:
            cell.setStyleSheet("font-size:8pt;")

    def _refresh_mw(self) -> None:
        items = self._svc.get_market_watch_items()
        for i, cell in enumerate(self._mw_cells):
            if i >= len(items):
                break
            it = items[i]
            cell.update_data(self._mw_sym_names.get(it.symbol, it.symbol), it.ltp, it.change_pct)

    def changeEvent(self, event: QEvent | None) -> None:
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.StyleChange:
            self._apply_mw_styles()
            self._refresh_mw()

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


# ── Confirmation Dialog ───────────────────────────────────────────────────────────

class _ConfirmDialog(QDialog):
    """Frameless yes/no confirmation styled to match the terminal title bar.

    Replaces the native QMessageBox so confirmations share the app's
    frameless look instead of the default OS dialog chrome.
    """

    _WC = (
        "QPushButton {{ background: transparent; color: {fg}; border: none;"
        " font-size: 14px; min-width: 32px; max-width: 32px;"
        " min-height: 28px; max-height: 28px; border-radius: 4px; }}"
        "QPushButton:hover {{ background: {hover}; color: white; }}"
    )

    def __init__(self, title: str, message: str, confirm_label: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_pos = QPoint()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setStyleSheet(
            f"QDialog {{ background: {C.BG}; border: 1px solid {C.OVERLAY}; }}"
            f"QLabel {{ background: transparent; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_title_bar(title))

        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(20, 20, 20, 16)
        col.setSpacing(20)

        msg = QLabel(message)
        msg.setWordWrap(True)
        col.addWidget(msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setFixedWidth(96)
        self._btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_cancel.setDefault(True)
        self._btn_cancel.clicked.connect(self.reject)

        self._btn_confirm = QPushButton(confirm_label)
        self._btn_confirm.setObjectName("close_btn")
        self._btn_confirm.setFixedWidth(140)
        self._btn_confirm.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_confirm.clicked.connect(self.accept)

        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_confirm)
        col.addLayout(btn_row)
        root.addWidget(body)

    def _build_title_bar(self, title: str) -> QWidget:
        bar = QWidget()
        bar.setObjectName("title_bar")
        bar.setStyleSheet("QWidget#title_bar { border-bottom: none; }")
        bar.setFixedHeight(40)
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 0, 4, 0)
        row.setSpacing(0)

        lbl = QLabel(title)
        lbl.setObjectName("top_brand")
        row.addWidget(lbl)
        row.addStretch(1)

        btn_cls = QPushButton("✕")
        btn_cls.setStyleSheet(self._WC.format(fg=C.SUBTEXT, hover="#c0392b"))
        btn_cls.setToolTip("Close")
        btn_cls.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_cls.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_cls.clicked.connect(self.reject)
        row.addWidget(btn_cls)
        return bar

    def mousePressEvent(self, ev):  # type: ignore[override]
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):  # type: ignore[override]
        if ev.buttons() & Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(ev)


# ── Admin Context Bar ─────────────────────────────────────────────────────────────

_NAV_ITEMS: list[tuple[str, str]] = [
    ("layout-dashboard", "Dashboard"),
    ("filter", "Screener"),
    ("zap", "Execution"),
    ("chart-candlestick", "Charts"),
    ("history", "Backtest"),
]
_WIDE_PAGES = frozenset({2, 3, 4})   # Execution, Chart, Backtest
_NO_PANEL_PAGES = frozenset({3})   # Chart
_RIGHT_PANELS = ("details", "watch")


class _MiniState:
    """Sidebar mini mode: the user's saved choice plus a per-screen auto shrink."""

    def __init__(self, user_mini: bool) -> None:
        self.user_mini = user_mini
        self.auto_mini = False
        self.panel_open = False

    def set_page(self, index: int) -> None:
        self.auto_mini = index in _WIDE_PAGES

    def set_user_mini(self, mini: bool) -> None:
        self.user_mini = mini
        if not mini:
            self.auto_mini = False

    def want_mini(self) -> bool:
        return self.user_mini or self.auto_mini or self.panel_open


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

        # ── Live Log first, so messages logged while the screens build are kept ─
        self._log_view = LogViewerPanel(svc)

        # ── Panels ─────────────────────────────────────────────────────────────
        self._dashboard_panel  = DashboardPanel(svc)
        self._screener_panel   = ScreenerPanel(svc)
        self._execution_panel  = ExecutionPanel(svc)
        self._chart_panel      = ChartWorkspace(svc)
        self._backtest_panel   = BacktestWorkspace(svc)
        self._settings_panel   = SettingsPanel(svc)
        panels = [
            self._dashboard_panel, self._screener_panel, self._execution_panel,
            self._chart_panel, self._backtest_panel,
        ]

        self._settings_panel.theme_changed.connect(self._chart_panel.refresh_theme)
        self._settings_panel.theme_changed.connect(self._execution_panel.refresh_theme)
        # settings_panel → theme_changed → MainWindow → _on_theme_changed
        self._settings_panel.theme_changed.connect(self._on_theme_changed)

        # The log panel is listening now, so a failed live-broker start can surface.
        svc.flush_broker_fallback_message()

        # ── Stacked content ────────────────────────────────────────────────────
        # Each screen is a card; the Screener lays out its own cards (SRD-GUI-023.002).
        self._stack = QStackedWidget()
        gutter(self._stack)
        for p in panels:
            if p in (self._screener_panel, self._execution_panel, self._dashboard_panel,
                     self._chart_panel, self._backtest_panel):
                # These screens lay out their own cards on the gutter.
                self._stack.addWidget(p)
            else:
                self._stack.addWidget(card(p))
        self._stack.setCurrentIndex(0)

        # ── Title bar (brand, index prices, feed, win controls) ────────────────
        self._title_bar = _TitleBar(svc, self)

        # ── Sidebar: floats over a width-reserving slot so hover peek never
        #    pushes the screen; the slot width is animated by RevealController.
        # Sections are cards with a GAP of gutter between them (SRD-GUI-023.001).
        body = gutter(QWidget())
        body_row = QHBoxLayout(body)
        body_row.setContentsMargins(GAP, GAP, GAP, GAP)
        body_row.setSpacing(GAP)
        self._side_slot = gutter(QWidget())
        body_row.addWidget(self._side_slot)

        # Right panel (Position Details | Watchlist) and bottom Live Log panel;
        # both are sized only by RevealController.
        self._details = PositionDetails(svc)
        self._right_stack = QStackedWidget()
        self._right_stack.addWidget(self._details)
        watchlist = self._dashboard_panel.watchlist_widget
        watchlist.set_compact()  # type: ignore[attr-defined]
        self._right_stack.addWidget(watchlist)
        # The gap sits inside each sliding panel, so a closed panel leaves none behind.
        self._right_panel = QFrame()
        self._right_panel.setObjectName("right_panel")
        rp = QVBoxLayout(self._right_panel)
        rp.setContentsMargins(GAP, 0, 0, 0)
        rp.addWidget(card(self._right_stack))
        self._right_name = "details"
        self._log_panel = QFrame()
        self._log_panel.setObjectName("log_panel")
        lp = QVBoxLayout(self._log_panel)
        lp.setContentsMargins(0, GAP, 0, 0)
        lp.addWidget(card(self._log_view))

        centre = gutter(QWidget())
        centre_col = QVBoxLayout(centre)
        centre_col.setContentsMargins(0, 0, 0, 0)
        centre_col.setSpacing(0)
        top_row = QHBoxLayout()
        top_row.setSpacing(0)
        top_row.addWidget(self._stack, 1)
        top_row.addWidget(self._right_panel)
        centre_col.addLayout(top_row, 1)
        centre_col.addWidget(self._log_panel)
        body_row.addWidget(centre, 1)
        self._strip = IconStrip()
        body_row.addWidget(self._strip)
        self._sidebar = Sidebar(svc, _NAV_ITEMS, body)
        self._sidebar.set_current(0)
        self._body = body
        self._peeking = False
        self._mini_state = _MiniState(bool(QSettings("USSwing", "MainWindow").value(
            "sidebar_mini", False, type=bool)))
        self._reveal = RevealController(self)
        want_mini = self._mini_state.want_mini()
        self._reveal.register("sidebar", self._side_slot, MINI_WIDTH, FULL_WIDTH,
                              start_open=not want_mini)
        self._reveal.register("right", self._right_panel, 0, 300 + GAP, start_open=False)
        self._reveal.register("log", self._log_panel, 0, 180 + GAP, horizontal=False,
                              start_open=False)
        self._sidebar.set_mini(want_mini)
        self._slide: QPropertyAnimation | None = None
        body.installEventFilter(self)
        self._side_slot.installEventFilter(self)

        # One reused dialog keeps the settings panel (and a running download) alive.
        self._settings_dialog = SettingsDialog(self._settings_panel, self)
        # feed / candle download → section dots, only while the dialog is open
        # (open_at refreshes them; each refresh reads the Telegram token store).
        svc.feed_status_changed.connect(self._refresh_settings_dots)
        self._settings_panel.data_panel.state_changed.connect(self._refresh_settings_dots)
        # sidebar → page_requested → MainWindow → stack + mini state
        self._sidebar.page_requested.connect(self._on_page_requested)
        # sidebar → settings_requested → Settings dialog (current screen unchanged)
        self._sidebar.settings_requested.connect(lambda: self._settings_dialog.open_at())
        # sidebar → mini_toggled → MainWindow → saved user choice
        self._sidebar.mini_toggled.connect(self._on_mini_toggled)
        # sidebar → hover_changed → MainWindow → peek overlay
        self._sidebar.hover_changed.connect(self._on_sidebar_hover)
        # strip → panel_toggled → MainWindow → RevealController
        self._strip.panel_toggled.connect(self._on_panel_toggled)
        # reveal → revealed → MainWindow → strip buttons + sidebar room
        self._reveal.revealed.connect(self._on_panel_revealed)
        # svc → log_message → strip → warning badge while the log is closed
        svc.log_message.connect(self._strip.count_warning)
        # data panel → state_changed → sidebar → Settings badge (percent, tick or !)
        self._settings_panel.data_panel.state_changed.connect(self._sidebar.set_data_state)
        self._sidebar.set_data_state(*self._settings_panel.data_panel.state)
        # dashboard → position_selected → details panel
        self._dashboard_panel.position_selected.connect(self._on_position_selected)
        # details → exit_requested / chart_requested → dashboard drawer / chart
        self._details.exit_requested.connect(self._on_details_exit)
        self._details.chart_requested.connect(self._on_details_chart)
        # screener → chart_requested → Charts screen
        self._screener_panel.chart_requested.connect(self._on_chart_requested)
        # backtest → chart_requested → Charts screen (SRD-GUI-031.023)
        self._backtest_panel.chart_requested.connect(self._on_chart_requested)
        # screener → quick_test_requested → Backtest screen on saved lists (SRD-GUI-031.061)
        self._screener_panel.quick_test_requested.connect(self._on_quick_test)
        # charts → execution_requested → Execution screen (SRD-GUI-026.010)
        self._chart_panel.execution_requested.connect(lambda _symbol: self._go_to(2))
        # ── Status bar widgets ─────────────────────────────────────────────────
        self._status = self.statusBar()
        self._status.setSizeGripEnabled(False)
        _sb_qss      = "background:transparent;color:#ffffff;font-weight:bold;padding:0 8px;"
        _sb_qss_sm   = "background:transparent;color:#ffffff;font-weight:bold;padding:0 8px;font-size:8pt;"
        _sb_pill_qss = "background:transparent;color:#ffffff;font-weight:bold;padding:0 10px;font-size:8pt;"
        self._sb_conn    = QLabel("●  Internet: Checking…")
        self._sb_conn.setStyleSheet(_sb_qss_sm)
        self._status.addWidget(self._sb_conn)
        # Backtest download status — shown only while a run is active (SRD-GUI-030.007)
        self._sb_backtest = QLabel("")
        self._sb_backtest.setStyleSheet(_sb_pill_qss)
        self._sb_backtest.setToolTip("Settings → Backtest data")
        self._sb_backtest.hide()
        self._status.addPermanentWidget(self._sb_backtest)
        self._sb_backtest_hide = QTimer(self)
        self._sb_backtest_hide.setSingleShot(True)
        self._sb_backtest_hide.setInterval(15_000)
        self._sb_backtest_hide.timeout.connect(self._sb_backtest.hide)
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
        rl.addWidget(body, 1)
        self.setCentralWidget(root)

        # ── Signals ─────────────────────────────────────────────────────────────
        svc.account_updated.connect(self._refresh_status)
        svc.positions_updated.connect(self._refresh_status)
        svc.viewing_changed.connect(self._refresh_status)
        svc.internet_status_changed.connect(self._on_internet_status_changed)
        svc.market_status_updated.connect(self._on_market_status)
        svc.candle_db_status_changed.connect(self._on_db_status_updated)
        svc.risk_warning_raised.connect(self._on_risk_warning)
        svc.backtest_progress.connect(self._on_backtest_progress)
        svc.backtest_finished.connect(self._on_backtest_finished)
        self._risk_warning_last: dict[str, float] = {}
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

    def _on_theme_changed(self) -> None:
        refresh_icons(self)

    def _on_page_requested(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._slide_in(self._stack.currentWidget())
        self._mini_state.set_page(index)
        if index in _NO_PANEL_PAGES:
            for name in ("right", "log"):
                if self._reveal.is_open(name):
                    self._reveal.reveal_requested.emit(name, False)
        self._apply_sidebar_mode()

    def _refresh_settings_dots(self, *_: object) -> None:
        if self._settings_dialog.isVisible():
            self._settings_panel.refresh_states()

    def _go_to(self, index: int) -> None:
        self._sidebar.set_current(index)
        self._on_page_requested(index)

    def _on_panel_toggled(self, name: str, show: bool) -> None:
        if name == "log":
            self._reveal.reveal_requested.emit("log", show)
            return
        if show:
            self._right_name = name
            self._right_stack.setCurrentIndex(_RIGHT_PANELS.index(name))
            for other in _RIGHT_PANELS:
                self._strip.set_checked(other, other == name)
            self._mini_state.panel_open = True
            self._apply_sidebar_mode()
            self._reveal.reveal_requested.emit("right", True)
        elif name == self._right_name:
            self._reveal.reveal_requested.emit("right", False)

    def _on_panel_revealed(self, name: str, shown: bool) -> None:
        if name == "log":
            self._strip.set_checked("log", shown)
        elif name == "right":
            for other in _RIGHT_PANELS:
                self._strip.set_checked(other, shown and other == self._right_name)
            self._mini_state.panel_open = shown
            self._apply_sidebar_mode()

    def _on_position_selected(self, pos: object, user_name: str) -> None:
        self._details.show_position(pos, user_name)  # type: ignore[arg-type]
        details_open = self._reveal.is_open("right") and self._right_name == "details"
        if pos is not None and not details_open:
            self._on_panel_toggled("details", True)

    def _on_details_exit(self, tab: int) -> None:
        self._go_to(0)
        self._dashboard_panel.open_exit(tab)

    def _on_details_chart(self, symbol: str) -> None:
        self._on_chart_requested(symbol, "1d")

    def _on_quick_test(self, preset_id: str) -> None:
        self._go_to(4)
        self._backtest_panel.quick_test(preset_id)

    def _on_chart_requested(self, symbol: str, timeframe: str) -> None:
        self._go_to(3)
        self._chart_panel.open_symbol(symbol, timeframe)

    def _on_mini_toggled(self, mini: bool) -> None:
        self._mini_state.set_user_mini(mini)
        QSettings("USSwing", "MainWindow").setValue("sidebar_mini", mini)
        self._apply_sidebar_mode()

    def _apply_sidebar_mode(self) -> None:
        mini = self._mini_state.want_mini()
        if mini == self._sidebar.is_mini:
            return
        self._peeking = False
        self._sidebar.set_mini(mini)
        self._reveal.reveal_requested.emit("sidebar", not mini)

    def _on_sidebar_hover(self, entered: bool) -> None:
        peek = entered and self._sidebar.is_mini
        if peek == self._peeking:
            return
        self._peeking = peek
        self._sidebar.set_labels_visible(peek)
        self._sync_sidebar_geometry()

    def _slide_in(self, page: QWidget | None) -> None:
        if page is None:
            return
        if self._slide is not None:
            self._slide.stop()
        self._slide = QPropertyAnimation(page, b"pos", self)
        self._slide.setDuration(180)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._slide.setStartValue(QPoint(24, 0))
        self._slide.setEndValue(QPoint(0, 0))
        self._slide.finished.connect(self._clear_slide)
        self._slide.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _clear_slide(self) -> None:
        self._slide = None

    def _sync_sidebar_geometry(self) -> None:
        width = FULL_WIDTH if self._peeking else self._side_slot.width()
        slot = self._side_slot.geometry()
        self._sidebar.setGeometry(slot.x(), slot.y(), width, slot.height())
        self._sidebar.raise_()

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        if event is not None and obj in (self._body, self._side_slot) and event.type() in (
            QEvent.Type.Resize, QEvent.Type.Show,
        ):
            self._sync_sidebar_geometry()
        return super().eventFilter(obj, event)


    def _refresh_status(self) -> None:
        pass

    def _on_risk_warning(self, kind: str, message: str) -> None:
        """Show a non-blocking advisory pop-up for a risk-limit breach (FO-EXE-017).

        Debounced per kind (30 s) so a stream of breaches cannot storm the user.
        Advisory only — never blocks, resizes, or closes an order.
        """
        import time
        from PyQt6.QtWidgets import QMessageBox

        now = time.monotonic()
        if now - self._risk_warning_last.get(kind, 0.0) < 30.0:
            return
        self._risk_warning_last[kind] = now

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Risk Warning")
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.show()

    def _on_internet_status_changed(self, online: bool) -> None:
        """Update the status-bar internet pill when connectivity flips."""
        if online:
            self._sb_conn.setText("●  Internet: Online")
        else:
            self._sb_conn.setText("●  Internet: Offline")

    def _on_backtest_progress(self, tf: str, done: int, total: int, _symbol: str) -> None:
        """Show backtest download progress in the status bar (SRD-GUI-030.007)."""
        self._sb_backtest_hide.stop()
        self._sb_backtest.setText(f"Backtest data · {tf} {done:,} of {total:,}")
        self._sb_backtest.show()

    def _on_backtest_finished(self, _ok: bool, message: str) -> None:
        """Show the backtest result briefly, then hide the status bar item."""
        self._sb_backtest.setText(f"Backtest data · {message}")
        self._sb_backtest.show()
        self._sb_backtest_hide.start()

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
        self._sidebar.set_feed_retry(1, self._feed_retry_max, 60_000)

    def _on_scheduler_feed_status(self, status: str) -> None:
        """Fires immediately when feed status changes during auto-connect."""
        if status != "connected":
            return
        self._demo.feed_status_changed.disconnect(self._on_scheduler_feed_status)
        if self._feed_retry_timer is not None:
            self._feed_retry_timer.stop()
            self._feed_retry_timer = None
        self._sidebar.clear_feed_retry()
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
            self._sidebar.set_feed_retry(
                self._feed_retry_count + 1, self._feed_retry_max, 60_000
            )
        else:
            self._demo.log_message.emit(
                "WARNING",
                f"Feed auto-connect failed after {self._feed_retry_max} attempts."
            )
            self._demo.feed_status_changed.disconnect(self._on_scheduler_feed_status)
            if self._feed_retry_timer is not None:
                self._feed_retry_timer.stop()
                self._feed_retry_timer = None
            self._sidebar.clear_feed_retry()

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
                "Auto Fill: no stored IBKR password — add it in Settings → Scheduler → TWS login and press Apply.",
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
        dlg = _ConfirmDialog(
            "Close Terminal",
            "Are you sure you want to close the Swing Trading Terminal?",
            "Close Terminal",
            self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            event.ignore()  # type: ignore[attr-defined]
            return
        if self._feed_retry_timer is not None:
            self._feed_retry_timer.stop()
        if self._auto_fill_timer is not None:
            self._auto_fill_timer.stop()
        worker = self._auto_fill_worker
        if worker is not None and hasattr(worker, "isRunning") and worker.isRunning():  # type: ignore[union-attr]
            worker.quit()   # type: ignore[union-attr]
            worker.wait(6000)  # type: ignore[union-attr]
        self._demo._stop_live_bar_worker()
        self._demo.shutdown_notifications()
        self._demo.shutdown_order_connection()
        self._demo.shutdown_backtest_download()
        settings = QSettings("USSwing", "MainWindow")
        settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)  # type: ignore[arg-type]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _vdiv(layout: QHBoxLayout) -> None:
    """Insert a subtle vertical divider into a horizontal layout."""
    d = QFrame()
    d.setFrameShape(QFrame.Shape.VLine)
    d.setFixedHeight(20)
    d.setStyleSheet(f"color:{C.OVERLAY2};margin:0 6px;")
    layout.addWidget(d)
