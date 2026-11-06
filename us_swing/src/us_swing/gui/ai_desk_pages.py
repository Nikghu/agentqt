"""
Module: MD-GUI-034.022.M19 — gui/ai_desk_pages.py
Parent SRD: SRD-GUI-034.022
Also: SRD-GUI-034.023 (sealed preview of the chosen version), SRD-GUI-034.026 (empty note)

The AI Desk "Pages" section: every report page version from ``desk.db`` on the left
and a view-only sealed preview of the chosen version on the right.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from us_swing.core.desk_floor import DeskFloorData
from us_swing.gui.ai_desk_sections import heading, make_table, muted, section_frame
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
        body.addWidget(muted(EMPTY_NOTE))
        body.addStretch(1)
        return frame
    row = QHBoxLayout()
    row.setSpacing(12)
    left = QVBoxLayout()
    left.addWidget(heading("Report pages"))
    table = make_table(COLUMNS, [(p.day, str(p.version), p.title, p.saved) for p in pages])
    table.setObjectName("pages_table")
    left.addWidget(table, 1)
    row.addLayout(left, 2)
    preview = make_preview()
    preview.setObjectName("pages_preview")
    row.addWidget(preview, 3)
    body.addLayout(row, 1)

    def show_row(index: int, *_: int) -> None:
        if not 0 <= index < len(pages):
            return
        page = data.report_page(pages[index].page_id)
        if page is not None:
            title, html = page
            preview.show_page(html, title)  # type: ignore[attr-defined]

    # table → currentCellChanged (mouse or arrow keys) → frame → show_row
    table.currentCellChanged.connect(show_row)
    table.setCurrentCell(0, 0)
    return frame
