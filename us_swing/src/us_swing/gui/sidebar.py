"""
Module: MD-GUI-018.001.M01 — Sidebar
Parent SRD: SRD-GUI-018.001
Connections panel: MD-GUI-018.008.M04 (Parent SRD: SRD-GUI-018.008)

Left navigation for the five screens, with a mini (icon-only) mode, a
Connections panel (internet, IBKR feed, market) and an account footer that
replaces the old admin context strip (SRD-GUI-018.004).
"""
from __future__ import annotations

import datetime
import time
from typing import Any

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QEnterEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.data.market_calendar import ET, NYSE_HOLIDAYS, get_exchange_status
from us_swing.data.models import ConnectionStatus
from us_swing.gui.app_service import AppService
from us_swing.gui.icons import icon as make_icon
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C, active_palette

FULL_WIDTH = 200
MINI_WIDTH = 56

_SESSION_LABEL = {
    "open": "Open",
    "pre_market": "Pre-market",
    "after_hours": "After hours",
    "closed": "Closed",
}


def _span(start: datetime.datetime, end: datetime.datetime) -> str:
    delta = end.astimezone(datetime.timezone.utc) - start.astimezone(datetime.timezone.utc)
    minutes = max(0, int(delta.total_seconds() // 60))
    days, rest = divmod(minutes, 24 * 60)
    hours, minutes = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _next_open(now_et: datetime.datetime) -> datetime.datetime:
    day = now_et.date()
    while True:
        open_at = datetime.datetime.combine(day, datetime.time(9, 30), tzinfo=now_et.tzinfo)
        trading_day = day.weekday() < 5 and (day.month, day.day) not in NYSE_HOLIDAYS
        if trading_day and open_at > now_et:
            return open_at
        day += datetime.timedelta(days=1)


def market_text(now_et: datetime.datetime) -> tuple[str, str, str]:
    """Describe the market session for the Connections panel.

    Args:
        now_et: Current time in Eastern Time.

    Returns:
        ``(status, label, detail)``, e.g. ``("open", "Open", "closes in 2h 14m")``.
    """
    status = get_exchange_status(now_et)
    if status == "open":
        close_at = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        detail = f"closes in {_span(now_et, close_at)}"
    else:
        detail = f"opens in {_span(now_et, _next_open(now_et))}"
    return status, _SESSION_LABEL[status], detail


class _Dot(QLabel):
    """Small round status light."""

    def __init__(self, size: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def set_colour(self, colour: str) -> None:
        if self.property("colour") == colour:
            return
        self.setProperty("colour", colour)
        self.setStyleSheet(f"background: {colour}; border-radius: {self._size // 2}px;")


class _ConnectionsPanel(QWidget):
    """Internet, IBKR feed and market status with a connect / disconnect button."""

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._retry: tuple[int, int] | None = None
        self._retry_due = 0.0
        self._retry_timer = QTimer(self)
        self._retry_timer.setInterval(1000)
        self._retry_timer.timeout.connect(self.refresh)
        self.setObjectName("side_conn")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(0)

        self._full = QWidget()
        self._full.setObjectName("side_conn_rows")
        rows = QVBoxLayout(self._full)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(6)
        head = QHBoxLayout()
        title = QLabel("CONNECTIONS")
        title.setObjectName("side_conn_title")
        head.addWidget(title)
        head.addStretch(1)
        self._power = QPushButton()
        self._power.setObjectName("side_power")
        self._power.setFixedWidth(C.BTN_H)
        self._power.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._power.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._power.clicked.connect(self._on_power_clicked)
        head.addWidget(self._power)
        rows.addLayout(head)
        self._net_dot, self._net_val, _ = self._add_row(rows, "Internet", with_detail=False)
        self._feed_dot, self._feed_val, self._feed_sub = self._add_row(rows, "IBKR Feed")
        self._mkt_dot, self._mkt_val, self._mkt_sub = self._add_row(rows, "Market")
        self._layout.addWidget(self._full)

        self._plug = QPushButton()
        self._plug.setObjectName("side_btn")
        set_icon(self._plug, "plug", "neutral", 20)
        self._plug.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._plug.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._plug.clicked.connect(self._on_power_clicked)
        self._plug.installEventFilter(self)
        self._badge = _Dot(9, self._plug)
        self._plug.hide()
        self._layout.addWidget(self._plug)

        svc.feed_status_changed.connect(self.refresh)
        svc.internet_status_changed.connect(self.refresh)
        svc.market_status_updated.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _add_row(parent: QVBoxLayout, name: str,
                 with_detail: bool = True) -> tuple[_Dot, QLabel, QLabel]:
        row = QHBoxLayout()
        row.setSpacing(8)
        dot = _Dot(7)
        key = QLabel(name)
        key.setObjectName("side_footer")
        value = QLabel()
        row.addWidget(dot)
        row.addWidget(key)
        row.addStretch(1)
        row.addWidget(value)
        parent.addLayout(row)
        detail = QLabel()
        detail.setObjectName("side_footer")
        detail.setContentsMargins(15, 0, 0, 0)
        detail.setVisible(with_detail)
        parent.addWidget(detail)
        return dot, value, detail

    def set_mini(self, mini: bool) -> None:
        side = 0 if mini else 6
        self._layout.setContentsMargins(side, 6, side, 6)
        self._full.setVisible(not mini)
        self._plug.setVisible(mini)

    def set_retry(self, attempt: int, total: int, next_in_ms: int) -> None:
        """Show auto-connect progress until :meth:`clear_retry` is called."""
        self._retry = (attempt, total)
        self._retry_due = time.monotonic() + next_in_ms / 1000
        self._retry_timer.start()
        self.refresh()

    def clear_retry(self) -> None:
        self._retry = None
        self._retry_timer.stop()
        self.refresh()

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        if obj is self._plug and event is not None and event.type() == QEvent.Type.Resize:
            self._badge.move(self._plug.width() // 2 + 3, self._plug.height() // 2 + 2)
        return super().eventFilter(obj, event)

    def changeEvent(self, event: QEvent | None) -> None:
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.StyleChange:
            self.refresh()

    def refresh(self, *_args: object) -> None:
        _T: Any = active_palette()
        status = self._svc.connection_status
        online = self._svc.is_internet_online()
        cfg = self._svc.get_system_config()
        address = f"{cfg.ibkr_host}:{cfg.ibkr_port}"
        connected = status is ConnectionStatus.CONNECTED
        probing = status is ConnectionStatus.RECONNECTING

        if connected:
            feed, feed_clr, feed_sub = "Live", _T.GREEN, address
        elif self._retry is not None:
            attempt, total = self._retry
            left = max(0, round(self._retry_due - time.monotonic()))
            feed, feed_clr = f"Attempt {attempt} of {total}", _T.YELLOW
            feed_sub = "Trying now" if probing else f"Next try in {left} s"
        elif probing:
            feed, feed_clr, feed_sub = "Connecting…", _T.YELLOW, address
        else:
            feed, feed_clr, feed_sub = "Not connected", _T.MUTED, address

        mkt_status, mkt_label, mkt_detail = market_text(datetime.datetime.now(ET))
        mkt_clr = {"open": _T.GREEN, "closed": _T.MUTED}.get(mkt_status, _T.YELLOW)

        self._net_dot.set_colour(_T.GREEN if online else _T.RED)
        self._net_val.setText("Online" if online else "Offline")
        self._feed_dot.set_colour(feed_clr)
        self._feed_val.setText(f"<b style='color:{feed_clr}'>{feed}</b>")
        self._feed_sub.setText(feed_sub)
        self._mkt_dot.set_colour(mkt_clr)
        self._mkt_val.setText(mkt_label)
        self._mkt_sub.setText(mkt_detail)

        tip = "Disconnect" if connected else ("Try now" if self._retry else "Connect")
        set_icon(self._power, "power", "neutral" if connected else "go", 14)
        self._power.setToolTip(tip)
        self._power.setAccessibleName(tip)
        self._power.setEnabled(not probing)
        self._power.setProperty("armed", not connected)
        style = self._power.style()
        if style is not None:
            style.unpolish(self._power)
            style.polish(self._power)

        self._badge.set_colour(_T.RED if not online else feed_clr)
        self._plug.setEnabled(not probing)
        self._plug.setToolTip(
            f"Internet: {'Online' if online else 'Offline'}\n"
            f"IBKR Feed: {feed} ({feed_sub})\n"
            f"Market: {mkt_label}, {mkt_detail}"
        )
        self._plug.setAccessibleName(f"Connections, feed {feed}")

    def _on_power_clicked(self) -> None:
        status = self._svc.connection_status
        if status is ConnectionStatus.CONNECTED:
            ret = QMessageBox.question(
                self, "Disconnect Feed",
                "Disconnect data feed?\nPosition prices will stop updating.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.Yes:
                self._svc.disconnect_feed()
        elif status is not ConnectionStatus.RECONNECTING:
            self._svc.connect_feed()


class _AccountFooter(QWidget):
    """Viewing scope and account figures for the active user."""

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._mini = False
        self.setObjectName("side_account")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 4)
        layout.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(8)
        self._scope_icon = QLabel()
        self._scope_icon.setFixedSize(16, 16)
        self._scope = QLabel()
        self._scope.setTextFormat(Qt.TextFormat.RichText)
        head.addWidget(self._scope_icon)
        head.addWidget(self._scope, 1)
        layout.addLayout(head)

        self._details = QLabel()
        self._details.setObjectName("side_footer")
        self._details.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._details)

        svc.viewing_changed.connect(self.refresh)
        svc.positions_updated.connect(self.refresh)
        svc.account_updated.connect(self.refresh)
        self.refresh()

    def set_mini(self, mini: bool) -> None:
        self._mini = mini
        self._scope.setVisible(not mini)
        self._details.setVisible(not mini)

    def changeEvent(self, event: QEvent | None) -> None:
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.StyleChange:
            self.refresh()

    def refresh(self) -> None:
        _T: Any = active_palette()
        uid = self._svc.get_viewing_uid()
        users = self._svc.get_users()
        if uid is None:
            self._scope_icon.setPixmap(make_icon("globe", "go").pixmap(16, 16))
            self._scope.setText(
                f"<b style='color:{_T.YELLOW}'>All Users</b>"
                f"<br><span style='color:{_T.MUTED};font-size:8pt'>{len(users)} accounts</span>"
            )
            self._scope.setToolTip(f"All Users · {len(users)} accounts")
            self._details.setText("")
            return
        user = self._svc.get_user_by_id(uid)
        if not user:
            return
        self._scope_icon.setPixmap(make_icon("user", "go").pixmap(16, 16))
        self._scope.setText(f"<b style='color:{_T.BLUE}'>{user.username}</b>")
        self._scope.setToolTip(user.username)
        mode_clr = _T.RED if user.mode == "live" else _T.BLUE
        cap = self._svc.effective_capital()
        avail = self._svc.margin_available()
        avail_clr = _T.GREEN if avail > 0 else _T.RED
        rows = [
            ("Mode", f"<b style='color:{mode_clr}'>{user.mode.upper()}</b>"),
            ("IBKR", f"<b>#{user.ibkr_client_id}</b>"),
            ("Risk/Trade", f"<b>{user.risk_config.risk_per_trade_pct:.1f}%</b>"),
            ("Cap", f"<b>${cap:,.0f}</b>"),
            ("Avail", f"<b style='color:{avail_clr}'>${avail:,.0f}</b>"),
        ]
        self._details.setText(
            "<table width='100%' cellspacing='0' cellpadding='1'>"
            + "".join(
                f"<tr><td style='color:{_T.MUTED}'>{k}</td><td align='right'>{v}</td></tr>"
                for k, v in rows
            )
            + "</table>"
        )


class Sidebar(QFrame):
    """Screen navigation with a collapse button and an account footer."""

    page_requested = pyqtSignal(int)
    mini_toggled = pyqtSignal(bool)
    hover_changed = pyqtSignal(bool)

    def __init__(self, svc: AppService, items: list[tuple[str, str]],
                 parent: QWidget | None = None) -> None:
        """Build the sidebar.

        Args:
            svc: App service for the account footer.
            items: ``(icon_name, label)`` per screen, in stack order.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._mini = False
        self._labels: dict[QPushButton, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._collapse_btn = self._make_button("panel-left-close", "Collapse")
        self._collapse_btn.clicked.connect(lambda: self.mini_toggled.emit(not self._mini))
        layout.addWidget(self._collapse_btn)

        sep = QFrame()
        sep.setObjectName("side_sep")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._nav: list[QPushButton] = []
        for index, (icon_name, label) in enumerate(items):
            btn = self._make_button(icon_name, label)
            btn.setCheckable(True)
            self._group.addButton(btn, index)
            self._nav.append(btn)
            layout.addWidget(btn)
        self._group.idClicked.connect(self.page_requested)

        layout.addStretch(1)
        sep2 = QFrame()
        sep2.setObjectName("side_sep")
        sep2.setFixedHeight(1)
        layout.addWidget(sep2)
        self._conn = _ConnectionsPanel(svc)
        layout.addWidget(self._conn)
        sep3 = QFrame()
        sep3.setObjectName("side_sep")
        sep3.setFixedHeight(1)
        layout.addWidget(sep3)
        self._footer = _AccountFooter(svc)
        layout.addWidget(self._footer)

    def _make_button(self, icon_name: str, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("side_btn")
        set_icon(btn, icon_name, "neutral", 20)
        btn.setToolTip(label)
        btn.setAccessibleName(label)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._labels[btn] = label
        return btn

    @property
    def is_mini(self) -> bool:
        return self._mini

    def set_current(self, index: int) -> None:
        """Check the nav item for ``index`` without emitting ``page_requested``."""
        if 0 <= index < len(self._nav):
            self._nav[index].setChecked(True)

    def set_labels_visible(self, visible: bool) -> None:
        """Show or hide button labels and footer details (used for mini and peek)."""
        for btn, label in self._labels.items():
            btn.setText(label if visible else "")
        self._conn.set_mini(not visible)
        self._footer.set_mini(not visible)

    def set_feed_retry(self, attempt: int, total: int, next_in_ms: int) -> None:
        """Show auto-connect attempt ``attempt`` of ``total`` with a countdown."""
        self._conn.set_retry(attempt, total, next_in_ms)

    def clear_feed_retry(self) -> None:
        """Hide auto-connect progress."""
        self._conn.clear_retry()

    def set_mini(self, mini: bool) -> None:
        """Record mini mode and update labels and the collapse icon."""
        self._mini = mini
        self.set_labels_visible(not mini)
        set_icon(self._collapse_btn, "panel-left-open" if mini else "panel-left-close",
                 "neutral", 20)
        tip = "Expand" if mini else "Collapse"
        self._collapse_btn.setToolTip(tip)
        self._collapse_btn.setAccessibleName(tip)
        self._labels[self._collapse_btn] = tip

    def enterEvent(self, event: QEnterEvent | None) -> None:
        self.hover_changed.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent | None) -> None:
        self.hover_changed.emit(False)
        super().leaveEvent(event)
