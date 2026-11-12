"""
Module: MD-GUI-039.001.M01 — gui/ai_desk_research.py
Parent SRD: SRD-GUI-039.001
Also: SRD-GUI-039.002 (Approve, Reject, Change cap), SRD-GUI-039.003 (ticket detail),
SRD-GUI-039.004 (lead research tokens), SRD-GUI-039.005 (edit log),
SRD-GUI-039.006–.007 (Add book and its log)

The AI Desk "Research" section: the research tickets the leads raised. It reads tickets
through ``core.desk_research`` and changes nothing itself: each button adds a ticket edit
that the desk applies at its next tick.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from us_swing.core.desk_books import BOOK_TYPES, BookAddError, add_book
from us_swing.core.desk_contract import desk_home
from us_swing.core.desk_research import (
    CAP_MAX,
    CAP_MIN,
    Action,
    Ticket,
    add_ticket_edit,
    lead_research,
    pending_ticket_edits,
    ticket_rows,
)
from us_swing.gui.ai_desk_sections import muted, section_frame
from us_swing.gui.theme import C

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
COLUMNS = ("Status", "Kind", "Goal", "Cap", "Spent", "Raised by", "Made")
NO_TICKETS = "No research tickets yet. Leads raise them with the morning plan and check-ins"
PENDING = "applies at the next desk tick"
ENDED = ("done", "failed", "stuck", "rejected", "expired")
_DONE_WORDS = {"approve": "approved", "reject": "rejected", "cap": "cap set to"}
BOOK_FILTER = "Books (" + " ".join(f"*{t}" for t in BOOK_TYPES) + ")"


def _cells(ticket: Ticket, pending: bool) -> list[str]:
    return [PENDING if pending else ticket.status, ticket.kind.replace("_", " "), ticket.goal,
            f"{ticket.token_cap:,}", f"{ticket.tokens:,}", ticket.raised_by_name,
            ticket.made[:16].replace("T", " ")]


def detail_text(ticket: Ticket | None) -> str:
    """The done test, and for an ended ticket its result and end reason."""
    if ticket is None:
        return ""
    lines = [f"Done when: {ticket.done_test}"]
    if ticket.status in ENDED:
        lines.append(f"Ended: {ticket.status}, {ticket.end_reason or 'no reason given'}")
        lines.append(f"Result: {ticket.result or 'nothing found'}")
    return "\n".join(lines)


def leads_text(rows: list[tuple[str, int, int]]) -> str:
    """One line with each lead's research tokens used and left today."""
    if not rows:
        return "No active lead"
    return "Research tokens today: " + " · ".join(
        f"{name} {used:,} used, {left:,} left" for name, used, left in rows)


def _table() -> QTableWidget:
    table = QTableWidget(0, len(COLUMNS))
    table.setHorizontalHeaderLabels(list(COLUMNS))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    side, head = table.verticalHeader(), table.horizontalHeader()
    if side is not None:
        side.setVisible(False)
    if head is not None:
        head.setStretchLastSection(True)
    return table


