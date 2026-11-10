"""Tests for MD-GUI-034.022.M19 — gui/ai_desk_pages.py and the page reader in core/desk_floor.py."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QLabel, QTableWidget, QWidget
from pytestqt.qtbot import QtBot

from us_swing.core.desk_floor import DeskFloorData
from us_swing.gui.ai_desk import SECTIONS
from us_swing.gui.ai_desk_pages import EMPTY_NOTE, pages_frame
from us_swing.gui.ai_desk_sections3 import _NoFallback
from us_swing.market.store import MarketStore


class _FakePreview(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.shown: list[tuple[str, str]] = []

    def show_page(self, body: str, title: str) -> None:
        self.shown.append((title, body))


def _seed(home: Path) -> None:
    store = MarketStore(home)
    try:
        store.add_page("2026-11-05", "Day one", "<p>one</p>", "2026-11-05T21:30:00+00:00")
        store.add_page("2026-11-06", "Day two", "<p>two</p>", "2026-11-06T21:30:00+00:00")
        store.add_page("2026-11-06", "Day two again", "<p onclick=\"x()\">three</p>",
                       "2026-11-06T22:00:00+00:00")
    finally:
        store.close()


def _frame(qtbot: QtBot, home: Path, previews: list[_FakePreview]) -> QWidget:
    def make() -> QWidget:
        previews.append(_FakePreview())
        return previews[-1]

    frame = pages_frame("Pages", home, make)
    qtbot.addWidget(frame)
    return frame


def test_page_reader(tmp_path: Path) -> None:
    """UT-GUI-034.022.M19.T01: versions come newest day and newest version first; html by id."""
    _seed(tmp_path)
    data = DeskFloorData(_NoFallback(), tmp_path)
    pages = data.report_pages()
    assert [(p.day, p.version, p.title) for p in pages] == [
        ("2026-11-06", 2, "Day two again"), ("2026-11-06", 1, "Day two"),
        ("2026-11-05", 1, "Day one")]
    assert pages[1].saved == "2026-11-06 16:30"
    assert data.report_page(pages[2].page_id) == ("Day one", "<p>one</p>")


def test_page_reader_without_table(tmp_path: Path) -> None:
    """UT-GUI-034.022.M19.T02: no desk.db or no canvas_pages gives no pages and no error."""
    assert DeskFloorData(_NoFallback(), tmp_path / "none").report_pages() == []
    (tmp_path / "desk.db").write_bytes(b"")
    data = DeskFloorData(_NoFallback(), tmp_path)
    assert data.report_pages() == [] and data.report_page(1) is None


def test_section_renamed() -> None:
    """UT-GUI-034.022.M19.T03: Pages sits where Studio was; Studio is gone. The WORK group
    left with SRD-GUI-035.001, so Pages now follows Hiring."""
    assert "Studio" not in SECTIONS
    assert SECTIONS.index("Pages") == SECTIONS.index("Hiring") + 1


def test_version_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.022.M19.T04: the table lists every version with day, version, title, time."""
    _seed(tmp_path)
    frame = _frame(qtbot, tmp_path, [])
    table = frame.findChild(QTableWidget, "pages_table")
    assert table is not None and table.rowCount() == 3
    row = [table.item(0, c).text() for c in range(4)]  # type: ignore[union-attr]
    assert row == ["2026-11-06", "2", "Day two again", "2026-11-06 17:00"]


def test_preview_follows_row(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.023.M19.T01: the first row shows at once; moving the row shows that version."""
    _seed(tmp_path)
    previews: list[_FakePreview] = []
    frame = _frame(qtbot, tmp_path, previews)
    (preview,) = previews
    assert preview.shown == [("Day two again", "<p onclick=\"x()\">three</p>")]
    table = frame.findChild(QTableWidget, "pages_table")
    assert table is not None
    table.setCurrentCell(1, 0)
    assert preview.shown[-1] == ("Day two", "<p>two</p>")


def test_empty_note(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.026.M19.T01: no pages shows the note and builds no preview."""
    previews: list[_FakePreview] = []
    frame = _frame(qtbot, tmp_path, previews)
    assert previews == []
    assert EMPTY_NOTE in [w.text() for w in frame.findChildren(QLabel)]
    assert frame.findChild(QTableWidget, "pages_table") is None
