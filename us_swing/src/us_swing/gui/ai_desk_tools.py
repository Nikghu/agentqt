"""
Module: MD-GUI-041.001.M01 — gui/ai_desk_tools.py
Parent SRD: SRD-GUI-041.001
Also: SRD-GUI-041.002 (table formats and plan state), SRD-GUI-041.003 (task cards),
SRD-GUI-041.004 (parts of the picked card), SRD-GUI-041.005 (failure log)

The AI Desk "Tools" section (AI Desk v3 M6): the registry tools, the table formats with the
tool that makes each column and the state of their plan, the latest task cards with the
parts of the picked card, and the failure log. Read-only: it reads ``desk.db`` and
``memory.db`` through ``core`` and writes nothing.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_contract import desk_home
from us_swing.core.desk_hiring import employees
from us_swing.core.desk_memory import failure_rows
from us_swing.core.desk_registry import TableFormat, Tool, list_formats, list_tools
from us_swing.core.desk_tasks import (
    RETIRED,
    Card,
    Plan,
    card_rows,
    group_label,
    group_of,
    plan_rows,
)
from us_swing.gui.ai_desk_sections import heading, muted, scroll_of, section_frame

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
TOOL_COLUMNS = ("Name", "Group", "Kind", "AI", "Time limit", "Status")
FORMAT_COLUMNS = ("Format", "Plan", "Columns")
CARD_COLUMNS = ("Card", "Time", "Asked by", "Format", "Rows", "Result", "Seconds")
FAILURE_COLUMNS = ("Day", "Text")
NO_TOOLS = "No tools yet. The list is filled when the desk starts"
NO_FORMATS = "No table formats yet"
NO_CARDS = "No task cards yet. The planner makes one for each table ask"
NO_FAILURES = "No failures logged"
PICK_CARD = "Pick a card to see its parts"
READ_FAILED = "Could not read the tools; try again in a moment"
_TABLE_MIN_H = 150


def tool_cells(tool: Tool) -> list[str]:
    """One tool row: name, group, kind, AI, time limit and status."""
    group = "MCP" if tool.kind == "mcp" else group_label(group_of(tool.name))
    return [tool.name, group, tool.kind, "Yes" if tool.ai else "No",
            f"{tool.secs} s" if tool.secs else "", tool.status.capitalize()]


def plan_label(plan: Plan | None) -> str:
    """Active, Retired with its reason, or No plan."""
    if plan is None:
        return "No plan"
    if plan.status == RETIRED:
        return f"Retired: {plan.why}" if plan.why else "Retired"
    return "Active"


def format_cells(fmt: TableFormat, plan: Plan | None) -> list[str]:
    """One format row: id, the plan state, and each column with the tool that makes it.

    The long column list comes last, so it takes the stretched last table column.
    """
    columns = ", ".join(f"{c.name} ← {c.by}" if c.by else c.name for c in fmt.columns)
    return [fmt.id, plan_label(plan), columns]


def _when(stamp: str) -> str:
    try:
        return datetime.fromisoformat(stamp).astimezone(NY).strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return stamp


def card_cells(card: Card, names: Mapping[str, str]) -> list[str]:
    """One card row: card, time (ET), asker's current name, format, rows, result, seconds."""
    return [f"TC-{card.id}", _when(card.made), names.get(card.asker, card.asker), card.format,
            str(card.rows), card.status.capitalize(),
            "" if card.secs is None else f"{card.secs:.1f}"]


def part_lines(card: Card | None) -> str:
    """One line per part of ``card``: group, tools, columns, rows, result, seconds, reason."""
    if card is None:
        return PICK_CARD
    lines = []
    for part in card.parts:
        bits = [part.id, group_label(part.group), ", ".join(part.tools), ", ".join(part.cols),
                f"{part.rows} rows", part.status, f"{part.secs:.1f} s"]
        if part.reason:
            bits.append(part.reason)
        lines.append(" · ".join(bits))
    if card.reason:
        lines.append(f"{card.status.capitalize()}: {card.reason}")
    return "\n".join(lines) or "This card has no parts yet"


