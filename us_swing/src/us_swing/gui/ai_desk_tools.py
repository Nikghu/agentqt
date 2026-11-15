"""
Module: MD-GUI-041.001.M01 — gui/ai_desk_tools.py
Parent SRD: SRD-GUI-041.001
Also: SRD-GUI-041.002 (table formats and plan state), SRD-GUI-041.003 (task cards),
SRD-GUI-041.004 (parts of the picked card), SRD-GUI-041.005 (failure log)
Also: SRD-GUI-041.006 (request a tool), .007 (tool requests), .008 (built tools), .009 (review
detail with the code), .010 (Enable and Disable) — AI Desk v3 M7b

The AI Desk "Tools" section (AI Desk v3 M6, M7b): the request box and the tool requests, the
built tools with the chosen version's checks, sample rows and code and its Enable and Disable
buttons, the registry tools, the table formats with the tool that makes each column and the
state of their plan, the latest task cards with the parts of the picked card, and the failure
log. It reads ``desk.db`` and ``memory.db`` through ``core`` and writes only through
``ask_tool()``, ``enable_tool()`` and ``disable_tool()``.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_built_tools import (
    CHECKS,
    MAX_REQUEST,
    BuiltTool,
    ToolRequest,
    ask_tool,
    built_tool_rows,
    changed,
    code_of,
    disable_tool,
    enable_tool,
    get_request,
    may_disable,
    may_enable,
    tool_requests,
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
from us_swing.gui.ai_desk_console import primary
from us_swing.gui.ai_desk_sections import heading, muted, read_only_text, scroll_of, section_frame

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
TOOL_COLUMNS = ("Name", "Group", "Kind", "AI", "Time limit", "Status")
FORMAT_COLUMNS = ("Format", "Plan", "Columns")
CARD_COLUMNS = ("Card", "Time", "Asked by", "Format", "Rows", "Result", "Seconds")
FAILURE_COLUMNS = ("Day", "Text")
REQUEST_COLUMNS = ("Request", "Time", "From", "State", "Reason", "Text")
BUILT_COLUMNS = ("Tool", "Version", "State", "Made", "Checks", "Title")
NO_TOOLS = "No tools yet. The list is filled when the desk starts"
NO_FORMATS = "No table formats yet"
NO_CARDS = "No task cards yet. The planner makes one for each table ask"
NO_FAILURES = "No failures logged"
NO_REQUESTS = "No tool requests yet"
NO_BUILT = "No built tools yet. Request one above"
PICK_CARD = "Pick a card to see its parts"
PICK_TOOL = "Pick a built tool to see its checks and code"
READ_FAILED = "Could not read the tools; try again in a moment"
SAVE_FAILED = "Could not save the request; try again in a moment."
REQUEST_HINT = ("What should the tool give for one stock? For example: percent below the "
                "52-week high")
OFF_NOTE = "Turn on Tool builder in Desk settings to request a tool."
MISSING_FILE = "The code file is missing."
CHANGED_LINE = "The code changed after review; it will not run."
_TABLE_MIN_H = 150
_CODE_MIN_H = 220


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


def request_cells(req: ToolRequest, names: Mapping[str, str]) -> list[str]:
    """One request row: number, time (ET), who asked, state, reason and the text last."""
    who = "You" if req.asker == "master" else names.get(req.asker, req.asker)
    return [f"#{req.id}", _when(req.made), who, req.state.capitalize(), req.reason, req.text]


def built_cells(tool: BuiltTool) -> list[str]:
    """One built version row: tool, version, state, made (ET), checks passed and title."""
    return [tool.name, f"v{tool.version}", tool.state.capitalize(), _when(tool.made),
            f"{tool.passed} of {len(CHECKS)}", tool.title]


def tool_text(tool: BuiltTool, request: ToolRequest | None, changed_file: bool) -> str:
    """The chosen version: its request, about, columns, each check, the sample rows, and a
    line when its file changed after review (SRD-GUI-041.009)."""
    lines = [f"Request #{request.id}: {request.text}"] if request is not None else []
    lines += [f"About: {tool.about}",
              "Columns: " + "; ".join(f"{c.name} ({c.type}): {c.meaning}" for c in tool.columns)]
    for c in tool.checks:
        mark = "✓" if c.ok else "✗"
        lines.append(f"{mark} {c.check}: {c.note}" if c.note else f"{mark} {c.check}")
    if tool.sample:
        lines += ["Sample rows:", *tool.sample]
    if changed_file:
        lines.append(CHANGED_LINE)
    return "\n".join(lines)


def sentence(text: str) -> str:
    """A core reason as a sentence for the screen: capital first letter and a full stop."""
    text = text.strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else f"{text}."


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


def _plain(label: QLabel) -> QLabel:
    """Show the label's text as plain text: model-written text is never read as HTML."""
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def _selectable(label: QLabel) -> QLabel:
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return _plain(label)