class ResearchView(QWidget):
    """Ticket table, lead research line, approval buttons and the ticket detail."""

    def __init__(self, name: str, home: Path,
                 clock: Callable[[], datetime] | None = None,
                 pick_file: Callable[[], str] | None = None) -> None:
        """Build the section for the desk folder ``home``; ``pick_file`` is for tests."""
        super().__init__()
        self._home = home
        self._clock = clock or (lambda: datetime.now(NY))
        self._pick_file = pick_file or self._browse
        self._tickets: list[Ticket] = []
        self._pending: set[int] = set()
        frame, body = section_frame(name, sample=False)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        self.leads = muted("")
        body.addWidget(self.leads)
        self.empty = muted(NO_TICKETS)
        body.addWidget(self.empty)
        self.table = _table()
        body.addWidget(self.table, 3)
        buttons = QHBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for label, action in (("Approve", "approve"), ("Reject", "reject")):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, a=action: self._edit(a))
            buttons.addWidget(button)
            self.buttons[action] = button
        self.cap = QSpinBox()
        self.cap.setRange(0, 2 * CAP_MAX)
        self.cap.setSingleStep(1_000)
        self.cap.setGroupSeparatorShown(True)
        self.cap.setFixedWidth(120)
        self.cap.setStyleSheet("QSpinBox { outline: none; } QSpinBox:focus { outline: none; }")
        buttons.addWidget(self.cap)
        change = QPushButton("Change cap")
        change.clicked.connect(lambda _=False: self._edit("cap"))
        buttons.addWidget(change)
        self.buttons["cap"] = change
        buttons.addStretch(1)
        self.add_book_button = QPushButton("Add book")
        self.add_book_button.clicked.connect(lambda _=False: self._add_book())
        buttons.addWidget(self.add_book_button)
        body.addLayout(buttons)
        self.note = muted("")
        body.addWidget(self.note)
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        body.addWidget(self.detail, 1)
        # table selection → buttons and detail
        self.table.itemSelectionChanged.connect(self._on_pick)
        self.refresh()

    def refresh(self) -> None:
        """Read the tickets and the leads' research tokens again."""
        now = self._clock()
        try:
            tickets = ticket_rows(self._home, now)
            pending = pending_ticket_edits(self._home)
            leads = leads_text(lead_research(self._home, now.date().isoformat()))
        except sqlite3.Error:
            log.warning("[Research] Could not read the tickets; try again in a moment")
            return
        self._tickets, self._pending = tickets, pending
        self.leads.setText(leads)
        self.table.setRowCount(len(self._tickets))
        for r, ticket in enumerate(self._tickets):
            for c, text in enumerate(_cells(ticket, ticket.id in pending)):
                item = QTableWidgetItem(text)
                if c == 0 and (ticket.id in pending or ticket.status == "waiting"):
                    item.setForeground(QColor(C.YELLOW))
                self.table.setItem(r, c, item)
        self.empty.setVisible(not self._tickets)
        self.table.setVisible(bool(self._tickets))
        self._on_pick()

    def _chosen(self) -> Ticket | None:
        model = self.table.selectionModel()
        rows = model.selectedRows() if model is not None else []
        return self._tickets[rows[0].row()] if rows else None

    def _on_pick(self) -> None:
        ticket = self._chosen()
        waiting = self._editable(ticket)
        for button in self.buttons.values():
            button.setEnabled(waiting)
        self.cap.setEnabled(waiting)
        self.cap.setValue(ticket.token_cap if ticket is not None and waiting else CAP_MIN)
        self.detail.setText(detail_text(ticket))

    def _editable(self, ticket: Ticket | None) -> bool:
        return (ticket is not None and ticket.status == "waiting"
                and ticket.id not in self._pending)

    def _edit(self, action: Action) -> None:
        ticket = self._chosen()
        if ticket is None or not self._editable(ticket):
            return
        cap = self.cap.value() if action == "cap" else None
        if cap is not None and not CAP_MIN <= cap <= CAP_MAX:
            self.note.setText(f"The cap must be {CAP_MIN:,} to {CAP_MAX:,} tokens")
            return
        try:
            add_ticket_edit(self._home, ticket.id, action, self._clock(), cap)
        except (sqlite3.Error, ValueError):
            log.warning("[Research] Could not save the ticket change; try again in a moment")
            return
        done = _DONE_WORDS[action] + (f" {cap:,} tokens" if cap is not None else "")
        log.info("[Research] Ticket %d %s from the app", ticket.id, done)
        self.note.setText("")
        row = self._tickets.index(ticket)
        self.refresh()
        if row < self.table.rowCount():
            self.table.selectRow(row)

    def _browse(self) -> str:
        chosen, _filter = QFileDialog.getOpenFileName(self, "Add book", "", BOOK_FILTER)
        return chosen

    def _add_book(self) -> None:
        chosen = self._pick_file()
        if not chosen:
            return
        try:
            added = add_book(self._home, Path(chosen))
        except (BookAddError, OSError) as exc:
            reason = str(exc) if isinstance(exc, BookAddError) else "the file could not be copied"
            log.warning("[Books] Book not added: %s", reason)
            self.note.setText(f"Book not added: {reason}")
            return
        log.info("[Books] Added %s to the desk books", added.name)
        self.note.setText(f"Added {added.name}. The lead sees it in the next plan")


def research_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the Research section for the desk folder ``home`` (the default folder when None)."""
    return ResearchView(name, home or desk_home())
