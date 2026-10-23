"""
Module: MD-GUI-018.001.M01 — Sidebar
Parent SRD: SRD-GUI-018.001

Left navigation for the five screens, with a mini (icon-only) mode and an
account footer that replaces the old admin context strip (SRD-GUI-018.004).
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QEnterEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.app_service import AppService
from us_swing.gui.icons import icon as make_icon
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import active_palette

FULL_WIDTH = 200
MINI_WIDTH = 56


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
        self._footer = _AccountFooter(svc)
        layout.addWidget(self._footer)

    def _make_button(self, icon_name: str, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("side_btn")
        set_icon(btn, icon_name, "neutral", 17)
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
        self._footer.set_mini(not visible)

    def set_mini(self, mini: bool) -> None:
        """Record mini mode and update labels and the collapse icon."""
        self._mini = mini
        self.set_labels_visible(not mini)
        set_icon(self._collapse_btn, "panel-left-open" if mini else "panel-left-close",
                 "neutral", 17)
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
