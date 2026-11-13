"""Tests for the AI Desk console look (SRD-GUI-034.065, SRD-GUI-034.066)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtWidgets import QFrame, QLabel, QPushButton
from pytestqt.qtbot import QtBot

from tests.desk.test_hiring import _emp
from us_swing.core.desk_contract import DeskState, DeskStatus
from us_swing.core.desk_overview import next_morning_run, run_name
from us_swing.gui.ai_desk import AiDeskWorkspace
from us_swing.gui.ai_desk_hiring import hiring_frame
from us_swing.gui.ai_desk_sections3 import cost_frame, settings_frame
from us_swing.desk.store import DeskStore
from us_swing.gui.desk_control import DeskPoller

NY = ZoneInfo("America/New_York")
SAT = datetime(2026, 11, 7, 12, 0, tzinfo=NY)


def _page(qtbot: QtBot, home: Path) -> AiDeskWorkspace:
    page = AiDeskWorkspace(DeskPoller(home), clock=lambda: SAT)
    qtbot.addWidget(page)
    return page


def test_next_morning_run(tmp_path: Path) -> None:
    """UT-GUI-034.065.M34.T01: Next morning run (SRD-GUI-034.065, .069)."""
    assert next_morning_run(SAT, tmp_path) == datetime(2026, 11, 9, 4, 0, tzinfo=NY)
    wed = datetime(2026, 11, 11, 3, 0, tzinfo=NY)
    assert next_morning_run(wed, tmp_path) == datetime(2026, 11, 11, 4, 0, tzinfo=NY)
    nine = datetime(2026, 11, 11, 9, 0, tzinfo=NY)
    assert next_morning_run(nine, tmp_path) == nine
    store = DeskStore(tmp_path)
    store.end_run(store.start_run("morning", nine - timedelta(minutes=30)), "ok", nine)
    store.close()
    assert next_morning_run(nine, tmp_path) == datetime(2026, 11, 12, 4, 0, tzinfo=NY)


def test_run_names() -> None:
    """UT-GUI-034.069.M34.T01: Run names (SRD-GUI-034.069)."""
    assert [run_name(k) for k in ("morning", "evening", "manual")] == [
        "Morning run", "Evening run", "Manual run"]


def test_header_tiles_and_controls(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.065.M39.T01: four header tiles and one joined control group, Stop last."""
    page = _page(qtbot, tmp_path)
    tiles = page.findChildren(QFrame, "stat_tile")[:4]
    titles = [t.findChildren(QLabel)[0].text() for t in tiles]
    assert titles == ["Last run", "Next run", "AI spend today", "Month budget · 0% used"]
    seg = page.findChild(QFrame, "desk_seg")
    assert seg is not None
    assert [b.text() for b in seg.findChildren(QPushButton)] == ["Start", "Pause", "Resume",
                                                                 "Stop"]
    assert page.next_run_label.text() == "Mon 09 Nov, 04:00 ET"


def test_state_note(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.065.M39.T02: the note follows the state; an error shows its message."""
    page = _page(qtbot, tmp_path)
    page.show_state_note(DeskStatus(DeskState.PAUSED))
    assert page.state_note.text() == "Paused; no runs until you resume"
    page.show_state_note(DeskStatus(DeskState.ERROR, message="Claude login expired"))
    assert page.state_note.text() == "Claude login expired"


def test_sections_use_icon_cards(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.066.M39.T01: Hiring, Cost and Settings are built from titled icon cards."""
    expected = {"Hiring": ["Hires", "Start hire", "Shadow report"],
                "Cost": ["Budget used", "By employee", "By model"],
                "Settings": ["Schedule and rules", "Claude Code CLI", "OpenRouter API", "Seats",
                             "Agent messages"]}
    frames = {"Hiring": hiring_frame("Hiring", tmp_path),
              "Cost": cost_frame("Cost & budget", tmp_path),
              "Settings": settings_frame("Desk settings", tmp_path)}
    for key, frame in frames.items():
        qtbot.addWidget(frame)
        titles = [w.text() for w in frame.findChildren(QLabel, "card_title")]
        assert titles == expected[key]


def test_hiring_seat_tiles(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.066.M21.T01: seat tiles count active and shadow employees against the cap."""
    _emp(tmp_path, "emp-002", "Tester A", status="active")
    frame = hiring_frame("Hiring", tmp_path)
    qtbot.addWidget(frame)
    texts = [w.text() for w in frame.findChildren(QLabel)]
    assert any(t.startswith("1 ") and "of " in t and "seats" in t for t in texts)
    assert "In shadow" in texts


def test_section_tabs(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.067.M33.T01: one tab per section in order; a click shows it; list and tab agree."""
    page = _page(qtbot, tmp_path)
    assert list(page.tabs) == page.section_names()
    assert page.tabs["Command"].isChecked()
    assert page.tabs["Cost & budget"].text() == "Cost && budget"  # shows a plain &
    page.tabs["Results"].click()
    assert page.current_section() == "Results" and page.tabs["Results"].isChecked()
    page.select_section("Hiring")
    assert page.tabs["Hiring"].isChecked() and not page.tabs["Results"].isChecked()


def test_command_tab_badge(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.067.M33.T02: the Command tab shows the waiting count, plain at 0."""
    page = _page(qtbot, tmp_path)
    page.set_ask_count(3)
    assert page.tabs["Command"].text() == "Command   3"
    page.set_ask_count(0)
    assert page.tabs["Command"].text() == "Command"
