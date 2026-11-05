"""Tests for the AI Desk shell (MD-GUI-034.009.M08)."""
from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from us_swing.gui.ai_desk import AiDeskWorkspace
from us_swing.gui.desk_control import DeskPoller


def test_all_sections_open(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.009.M08.T01: 11 sections in order, Command first, each switches the stack."""
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
