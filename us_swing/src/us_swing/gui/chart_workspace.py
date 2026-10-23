"""
Module: MD-GUI-020.001.M01 — Charts Workspace
Parent SRD: SRD-GUI-020.001

The Charts screen: up to six ``CandleChartPanel`` windows in a ``QMdiArea``,
arranged as tiles, a cascade or tabs (SRD-GUI-020.002).
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QIcon, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMdiArea,
    QMdiSubWindow,
    QPushButton,
    QStyle,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.app_service import AppService
from us_swing.gui.chart_panel import CandleChartPanel
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import active_palette

MAX_CHARTS = 6
_MODES = (("tile", "Tile"), ("cascade", "Cascade"), ("tabs", "Tabs"))


class ChartWorkspace(QWidget):
    """Several chart windows side by side on the Charts screen."""

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._mode = "tile"
        # Fusion draws MDI title bars from the palette, so they follow the theme
        # instead of the light native Windows frame.
        self._frame_style: QStyle | None = QStyleFactory.create("Fusion")
        blank = QPixmap(1, 1)
        blank.fill(Qt.GlobalColor.transparent)
        self._blank_icon = QIcon(blank)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(6)
        title = QLabel("Charts")
        title.setObjectName("page_title")
        self._count_lbl = QLabel()
        self._count_lbl.setObjectName("page_meta")
        self._new_btn = QPushButton("New Chart")
        set_icon(self._new_btn, "plus", "add")
        self._new_btn.clicked.connect(self._add_window)
        head.addWidget(title)
        head.addWidget(self._count_lbl)
        head.addStretch(1)
        head.addWidget(self._new_btn)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_buttons: dict[str, QPushButton] = {}
        for key, label in _MODES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("mode_btn")
            self._mode_group.addButton(btn)
            self._mode_buttons[key] = btn
            btn.clicked.connect(lambda _c, k=key: self.set_mode(k))
            head.addWidget(btn)
        root.addLayout(head)

        self._mdi = QMdiArea()
        self._mdi.setObjectName("chart_mdi")
        self._mdi.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._mdi.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._mdi.setTabsClosable(True)
        self._mdi.setTabsMovable(True)
        root.addWidget(self._mdi, 1)

        self._mode_buttons["tile"].setChecked(True)
        self._add_window()

    # ── Public API ────────────────────────────────────────────────────────────

    def open_symbol(self, symbol: str, timeframe: str = "1d") -> None:
        """Show ``symbol``: focus its window, else open one, else reuse the active one."""
        symbol = symbol.strip().upper()
        subs = self._mdi.subWindowList()
        for sub in subs:
            panel = sub.widget()
            if isinstance(panel, CandleChartPanel) and panel.current_symbol == symbol:
                self._mdi.setActiveSubWindow(sub)
                if panel.current_timeframe != timeframe:
                    panel.show_symbol(symbol, timeframe)
                return
        empty = None
        for candidate in subs:
            panel = candidate.widget()
            if isinstance(panel, CandleChartPanel) and not panel.current_symbol:
                empty = candidate
                break
        if empty is not None:
            sub = empty
            self._mdi.setActiveSubWindow(sub)
        elif len(subs) < MAX_CHARTS:
            sub = self._add_window()
        else:
            sub = self._mdi.activeSubWindow() or self._mdi.subWindowList()[0]
            self._mdi.setActiveSubWindow(sub)
        panel = sub.widget()
        if isinstance(panel, CandleChartPanel):
            panel.show_symbol(symbol, timeframe)

    def set_mode(self, mode: str) -> None:
        """Arrange windows as ``tile``, ``cascade`` or ``tabs``."""
        self._mode = mode
        self._mode_buttons[mode].setChecked(True)
        if mode == "tabs":
            self._mdi.setViewMode(QMdiArea.ViewMode.TabbedView)
            return
        self._mdi.setViewMode(QMdiArea.ViewMode.SubWindowView)
        for sub in self._mdi.subWindowList():
            sub.showNormal()
        if mode == "tile":
            self._mdi.tileSubWindows()
        else:
            self._mdi.cascadeSubWindows()

    def refresh_theme(self, _theme_id: str = "") -> None:
        """Re-render every open chart in the new theme colours."""
        for sub in self._mdi.subWindowList():
            self._style_frame(sub)
            panel = sub.widget()
            if isinstance(panel, CandleChartPanel):
                panel.refresh_theme(_theme_id)

    def _style_frame(self, sub: QMdiSubWindow) -> None:
        _T: Any = active_palette()
        pal = sub.palette()
        for role, colour in ((QPalette.ColorRole.Window, _T.SURFACE),
                             (QPalette.ColorRole.WindowText, _T.SUBTEXT),
                             (QPalette.ColorRole.Highlight, _T.OVERLAY),
                             (QPalette.ColorRole.HighlightedText, _T.TEXT),
                             (QPalette.ColorRole.Button, _T.SURFACE),
                             (QPalette.ColorRole.ButtonText, _T.SUBTEXT)):
            pal.setColor(role, QColor(colour))
        sub.setPalette(pal)
        panel = sub.widget()
        if panel is not None:
            panel.setPalette(QPalette())

    @property
    def window_count(self) -> int:
        return len(self._mdi.subWindowList())

    # ── Internals ─────────────────────────────────────────────────────────────

    def _add_window(self) -> QMdiSubWindow:
        panel = CandleChartPanel(self._svc)
        panel.set_compact()
        sub = self._mdi.addSubWindow(panel)
        assert sub is not None
        if self._frame_style is not None:
            sub.setStyle(self._frame_style)
        sub.setWindowIcon(self._blank_icon)
        self._style_frame(sub)
        sub.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        sub.setWindowTitle("Chart")
        sub.setMinimumSize(360, 260)
        sub.resize(640, 420)
        panel.chart_loaded.connect(self._on_chart_loaded)
        sub.destroyed.connect(self._on_window_destroyed)
        sub.show()
        self._mdi.setActiveSubWindow(sub)
        self._update_count()
        self.set_mode(self._mode)
        return sub

    def _on_chart_loaded(self, symbol: str, timeframe: str) -> None:
        panel = self.sender()
        sub = panel.parent() if panel is not None else None
        if isinstance(sub, QMdiSubWindow):
            sub.setWindowTitle(f"{symbol} · {timeframe.upper()}")

    def _on_window_destroyed(self) -> None:
        # The closed window leaves the list only after destroyed, so look on the next tick.
        QTimer.singleShot(0, self._after_close)

    def _after_close(self) -> None:
        try:
            self._update_count()
            if self._mode in ("tile", "cascade"):
                self.set_mode(self._mode)
        except RuntimeError:
            pass  # workspace already deleted (app closing)

    def _update_count(self) -> None:
        n = len(self._mdi.subWindowList())
        self._count_lbl.setText(f"{n} of {MAX_CHARTS} charts")
        self._new_btn.setEnabled(n < MAX_CHARTS)
