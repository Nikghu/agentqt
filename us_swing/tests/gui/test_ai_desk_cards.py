"""Tests for MD-GUI-040.001.M01 (AI Desk Cards section)."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QTableWidget, QWidget
from pytestqt.qtbot import QtBot

from tests.desk.research_support import NOW, employee
from us_swing.core.desk_cards import CardTest, save_test
from us_swing.core.desk_research import raise_owner_test
from us_swing.gui.ai_desk_cards import NO_CARDS, CardsView
from us_swing.market.book_cards import CardText, save_card

_ALIVE: list[QWidget] = []
MADE = "2026-11-10T09:30:00-05:00"


def _text(name: str) -> CardText:
    return CardText(name, f"{name} idea", "US stocks", f"{name} entry", f"{name} exit",
                    f"{name} stop", ("a quote",))


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "desk"
    employee(h, "l-9", "Lead P", "lead", "lead_brief")
    return h


def _cards(home: Path, count: int) -> None:
    for i in range(count):
        save_card(home, "upload:book.txt", 3, 1, _text(f"Card{i + 1}"), MADE)


def _view(qtbot: QtBot, home: Path) -> CardsView:
    view = CardsView("Cards", home, lambda: NOW)
    qtbot.addWidget(view)
    _ALIVE.append(view)
    return view


def _cells(table: QTableWidget) -> list[list[str]]:
    return [[table.item(r, c).text() if table.item(r, c) else ""  # type: ignore[union-attr]
             for c in range(table.columnCount())] for r in range(table.rowCount())]


def _with_tests(home: Path) -> None:
    _cards(home, 4)
    save_test(home, CardTest(2, 5, MADE, "pass", trades=42, win_rate=0.55, avg_r=0.31,
                             worst_run=4, base_r=0.05, verdict="Beats the baseline"))
    save_test(home, CardTest(4, 6, MADE, "cant_test", reason="needs news data"))
    raise_owner_test(home, 3, NOW)


def test_card_list(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-040.001.M01.T01: rows newest first with Not tested, Pass, Testing, Can't test."""
    _with_tests(home)
    view = _view(qtbot, home)
    rows = _cells(view.table)
    assert [r[0] for r in rows] == ["SC-4", "SC-3", "SC-2", "SC-1"]
    assert [r[4] for r in rows] == ["Can't test", "Testing", "Pass", "Not tested"]
    assert rows[2][2:4] == ["upload:book.txt ch 3", MADE[:10]]
    assert rows[2][5:] == ["42", "+0.31"] and rows[0][5:] == ["", ""]


def test_no_cards(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-040.001.M01.T02: without any desk.db the empty note shows."""
    view = _view(qtbot, tmp_path / "none")
    assert view.empty.text() == NO_CARDS and not view.empty.isHidden()
    assert view.table.isHidden() and not view.test_button.isEnabled()


def test_card_detail(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-040.002.M01.T01: detail shows rules, quotes, test line and verdict."""
    _with_tests(home)
    view = _view(qtbot, home)
    view.table.selectRow(2)
    text = view.detail.text()
    for part in ("Card2 idea", "Card2 entry", "Card2 exit", "Card2 stop", "a quote",
                 "Last test: 42 trades, win rate 55%, average R +0.31, worst losing run 4, "
                 "baseline +0.05R", "Verdict: Beats the baseline"):
        assert part in text
    view.table.selectRow(0)
    assert "Last test: can't test — needs news data" in view.detail.text()


def test_test_button(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-040.003.M01.T01: Test raises one approved ticket and the card shows Testing."""
    _cards(home, 1)
    view = _view(qtbot, home)
    assert not view.test_button.isEnabled()
    view.table.selectRow(0)
    assert view.test_button.isEnabled()
    view.test_button.click()
    assert view.note.text().startswith("Test started as ticket ")
    assert _cells(view.table)[0][4] == "Testing"
    assert not view.test_button.isEnabled()
    assert view.table.currentRow() == 0 or view._chosen() is not None


def test_test_off_while_testing(qtbot: QtBot, home: Path) -> None:
    """UT-GUI-040.003.M01.T02: Test is disabled for a card that is being tested."""
    _cards(home, 3)
    raise_owner_test(home, 3, NOW)
    view = _view(qtbot, home)
    view.table.selectRow(0)
    assert _cells(view.table)[0][4] == "Testing" and not view.test_button.isEnabled()


def test_test_log(qtbot: QtBot, home: Path, tmp_path: Path,
                  caplog: pytest.LogCaptureFixture) -> None:
    """UT-GUI-040.004.M01.T01: started and not-started lines are logged with the reason."""
    _cards(home, 1)
    view = _view(qtbot, home)
    view.table.selectRow(0)
    with caplog.at_level(logging.INFO):
        view.test_button.click()
    assert any(r.getMessage().startswith("[Research] Test of card SC-1 started from the app "
                                         "as ticket ") for r in caplog.records)
    bare = tmp_path / "bare"
    _cards(bare, 1)
    other = _view(qtbot, bare)
    other.table.selectRow(0)
    caplog.clear()
    with caplog.at_level(logging.INFO):
        other.test_button.click()
    assert any(r.getMessage().startswith("[Research] Test of card SC-1 not started: ")
               for r in caplog.records)
    assert other.note.text().startswith("Test not started: ")
