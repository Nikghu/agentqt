"""
Module: MD-GUI-034.009.M08 — AI Desk sections (Reports to Desk settings)
Parent SRD: SRD-GUI-034.009

Frames only: sample content, no real data and no actions.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from us_swing.gui import ai_desk_sample as S
from us_swing.gui.ai_desk_sections import (
    heading,
    make_table,
    muted,
    read_only_text,
    section_frame,
)
from us_swing.gui.ai_desk_sections2 import page_list


def reports_frame(name: str) -> QWidget:
    """Build the report list and the text of the selected report."""
    frame, body = section_frame(name)
    row = QHBoxLayout()
    row.setSpacing(12)
    names = list(S.REPORTS)
    listing = page_list(names)
    text = read_only_text(S.REPORTS[names[0]], mono=False)
    row.addWidget(listing, 1)
    row.addWidget(text, 3)
    body.addLayout(row, 1)

    def show(index: int) -> None:
        if index >= 0:
            text.setPlainText(S.REPORTS[names[index]])

    # list → currentRowChanged → frame → show
    listing.currentRowChanged.connect(show)
    listing.setCurrentRow(0)
    return frame


def cost_frame(name: str) -> QWidget:
    """Build the budget bar and the cost tables by employee and by model."""
    frame, body = section_frame(name)
    left = S.MONTHLY_BUDGET - S.SPENT
    body.addWidget(QLabel(
        f"Budget USD {S.MONTHLY_BUDGET:.2f} per month · spent USD {S.SPENT:.2f}"
        f" · remaining USD {left:.2f}"
    ))
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(round(100 * S.SPENT / S.MONTHLY_BUDGET))
    body.addWidget(bar)
    row = QHBoxLayout()
    row.setSpacing(12)
    for title, cols, rows in (
        ("By employee", S.COST_EMPLOYEE_COLUMNS, S.COST_EMPLOYEE),
        ("By model", S.COST_MODEL_COLUMNS, S.COST_MODEL),
    ):
        col = QVBoxLayout()
        col.addWidget(heading(title))
        col.addWidget(make_table(cols, rows), 1)
        row.addLayout(col, 1)
    body.addLayout(row, 1)
    body.addWidget(muted("Cheap models while testing"))
    return frame


def settings_frame(name: str) -> QWidget:
    """Build the read-only form of desk settings."""
    frame, body = section_frame(name)
    form = QFormLayout()
    caps = " · ".join(f"{k} {v}" for k, v in S.SEAT_CAPS.items())
    form.addRow("Seat caps", QLabel(caps))
    form.addRow("Monthly budget", QLabel(f"USD {S.MONTHLY_BUDGET:.2f}"))
    form.addRow("Trade approval", QLabel("Master approves every trade"))
    form.addRow("LLM sources", QLabel("\n".join(S.LLM_SOURCES)))
    form.addRow("Evening run", QLabel(f"{S.EVENING_RUN_ET} New York time (02:55 IST in winter)"))
    form.addRow("Data folder", QLabel(S.DATA_FOLDER))
    body.addLayout(form)
    body.addWidget(muted("Editing comes in phase P6"))
    body.addStretch(1)
    return frame
