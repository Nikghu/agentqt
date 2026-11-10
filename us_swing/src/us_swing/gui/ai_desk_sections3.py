"""
Module: MD-GUI-034.009.M08 — AI Desk sections (Reports to Desk settings)
Parent SRD: SRD-GUI-034.009
Also: MD-GUI-034.016.M15 — editable desk AI settings (SRD-GUI-034.016)
Also: MD-GUI-034.017.M16 — real month cost (SRD-GUI-034.017)
Also: MD-GUI-034.032.M22 — weekly reports (SRD-GUI-034.032)
Also: SRD-GUI-034.066 — tiles and icon cards (console look) for Reports, Cost and Settings

Reports shows the desk's weekly reports (sample reports until the first one). Cost & budget shows the real month once the desk has used AI;
Desk settings has the editable desk AI settings.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QWidget

from us_swing.core.desk_contract import ProductDescriptor
from us_swing.core.desk_floor import DeskFloorData
from us_swing.gui.ai_desk_console import icon_card, thin_bar, tile_row
from us_swing.gui.ai_desk_settings import DeskAiSettingsForm

from us_swing.gui import ai_desk_sample as S
from us_swing.gui.ai_desk_sections import make_table, muted, read_only_text, section_frame
from us_swing.gui.ai_desk_sections2 import page_list
from us_swing.gui.theme import C


_REAL_COLUMNS = (("Employee", "Tries", "Tokens", "Cost"), ("Model", "Tries", "Tokens", "Cost"))


class _NoFallback:
    """Fallback for reading cost only; the AI Desk has no Floor products."""

    def products(self) -> list[ProductDescriptor]:
        return []

    def rows(self, product_id: str, filters: Mapping[str, str]) -> list[dict[str, Any]]:
        return []


def reports_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the report list and the text of the selected report.

    Weekly reports from the desk when there are any (SRD-GUI-034.032), else sample reports.
    """
    real = DeskFloorData(_NoFallback(), home).weekly_reports()
    reports = dict(real) if real else dict(S.REPORTS)
    frame, body = section_frame(name, sample=not real)
    row = QHBoxLayout()
    row.setSpacing(12)
    names = list(reports)
    left, left_body = icon_card("scroll-text", "Weekly reports")
    listing = page_list(names)
    left_body.addWidget(listing, 1)
    right, right_body = icon_card("eye", names[0])
    reader_title = right.findChild(QLabel, "card_title")
    text = read_only_text(reports[names[0]], mono=bool(real))
    right_body.addWidget(text, 1)
    row.addWidget(left, 1)
    row.addWidget(right, 3)
    body.addLayout(row, 1)

    def show(index: int) -> None:
        if index >= 0:
            text.setPlainText(reports[names[index]])
            if reader_title is not None:
                reader_title.setText(names[index])

    # list → currentRowChanged → frame → show
    listing.currentRowChanged.connect(show)
    listing.setCurrentRow(0)
    return frame


def cost_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the budget bar and the cost tables; sample figures until the desk used AI."""
    real = DeskFloorData(_NoFallback(), home).month_cost()
    frame, body = section_frame(name, sample=real is None)
    budget, spent = (real.budget_usd, real.spent_usd) if real else (S.MONTHLY_BUDGET, S.SPENT)
    tiles, values = tile_row((("Monthly budget", f"${budget:.2f}"),
                              ("Spent this month", f"${spent:.2f}"),
                              ("Remaining", f"${budget - spent:.2f}")))
    left_tone = C.GREEN if spent <= budget else C.RED
    values[2].setStyleSheet(f"{values[2].styleSheet()} color: {left_tone};")
    body.addLayout(tiles)
    share = min(100, round(100 * spent / budget)) if budget > 0 else 0
    used = QLabel(f"{share}%")
    used.setStyleSheet("background: transparent; border: none;")
    gauge, gauge_body = icon_card("chart-line", "Budget used", side=used)
    gauge_body.addWidget(thin_bar(share))
    body.addWidget(gauge)
    row = QHBoxLayout()
    row.setSpacing(12)
    tables: tuple[tuple[str, Sequence[str], Sequence[Sequence[str]]], ...] = (
        (("By employee", _REAL_COLUMNS[0], real.by_employee),
         ("By model", _REAL_COLUMNS[1], real.by_model)) if real else
        (("By employee", S.COST_EMPLOYEE_COLUMNS, S.COST_EMPLOYEE),
         ("By model", S.COST_MODEL_COLUMNS, S.COST_MODEL)))
    for (title, cols, rows), icon_name in zip(tables, ("users", "zap"), strict=True):
        box, box_body = icon_card(icon_name, title)
        box_body.addWidget(make_table(cols, rows), 1)
        row.addWidget(box, 1)
    body.addLayout(row, 1)
    body.addWidget(muted("Claude Code CLI runs on the subscription: tokens only, cost 0"))
    return frame


def settings_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the desk settings: read-only desk facts and the editable desk AI form."""
    frame, body = section_frame(name, sample=False)
    facts, facts_body = icon_card("calendar", "Schedule and rules")
    form = QFormLayout()
    form.setHorizontalSpacing(16)
    caps = " · ".join(f"{k} {v}" for k, v in S.SEAT_CAPS.items())
    form.addRow("Seat caps", QLabel(caps))
    form.addRow("Trade approval", QLabel("Master approves every trade"))
    form.addRow("Morning run", QLabel("From 04:00 New York time on trading days, while the app is open"))
    form.addRow("Data folder", QLabel(S.DATA_FOLDER))
    facts_body.addLayout(form)
    body.addWidget(facts)
    body.addWidget(DeskAiSettingsForm(home))
    body.addWidget(muted("Seat caps and other settings become editable in phase P6"))
    body.addStretch(1)
    return frame
