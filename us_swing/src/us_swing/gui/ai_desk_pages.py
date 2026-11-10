"""
Module: MD-GUI-034.022.M19 — gui/ai_desk_pages.py
Parent SRD: SRD-GUI-034.022
Also: SRD-GUI-034.023 (sealed preview of the chosen version), SRD-GUI-034.026 (empty note)
Also: SRD-GUI-034.066 — list and preview in icon cards (console look)

The AI Desk "Pages" section: every report page version from ``desk.db`` on the left
and a view-only sealed preview of the chosen version on the right.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from us_swing.core.desk_floor import DeskFloorData
from us_swing.gui.ai_desk_console import icon_card
from us_swing.gui.ai_desk_sections import make_table, muted, section_frame
from us_swing.gui.ai_desk_sections3 import _NoFallback

COLUMNS = ("Day", "Version", "Title", "Saved (NY)")
EMPTY_NOTE = "No report page yet. The first page comes after an evening run with a lead brief"


def _sealed_view() -> QWidget:
    from us_swing.gui.sealed_view import SealedView  # QtWebEngine loads only when needed

    return SealedView()


def pages_frame(name: str, home: Path | None = None,
                make_preview: Callable[[], QWidget] = _sealed_view) -> QWidget:
    """Build the page version list and its sealed preview; a note when there is no page."""
    data = DeskFloorData(_NoFallback(), home)
    pages = data.report_pages()
    frame, body = section_frame(name, sample=False)
    if not pages:
        empty, empty_body = icon_card("list", "Report pages")
        empty_body.addWidget(muted(EMPTY_NOTE))
        body.addWidget(empty)
        body.addStretch(1)
        return frame
    row = QHBoxLayout()
    row.setSpacing(12)
    left, left_body = icon_card("list", f"Report pages · {len(pages)} versions")
    table = make_table(COLUMNS, [(p.day, str(p.version), p.title, p.saved) for p in pages])
    table.setObjectName("pages_table")
    left_body.addWidget(table, 1)
    row.addWidget(left, 2)
    right, right_body = icon_card("eye", "Preview")
    preview_title = right.findChild(QLabel, "card_title")
    preview = make_preview()
    preview.setObjectName("pages_preview")
    right_body.addWidget(preview, 1)
    row.addWidget(right, 3)
    body.addLayout(row, 1)

    def show_row(index: int, *_: int) -> None:
        if not 0 <= index < len(pages):
            return
        page = data.report_page(pages[index].page_id)
        if page is not None:
            title, html = page
            preview.show_page(html, title)  # type: ignore[attr-defined]
            if preview_title is not None:
                preview_title.setText(title)

    # table → currentCellChanged (mouse or arrow keys) → frame → show_row
    table.currentCellChanged.connect(show_row)
    table.setCurrentCell(0, 0)
    return frame
