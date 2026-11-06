"""
Module: MD-GUI-034.009.M08 — AI Desk sections (Task board to Studio)
Parent SRD: SRD-GUI-034.009

Frames only: sample content, no real data and no actions.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QVBoxLayout, QWidget

from us_swing.gui import ai_desk_sample as S
from us_swing.gui.ai_desk_sections import (
    heading,
    make_table,
    muted,
    read_only_text,
    section_frame,
    tile,
)


def tasks_frame(name: str) -> QWidget:
    """Build the kanban board with Queued, Running, Done and Failed columns."""
    frame, body = section_frame(name)
    cols = QHBoxLayout()
    cols.setSpacing(8)
    for column in S.TASK_COLUMNS:
        col = QVBoxLayout()
        col.addWidget(heading(column))
        for task in S.TASKS:
            if task.column == column:
                detail = f"{task.employee} · {task.priority} · due {task.deadline}"
                col.addWidget(tile(task.title, detail))
        col.addStretch(1)
        cols.addLayout(col, 1)
    body.addLayout(cols, 1)
    return frame


def activity_frame(name: str) -> QWidget:
    """Build the trace table with the input and output of the selected row."""
    frame, body = section_frame(name)
    table = make_table(S.TRACE_COLUMNS, S.TRACE)
    body.addWidget(table, 3)
    body.addWidget(heading("Input and output"))
    detail = read_only_text(S.TRACE_DETAIL)
    body.addWidget(detail, 2)

    def show_row(row: int, _col: int) -> None:
        step = S.TRACE[row][2]
        detail.setPlainText(f"Step: {step}\n\n{S.TRACE_DETAIL}")

    # table → cellClicked → frame → show_row
    table.cellClicked.connect(show_row)
    return frame


def schedule_frame(name: str) -> QWidget:
    """Build the timers and events table."""
    frame, body = section_frame(name)
    body.addWidget(muted("Agents sleep until an event or timer wakes them"))
    body.addWidget(make_table(S.SCHEDULE_COLUMNS, S.SCHEDULE), 1)
    body.addWidget(muted("Evening run 16:25 New York time (02:55 IST in winter)"))
    return frame


def studio_frame(name: str) -> QWidget:
    """Build the AI page list and the preview placeholder."""
    frame, body = section_frame(name)
    row = QHBoxLayout()
    row.setSpacing(12)
    left = QVBoxLayout()
    left.addWidget(heading("AI pages"))
    left.addWidget(make_table(S.STUDIO_COLUMNS, S.STUDIO), 1)
    row.addLayout(left, 2)
    preview = tile("Preview", "Sealed web view comes in phase P5d")
    inner = QVBoxLayout()
    inner.addWidget(preview)
    inner.addStretch(1)
    row.addLayout(inner, 3)
    body.addLayout(row, 1)
    return frame


def page_list(names: list[str]) -> QListWidget:
    """Return a plain list of ``names`` (used by Reports)."""
    box = QListWidget()
    box.setStyleSheet("QListWidget { outline: none; }")
    box.addItems(names)
    return box
