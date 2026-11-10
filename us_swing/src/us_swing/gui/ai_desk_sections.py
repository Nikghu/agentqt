"""
Module: MD-GUI-034.009.M08 — AI Desk sections (Command to Hiring)
Parent SRD: SRD-GUI-034.009
Also: MD-GUI-034.062.M36 — real Today's runs and Team now in Command (SRD-GUI-034.063–.064)

Frames only: sample content, no real data and no actions. Shared helpers live here too.
"""
from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_contract import ProductDescriptor
from us_swing.core.desk_overview import RunRow
from us_swing.gui import ai_desk_sample as S
from us_swing.gui.floor_panel import table_body
from us_swing.gui.floor_sample import SAMPLE_TAG
from us_swing.gui.theme import C

NO_RUNS = "No desk runs today"
MONO = "font-family: Consolas, 'Courier New', monospace;"


def muted(text: str) -> QLabel:
    """Return a muted, word-wrapped note label."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {C.MUTED};")
    return label


def section_frame(name: str, sample: bool = True) -> tuple[QWidget, QVBoxLayout]:
    """Return a section frame titled ``name`` (with the sample tag when ``sample``) and its body."""
    box = QWidget()
    body = QVBoxLayout(box)
    body.setContentsMargins(14, 12, 14, 12)
    body.setSpacing(8)
    head = QHBoxLayout()
    title = QLabel(name)
    title.setObjectName("page_title")
    tag = QLabel(SAMPLE_TAG)
    tag.setObjectName("sample_tag")
    tag.setStyleSheet(f"color: {C.MUTED};")
    head.addWidget(title)
    if sample:
        head.addWidget(tag)
    head.addStretch(1)
    body.addLayout(head)
    return box, body


def heading(text: str) -> QLabel:
    """Return a small section heading label."""
    label = QLabel(text)
    label.setObjectName("view_head")
    return label


def make_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> QTableWidget:
    """Return a read-only table with ``headers`` built through the Floor table helper."""
    keys = tuple(h.lower().replace(" ", "_") for h in headers)
    product = ProductDescriptor("desk.sample", "Sample", "table", ("table",), keys, sample=True)
    table = table_body(product, [dict(zip(keys, row, strict=False)) for row in rows])
    table.setHorizontalHeaderLabels(list(headers))
    return table


def read_only_text(text: str, mono: bool = True) -> QPlainTextEdit:
    """Return a read-only text box showing ``text``."""
    box = QPlainTextEdit(text)
    box.setReadOnly(True)
    box.setStyleSheet(
        f"QPlainTextEdit {{ background: {C.SURFACE}; border: 1px solid {C.OVERLAY};"
        f" border-radius: 4px; padding: 4px; outline: none; {MONO if mono else ''} }}"
    )
    return box


def tile(title: str, detail: str, tag: str = "") -> QFrame:
    """Return a small bordered card with a bold ``title`` and a ``detail`` line."""
    tile = QFrame()
    tile.setObjectName("desk_tile")
    tile.setStyleSheet(
        f"QFrame#desk_tile {{ background: {C.SURFACE}; border: 1px solid {C.OVERLAY};"
        " border-radius: 6px; }"
    )
    lines = QVBoxLayout(tile)
    lines.setContentsMargins(8, 6, 8, 6)
    lines.setSpacing(2)
    head = QLabel(f"{tag}  {title}" if tag else title)
    head.setStyleSheet("font-weight: bold; background: transparent; border: none;")
    head.setWordWrap(True)
    note = QLabel(detail)
    note.setWordWrap(True)
    note.setStyleSheet(f"color: {C.SUBTEXT}; background: transparent; border: none;")
    lines.addWidget(head)
    lines.addWidget(note)
    return tile


def scroll_of(inner: QWidget) -> QScrollArea:
    """Wrap ``inner`` in a borderless scroll area."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(inner)
    return area


def _chat_frame() -> QWidget:
    box = QWidget()
    lines = QVBoxLayout(box)
    lines.setContentsMargins(0, 0, 0, 0)
    lines.addWidget(heading("Lead chat"))
    feed = QWidget()
    msgs = QVBoxLayout(feed)
    msgs.setSpacing(6)
    for who, text in S.CHAT:
        colour = C.GREEN if who == "Master" else C.BLUE
        label = QLabel(f"<b style='color:{colour}'>{who}</b><br>{text}")
        label.setWordWrap(True)
        msgs.addWidget(label)
    msgs.addStretch(1)
    lines.addWidget(scroll_of(feed), 1)
    row = QHBoxLayout()
    entry = QLineEdit()
    entry.setPlaceholderText("Write to the lead")
    entry.setEnabled(False)
    send = QPushButton("Send")
    send.setEnabled(False)
    send.setFixedWidth(80)
    tip = "Chat with the lead comes in phase P5b"
    entry.setToolTip(tip)
    send.setToolTip(tip)
    row.addWidget(entry, 1)
    row.addWidget(send)
    lines.addLayout(row)
    return box


