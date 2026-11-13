"""Tests for the AI Desk v3 M3 changes in MD-GUI-037.001.M01 (Memory section: notes, views,
core block, note edits) and MD-GUI-034.016.M15 (Memory v2 switch).

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import QTableWidget, QWidget
from pytestqt.qtbot import QtBot

from us_swing.core import desk_memory
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_msg import Remember
from us_swing.desk.recorder import NY
from us_swing.gui.ai_desk_memory import PENDING, MemoryView
from us_swing.gui.ai_desk_settings import DeskAiSettingsForm

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=NY)
DAY = "2026-11-06"
_ALIVE: list[QWidget] = []


def _person(home: Path, emp_id: str, name: str) -> None:
    folder = home / "employees" / emp_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "employee.md").write_text(f"""---
id: {emp_id}
name: {name}
title: Test helper
level: expert
reports_to: null
skill: setup_review
version: 1
trigger: after_run
models:
  primary: {{source: openrouter, model: m}}
  backup: {{source: claude, model: default}}
calls_per_day: 20
monthly_cost_usd: 3.0
kpis: [valid answers]
---
You are {name}.
""", encoding="utf-8")


def _setup(home: Path) -> None:
    _person(home, "emp-p", "Pia")
    _person(home, "emp-q", "Quin")
    desk_memory.write(home, "emp-p", [Remember(kind="note", text="Semis lead", symbol="NVDA"),
                                      Remember(kind="view", text="call", symbol="NVDA",
                                               direction="up")], DAY, NOW)
    desk_memory.write(home, "emp-q", [Remember(kind="note", text="Banks lag")], DAY, NOW)


def _view(qtbot: QtBot, home: Path) -> MemoryView:
    view = MemoryView("Memory", home, lambda: NOW, lambda *_a: True)
    qtbot.addWidget(view)
    _ALIVE.append(view)
    return view


def _cells(table: QTableWidget) -> list[list[str]]:
    return [[table.item(r, c).text() if table.item(r, c) else ""  # type: ignore[union-attr]
             for c in range(table.columnCount())] for r in range(table.rowCount())]


def test_kind_filter(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.005.M01.T01: Notes lists the notes with their columns."""
    _setup(tmp_path)
    view = _view(qtbot, tmp_path)
    view.kind.setCurrentText("Notes")
    rows = _cells(view.notes.table)
    assert sorted(r[3] for r in rows) == ["Banks lag", "Semis lead"]
    pia = next(r for r in rows if r[3] == "Semis lead")
    assert pia[:3] == ["active", "", "Pia"] and pia[4] == "NVDA" and pia[6] == DAY
    assert pia[7:9] == ["0", "0"]


def test_lessons_as_before(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.005.M01.T02: Lessons shows the lesson table; the Employee list is hidden."""
    _setup(tmp_path)
    view = _view(qtbot, tmp_path)
    assert view.kind.currentText() == "Lessons"
    assert not view.lessons_box.isHidden() and view.notes.isHidden() and view.owner.isHidden()
    assert view.filter.itemText(0) == "Active"


def test_employee_filter(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.006.M01.T01: Choosing one employee shows only that employee's notes."""
    _setup(tmp_path)
    view = _view(qtbot, tmp_path)
    view.kind.setCurrentText("Notes")
    view.owner.setCurrentText("Quin")
    assert [r[3] for r in _cells(view.notes.table)] == ["Banks lag"]


def test_all_employees(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.006.M01.T02: All employees shows every owner's notes."""
    _setup(tmp_path)
    view = _view(qtbot, tmp_path)
    view.kind.setCurrentText("Notes")
    assert view.owner.currentText() == "All employees"
    assert {r[2] for r in _cells(view.notes.table)} == {"Pia", "Quin"}


def test_core_block_box(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.007.M01.T01: The box shows the same text as core_block()."""
    _setup(tmp_path)
    view = _view(qtbot, tmp_path)
    view.kind.setCurrentText("Views")
    view.owner.setCurrentText("Pia")
    assert not view.notes.core.isHidden()
    assert view.notes.core.toPlainText() == desk_memory.core_block(tmp_path, "emp-p", DAY)
    assert "NVDA up" in view.notes.core.toPlainText()


def test_core_block_hidden_for_all(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.007.M01.T02: With All employees the box is hidden."""
    _setup(tmp_path)
    view = _view(qtbot, tmp_path)
    view.kind.setCurrentText("Notes")
    assert view.notes.core.isHidden()


def test_pin_note(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.008.M01.T01: Pin writes a memory edit and marks the row pending."""
    _setup(tmp_path)
    view = _view(qtbot, tmp_path)
    view.kind.setCurrentText("Notes")
    view.notes.table.selectRow(0)
    view.notes.buttons["pin"].click()
    assert desk_memory.pending_edits(tmp_path)
    assert _cells(view.notes.table)[0][0] == PENDING


def test_no_buttons_on_views(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-037.008.M01.T02: Views have no edit buttons."""
    _setup(tmp_path)
    view = _view(qtbot, tmp_path)
    view.kind.setCurrentText("Views")
    assert all(b.isHidden() for b in view.notes.buttons.values())


def test_memory_switch(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.072.M15.T01: Ticking Memory v2 saves memory_v2_on."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    form.memory_v2_on.setChecked(True)
    assert form.save()
    assert load_settings(tmp_path).memory_v2_on is True


def test_memory_switch_off_by_default(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.072.M15.T02: A new desk folder shows the box unticked."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.memory_v2_on.isChecked()
