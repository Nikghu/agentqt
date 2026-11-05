"""Tests for the AI Desk frames (MD-GUI-034.009.M08, MD-GUI-034.010.M03)."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QLabel, QWidget
from pytestqt.qtbot import QtBot

from us_swing.gui import ai_desk_sample
from us_swing.gui.ai_desk import AiDeskWorkspace
from us_swing.gui.desk_control import DeskPoller


def _titles(frame: QWidget) -> list[str]:
    return [w.text() for w in frame.findChildren(QLabel) if w.objectName() == "page_title"]


def test_all_sections_open(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.009.M08.T01: 11 sections in order; each shows its own filled frame."""
    page = AiDeskWorkspace(DeskPoller(tmp_path))
    qtbot.addWidget(page)
    names = page.section_names()
    assert len(names) == 11
    assert names[0] == "Command"
    assert names[-1] == "Desk settings"
    assert page.current_section() == "Command"
    for index, name in enumerate(names):
        page.select_section(name)
        assert page.current_section() == name
        assert page._stack.currentIndex() == index
        frame = page._stack.currentWidget()
        assert frame is not None
        assert _titles(frame) == [name]
        texts = [w.text() for w in frame.findChildren(QLabel)]
        assert "Frame comes in the next step" not in texts


def test_every_section_shows_sample_tag(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.010.M03.T02: every AI Desk section frame carries the Sample data tag."""
    page = AiDeskWorkspace(DeskPoller(tmp_path))
    qtbot.addWidget(page)
    for name in page.section_names():
        page.select_section(name)
        frame = page._stack.currentWidget()
        assert frame is not None
        tags = [w.text() for w in frame.findChildren(QLabel) if w.objectName() == "sample_tag"]
        assert tags == ["Sample data"]


def test_sample_seats_within_caps() -> None:
    """UT-GUI-034.009.M08.T02: sample seats stay within caps 3 / 5 / 30."""
    assert ai_desk_sample.SEAT_CAPS == {"Experts": 3, "Champions": 5, "Juniors": 30}
    used = ai_desk_sample.seats_used()
    for key, cap in ai_desk_sample.SEAT_CAPS.items():
        assert 0 < used[key] <= cap
    assert used == {"Experts": 3, "Champions": 3, "Juniors": 18}