_RESULT_COLOURS = {"ok": "GREEN", "failed": "RED", "error": "RED", "running": "YELLOW"}


def runs_box(rows: Sequence[RunRow]) -> QWidget:
    """Today's runs: ET time, run name (with the event count) and a coloured result."""
    box = QWidget()
    grid = QGridLayout(box)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    if not rows:
        grid.addWidget(muted(NO_RUNS), 0, 0)
    for r, run in enumerate(rows):
        name = f"{run.name} (×{run.count})" if run.count > 1 else run.name
        colour = getattr(C, _RESULT_COLOURS.get(run.result, "SUBTEXT"))
        result = QLabel(run.result)
        result.setObjectName("run_result")
        result.setStyleSheet(f"color: {colour}; border: 1px solid {colour};"
                             " border-radius: 8px; padding: 0 8px;")
        when = QLabel(run.when.strftime("%H:%M ET"))
        when.setStyleSheet(f"color: {C.MUTED};")
        grid.addWidget(when, r, 0)
        grid.addWidget(QLabel(name), r, 1)
        grid.addWidget(result, r, 2, Qt.AlignmentFlag.AlignRight)
    grid.setColumnStretch(1, 1)
    grid.setRowStretch(max(len(rows), 1), 1)
    return box


def team_line(counts: dict[str, int]) -> QLabel:
    """The Team now line, e.g. ``Team now: 8 active · 1 shadow``; hidden with no employees."""
    label = muted("Team now: " + " · ".join(f"{n} {s}" for s, n in counts.items()))
    label.setObjectName("team_now")
    if not counts:
        label.hide()
    return label


def command_frame(name: str, approvals: QWidget | None = None, chat: QWidget | None = None,
                  runs: QWidget | None = None, team: QWidget | None = None) -> QWidget:
    """Build the Command home: lead chat, approvals waiting, today's runs and the team line.

    Without real widgets the samples show with the Sample tag.
    """
    frame, body = section_frame(name, sample=runs is None)
    row = QHBoxLayout()
    row.setSpacing(12)
    row.addWidget(chat or _chat_frame(), 3)
    right = QVBoxLayout()
    right.addWidget(scroll_of(approvals or muted("No approvals")), 3)
    right.addWidget(heading("Today's runs"))
    right.addWidget(runs or make_table(S.RUN_COLUMNS, S.RUNS), 2)
    if team is not None:
        right.addWidget(team)
    row.addLayout(right, 2)
    body.addLayout(row, 1)
    return frame


def _fill_tree(parent: QTreeWidgetItem, node: S.OrgNode) -> None:
    item = QTreeWidgetItem(parent, [node.name, node.role, node.state])
    for kid in node.children:
        _fill_tree(item, kid)


def org_frame(name: str) -> QWidget:
    """Build the org chart tree and the seats strip."""
    frame, body = section_frame(name)
    used = S.seats_used()
    strip = " · ".join(f"{k} {used[k]} of {S.SEAT_CAPS[k]}" for k in S.SEAT_CAPS)
    seats = QLabel(strip)
    seats.setObjectName("seats_strip")
    body.addWidget(seats)
    tree = QTreeWidget()
    tree.setHeaderLabels(["Employee", "Role", "State"])
    tree.setColumnWidth(0, 260)
    tree.setColumnWidth(1, 260)
    root = QTreeWidgetItem(tree, [S.ORG_TREE.name, S.ORG_TREE.role, S.ORG_TREE.state])
    for kid in S.ORG_TREE.children:
        _fill_tree(root, kid)
    tree.expandToDepth(3)
    body.addWidget(tree, 1)
    return frame


def _profile_text(row: Sequence[str]) -> str:
    return "\n".join(f"{h}: {v}" for h, v in zip(S.EMPLOYEE_COLUMNS, row, strict=False))


def employees_frame(name: str) -> QWidget:
    """Build the employee table with Profile and Job tabs."""
    frame, body = section_frame(name)
    table = make_table(S.EMPLOYEE_COLUMNS, S.EMPLOYEES)
    body.addWidget(table, 3)
    tabs = QTabWidget()
    profile = read_only_text(_profile_text(S.EMPLOYEES[0]), mono=False)
    tabs.addTab(profile, "Profile")
    job = QWidget()
    cols = QHBoxLayout(job)
    cols.addWidget(read_only_text(S.SOUL_TEXT), 1)
    cols.addWidget(read_only_text(S.JOB_YAML), 1)
    wrap = QWidget()
    stack = QVBoxLayout(wrap)
    stack.setContentsMargins(0, 0, 0, 0)
    stack.addWidget(muted("soul.md and job.yaml. The lead drafts changes; the Master approves."))
    stack.addWidget(job, 1)
    tabs.addTab(wrap, "Job")
    body.addWidget(tabs, 3)

    def show_profile(row: int, _col: int) -> None:
        profile.setPlainText(_profile_text(S.EMPLOYEES[row]))

    # table → cellClicked → frame → show_profile
    table.cellClicked.connect(show_profile)
    return frame


