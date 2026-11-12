"""Tests for MD-GUI-039.001.M01 (AI Desk Research section, step E)."""
from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QTableWidget, QWidget
from pytestqt.qtbot import QtBot

from tests.desk.research_support import NOW, add_try, ask, execute, rows, team
from us_swing.core.desk_research import raise_tickets
from us_swing.gui.ai_desk_research import NO_TICKETS, PENDING, ResearchView

_ALIVE: list[QWidget] = []


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "desk"
    team(h)
    return h


def _view(qtbot: QtBot, home: Path) -> ResearchView:
    view = ResearchView("Research", home, lambda: NOW)
    qtbot.addWidget(view)
    _ALIVE.append(view)
    return view


def _cells(table: QTableWidget) -> list[list[str]]:
    return [[table.item(r, c).text() if table.item(r, c) else ""  # type: ignore[union-attr]
             for c in range(table.columnCount())] for r in range(table.rowCount())]


def _raise(home: Path, *caps: int) -> None:
    raise_tickets(home, "fake_lead", [ask(cap=c, goal=f"Goal number {i} to test")
                                      for i, c in enumerate(caps)], NOW, lambda _t: True)


def _select(view: ResearchView, goal: str) -> None:
    for r in range(view.table.rowCount()):
        item = view.table.item(r, 2)
        if item is not None and item.text() == goal:
            view.table.selectRow(r)
            return
    raise AssertionError(goal)


def test_ticket_list(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-039.001.M01.T01: Columns show; order waiting, running, approved, ended."""
    _raise(home, 5_000, 30_000, 5_000)
    execute(home, "UPDATE tickets SET status = 'running' WHERE id = 3")
    raise_tickets(home, "fake_lead", [ask(goal="An ended goal to test")],
                  NOW + timedelta(days=1), lambda _t: True)
    execute(home, "UPDATE tickets SET status = 'done', ended = ? WHERE id = 4",
            (NOW.isoformat(),))
    view = _view(qtbot, home)
    cells = _cells(view.table)
    assert [view.table.horizontalHeaderItem(c).text()  # type: ignore[union-attr]
            for c in range(7)] == ["Status", "Kind", "Goal", "Cap", "Spent", "Raised by", "Made"]
    assert [c[0] for c in cells] == ["waiting", "running", "approved", "done"]
    assert cells[0][1:6] == ["setup tuning", "Goal number 1 to test", "30,000", "0", "Lead A"]


def test_old_and_none(qtbot: QtBot, tmp_path: Path, home: Path) -> None:
    """UT-GUI-039.001.M01.T02: Tickets ended 8 days ago are hidden; no desk.db shows the note."""
    _raise(home, 5_000)
    execute(home, "UPDATE tickets SET status = 'done', ended = ?",
            ((NOW - timedelta(days=8)).isoformat(),))
    assert _view(qtbot, home).table.rowCount() == 0
    empty = _view(qtbot, tmp_path / "none")
    assert not empty.empty.isHidden() and empty.empty.text() == NO_TICKETS


def test_approve(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-039.002.M01.T01: Approve writes one edit and shows it as pending."""
    _raise(home, 30_000)
    view = _view(qtbot, home)
    _select(view, "Goal number 0 to test")
    view.buttons["approve"].click()
    assert rows(home, "SELECT ticket_id, action, token_cap FROM ticket_edits") == [
        (1, "approve", None)]
    assert _cells(view.table)[0][0] == PENDING
    assert not any(b.isEnabled() for b in view.buttons.values())
    view.buttons["reject"].click()
    assert len(rows(home, "SELECT id FROM ticket_edits")) == 1


def test_buttons_only_for_waiting(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-039.002.M01.T02: For an approved ticket all three buttons are off."""
    _raise(home, 5_000)
    view = _view(qtbot, home)
    _select(view, "Goal number 0 to test")
    assert not any(b.isEnabled() for b in view.buttons.values())


def test_cap_range(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-039.002.M01.T03: A cap of 500 writes no edit."""
    _raise(home, 30_000)
    view = _view(qtbot, home)
    _select(view, "Goal number 0 to test")
    view.cap.setValue(500)
    view.buttons["cap"].click()
    assert rows(home, "SELECT id FROM ticket_edits") == []
    assert "1,000 to 100,000" in view.note.text()


def test_ended_detail(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-039.003.M01.T01: An ended ticket shows its result and end reason."""
    _raise(home, 5_000)
    execute(home, "UPDATE tickets SET status = 'done', ended = ?, end_reason = 'token cap', "
                  "result = 'RSI 40 beats the base'", (NOW.isoformat(),))
    view = _view(qtbot, home)
    _select(view, "Goal number 0 to test")
    assert "Ended: done, token cap" in view.detail.text()
    assert "Result: RSI 40 beats the base" in view.detail.text()


def test_no_result_while_open(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-039.003.M01.T02: A waiting ticket shows its done test and no result."""
    _raise(home, 30_000)
    view = _view(qtbot, home)
    _select(view, "Goal number 0 to test")
    assert view.detail.text() == "Done when: Any variant beats the base by 0.05R"


def test_lead_line(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-039.004.M01.T01: The lead line shows research tokens used and left."""
    add_try(home, "r-1", 5_000, part="research", payer="l-1")
    view = _view(qtbot, home)
    assert view.leads.text() == "Research tokens today: Lead A 5,000 used, 13,000 left"


def test_edit_log(qtbot: QtBot, home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-GUI-039.005.M01.T01: Reject is logged with the ticket id."""
    _raise(home, 30_000)
    view = _view(qtbot, home)
    _select(view, "Goal number 0 to test")
    with caplog.at_level(logging.INFO):
        view.buttons["reject"].click()
    assert "[Research] Ticket 1 rejected from the app" in caplog.text


def _book_view(qtbot: QtBot, home: Path, chosen: str) -> ResearchView:
    view = ResearchView("Research", home, lambda: NOW, lambda: chosen)
    qtbot.addWidget(view)
    _ALIVE.append(view)
    return view


def test_add_book(qtbot: QtBot, tmp_path: Path, home: Path,
                  caplog: pytest.LogCaptureFixture) -> None:
    """UT-GUI-039.006.M01.T01: Add book copies the chosen file and shows a note."""
    source = tmp_path / "My Swing Book.pdf"
    source.write_bytes(b"%PDF-1.4 test")
    view = _book_view(qtbot, home, str(source))
    with caplog.at_level(logging.INFO):
        view.add_book_button.click()
    assert (home / "books" / "My_Swing_Book.pdf").read_bytes() == b"%PDF-1.4 test"
    assert view.note.text().startswith("Added My_Swing_Book.pdf")
    assert "[Books] Added My_Swing_Book.pdf" in caplog.text


def test_add_book_cancelled(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-039.006.M01.T02: A cancelled file browser adds nothing."""
    view = _book_view(qtbot, home, "")
    view.add_book_button.click()
    assert not (home / "books").exists()
    assert view.note.text() == ""


def test_add_book_refused_logged(qtbot: QtBot, tmp_path: Path, home: Path,
                                 caplog: pytest.LogCaptureFixture) -> None:
    """UT-GUI-039.007.M01.T01: A refused book shows why and logs a [Books] warning."""
    source = tmp_path / "notes.docx"
    source.write_bytes(b"x")
    view = _book_view(qtbot, home, str(source))
    with caplog.at_level(logging.WARNING):
        view.add_book_button.click()
    assert view.note.text() == "Book not added: notes.docx is not a PDF, TXT, MD or HTML file"
    assert "[Books] Book not added" in caplog.text
