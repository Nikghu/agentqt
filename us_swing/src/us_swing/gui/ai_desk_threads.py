"""
Module: MD-GUI-035.016.M05 — gui/ai_desk_threads.py
Parent SRD: SRD-GUI-035.016

Team at work "Threads" tab: today's message threads in a table and the messages of the
selected thread below it. Read-only; the data comes from ``core/desk_messages``.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QListWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_messages import MessageRow, ThreadRow, messages_of, thread_rows
from us_swing.gui.ai_desk_sections import muted

HEADERS = ("Started", "Starter", "Messages", "Rounds", "State", "Tokens")
_ROLE = Qt.ItemDataRole.UserRole


def _clock(text: str) -> str:
    try:
        return datetime.fromisoformat(text).strftime("%H:%M:%S")
    except ValueError:
        return text


def empty_text(messages_on: bool) -> str:
    """What the tab says when there are no threads today."""
    return "No messages today" if messages_on else (
        "No messages today. Agent messages are off in Desk settings")


def message_line(m: MessageRow, names: Mapping[str, str]) -> str:
    """One message in plain words: time, type, from and to, words, state."""
    words = str(m.body.get("subject") or m.body.get("text")
                or (m.body.get("verdict") or {}).get("reason")
                or (m.body.get("verdict") or {}).get("result") or "")
    when = _clock(m.at)
    return (f"{when}  {m.type.replace('_', ' ')}  {names.get(m.sender, m.sender)} → "
            f"{names.get(m.receiver, m.receiver)}  {words[:120]}  ({m.state})")


class ThreadsView(QWidget):
    """Today's threads with the selected thread's messages."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the table, the empty note and the message list."""
        super().__init__(parent)
        self._home: Path | None = None
        self._names: dict[str, str] = {}
        self._shown: tuple[int, int] | None = None
        lines = QVBoxLayout(self)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(8)
        self.note = muted("")
        lines.addWidget(self.note)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lines.addWidget(self.table, 2)
        self.detail_title = QLabel("Messages")
        lines.addWidget(self.detail_title)
        self.detail = QListWidget()
        lines.addWidget(self.detail, 1)
        # table → itemSelectionChanged → view → _on_pick
        self.table.itemSelectionChanged.connect(self._on_pick)

    def show_threads(self, home: Path, day: str, names: Mapping[str, str],
                     messages_on: bool) -> None:
        """Show the threads opened on ``day`` and keep the selection when it still exists."""
        self._home, self._names = home, dict(names)
        rows = thread_rows(home, day)
        chosen = self._chosen()
        self.note.setText(empty_text(messages_on) if not rows else f"{len(rows)} thread(s) today")
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for i, t in enumerate(rows):
            self._fill_row(i, t)
        self.table.blockSignals(False)
        index = next((i for i, t in enumerate(rows) if t.id == chosen), 0 if rows else -1)
        if index >= 0:
            self.table.selectRow(index)
        self._on_pick()

    def _fill_row(self, i: int, t: ThreadRow) -> None:
        cells = (_clock(t.opened),
                 self._names.get(t.starter, t.starter), str(t.msgs), str(t.rounds), t.state,
                 f"{t.tokens:,}")
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setData(_ROLE, t.id)
            if col == 1:
                item.setToolTip(t.starter)
            self.table.setItem(i, col, item)

    def _chosen(self) -> int | None:
        items = self.table.selectedItems()
        value = items[0].data(_ROLE) if items else None
        return int(value) if value is not None else None

    def _on_pick(self) -> None:
        thread = self._chosen()
        if thread is None or self._home is None:
            self._shown = None
            self.detail.clear()
            self.detail_title.setText("Messages")
            return
        rows = messages_of(self._home, thread)
        if self._shown == (thread, len(rows)):
            return  # same thread, nothing new: keep the scroll place
        self._shown = (thread, len(rows))
        self.detail.clear()
        self.detail_title.setText(f"Messages of thread {thread}")
        for m in rows:
            self.detail.addItem(message_line(m, self._names))
