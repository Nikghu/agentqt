"""Tests for MD-GUI-034.027.M21 (Hiring and approvals), MD-GUI-034.032.M22 (Reports) and
MD-GUI-034.033.M23 (seat caps). Employee names here are made up.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from PyQt6.QtWidgets import QLabel, QListWidget, QPushButton, QTableWidget, QWidget
from pytestqt.qtbot import QtBot

import tests.desk.test_harness as th
from tests.desk.test_hiring import _days, _emp, _try
from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings, save_settings
from us_swing.core.desk_hiring import SHADOW_DAYS
from us_swing.gui.ai_desk_hiring import NO_APPROVALS, NO_HIRES, HiringPanel, approvals_box
from us_swing.gui.ai_desk_sections3 import reports_frame
from us_swing.gui.ai_desk_settings import DeskAiSettingsForm


def _ready(home: Path, folder: str = "emp-002") -> None:
    _emp(home, folder, f"Shadow {folder}", status="shadow", hired="2026-09-30")
    for day in _days(SHADOW_DAYS):
        _try(home, folder, day, {"word": "x"}, 1)


def _panel(qtbot: QtBot, home: Path) -> HiringPanel:
    panel = HiringPanel(home)
    qtbot.addWidget(panel)
    return panel


def _cells(table: QTableWidget, row: int) -> list[str]:
    return [table.item(row, c).text() for c in range(table.columnCount())]  # type: ignore[union-attr]


def _texts(widget: QWidget) -> list[str]:
    return [w.text() for w in widget.findChildren(QLabel)]


def test_hires_listed(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.027.M21.T01: hires show skill, level, name, model, start, days and status."""
    _emp(tmp_path, "emp-001", "Default Person")
    _emp(tmp_path, "emp-002", "Shadow Person", status="shadow", hired="2026-11-01")
    _emp(tmp_path, "emp-003", "Active Hire", hired="2026-09-01")
    _try(tmp_path, "emp-002", "2026-11-03", {"word": "x"}, 1)
    panel = _panel(qtbot, tmp_path)
    assert panel.table.rowCount() == 2
    assert _cells(panel.table, 0) == ["Shadow Person", "fake", "expert", "openrouter / or-model",
                                      "2026-11-01", "1 of 14", "shadow"]
    assert _cells(panel.table, 1)[-1] == "active"


