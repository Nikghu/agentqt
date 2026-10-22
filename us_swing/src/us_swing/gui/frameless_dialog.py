"""
Module: MD-GUI-015.002.M01 — Frameless Dialog
Parent SRD: SRD-GUI-015.002
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.theme import C


class FramelessDialog(QDialog):
    """QDialog subclass: frameless OS chrome + custom title bar with min/max/close."""

    def __init__(
        self,
        title: str,
        min_width: int = 420,
        min_height: int = 0,
        extra_qss: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)
        if min_height:
            self.setMinimumHeight(min_height)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        if extra_qss:
            self.setStyleSheet(extra_qss)
        self._drag_pos: QPoint | None = None
        self._maximized = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._title_bar = self._make_title_bar(title)
        outer.addWidget(self._title_bar)

        self._content = QWidget()
        self._content.setStyleSheet("QWidget { background: transparent; }")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 12, 16, 12)
        self._content_layout.setSpacing(8)
        outer.addWidget(self._content, 1)

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def _make_title_bar(self, title: str) -> QFrame:
        bar = QFrame()
        bar.setObjectName("dlg_title_bar")
        bar.setFixedHeight(38)
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 0, 6, 0)
        hl.setSpacing(0)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("top_brand")
        hl.addWidget(title_lbl)
        hl.addStretch()

        _wc_style = (
            "QPushButton {{ background: transparent; color: {fg}; border: none;"
            " font-size: 14px; min-width: 32px; max-width: 32px;"
            " min-height: 28px; max-height: 28px; border-radius: 4px; }}"
            "QPushButton:hover {{ background: {hover}; color: white; }}"
        )
        min_btn = QPushButton("−")
        min_btn.setStyleSheet(_wc_style.format(fg=C.SUBTEXT, hover=C.OVERLAY2))
        min_btn.setToolTip("Minimize")
        min_btn.clicked.connect(self.showMinimized)

        self._max_btn = QPushButton("□")
        self._max_btn.setStyleSheet(_wc_style.format(fg=C.SUBTEXT, hover=C.OVERLAY2))
        self._max_btn.setToolTip("Maximize")
        self._max_btn.clicked.connect(self._toggle_maximize)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(_wc_style.format(fg=C.SUBTEXT, hover="#c0392b"))
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.reject)

        hl.addWidget(min_btn)
        hl.addSpacing(2)
        hl.addWidget(self._max_btn)
        hl.addSpacing(2)
        hl.addWidget(close_btn)
        return bar

    def _toggle_maximize(self) -> None:
        if self._maximized:
            self.showNormal()
            self._max_btn.setText("□")
            self._max_btn.setToolTip("Maximize")
        else:
            self.showMaximized()
            self._max_btn.setText("❐")
            self._max_btn.setToolTip("Restore")
        self._maximized = not self._maximized

    def mousePressEvent(self, event: Any) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._title_bar.geometry().contains(event.pos())
        ):
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)
