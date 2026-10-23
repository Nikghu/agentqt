"""
Module: MD-GUI-019.001.M01 — Side Panels
Parent SRD: SRD-GUI-019.001

Right-edge icon strip that opens the side panels, and the Position Details
panel shown in the right panel (SRD-GUI-019.003).
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui._types import OpenPosition
from us_swing.gui.app_service import AppService
from us_swing.gui.icons import icon, mark_danger, set_icon
from us_swing.gui.theme import active_palette

_STRIP_ITEMS = (("details", "clipboard-list", "Position Details"),
                ("watch", "eye", "Watchlist"),
                ("log", "scroll-text", "Live Log"),
                ("system", "settings-2", "System"),
                ("data", "database", "Data"))
_ALERT_LEVELS = frozenset({"WARNING", "ERROR", "CRITICAL"})


class IconStrip(QFrame):
    """Thin right-edge strip whose buttons toggle the side panels."""

    panel_toggled = pyqtSignal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("icon_strip")
        self.setFixedWidth(46)  # 36 px buttons + 4 px margins + 1 px border each side
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)
        self._buttons: dict[str, QPushButton] = {}
        for name, icon_name, tip in _STRIP_ITEMS:
            btn = QPushButton()
            btn.setObjectName("strip_btn")
            btn.setCheckable(True)
            btn.setFixedWidth(36)
            set_icon(btn, icon_name, "neutral", 20)
            btn.setToolTip(tip)
            btn.setAccessibleName(tip)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.toggled.connect(lambda on, n=name: self.panel_toggled.emit(n, on))
            layout.addWidget(btn)
            self._buttons[name] = btn
        layout.addStretch(1)

        self._unseen = 0
        self._badge = QLabel(self._buttons["log"])
        self._badge.setObjectName("strip_badge")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFixedSize(16, 14)
        self._badge.move(19, 1)
        self._badge.hide()

        self._data_badge = QLabel(self._buttons["data"])
        self._data_badge.setObjectName("data_badge")
        self._data_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._data_badge.setFixedSize(18, 14)
        self._data_badge.move(18, 1)
        self._data_badge.hide()

    def set_data_state(self, state: str, percent: int) -> None:
        """Badge the Data button: percent while downloading, tick or ! when done."""
        text = {"downloading": str(percent), "complete": "", "partial": "!"}.get(state)
        if text is None:
            self._data_badge.hide()
            return
        self._data_badge.setText(text)
        if state == "complete":
            self._data_badge.setPixmap(icon("check", "inverse").pixmap(10, 10))
        self._data_badge.setProperty("state", state)
        style = self._data_badge.style()
        if style is not None:
            style.unpolish(self._data_badge)
            style.polish(self._data_badge)
        self._data_badge.show()

    def set_checked(self, name: str, checked: bool) -> None:
        """Sync a button with its panel without emitting ``panel_toggled``."""
        btn = self._buttons.get(name)
        if btn is None:
            return
        btn.blockSignals(True)
        btn.setChecked(checked)
        btn.blockSignals(False)
        if name == "log" and checked:
            self._unseen = 0
            self._badge.hide()

    def count_warning(self, level: str, _message: str = "") -> None:
        """Count warnings and errors that arrive while the Live Log is closed."""
        if level not in _ALERT_LEVELS or self._buttons["log"].isChecked():
            return
        self._unseen += 1
        self._badge.setText(str(self._unseen) if self._unseen < 100 else "99+")
        self._badge.show()

    @property
    def unseen(self) -> int:
        return self._unseen


class PositionDetails(QWidget):
    """Read-only view of the selected position with exit shortcuts."""

    exit_requested = pyqtSignal(int)      # Exit drawer tab: 0 = Market, 3 = Stop / Trail
    chart_requested = pyqtSignal(str)

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._pos: OpenPosition | None = None
        self._user_name = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self._hint = QLabel("Click a position on the Dashboard to see its details")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self._symbol = QLabel()
        self._symbol.setObjectName("details_symbol")
        self._price = QLabel()
        layout.addWidget(self._symbol)
        layout.addWidget(self._price)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self._values: dict[str, QLabel] = {}
        for row, key in enumerate(("User", "Quantity", "Avg entry", "Unrealised P&L",
                                   "Stop", "Target", "State")):
            name = QLabel(key)
            name.setObjectName("details_key")
            value = QLabel()
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(name, row, 0)
            grid.addWidget(value, row, 1)
            self._values[key] = value
        layout.addLayout(grid)

        self._exit_btn = QPushButton("Exit")
        set_icon(self._exit_btn, "log-out", "danger")
        mark_danger(self._exit_btn)
        self._stop_btn = QPushButton("Stop / Trail")
        set_icon(self._stop_btn, "shield", "go")
        self._chart_btn = QPushButton("Open in Chart")
        set_icon(self._chart_btn, "chart-candlestick", "info")
        self._exit_btn.clicked.connect(lambda: self.exit_requested.emit(0))
        self._stop_btn.clicked.connect(lambda: self.exit_requested.emit(3))
        self._chart_btn.clicked.connect(self._on_chart)
        for btn in (self._exit_btn, self._stop_btn, self._chart_btn):
            layout.addWidget(btn)
        layout.addStretch(1)

        svc.positions_updated.connect(self._on_positions_updated)
        self.show_position(None)

    def show_position(self, pos: OpenPosition | None, user_name: str = "") -> None:
        """Show ``pos``, or the empty hint when it is None."""
        self._pos = pos
        self._user_name = user_name
        has = pos is not None
        self._hint.setVisible(not has)
        for widget in (self._symbol, self._price, *self._values.values()):
            widget.setVisible(has)
        for btn in (self._exit_btn, self._stop_btn, self._chart_btn):
            btn.setEnabled(has)
        if pos is not None:
            self._render(pos)

    def changeEvent(self, event: QEvent | None) -> None:
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.StyleChange and self._pos:
            self._render(self._pos)

    def _on_positions_updated(self) -> None:
        if self._pos is None:
            return
        key = (self._pos.symbol, self._pos.user_id)
        fresh = next((p for p in self._svc.get_positions()
                      if (p.symbol, p.user_id) == key), None)
        self.show_position(fresh, self._user_name if fresh else "")

    def _on_chart(self) -> None:
        if self._pos is not None:
            self.chart_requested.emit(self._pos.symbol)

    def _render(self, pos: OpenPosition) -> None:
        _T: Any = active_palette()
        pnl = (pos.current_price - pos.average_price) * pos.quantity
        pct = (pos.current_price / pos.average_price - 1) * 100 if pos.average_price else 0.0
        clr = _T.GREEN if pnl >= 0 else _T.RED
        self._symbol.setText(f"<span style='font-size:16pt;font-weight:bold'>{pos.symbol}</span>")
        self._price.setText(
            f"<span style='font-family:\"IBM Plex Mono\",Consolas'>${pos.current_price:,.2f}</span>"
            f"  <span style='color:{clr}'>{pct:+.2f}%</span>"
        )
        self._values["User"].setText(self._user_name or "—")
        self._values["Quantity"].setText(str(pos.quantity))
        self._values["Avg entry"].setText(f"${pos.average_price:,.2f}")
        self._values["Unrealised P&L"].setText(f"<span style='color:{clr}'>{pnl:+,.2f}</span>")
        self._values["Stop"].setText(f"${pos.stop_loss:,.2f}" if pos.stop_loss else "—")
        self._values["Target"].setText(f"${pos.target_price:,.2f}" if pos.target_price else "—")
        self._values["State"].setText("Open" if pos.quantity > 0 else "Closed")
