"""
Module: MD-GUI-034.009.M08 — AI Desk workspace
Parent SRD: SRD-GUI-034.009
"""
from __future__ import annotations

from collections.abc import Callable

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
from us_swing.gui.ai_desk_sections import (
    command_frame,
    employees_frame,
    hiring_frame,
    org_frame,
)
from us_swing.gui.ai_desk_sections2 import (
    activity_frame,
    schedule_frame,
    studio_frame,
    tasks_frame,
)
from us_swing.gui.ai_desk_sections3 import cost_frame, reports_frame, settings_frame
from us_swing.gui.theme import C

SECTIONS = (
    "Command", "Org chart", "Employees", "Hiring", "Task board", "Activity",
    "Schedule", "Studio", "Reports", "Cost & budget", "Desk settings",
)

_BUILDERS: dict[str, Callable[[str], QWidget]] = {
    "Command": command_frame, "Org chart": org_frame, "Employees": employees_frame,
    "Hiring": hiring_frame, "Task board": tasks_frame, "Activity": activity_frame,
    "Schedule": schedule_frame, "Studio": studio_frame, "Reports": reports_frame,
    "Cost & budget": cost_frame, "Desk settings": settings_frame,
}


def _nav_style() -> str:
    return (
        f"QListWidget {{ background: transparent; border: none; outline: none; }}"
        f"QListWidget::item {{ padding: 9px 12px; border-radius: 4px; margin: 1px 4px; }}"
        f"QListWidget::item:hover:!selected {{ background: {C.OVERLAY}; }}"
        f"QListWidget::item:selected {{ background: {C.BLUE}; color: {C.BG}; }}"
        f"QListWidget::item:focus {{ outline: none; border: none; }}"
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
        self._list.setStyleSheet(_nav_style())
        self._list.addItems(SECTIONS)
        main.addWidget(card(self._list))
        right = QVBoxLayout()
        right.setSpacing(GAP)
        right.addWidget(card(self._build_top(poller)))
        self._stack = QStackedWidget()
        for name in SECTIONS:
            self._stack.addWidget(card(_BUILDERS[name](name)))
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
