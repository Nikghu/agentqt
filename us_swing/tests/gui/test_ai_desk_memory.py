"""Tests for MD-GUI-037.001.M01 (AI Desk Memory section)."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QLabel, QTableWidget, QWidget
from pytestqt.qtbot import QtBot

from tests.desk.test_desk_lessons import NOW, PULL, _active, _base, _rows
from us_swing.core.desk_lessons import add_candidate, add_edit, apply_edits
from us_swing.gui.ai_desk_memory import NO_LESSONS, PENDING, MemoryView

_ALIVE: list[QWidget] = []


def _view(qtbot: QtBot, home: Path, ask: bool = True) -> MemoryView:
    view = MemoryView("Memory", home, lambda: NOW, lambda *_a: ask)
    qtbot.addWidget(view)
    _ALIVE.append(view)
    return view


def _cells(table: QTableWidget) -> list[list[str]]:
    return [[table.item(r, c).text() if table.item(r, c) else ""  # type: ignore[union-attr]
             for c in range(table.columnCount())] for r in range(table.rowCount())]


def test_memory_section(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.001.M01.T01: Memory comes after Cards (after Results) in the review group and is live."""
    from us_swing.gui.ai_desk import _LIVE_SECTIONS, GROUPS, AiDeskWorkspace
    from us_swing.gui.desk_control import DeskPoller as Poller

    review = dict(GROUPS)["REVIEW"]
    assert review.index("Memory") == review.index("Cards") + 1 and "Memory" in _LIVE_SECTIONS
    page = AiDeskWorkspace(Poller(tmp_path))
    qtbot.addWidget(page)
    page.select_section("Memory")
    assert NO_LESSONS in [x.text() for x in page.findChildren(QLabel)]


def test_no_lessons_yet(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.001.M01.T02: With no lessons the note shows and the buttons are off."""
    view = _view(qtbot, tmp_path)
    assert not view.empty.isHidden() and view.table.isHidden()
    assert not any(b.isEnabled() for b in view.buttons.values())


def test_lessons_table(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.002.M01.T01: Active lessons show; the filter shows candidates and retired."""
    _active(tmp_path, "Long picks need care", {"side": "long"})
    add_candidate(tmp_path, "Pullbacks fail", PULL, "worse", [], NOW)
    gone = _active(tmp_path, "Old one", {"side": "short"})
    add_edit(tmp_path, gone, "retire", NOW)
    apply_edits(tmp_path, NOW)
    view = _view(qtbot, tmp_path)
    rows = _cells(view.table)
    assert len(rows) == 1 and rows[0][0] == "active" and rows[0][2] == "Long picks need care"
    assert rows[0][3] == "side long" and rows[0][4] == "5"
    view.filter.setCurrentText("Candidate")
    assert [r[2] for r in _cells(view.table)] == ["Pullbacks fail"]
    view.filter.setCurrentText("Retired")
    assert [r[2] for r in _cells(view.table)] == ["Old one"]


def test_no_desk_data(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.002.M01.T02: With no desk.db the table is empty and nothing fails."""
    view = _view(qtbot, tmp_path / "missing")
    assert view.table.rowCount() == 0 and not (tmp_path / "missing" / "desk.db").exists()


def test_pin_adds_an_edit(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.003.M01.T01: Pin adds one edit and the status says it applies at the tick."""
    lid = _active(tmp_path, "Long picks need care", {"side": "long"})
    view = _view(qtbot, tmp_path)
    view.table.selectRow(0)
    view.buttons["pin"].click()
    assert _rows(tmp_path, "SELECT lesson_id, action FROM lesson_edits") == [(lid, "pin")]
    assert _cells(view.table)[0][0] == PENDING


def test_delete_cancelled(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.003.M01.T02: Answering No to Delete adds no edit."""
    _active(tmp_path, "Long picks need care", {"side": "long"})
    view = _view(qtbot, tmp_path, ask=False)
    view.table.selectRow(0)
    view.buttons["delete"].click()
    assert _rows(tmp_path, "SELECT COUNT(*) FROM lesson_edits") == [(0,)]


def test_proof_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.004.M01.T01: Choosing a lesson lists its 5 proof picks with R."""
    keys = _base(tmp_path)
    add_candidate(tmp_path, "Pullbacks fail", PULL, "worse", keys[:5], NOW)
    view = _view(qtbot, tmp_path)
    view.table.selectRow(0)
    rows = _cells(view.proof)
    assert len(rows) == 5 and rows[0][1:] == ["long", "P0", "-1.00"]
