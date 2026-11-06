"""
Module: MD-GUI-034.009.M08 — AI Desk sections (Command to Hiring)
Parent SRD: SRD-GUI-034.009

Frames only: sample content, no real data and no actions. Shared helpers live here too.
"""
from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtWidgets import (
    QFrame,
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
from us_swing.gui import ai_desk_sample as S
from us_swing.gui.floor_panel import table_body
from us_swing.gui.floor_sample import SAMPLE_TAG
from us_swing.gui.theme import C

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
    lines.addWidget(heading("HELM chat"))
    feed = QWidget()
    msgs = QVBoxLayout(feed)
    msgs.setSpacing(6)
    for who, text in S.CHAT:
        colour = C.BLUE if who == "HELM" else C.GREEN
        label = QLabel(f"<b style='color:{colour}'>{who}</b><br>{text}")
        label.setWordWrap(True)
        msgs.addWidget(label)
    msgs.addStretch(1)
    lines.addWidget(scroll_of(feed), 1)
    row = QHBoxLayout()
    entry = QLineEdit()
    entry.setPlaceholderText("Write to HELM")
    entry.setEnabled(False)
    send = QPushButton("Send")
    send.setEnabled(False)
    send.setFixedWidth(80)
    tip = "Chat comes with HELM in phase P5b"
    entry.setToolTip(tip)
    send.setToolTip(tip)
    row.addWidget(entry, 1)
    row.addWidget(send)
    lines.addLayout(row)
    return box


def _approvals_frame() -> QWidget:
    box = QWidget()
    lines = QVBoxLayout(box)
    lines.setContentsMargins(0, 0, 0, 0)
    lines.addWidget(heading("Approvals waiting"))
    for item in S.APPROVALS:
        lines.addWidget(tile(item.title, item.detail, item.kind))
        row = QHBoxLayout()
        row.addStretch(1)
        for label in ("Approve", "Reject"):
            btn = QPushButton(label)
            btn.setEnabled(False)
            btn.setFixedWidth(80)
            btn.setToolTip("Approvals come with HELM in phase P5b")
            row.addWidget(btn)
        lines.addLayout(row)
    lines.addStretch(1)
    return box


def command_frame(name: str) -> QWidget:
    """Build the Command home: HELM chat, approvals waiting and today's runs."""
    frame, body = section_frame(name)
    row = QHBoxLayout()
    row.setSpacing(12)
    row.addWidget(_chat_frame(), 3)
    right = QVBoxLayout()
    right.addWidget(scroll_of(_approvals_frame()), 3)
    right.addWidget(heading("Today's runs"))
    right.addWidget(make_table(S.RUN_COLUMNS, S.RUNS), 2)
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
    stack.addWidget(muted("soul.md and job.yaml. HELM drafts changes; the Master approves."))
    stack.addWidget(job, 1)
    tabs.addTab(wrap, "Job")
    body.addWidget(tabs, 3)

    def show_profile(row: int, _col: int) -> None:
        profile.setPlainText(_profile_text(S.EMPLOYEES[row]))

    # table → cellClicked → frame → show_profile
    table.cellClicked.connect(show_profile)
    return frame


def hiring_frame(name: str) -> QWidget:
    """Build the hiring pipeline columns with sample candidates."""
    frame, body = section_frame(name)
    cols = QHBoxLayout()
    cols.setSpacing(8)
    for index, stage in enumerate(S.HIRING_STAGES):
        col = QVBoxLayout()
        col.addWidget(heading(stage))
        for cand in S.CANDIDATES:
            if cand.stage == index:
                col.addWidget(tile(cand.name, cand.note))
        col.addStretch(1)
        cols.addLayout(col, 1)
    body.addLayout(cols, 1)
    body.addWidget(muted("The Master approves twice: before the shadow trial and after it."))
    return frame