def _table(columns: Sequence[str]) -> QTableWidget:
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(list(columns))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setMinimumHeight(_TABLE_MIN_H)
    side, head = table.verticalHeader(), table.horizontalHeader()
    if side is not None:
        side.setVisible(False)
    if head is not None:
        head.setStretchLastSection(True)
    return table


def _fill(table: QTableWidget, empty: QLabel, rows: Sequence[Sequence[str]]) -> None:
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(text))
    table.resizeColumnsToContents()
    empty.setVisible(not rows)
    table.setVisible(bool(rows))


class ToolsView(QWidget):
    """Tools, table formats, task cards with the picked card's parts, and the failure log."""

    def __init__(self, name: str, home: Path) -> None:
        """Build the section for the desk folder ``home``."""
        super().__init__()
        self._home = home
        self._cards: list[Card] = []
        frame, body = section_frame(name, sample=False)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        inner = QWidget()
        self._lines = QVBoxLayout(inner)
        self._lines.setContentsMargins(0, 0, 0, 0)
        self._lines.setSpacing(8)
        self.note = muted("")
        self._lines.addWidget(self.note)
        self.tools_table, self.tools_empty = self._block("Tools", TOOL_COLUMNS, NO_TOOLS)
        self.formats_table, self.formats_empty = self._block("Table formats", FORMAT_COLUMNS,
                                                             NO_FORMATS)
        self.cards_table, self.cards_empty = self._block("Task cards", CARD_COLUMNS, NO_CARDS)
        self.parts = QLabel("")
        self.parts.setWordWrap(True)
        self.parts.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._lines.addWidget(self.parts)
        self.failures_table, self.failures_empty = self._block("Failure log", FAILURE_COLUMNS,
                                                               NO_FAILURES)
        self._lines.addStretch(1)
        body.addWidget(scroll_of(inner), 1)
        # cards table → itemSelectionChanged → view → _on_pick
        self.cards_table.itemSelectionChanged.connect(self._on_pick)
        self.refresh()

    def _block(self, title: str, columns: Sequence[str],
               empty_text: str) -> tuple[QTableWidget, QLabel]:
        self._lines.addWidget(heading(title))
        empty = muted(empty_text)
        table = _table(columns)
        self._lines.addWidget(empty)
        self._lines.addWidget(table)
        return table, empty

    def refresh(self) -> None:
        """Read the tools, formats, plans, cards and failure rows again and show them."""
        try:
            tools = list_tools(self._home)
            formats = list_formats(self._home)
            plans = {p.format: p for p in plan_rows(self._home)}
            cards = card_rows(self._home)
            failures = failure_rows(self._home)
            names = {e.id: e.name for e in employees(self._home)}
        except (sqlite3.Error, OSError):
            log.warning("[Tools] Could not read the tools view data; try again in a moment")
            self.note.setText(READ_FAILED)
            self.note.setVisible(True)
            return
        self.note.setVisible(False)
        self._cards = cards
        _fill(self.tools_table, self.tools_empty, [tool_cells(t) for t in tools])
        _fill(self.formats_table, self.formats_empty,
              [format_cells(f, plans.get(f.id)) for f in formats])
        _fill(self.cards_table, self.cards_empty, [card_cells(c, names) for c in cards])
        _fill(self.failures_table, self.failures_empty, [[m.made, m.text] for m in failures])
        self._on_pick()

    def _chosen(self) -> Card | None:
        model = self.cards_table.selectionModel()
        rows = model.selectedRows() if model is not None else []
        return self._cards[rows[0].row()] if rows and rows[0].row() < len(self._cards) else None

    def _on_pick(self) -> None:
        self.parts.setText(part_lines(self._chosen()) if self._cards else "")
        self.parts.setVisible(bool(self._cards))


def tools_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the Tools section for the desk folder ``home`` (the default folder when None)."""
    return ToolsView(name, home or desk_home())
