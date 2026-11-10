"""
Module: MD-GUI-034.009.M08 — AI Desk workspace
Parent SRD: SRD-GUI-034.009
Also: SRD-GUI-034.022 — the Pages section (was Studio), rebuilt each time it is shown
Also: SRD-GUI-034.027–.032 — real Hiring, Command approvals and Reports (live sections)
Also: MD-GUI-034.059.M33 — grouped section list, Command badge, header chips and spend bar
(SRD-GUI-034.059–.060)
Also: MD-GUI-035.001.M01 — Team at work replaces the five sample team sections (SRD-GUI-035.001)
Also: SRD-GUI-018.012 — the section list moves to the sidebar under the AI Desk item
Also: SRD-GUI-034.065 — console header: icon, state note, desk controls and four tiles
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import DeskState, DeskStatus, desk_home
from us_swing.core.desk_feed import ask_cards
from us_swing.core.desk_overview import (
    last_run,
    next_evening_run,
    spend,
    team_counts,
    todays_runs,
)
from us_swing.core.desk_trades import DeskTradeSink
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.desk_control import DeskBar, DeskPoller
from us_swing.gui.ai_desk_sections import command_frame, runs_box, team_line
from us_swing.gui.ai_desk_hiring import approvals_box, hiring_frame
from us_swing.gui.ai_desk_chat import ChatPanel
from us_swing.gui.ai_desk_console import icon_badge, stat_tile, thin_bar
from us_swing.gui.ai_desk_results import results_frame
from us_swing.gui.ai_desk_pages import pages_frame
from us_swing.gui.ai_desk_sections3 import cost_frame, reports_frame, settings_frame
from us_swing.gui.ai_desk_team import TeamAtWork
from us_swing.gui.theme import C

NY = ZoneInfo("America/New_York")
IST = ZoneInfo("Asia/Kolkata")
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("TALK", ("Command",)),
    ("TEAM", ("Team at work", "Hiring")),
    ("CREATE", ("Pages",)),
    ("REVIEW", ("Reports", "Results", "Cost & budget")),
    ("SETUP", ("Desk settings",)),
)
SECTIONS = tuple(name for _group, names in GROUPS for name in names)
_ROLE = Qt.ItemDataRole.UserRole
_RESULT_TONE = {"ok": "GREEN", "failed": "RED", "error": "RED", "running": "YELLOW"}
_STATE_NOTES = {
    DeskState.RUNNING: "A desk run is in progress",
    DeskState.SLEEPING: "Sleeping until the next run",
    DeskState.PAUSED: "Paused; no runs until you resume",
    DeskState.STOPPING: "Stopping",
    DeskState.STOPPED: "Stopped; press Start to run the desk",
    DeskState.OFF: "Off; press Start to run the desk",
    DeskState.ERROR: "The desk needs attention",
}

_LIVE_SECTIONS = ("Command", "Hiring", "Pages", "Reports", "Results", "Cost & budget")


def _nav_style() -> str:
    return (
        f"QListWidget {{ background: transparent; border: none; outline: none; }}"
        f"QListWidget::item {{ padding: 4px 10px; border-radius: 4px; margin: 1px 4px; }}"
        f"QListWidget::item:hover:!selected {{ background: {C.OVERLAY}; }}"
        f"QListWidget::item:selected {{ background: {C.OVERLAY}; color: {C.BLUE}; }}"
        f"QListWidget::item:focus {{ outline: none; border: none; }}"
    )


def _small(text: str) -> str:
    return f"<span style='color:{C.MUTED}; font-size:11px; font-weight:normal'>{text}</span>"


class AiDeskWorkspace(QWidget):
    """AI Desk page: header and section frame; the grouped section list is ``nav``."""

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
        self._list = QListWidget(self)
        self._list.hide()
        self._list.setStyleSheet(_nav_style())
        self._fill_list()
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
        # poller → status_changed → page → _on_status, show_state_note
        poller.status_changed.connect(self._on_status)
        poller.status_changed.connect(self.show_state_note)
        self.show_state_note(poller.status)
        self.select_section("Command")
        self.refresh_header()

    @property
    def nav(self) -> QListWidget:
        """The grouped section list, for the main window to place in the sidebar."""
        return self._list

    def _folder(self) -> Path:
        return self._home or desk_home()

    def _fill_list(self) -> None:
        for name in SECTIONS:
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
        if name == "Team at work":
            return TeamAtWork(self._home, self._clock)
        return settings_frame(name, self._home)

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
        lines = QVBoxLayout(box)
        lines.setContentsMargins(16, 12, 16, 12)
        lines.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(icon_badge("users", "go", 38))
        names = QVBoxLayout()
        names.setSpacing(2)
        title = QLabel("AI Desk")
        title.setObjectName("page_title")
        self.state_note = QLabel()
        self.state_note.setObjectName("state_note")
        self.state_note.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 12px;")
        names.addWidget(title)
        names.addWidget(self.state_note)
        row.addLayout(names)
        row.addStretch(1)
        row.addWidget(DeskBar(poller))
        lines.addLayout(row)
        self.spend_bar = thin_bar(0)
        run_tile, self.last_run_title, self.last_run_chip = stat_tile("Last run")
        next_tile, _head, self.next_run_label = stat_tile("Next run")
        spend_tile, _head, self.spend_label = stat_tile("AI spend today")
        month_tile, self.budget_title, self.budget_label = stat_tile("Month budget",
                                                                     bar=self.spend_bar)
        self.last_run_chip.setObjectName("last_run_chip")
        self.spend_label.setObjectName("spend_label")
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        for tile in (run_tile, next_tile, spend_tile, month_tile):
            tiles.addWidget(tile, 1)
        lines.addLayout(tiles)
        return box

    def show_state_note(self, status: DeskStatus) -> None:
        """Show one plain line about the desk state under the title."""
        note = status.message if status.state is DeskState.ERROR and status.message else ""
        self.state_note.setText(note or _STATE_NOTES.get(status.state, ""))

    def refresh_header(self) -> None:
        """Read the last run, the next run and the AI spend again and show them."""
        folder = self._folder()
        now = self._clock()
        run = last_run(folder)
        if run is None:
            self.last_run_title.setText("Last run")
            self.last_run_chip.setText("No runs yet")
        else:
            colour = getattr(C, _RESULT_TONE.get(run.result, "SUBTEXT"))
            self.last_run_title.setText(f"Last run · {run.result}")
            self.last_run_chip.setText(f"<span style='color:{colour}'>●</span>&nbsp;"
                                       f"{run.name} · {run.when:%H:%M} ET")
        upcoming = next_evening_run(now)
        day = "" if upcoming.date() == now.astimezone(NY).date() else f"{upcoming:%a} "
        self.next_run_label.setText(f"{day}{upcoming:%H:%M} ET&nbsp; "
                                    + _small(f"{upcoming.astimezone(IST):%H:%M} IST"))
        used = spend(folder, now)
        budget = used.budget_usd if used else load_settings(folder).monthly_budget_usd
        month = used.month_usd if used else 0.0
        share = round(used.month_share * 100) if used else 0
        self.spend_label.setText(f"${used.today_usd if used else 0.0:.2f}")
        self.budget_title.setText(f"Month budget · {share}% used")
        self.budget_label.setText(f"${month:.2f}&nbsp; " + _small(f"of ${budget:.2f}"))
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