def test_no_hires(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.027.M21.T02: no hires shows the note; the form is still there."""
    panel = _panel(qtbot, tmp_path)
    assert NO_HIRES in _texts(panel) and panel.table.isHidden()
    assert panel.start_btn.isEnabled()


def test_start_hire_form(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.028.M21.T01: the form starts a hire, listed as shadow."""
    panel = _panel(qtbot, tmp_path)
    panel.skill.setCurrentIndex(panel.skill.findData("setup_review"))
    panel.name.setText("Made Up Three")
    panel.start_btn.click()
    assert panel.table.rowCount() == 1
    assert _cells(panel.table, 0)[0] == "Made Up Three"
    assert _cells(panel.table, 0)[-1] == "shadow"
    assert "started in shadow" in panel.form_status.text()


def test_refused_hire_form(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.028.M21.T02: a used name shows the reason and adds no row."""
    _emp(tmp_path, "emp-001", "Taken Name")
    panel = _panel(qtbot, tmp_path)
    panel.name.setText("taken name")
    panel.start_btn.click()
    assert "already used" in panel.form_status.text()
    assert panel.table.rowCount() == 0


def test_shadow_report_shown(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.029.M21.T01: choosing a hire shows rows for the hire and the holder."""
    _emp(tmp_path, "emp-001", "Holder Person")
    _emp(tmp_path, "emp-002", "Shadow Person", status="shadow", hired="2026-10-01")
    _try(tmp_path, "emp-002", "2026-10-01", {"grade": "A"}, 1)
    _try(tmp_path, "emp-001", "2026-10-01", {"grade": "A"}, 0)
    panel = _panel(qtbot, tmp_path)
    assert [_cells(panel.report, r)[0] for r in range(2)] == ["Shadow Person", "Holder Person"]
    assert panel.agreement.text() == "Agreement with the holder: 100%"


def test_buttons_follow_rules(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.030.M21.T01: not ready -> only Reject; ready -> Replace or Add."""
    _emp(tmp_path, "emp-003", "Early Hire", status="shadow", hired="2026-11-05")
    panel = _panel(qtbot, tmp_path)
    states = (panel.replace_btn.isEnabled(), panel.add_btn.isEnabled(),
              panel.reject_btn.isEnabled())
    assert states == (False, False, True)
    _ready(tmp_path)
    panel.reload()
    ready_row = next(r for r in range(panel.table.rowCount())
                     if _cells(panel.table, r)[0] == "Shadow emp-002")
    panel.table.setCurrentCell(ready_row, 0)
    assert (panel.replace_btn.isEnabled(), panel.add_btn.isEnabled()) == (False, True)
    _emp(tmp_path, "emp-001", "Holder Person")
    panel.reload()
    assert (panel.replace_btn.isEnabled(), panel.add_btn.isEnabled()) == (True, False)


def test_replace_click(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.030.M21.T02: Replace saves an approvals row and lists the hire as active."""
    _emp(tmp_path, "emp-001", "Holder Person")
    _ready(tmp_path)
    panel = _panel(qtbot, tmp_path)
    panel.replace_btn.click()
    assert _cells(panel.table, 0)[-1] == "active"
    assert "replace saved" in panel.decision_status.text()
    assert th._rows(tmp_path, "SELECT decision FROM approvals") == [("replace",)]


def test_approvals_waiting(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.031.M21.T01: a ready hire is listed; a click opens Hiring."""
    _ready(tmp_path)
    opened: list[bool] = []
    box = approvals_box(tmp_path, lambda: opened.append(True))
    qtbot.addWidget(box)
    cards = box.cards()
    assert len(cards) == 1 and cards[0].card.subject == "Hire · Shadow emp-002"
    button = next(b for b in cards[0].findChildren(QPushButton) if b.text() == "Open Hiring")
    button.click()
    assert opened == [True]


def test_nothing_waiting(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.031.M21.T02: no ready hire shows the empty note."""
    box = approvals_box(tmp_path, lambda: None)
    qtbot.addWidget(box)
    assert NO_APPROVALS in _texts(box)


def _report(home: Path, week: str, text: str) -> None:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / "desk.db")
    try:
        with con:
            con.execute("CREATE TABLE IF NOT EXISTS desk_reports (id INTEGER PRIMARY KEY, "
                        "week TEXT UNIQUE, created TEXT, title TEXT, text TEXT)")
            con.execute("INSERT INTO desk_reports (week, created, title, text) VALUES "
                        "(?, ?, ?, ?)", (week, week, f"Weekly report {week}", text))
    finally:
        con.close()


def test_weekly_reports(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.032.M22.T01: weekly reports newest first; no Sample tag."""
    _report(tmp_path, "2026-10-30", "older text")
    _report(tmp_path, "2026-11-06", "newer text")
    frame = reports_frame("Reports", tmp_path)
    qtbot.addWidget(frame)
    listing = frame.findChild(QListWidget)
    assert listing is not None
    assert [listing.item(i).text() for i in range(2)] == [  # type: ignore[union-attr]
        "Weekly report 2026-11-06", "Weekly report 2026-10-30"]
    assert "Sample data" not in _texts(frame)
    assert "newer text" in json.dumps([w.toPlainText() for w in frame.findChildren(QWidget)
                                       if hasattr(w, "toPlainText")])


def test_no_weekly_reports(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.032.M22.T02: with no reports table, sample reports show with the tag."""
    frame = reports_frame("Reports", tmp_path)
    qtbot.addWidget(frame)
    assert "Sample data" in _texts(frame)


def test_seat_caps_saved(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.033.M23.T01: a changed expert cap is saved."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert form.caps["expert"].text() == "8"
    form.caps["expert"].setText("9")
    assert form.save()
    assert load_settings(tmp_path).expert_cap == 9


def test_cap_below_count(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.033.M23.T02: a cap below the current count is refused; file unchanged."""
    for i in range(6):
        _emp(tmp_path, f"emp-00{i + 1}", f"Person {i}")
    save_settings(DeskAiSettings(), tmp_path)
    before = (tmp_path / "desk_ai.json").read_text(encoding="utf-8")
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    form.caps["expert"].setText("5")
    assert not form.save()
    assert "6 experts already work" in form.status.text()
    assert (tmp_path / "desk_ai.json").read_text(encoding="utf-8") == before
