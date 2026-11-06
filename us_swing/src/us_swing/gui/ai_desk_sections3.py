"""
Module: MD-GUI-034.009.M08 — AI Desk sections (Reports to Desk settings)
Parent SRD: SRD-GUI-034.009
Also: MD-GUI-034.016.M15 — editable desk AI settings (SRD-GUI-034.016)
Also: MD-GUI-034.017.M16 — real month cost (SRD-GUI-034.017)

Reports is sample content. Cost & budget shows the real month once the desk has used AI;
Desk settings has the editable desk AI settings.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from us_swing.core.desk_contract import ProductDescriptor
from us_swing.core.desk_floor import DeskFloorData
from us_swing.gui.ai_desk_settings import DeskAiSettingsForm

from us_swing.gui import ai_desk_sample as S
from us_swing.gui.ai_desk_sections import (
    heading,
    make_table,
    muted,
    read_only_text,
    section_frame,
)
from us_swing.gui.ai_desk_sections2 import page_list


_REAL_COLUMNS = (("Employee", "Tries", "Tokens", "Cost"), ("Model", "Tries", "Tokens", "Cost"))


class _NoFallback:
    """Fallback for reading cost only; the AI Desk has no Floor products."""

    def products(self) -> list[ProductDescriptor]:
        return []

    def rows(self, product_id: str, filters: Mapping[str, str]) -> list[dict[str, Any]]:
        return []


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


def cost_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the budget bar and the cost tables; sample figures until the desk used AI."""
    real = DeskFloorData(_NoFallback(), home).month_cost()
    frame, body = section_frame(name, sample=real is None)
    budget, spent = (real.budget_usd, real.spent_usd) if real else (S.MONTHLY_BUDGET, S.SPENT)
    body.addWidget(QLabel(
        f"API budget USD {budget:.2f} per month · spent USD {spent:.2f}"
        f" · remaining USD {budget - spent:.2f}"
    ))
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(min(100, round(100 * spent / budget)))
    body.addWidget(bar)
    row = QHBoxLayout()
    row.setSpacing(12)
    tables: tuple[tuple[str, Sequence[str], Sequence[Sequence[str]]], ...] = (
        (("By employee", _REAL_COLUMNS[0], real.by_employee),
         ("By model", _REAL_COLUMNS[1], real.by_model)) if real else
        (("By employee", S.COST_EMPLOYEE_COLUMNS, S.COST_EMPLOYEE),
         ("By model", S.COST_MODEL_COLUMNS, S.COST_MODEL)))
    for title, cols, rows in tables:
        col = QVBoxLayout()
        col.addWidget(heading(title))
        col.addWidget(make_table(cols, rows), 1)
        row.addLayout(col, 1)
    body.addLayout(row, 1)
    body.addWidget(muted("Claude Code CLI runs on the subscription: tokens only, cost 0"))
    return frame


def settings_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the desk settings: read-only desk facts and the editable desk AI form."""
    frame, body = section_frame(name, sample=False)
    form = QFormLayout()
    caps = " · ".join(f"{k} {v}" for k, v in S.SEAT_CAPS.items())
    form.addRow("Seat caps", QLabel(caps))
    form.addRow("Trade approval", QLabel("Master approves every trade"))
    form.addRow("Evening run", QLabel(f"{S.EVENING_RUN_ET} New York time (02:55 IST in winter)"))
    form.addRow("Data folder", QLabel(S.DATA_FOLDER))
    body.addLayout(form)
    body.addWidget(heading("Desk AI"))
    body.addWidget(DeskAiSettingsForm(home))
    body.addWidget(muted("Seat caps and other settings become editable in phase P6"))
    body.addStretch(1)
    return frame
