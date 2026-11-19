"""
Module: MD-GUI-044.001.M01 — screener_tree.py
Parent SRD: SRD-GUI-044.001

Rows of the Screener preset tree: style folders and presets (FO-GUI-044).
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from us_swing.gui.icons import icon

_ICON_PX = 13

FOLDERS: tuple[tuple[str, str, str], ...] = (
    ("swing", "Swing", "info"),
    ("day", "Day", "go"),
    ("position", "Position", "add"),
    ("ready", "Ready-made", "neutral"),
)
"""Folder key, title and icon role, top to bottom (SRD-GUI-044.001)."""


def folder_key(preset: Any, *, admin: bool) -> str:
    """Folder a preset belongs in: Ready-made for admin presets, else its style."""
    if admin:
        return "ready"
    style = str(getattr(preset, "style", "") or "swing").lower()
    return style if style in ("swing", "day", "position") else "swing"


def _icon_label(name: str, role: str = "neutral") -> QLabel:
    label = QLabel()
    label.setPixmap(icon(name, role).pixmap(_ICON_PX, _ICON_PX))
    label.setFixedWidth(_ICON_PX)
    return label


class TreeRow(QFrame):
    """A clickable tree row with a chevron; right-click asks for the row's menu."""

    clicked = pyqtSignal()
    menu_requested = pyqtSignal(QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tree_row")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(6, 0, 6, 0)
        self.row.setSpacing(7)
        self._chevron = QLabel()
        self._chevron.setFixedWidth(_ICON_PX)
        self.row.addWidget(self._chevron)
        self.set_open(False)

    def set_open(self, is_open: bool) -> None:
        name = "chevron-down" if is_open else "chevron-right"
        self._chevron.setPixmap(icon(name).pixmap(11, 11))
        self.setProperty("open", is_open)
        self.style().unpolish(self)  # type: ignore[union-attr]
        self.style().polish(self)  # type: ignore[union-attr]

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: Any) -> None:
        self.menu_requested.emit(event.globalPos())


class FolderRow(TreeRow):
    """Folder row: chevron, folder icon, title and preset count (SRD-GUI-044.001)."""

    def __init__(self, key: str, title: str, role: str, count: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.setObjectName("tree_folder")
        self.row.addWidget(_icon_label("folder", role))
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("tree_folder_name")
        self.row.addWidget(self.title_lbl, 1)
        self.count_lbl = QLabel(str(count))
        self.count_lbl.setObjectName("view_key")
        self.row.addWidget(self.count_lbl)


class PresetRow(TreeRow):
    """Closed preset row: chevron, name and last run line (SRD-GUI-044.002)."""

    def __init__(self, pid: str, name: str, meta: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pid = pid
        self.setToolTip(name)
        self.name_lbl = QLabel(name)
        self.name_lbl.setObjectName("tree_preset_name")
        self.name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.row.addWidget(self.name_lbl, 1)
        self.meta_lbl = QLabel()
        self.meta_lbl.setObjectName("view_key")
        self.row.addWidget(self.meta_lbl)
        self.set_meta(meta)

    def set_meta(self, meta: str) -> None:
        self.meta_lbl.setText(meta)


def branch() -> tuple[QFrame, QVBoxLayout]:
    """Indented box with a guide line on its left, for a row's children."""
    frame = QFrame()
    frame.setObjectName("tree_branch")
    box = QVBoxLayout(frame)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(1)
    return frame, box


__all__ = ["FOLDERS", "FolderRow", "PresetRow", "TreeRow", "branch", "folder_key"]
