"""
Module: MD-GUI-034.009.M08 — AI Desk workspace
Parent SRD: SRD-GUI-034.009
Also: SRD-GUI-034.022 — the Pages section (was Studio), rebuilt each time it is shown
Also: SRD-GUI-034.027–.032 — real Hiring, Command approvals and Reports (live sections)
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

from us_swing.core.desk_trades import DeskTradeSink
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.desk_control import DeskBar, DeskPoller
from us_swing.gui.ai_desk_sections import (
    command_frame,
    employees_frame,
    org_frame,
)
from us_swing.gui.ai_desk_hiring import approvals_box, hiring_frame
from us_swing.gui.ai_desk_chat import ChatPanel
from us_swing.gui.ai_desk_results import results_frame
from us_swing.gui.ai_desk_sections2 import (
    activity_frame,
    schedule_frame,
    tasks_frame,
)
from us_swing.gui.ai_desk_pages import pages_frame
from us_swing.gui.ai_desk_sections3 import cost_frame, reports_frame, settings_frame
from us_swing.gui.theme import C

SECTIONS = (
    "Command", "Org chart", "Employees", "Hiring", "Task board", "Activity",
    "Schedule", "Pages", "Reports", "Results", "Cost & budget", "Desk settings",
)

_LIVE_SECTIONS = ("Command", "Hiring", "Pages", "Reports", "Results", "Cost & budget")
_BUILDERS: dict[str, Callable[[str], QWidget]] = {
    "Org chart": org_frame, "Employees": employees_frame,
    "Task board": tasks_frame, "Activity": activity_frame, "Schedule": schedule_frame,
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

    def __init__(self, poller: DeskPoller, sink: DeskTradeSink | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sink = sink
        self._poller = poller
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
        self._home = poller.home
        for name in SECTIONS:
            # live sections are built when first shown, so no web view starts with the desk
            self._stack.addWidget(QWidget() if name in _LIVE_SECTIONS else card(self._build(name)))
        right.addWidget(self._stack, 1)
        main.addLayout(right, 1)
        # list → currentRowChanged → page → _show_section
        self._list.currentRowChanged.connect(self._show_section)
        self._list.setCurrentRow(0)

    def _show_section(self, row: int) -> None:
        """Show section ``row``; live sections are rebuilt so they are current."""
        if 0 <= row < len(SECTIONS) and SECTIONS[row] in _LIVE_SECTIONS:
            old = self._stack.widget(row)
            self._stack.insertWidget(row, card(self._build(SECTIONS[row])))
            if old is not None:
                self._stack.removeWidget(old)
                old.deleteLater()
        self._stack.setCurrentIndex(row)

    def _build(self, name: str) -> QWidget:
        if name == "Command":
            return command_frame(name, approvals_box(
                self._home, lambda: self.select_section("Hiring"), self._sink),
                ChatPanel(self._home, lambda: self._poller.status.state))
        if name == "Hiring":
            return hiring_frame(name, self._home)
        if name == "Reports":
            return reports_frame(name, self._home)
        if name == "Results":
            return results_frame(name, self._home)
        if name == "Pages":
            return pages_frame(name, self._home)
        if name == "Cost & budget":
            return cost_frame(name, self._home)
        if name == "Desk settings":
            return settings_frame(name, self._home)
        return _BUILDERS[name](name)

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
