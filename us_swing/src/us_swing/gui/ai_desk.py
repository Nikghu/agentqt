"""
Module: MD-GUI-034.009.M08 — AI Desk workspace
Parent SRD: SRD-GUI-034.009
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.desk_control import DeskBar, DeskPoller
from us_swing.gui.floor_sample import SAMPLE_TAG
from us_swing.gui.theme import C

SECTIONS = (
    "Command", "Org chart", "Employees", "Hiring", "Task board", "Activity",
    "Schedule", "Studio", "Reports", "Cost & budget", "Desk settings",
)


class AiDeskWorkspace(QWidget):
    """AI Desk page: section list on the left, section frame on the right."""

    def __init__(self, poller: DeskPoller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        gutter(self)
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(GAP)
        self._list = QListWidget()
        self._list.setFixedWidth(190)
        self._list.addItems(SECTIONS)
        main.addWidget(card(self._list))
        right = QVBoxLayout()
        right.setSpacing(GAP)
        right.addWidget(card(self._build_top(poller)))
        self._stack = QStackedWidget()
        for name in SECTIONS:
            self._stack.addWidget(card(self._placeholder(name)))
        right.addWidget(self._stack, 1)
        main.addLayout(right, 1)
        # list → currentRowChanged → stack → setCurrentIndex
        self._list.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._list.setCurrentRow(0)

    def section_names(self) -> list[str]:
        """Return the section names in list order."""
        return [self._list.item(i).text() for i in range(self._list.count())]  # type: ignore[union-attr]

    def current_section(self) -> str:
        """Return the name of the section on show."""
        item = self._list.currentItem()
        return item.text() if item is not None else ""

    def select_section(self, name: str) -> None:
        """Show the section called ``name``."""
        self._list.setCurrentRow(SECTIONS.index(name))

    @staticmethod
    def _build_top(poller: DeskPoller) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(14, 10, 14, 10)
        title = QLabel("AI Desk")
        title.setObjectName("page_title")
        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(DeskBar(poller))
        return box

    @staticmethod
    def _placeholder(name: str) -> QWidget:
        box = QWidget()
        body = QVBoxLayout(box)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(6)
        head = QHBoxLayout()
        title = QLabel(name)
        title.setObjectName("page_title")
        tag = QLabel(SAMPLE_TAG)
        tag.setStyleSheet(f"color: {C.MUTED};")
        head.addWidget(title)
        head.addWidget(tag)
        head.addStretch(1)
        body.addLayout(head)
        note = QLabel("Frame comes in the next step")
        note.setStyleSheet(f"color: {C.MUTED};")
        body.addWidget(note)
        body.addStretch(1)
        return box