class ToolsView(QWidget):
    """Tool requests, built tools with review, tools, table formats, task cards with the
    picked card's parts, and the failure log."""

    def __init__(self, name: str, home: Path,
                 clock: Callable[[], datetime] | None = None) -> None:
        """Build the section for the desk folder ``home``; ``clock`` is injectable for tests."""
        super().__init__()
        self._home = home
        self._clock = clock or (lambda: datetime.now(NY))
        self._cards: list[Card] = []
        self._built: list[BuiltTool] = []
        self._chosen_tool: int | None = None
        self._request_message = ""
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
        self._request_row()
        self.requests_table, self.requests_empty = self._block(
            "Tool requests", REQUEST_COLUMNS, NO_REQUESTS)
        self.built_table, self.built_empty = self._block("Built tools", BUILT_COLUMNS,
                                                         NO_BUILT)
        self._review_area()
        self.tools_table, self.tools_empty = self._block("Tools", TOOL_COLUMNS, NO_TOOLS)
        self.formats_table, self.formats_empty = self._block("Table formats", FORMAT_COLUMNS,
                                                             NO_FORMATS)
        self.cards_table, self.cards_empty = self._block("Task cards", CARD_COLUMNS, NO_CARDS)
        self.parts = _selectable(QLabel(""))
        self._lines.addWidget(self.parts)
        self.failures_table, self.failures_empty = self._block("Failure log", FAILURE_COLUMNS,
                                                               NO_FAILURES)
        self._lines.addStretch(1)
        body.addWidget(scroll_of(inner), 1)
        # cards table → itemSelectionChanged → view → _on_pick
        self.cards_table.itemSelectionChanged.connect(self._on_pick)
        # built tools table → itemSelectionChanged → view → _on_pick_tool
        self.built_table.itemSelectionChanged.connect(self._on_pick_tool)
        self.refresh()

    def _request_row(self) -> None:
        """The request box, its button and its note line (SRD-GUI-041.006)."""
        self._lines.addWidget(heading("Request a tool"))
        row = QHBoxLayout()
        self.request_edit = QLineEdit()
        self.request_edit.setMaxLength(MAX_REQUEST)
        self.request_edit.setPlaceholderText(REQUEST_HINT)
        self.request_btn = primary(QPushButton("Request"))
        row.addWidget(self.request_edit, 1)
        row.addWidget(self.request_btn)
        self._lines.addLayout(row)
        self.request_note = _plain(muted(""))
        self._lines.addWidget(self.request_note)
        # request button → clicked → view → _on_request; Enter in the box does the same
        self.request_btn.clicked.connect(self._on_request)
        self.request_edit.returnPressed.connect(self._on_request)

    def _review_area(self) -> None:
        """The chosen version's detail, its code and the Enable and Disable buttons."""
        self.tool_detail = _selectable(QLabel(""))
        self._lines.addWidget(self.tool_detail)
        self.code_box: QPlainTextEdit = read_only_text("", mono=True)
        self.code_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code_box.setMinimumHeight(_CODE_MIN_H)
        self._lines.addWidget(self.code_box)
        row = QHBoxLayout()
        self.enable_btn = primary(QPushButton("Enable"))
        self.disable_btn = QPushButton("Disable")
        self.tool_note = _plain(muted(""))
        row.addWidget(self.enable_btn)
        row.addWidget(self.disable_btn)
        row.addWidget(self.tool_note, 1)
        self._lines.addLayout(row)
        # Enable / Disable → clicked → view → _on_switch
        self.enable_btn.clicked.connect(lambda: self._on_switch(enable_tool))
        self.disable_btn.clicked.connect(lambda: self._on_switch(disable_tool))

    def _block(self, title: str, columns: Sequence[str],
               empty_text: str) -> tuple[QTableWidget, QLabel]:
        self._lines.addWidget(heading(title))
        empty = muted(empty_text)
        table = _table(columns)
        self._lines.addWidget(empty)
        self._lines.addWidget(table)
        return table, empty

    def refresh(self) -> None:
        """Read the requests, built tools, tools, formats, plans, cards and failure rows again
        and show them; the chosen built tool stays chosen."""
        try:
            requests = tool_requests(self._home)
            built = built_tool_rows(self._home)
            builder_on = load_settings(self._home).tool_builder_on
            tools = list_tools(self._home)
            formats = list_formats(self._home)
            plans = {p.format: p for p in plan_rows(self._home)}
            cards = card_rows(self._home)
            failures = failure_rows(self._home)
            names = {e.id: e.name for e in employees(self._home)}
        except (sqlite3.Error, OSError, ValueError) as exc:
            log.warning("[Tools] Could not read the tools view data: %s", exc)
            self.note.setText(READ_FAILED)
            self.note.setVisible(True)
            self._built = []
            self._on_pick_tool()
            return
        self.note.setVisible(False)
        self.request_btn.setEnabled(builder_on)
        self.request_note.setText(self._request_message if builder_on else OFF_NOTE)
        self.request_note.setVisible(bool(self.request_note.text()))
        _fill(self.requests_table, self.requests_empty,
              [request_cells(r, names) for r in requests])
        self._built = built
        _fill(self.built_table, self.built_empty, [built_cells(t) for t in built])
        self._choose_tool()
        self._cards = cards
        _fill(self.tools_table, self.tools_empty, [tool_cells(t) for t in tools])
        _fill(self.formats_table, self.formats_empty,
              [format_cells(f, plans.get(f.id)) for f in formats])
        _fill(self.cards_table, self.cards_empty, [card_cells(c, names) for c in cards])
        _fill(self.failures_table, self.failures_empty, [[m.made, m.text] for m in failures])
        self._on_pick()

    def _choose_tool(self) -> None:
        """Select the chosen built tool again after a reload, by its id."""
        row = next((i for i, t in enumerate(self._built) if t.id == self._chosen_tool), None)
        if row is not None:
            self.built_table.selectRow(row)
        self._on_pick_tool()

    def _chosen(self) -> Card | None:
        model = self.cards_table.selectionModel()
        rows = model.selectedRows() if model is not None else []
        return self._cards[rows[0].row()] if rows and rows[0].row() < len(self._cards) else None

    def _on_pick(self) -> None:
        self.parts.setText(part_lines(self._chosen()) if self._cards else "")
        self.parts.setVisible(bool(self._cards))

    def _picked_tool(self) -> BuiltTool | None:
        model = self.built_table.selectionModel()
        rows = model.selectedRows() if model is not None else []
        return self._built[rows[0].row()] if rows and rows[0].row() < len(self._built) else None

    def _on_pick_tool(self) -> None:
        """Show the chosen version's detail, code and buttons (SRD-GUI-041.009, .010)."""
        tool = self._picked_tool()
        if tool is not None and tool.id != self._chosen_tool:
            self._chosen_tool = tool.id
            self.tool_note.setText("")
        shown = bool(self._built)
        for widget in (self.tool_detail, self.code_box, self.enable_btn, self.disable_btn,
                       self.tool_note):
            widget.setVisible(shown)
        self.enable_btn.setEnabled(may_enable(tool))
        self.disable_btn.setEnabled(may_disable(tool))
        if tool is None:
            self.tool_detail.setText(PICK_TOOL)
            self.code_box.setPlainText("")
            return
        code = code_of(self._home, tool)
        request = get_request(self._home, tool.request) if tool.request is not None else None
        edited = bool(code) and changed(self._home, tool)
        self.tool_detail.setText(tool_text(tool, request, edited))
        self.code_box.setPlainText(code or MISSING_FILE)

    def _on_request(self) -> None:
        """Save the typed request through core (SRD-GUI-041.006); Enter does nothing while
        the button is off."""
        if not self.request_btn.isEnabled():
            return
        try:
            rid = ask_tool(self._home, self.request_edit.text(), self._clock())
        except ValueError as exc:
            self._show_request(sentence(str(exc)))
            return
        except (sqlite3.Error, OSError) as exc:
            log.warning("[Tools] Could not save the tool request: %s", exc)
            self._show_request(SAVE_FAILED)
            return
        self.request_edit.clear()
        self._request_message = f"Request #{rid} saved. The builder starts at its next turn."
        self.refresh()

    def _show_request(self, text: str) -> None:
        self._request_message = text
        self.request_note.setText(text)
        self.request_note.setVisible(True)

    def _on_switch(self, action: Callable[[Path, int, datetime], str]) -> None:
        """Enable or disable the chosen version through core and reload (SRD-GUI-041.010)."""
        tool = self._picked_tool()
        if tool is None:
            return
        why = action(self._home, tool.id, self._clock())
        self.refresh()
        done = "Enabled" if action is enable_tool else "Disabled"
        self.tool_note.setText(sentence(why) if why else f"{done} {tool.name} v{tool.version}.")


def tools_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the Tools section for the desk folder ``home`` (the default folder when None)."""
    return ToolsView(name, home or desk_home())
