"""Tests for the AI Desk frames (MD-GUI-034.009.M08, MD-GUI-034.010.M03)."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QLabel, QWidget
from pytestqt.qtbot import QtBot

from us_swing.gui.ai_desk import AiDeskWorkspace
from us_swing.gui.desk_control import DeskPoller


def _titles(frame: QWidget) -> list[str]:
    return [w.text() for w in frame.findChildren(QLabel) if w.objectName() == "page_title"]


def test_all_sections_open(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.009.M08.T01: 11 sections in order (five sample team sections became Team at
    work, SRD-GUI-035.001; Memory added, SRD-GUI-037.001; Research added, SRD-GUI-039.001);
    each shows its own filled frame."""
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
    """UT-GUI-034.010.M03.T02: every sample AI Desk section carries the Sample data tag.

    Desk settings is real from P5a (SRD-GUI-034.016); Cost & budget is sample until AI runs;
    Pages is real from P5d (SRD-GUI-034.022); Hiring is real from P6 (SRD-GUI-034.027);
    Results is real from P8 (SRD-GUI-034.037); Command is real from design phase 3
    (SRD-GUI-034.063); Team at work is real (SRD-GUI-035.001); Memory is real
    (SRD-GUI-037.001); Research is real (SRD-GUI-039.001).
    """
    page = AiDeskWorkspace(DeskPoller(tmp_path))
    qtbot.addWidget(page)
    real = ("Desk settings", "Pages", "Hiring", "Results", "Command", "Team at work",
            "Team setup", "Memory", "Research")
    for name in [n for n in page.section_names() if n not in real]:
        page.select_section(name)
        frame = page._stack.currentWidget()
        assert frame is not None
        tags = [w.text() for w in frame.findChildren(QLabel) if w.objectName() == "sample_tag"]
        assert tags == ["Sample data"]

