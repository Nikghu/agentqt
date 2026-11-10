"""Tests for the AI Desk console look (SRD-GUI-034.065, SRD-GUI-034.066)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtWidgets import QFrame, QLabel, QPushButton
from pytestqt.qtbot import QtBot

from tests.desk.test_hiring import _emp
from us_swing.core.desk_contract import DeskState, DeskStatus
from us_swing.core.desk_overview import next_evening_run
from us_swing.gui.ai_desk import AiDeskWorkspace
from us_swing.gui.ai_desk_hiring import hiring_frame
from us_swing.gui.ai_desk_sections3 import cost_frame, settings_frame
from us_swing.gui.desk_control import DeskPoller

NY = ZoneInfo("America/New_York")
SAT = datetime(2026, 11, 7, 12, 0, tzinfo=NY)


def _page(qtbot: QtBot, home: Path) -> AiDeskWorkspace:
    page = AiDeskWorkspace(DeskPoller(home), clock=lambda: SAT)
    qtbot.addWidget(page)
    return page


def test_next_evening_run() -> None:
    """UT-GUI-034.065.M34.T01: the next run skips the weekend and a passed 16:25."""
    assert next_evening_run(SAT) == datetime(2026, 11, 9, 16, 25, tzinfo=NY)
    tue = datetime(2026, 11, 10, 10, 0, tzinfo=NY)
    assert next_evening_run(tue) == datetime(2026, 11, 10, 16, 25, tzinfo=NY)
    late = datetime(2026, 11, 10, 17, 0, tzinfo=NY)
    assert next_evening_run(late) == datetime(2026, 11, 11, 16, 25, tzinfo=NY)


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
    assert page.next_run_label.text().startswith("Mon 16:25 ET")
    assert "IST" in page.next_run_label.text()


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
                "Settings": ["Schedule and rules", "Claude Code CLI", "OpenRouter API", "Seats"]}
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
