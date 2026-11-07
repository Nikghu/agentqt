"""
Module: MD-GUI-034.009.M08 — AI Desk workspace
Parent SRD: SRD-GUI-034.009
Also: SRD-GUI-034.022 — the Pages section (was Studio), rebuilt each time it is shown
Also: SRD-GUI-034.027–.032 — real Hiring, Command approvals and Reports (live sections)
Also: MD-GUI-034.059.M33 — grouped section list, Command badge, header chips and spend bar
(SRD-GUI-034.059–.060)
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QShowEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_contract import DeskStatus, desk_home
from us_swing.core.desk_feed import ask_cards
from us_swing.core.desk_overview import last_run, spend, team_counts, todays_runs
from us_swing.core.desk_trades import DeskTradeSink
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.desk_control import DeskBar, DeskPoller
from us_swing.gui.ai_desk_sections import (
    command_frame,
    employees_frame,
    org_frame,
    runs_box,
    team_line,
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

NY = ZoneInfo("America/New_York")
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("TALK", ("Command",)),
    ("TEAM", ("Org chart", "Employees", "Hiring")),
    ("WORK", ("Task board", "Activity", "Schedule")),
    ("CREATE", ("Pages",)),
    ("REVIEW", ("Reports", "Results", "Cost & budget")),
    ("SETUP", ("Desk settings",)),
)
SECTIONS = tuple(name for _group, names in GROUPS for name in names)
_ROLE = Qt.ItemDataRole.UserRole
_RESULT_TONE = {"ok": "GREEN", "failed": "RED", "error": "RED", "running": "YELLOW"}

_LIVE_SECTIONS = ("Command", "Hiring", "Pages", "Reports", "Results", "Cost & budget")
_BUILDERS: dict[str, Callable[[str], QWidget]] = {
    "Org chart": org_frame, "Employees": employees_frame,
    "Task board": tasks_frame, "Activity": activity_frame, "Schedule": schedule_frame,
    "Cost & budget": cost_frame, "Desk settings": settings_frame,
}


def _nav_style() -> str:
    return (
        f"QListWidget {{ background: transparent; border: none; outline: none; }}"
        f"QListWidget::item {{ padding: 6px 12px; border-radius: 4px; margin: 1px 4px; }}"
        f"QListWidget::item:hover:!selected {{ background: {C.OVERLAY}; }}"
        f"QListWidget::item:selected {{ background: {C.OVERLAY}; color: {C.BLUE}; }}"
        f"QListWidget::item:focus {{ outline: none; border: none; }}"
    )


def _chip_style(tone: str) -> str:
    colour = getattr(C, tone)
    return f"color: {colour}; border: 1px solid {colour}; border-radius: 9px; padding: 1px 8px;"


def _chip(text: str, tone: str) -> QLabel:
    chip = QLabel(text)
    chip.setStyleSheet(_chip_style(tone))
    return chip


class AiDeskWorkspace(QWidget):
    """AI Desk page: grouped section list on the left, section frame on the right."""

    chart_requested = pyqtSignal(str)

    def __init__(self, poller: DeskPoller, sink: DeskTradeSink | None = None,
                 parent: QWidget | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        super().__init__(parent)
        self._sink = sink
        self._poller = poller
        self._clock = clock or (lambda: datetime.now(NY))
        self._home = poller.home
        gutter(self)
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(GAP)
        self._list = QListWidget()
        self._list.setFixedWidth(190)
        self._list.setStyleSheet(_nav_style())
        self._fill_list()
        main.addWidget(card(self._list))
        right = QVBoxLayout()
        right.setSpacing(GAP)
        right.addWidget(card(self._build_top(poller)))
        self._stack = QStackedWidget()
        for name in SECTIONS:
            # live sections are built when first shown, so no web view starts with the desk
            self._stack.addWidget(QWidget() if name in _LIVE_SECTIONS else card(self._build(name)))
        right.addWidget(self._stack, 1)
        main.addLayout(right, 1)
        # list → currentItemChanged → page → _on_item
        self._list.currentItemChanged.connect(self._on_item)
        self._state = poller.status.state
        # poller → status_changed → page → _on_status
        poller.status_changed.connect(self._on_status)
        self.select_section("Command")
        self.refresh_header()

    def _folder(self) -> Path:
        return self._home or desk_home()

    def _fill_list(self) -> None:
        small = self._list.font()
        small.setPointSizeF(max(small.pointSizeF() - 1.5, 6.0))
        small.setBold(True)
        for group, names in GROUPS:
            head = QListWidgetItem(group)
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            head.setFont(small)
            head.setForeground(QColor(C.MUTED))
            self._list.addItem(head)
            for name in names:
                item = QListWidgetItem(name)
                item.setData(_ROLE, name)
                self._list.addItem(item)

    def _item(self, name: str) -> QListWidgetItem | None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is not None and item.data(_ROLE) == name:
                return item
        return None

    def _on_item(self, item: QListWidgetItem | None, _old: QListWidgetItem | None) -> None:
        name = item.data(_ROLE) if item is not None else None
        if name in SECTIONS:
            self._show_section(str(name))

    def _show_section(self, name: str) -> None:
        """Show section ``name``; live sections are rebuilt so they are current."""
        index = SECTIONS.index(name)
        if name in _LIVE_SECTIONS:
            old = self._stack.widget(index)
            self._stack.insertWidget(index, card(self._build(name)))
            if old is not None:
                self._stack.removeWidget(old)
                old.deleteLater()
        self._stack.setCurrentIndex(index)

    def _build(self, name: str) -> QWidget:
        if name == "Command":
            return self._command(name)
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

    def _command(self, name: str) -> QWidget:
        folder = self._folder()
        box = approvals_box(self._home, lambda: self.select_section("Hiring"), self._sink,
                            self._clock)
        # approvals → chart_requested → page → main window; count_changed → Command badge
        box.chart_requested.connect(self.chart_requested)
        box.count_changed.connect(self.set_ask_count)
        self.set_ask_count(box.count)
        return command_frame(name, box, ChatPanel(self._home, lambda: self._poller.status.state),
                             runs_box(todays_runs(folder, self._clock())),
                             team_line(team_counts(folder)))

    def set_ask_count(self, count: int) -> None:
        """Show ``count`` waiting asks next to Command (plain Command at 0)."""
        item = self._item("Command")
        if item is not None:
            item.setText(f"Command   {count}" if count else "Command")

    def section_names(self) -> list[str]:
        """Return the section names in list order."""
        return [str(item.data(_ROLE)) for row in range(self._list.count())
                if (item := self._list.item(row)) is not None and item.data(_ROLE)]

    def current_section(self) -> str:
        """Return the name of the section on show."""
        item = self._list.currentItem()
        return str(item.data(_ROLE)) if item is not None and item.data(_ROLE) else ""

    def select_section(self, name: str) -> None:
        """Show the section called ``name``."""
        item = self._item(name)
        if item is not None:
            self._list.setCurrentItem(item)

    def _build_top(self, poller: DeskPoller) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(14, 10, 14, 10)
        title = QLabel("AI Desk")
        title.setObjectName("page_title")
        row.addWidget(title)
        row.addSpacing(GAP * 3)
        self.last_run_chip = _chip("", "SUBTEXT")
        self.last_run_chip.setObjectName("last_run_chip")
        row.addWidget(self.last_run_chip)
        spend_box = QVBoxLayout()
        spend_box.setSpacing(2)
        self.spend_label = QLabel()
        self.spend_label.setObjectName("spend_label")
        self.spend_label.setStyleSheet(f"color: {C.SUBTEXT};")
        self.spend_bar = QProgressBar()
        self.spend_bar.setRange(0, 100)
        self.spend_bar.setTextVisible(False)
        self.spend_bar.setFixedWidth(180)
        self.spend_bar.setMaximumHeight(4)
        self.spend_bar.setStyleSheet(
            f"QProgressBar {{ background: {C.OVERLAY}; border: none; border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background: {C.YELLOW}; border-radius: 2px; }}"
        )
        spend_box.addWidget(self.spend_label)
        spend_box.addWidget(self.spend_bar)
        row.addSpacing(GAP * 2)
        row.addLayout(spend_box)
        row.addStretch(1)
        row.addWidget(DeskBar(poller))
        return box

    def refresh_header(self) -> None:
        """Read the last run and the AI spend again and show them."""
        folder = self._folder()
        run = last_run(folder)
        self.last_run_chip.setVisible(run is not None)
        if run is not None:
            self.last_run_chip.setText(
                f"Last run: {run.name} · {run.result} {run.when:%H:%M} ET")
            self.last_run_chip.setStyleSheet(
                _chip_style(_RESULT_TONE.get(run.result, "SUBTEXT")))
        used = spend(folder, self._clock())
        for widget in (self.spend_label, self.spend_bar):
            widget.setVisible(used is not None)
        if used is not None:
            share = round(used.month_share * 100)
            self.spend_label.setText(
                f"AI spend ${used.today_usd:.2f} today · {share}% of month")
            self.spend_bar.setValue(share)

    def _on_status(self, status: DeskStatus) -> None:
        """Refresh the header and badge only when the desk state changed and the page shows."""
        if status.state is self._state:
            return
        self._state = status.state
        if self.isVisible():
            self._refresh_page()

    def _refresh_page(self) -> None:
        self.refresh_header()
        if self.current_section() == "Command":
            self._show_section("Command")
        else:
            self.set_ask_count(len(ask_cards(self._folder(), self._clock())))

    def showEvent(self, event: QShowEvent | None) -> None:  # noqa: N802
        """Refresh the header, Command and its badge each time the page is shown."""
        super().showEvent(event)
        self._refresh_page()
