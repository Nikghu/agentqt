"""
Module: MD-GUI-037.001.M01 — gui/ai_desk_memory.py
Parent SRD: SRD-GUI-037.001
Also: SRD-GUI-037.002 (lessons table and status filter), SRD-GUI-037.003 (Pin, Unpin, Edit,
Retire, Delete), SRD-GUI-037.004 (proof picks)

The AI Desk "Memory" section: what the desk has learned from its picks. It reads lessons
through ``core.desk_lessons`` and changes nothing itself: each button adds a lesson edit
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
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from us_swing.core.desk_contract import desk_home
from us_swing.core.desk_lessons import (
    Lesson,
    add_edit,
    lesson_rows,
    pending_edits,
    proof_rows,
)
from us_swing.gui.ai_desk_sections import muted, section_frame
from us_swing.gui.popups import confirm
from us_swing.gui.theme import C

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
STATUSES = ("Active", "Candidate", "Retired")
COLUMNS = ("Status", "Pinned", "Lesson", "Tags", "Cases", "Avg R", "Confidence",
           "Last confirmed")
PROOF_COLUMNS = ("Day", "Side", "Stock", "R")
NO_LESSONS = "No lessons yet. The desk writes them after its picks close"
PENDING = "applies at the next desk tick"
Ask = Callable[[QWidget, str, str], bool]


def _ask(parent: QWidget, title: str, text: str) -> bool:
    return confirm(parent, title, text, confirm_text="Delete", danger=True)


def _cells(lesson: Lesson, pending: bool) -> list[str]:
    tags = ", ".join(f"{k} {v}" for k, v in sorted(lesson.tags.items()))
    return [PENDING if pending else lesson.status, "yes" if lesson.pinned else "",
            lesson.text, tags, str(lesson.cases), f"{lesson.avg_r:+.2f}",
            f"{round(100 * lesson.confidence)}%", (lesson.last_confirmed or "")[:10]]


def _table(headers: tuple[str, ...]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    side, head = table.verticalHeader(), table.horizontalHeader()
    if side is not None:
        side.setVisible(False)
    if head is not None:
        head.setStretchLastSection(True)
    return table


def _fill(table: QTableWidget, rows: list[list[str]]) -> None:
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(text))


class MemoryView(QWidget):
    """Lessons table with a status filter, edit buttons and the proof picks."""

    def __init__(self, name: str, home: Path, clock: Callable[[], datetime] | None = None,
                 ask: Ask = _ask) -> None:
        """Build the section for the desk folder ``home``; ``ask`` confirms a delete."""
        super().__init__()
        self._home = home
        self._clock = clock or (lambda: datetime.now(NY))
        self._ask = ask
        self._ids: list[int] = []
        self._texts: dict[int, str] = {}
        self._shown: int | None = None
        frame, body = section_frame(name, sample=False)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        top = QHBoxLayout()
        top.addWidget(QLabel("Show"))
        self.filter = QComboBox()
        self.filter.addItems(STATUSES)
        self.filter.setFixedWidth(140)
        top.addWidget(self.filter)
        top.addStretch(1)
        body.addLayout(top)
        self.empty = muted(NO_LESSONS)
        body.addWidget(self.empty)
        self.table = _table(COLUMNS)
        body.addWidget(self.table, 3)
        self.text = QLineEdit()
        self.text.setPlaceholderText("Choose a lesson to change its text")
        body.addWidget(self.text)
        buttons = QHBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for label, action in (("Pin", "pin"), ("Unpin", "unpin"), ("Save text", "edit"),
                              ("Retire", "retire"), ("Delete", "delete")):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, a=action: self._edit(a))
            buttons.addWidget(button)
            self.buttons[action] = button
        buttons.addStretch(1)
        body.addLayout(buttons)
        body.addWidget(QLabel("Picks that back this lesson"))
        self.proof = _table(PROOF_COLUMNS)
        body.addWidget(self.proof, 2)
        # filter → refresh; table selection → proof list and text box
        self.filter.currentIndexChanged.connect(lambda _i: self.refresh())
        self.table.itemSelectionChanged.connect(self._on_pick)
        self.refresh()

    def refresh(self) -> None:
        """Read the lessons of the chosen status again."""
        status = self.filter.currentText().lower()
        lessons = lesson_rows(self._home, status)
        pending = pending_edits(self._home)
        self._ids = [x.id for x in lessons]
        self._texts = {x.id: x.text for x in lessons}
        _fill(self.table, [_cells(x, x.id in pending) for x in lessons])
        for r, lesson in enumerate(lessons):
            item = self.table.item(r, 0)
            if item is not None and lesson.id in pending:
                item.setForeground(QColor(C.YELLOW))
        self.empty.setVisible(not lessons)
        self.table.setVisible(bool(lessons))
        self._on_pick()

    def _chosen(self) -> int | None:
        model = self.table.selectionModel()
        rows = model.selectedRows() if model is not None else []
        return self._ids[rows[0].row()] if rows else None

    def _on_pick(self) -> None:
        lid = self._chosen()
        for button in self.buttons.values():
            button.setEnabled(lid is not None)
        if lid != self._shown:
            self.text.setText(self._texts.get(lid, "") if lid is not None else "")
            self._shown = lid
        rows = proof_rows(self._home, lid) if lid is not None else []
        _fill(self.proof, [[p.day, p.side, p.symbol, "—" if p.r is None else f"{p.r:+.2f}"]
                           for p in rows])

    def _edit(self, action: str) -> None:
        lid = self._chosen()
        if lid is None:
            return
        if action == "delete" and not self._ask(self, "Delete lesson",
                                                f"Delete lesson L-{lid} for good?"):
            return
        text = self.text.text().strip()
        if action == "edit" and not text:
            return
        try:
            add_edit(self._home, lid, action, self._clock(), text)
        except sqlite3.Error:
            log.warning("[AI Desk] Could not save the lesson change; try again in a moment")
            return
        row = self._ids.index(lid)
        self.refresh()
        if row < self.table.rowCount():
            self.table.selectRow(row)


def memory_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the Memory section for the desk folder ``home`` (the default folder when None)."""
    return MemoryView(name, home or desk_home())
