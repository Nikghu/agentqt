"""Tests for AI Desk → Team setup (MD-GUI-036.001.M01). Employee names are made up."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pytestqt.qtbot import QtBot

from tests.gui.team_fixtures import call, hire
from us_swing.core import desk_employee as de
from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.gui.ai_desk_setup import RULES_TEXT, TeamSetup
from us_swing.gui.theme import C


def _hire(home: Path, emp_id: str, name: str, prompt: str = "You are {name}.") -> Path:
    job: dict[str, Any] = {
        "id": emp_id, "name": name, "title": "Tester", "level": "expert", "reports_to": None,
        "skill": "fake", "version": 1, "trigger": ["after_run"],
        "models": {"primary": {"source": "claude", "model": "default"},
                   "backup": {"source": "openrouter", "model": "default"}},
        "calls_per_day": 3, "monthly_cost_usd": 3.0, "kpis": ["valid answers", "fast"]}
    folder = home / "employees" / emp_id
    de.write_new(folder, de.check(yaml.safe_load(yaml.safe_dump(job))), prompt)
    return folder


def _page(qtbot: QtBot, home: Path, answers: list[bool] | None = None,
          asked: list[str] | None = None, runner: Any = None) -> TeamSetup:
    def ask(text: str) -> bool:
        if asked is not None:
            asked.append(text)
        return answers.pop(0) if answers else True

    page = TeamSetup(home, ask=ask, runner=runner or de.try_draft)
    qtbot.addWidget(page)
    return page


def test_list_every_employee(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.001.M01.T01: all employees listed again on show; old files move."""
    _hire(tmp_path, "emp-a", "Alpha")
    _hire(tmp_path, "emp-b", "Beta")
    hire(tmp_path, "emp-c", "Gamma", "regime_view", "after_run")
    page = _page(qtbot, tmp_path)
    page.show()
    assert page.emp_list.count() == 3
    assert (tmp_path / "employees" / "emp-c" / de.EMPLOYEE_FILE).exists()
    _hire(tmp_path, "emp-d", "Delta")
    page.hide()
    page.show()
    assert page.emp_list.count() == 4 and page.employee_ids()[-1] == "emp-d"


def test_broken_file(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.001.M01.T02: a file without front matter is marked and its form is off."""
    _hire(tmp_path, "emp-a", "Alpha")
    bad = tmp_path / "employees" / "emp-b"
    bad.mkdir()
    (bad / de.EMPLOYEE_FILE).write_text("just words\n", encoding="utf-8")
    page = _page(qtbot, tmp_path)
    page.select("emp-b")
    assert "not valid" in page.emp_list.item(1).text()
    assert not page.form.isEnabled() and not page.save_btn.isEnabled()
    assert "settings block" in page.note_label.text()


def test_form_fills(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.002.M01.T01: the form shows the file; the skill is read-only text."""
    _hire(tmp_path, "emp-a", "Alpha")
    _hire(tmp_path, "emp-b", "Beta")
    page = _page(qtbot, tmp_path)
    page.select("emp-b")
    assert page.current_id() == "emp-b"
    assert page.name_edit.text() == "Beta" and page.title_edit.text() == "Tester"
    assert page.level_box.currentText() == "expert" and page.boss_box.currentText() == "none"
    assert page.boss_box.findData("emp-a") >= 0 and page.boss_box.findData("emp-b") < 0
    assert page.kpis_edit.toPlainText() == "valid answers\nfast"
    assert (page.main_source.currentText(), page.main_model.currentText()) == (
        "claude", "default")
    assert page.backup_source.currentText() == "openrouter"
    assert page.calls_spin.value() == 3 and page.cap_spin.value() == 3.0
    assert page.status_box.currentText() == "active"
    assert [k for k, b in page.wake_checks.items() if b.isChecked()] == ["after_run"]
    assert page.skill_label.text() == "Fake"
    assert not page.save_btn.isEnabled()
    assert list(page.tabs) == ["Prompt", "Profile", "Model", "Limits & wake", "History"]


def test_empty_desk(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.002.M01.T02: no employees gives a plain note and a dead form."""
    page = _page(qtbot, tmp_path)
    assert page.note_label.text() == "No employees yet"
    assert not page.form.isEnabled() and not page.save_btn.isEnabled()
    assert page.employee_ids() == [] and page.current_id() == ""


def test_prompt_tab(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.003.M01.T01: file prompt shown; rules are read-only text; typing enables Save."""
    _hire(tmp_path, "emp-a", "Alpha", "Be {name}, the {title}.")
    page = _page(qtbot, tmp_path)
    assert page.prompt_edit.toPlainText() == "Be {name}, the {title}."
    assert page.rules_label.text() == RULES_TEXT and "JSON" in page.rules_label.text()
    assert not page.save_btn.isEnabled()
    page.prompt_edit.setPlainText("Be brief.")
    assert page.save_btn.isEnabled()


def test_empty_prompt_refused(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.003.M01.T02: an empty prompt is refused with a reason; file unchanged."""
    folder = _hire(tmp_path, "emp-a", "Alpha")
    before = (folder / de.EMPLOYEE_FILE).read_bytes()
    page = _page(qtbot, tmp_path)
    page.prompt_edit.setPlainText("")
    page.save_btn.click()
    assert page.note_label.text() == "Not saved: the prompt is empty"
    assert (folder / de.EMPLOYEE_FILE).read_bytes() == before


def test_model_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.004.M01.T01: list has default, settings model, used model; typed name saves."""
    folder = _hire(tmp_path, "emp-a", "Alpha")
    save_settings(DeskAiSettings(claude_model="claude-x", openrouter_model="or-x"), tmp_path)
    call(tmp_path, 1, "emp-a", "16:26:00", True)
    page = _page(qtbot, tmp_path)
    items = [page.main_model.itemText(i) for i in range(page.main_model.count())]
    assert items == ["default", "claude-x", "m"]
    page.main_source.setCurrentText("openrouter")
    assert "or-x" in [page.main_model.itemText(i) for i in range(page.main_model.count())]
    page.main_source.setCurrentText("claude")
    page.main_model.setEditText("my-own")
    page.save_btn.click()
    saved = de.load(folder).spec.models.primary
    assert (saved.source, saved.model) == ("claude", "my-own")


def test_blank_model_refused(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.004.M01.T02: a blank backup model is refused; file unchanged."""
    folder = _hire(tmp_path, "emp-a", "Alpha")
    before = (folder / de.EMPLOYEE_FILE).read_bytes()
    page = _page(qtbot, tmp_path)
    page.backup_model.setEditText("")
    page.save_btn.click()
    assert page.note_label.text().startswith("Not saved: ")
    assert (folder / de.EMPLOYEE_FILE).read_bytes() == before


def test_save_new_version(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.005.M01.T01: Save writes version + 1, says so, and turns Save off."""
    folder = _hire(tmp_path, "emp-a", "Alpha")
    page = _page(qtbot, tmp_path)
    page.prompt_edit.setPlainText("New words.")
    with qtbot.waitSignal(page.saved) as seen:
        page.save_btn.click()
    assert seen.args == ["emp-a"]
    emp = de.load(folder)
    assert emp.spec.version == 2 and emp.prompt == "New words."
    assert page.note_label.text() == "Saved as version 2 · applies from the next wake"
    assert not page.save_btn.isEnabled() and page.current_id() == "emp-a"


def test_refused_save(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.005.M01.T02: a blank name is refused in red; file unchanged."""
    folder = _hire(tmp_path, "emp-a", "Alpha")
    before = (folder / de.EMPLOYEE_FILE).read_bytes()
    page = _page(qtbot, tmp_path)
    page.name_edit.setText("   ")
    page.save_btn.click()
    assert page.note_label.text().startswith("Not saved: name")
    assert C.RED in page.note_label.styleSheet()
    assert (folder / de.EMPLOYEE_FILE).read_bytes() == before


def test_unsaved_switch(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.005.M01.T03: a No stays on the employee; a Yes moves and drops the edit."""
    _hire(tmp_path, "emp-a", "Alpha")
    _hire(tmp_path, "emp-b", "Beta")
    asked: list[str] = []
    page = _page(qtbot, tmp_path, [False, True], asked)
    page.name_edit.setText("Changed")
    page.select("emp-b")
    assert page.current_id() == "emp-a" and page.emp_list.currentRow() == 0
    assert page.name_edit.text() == "Changed"
    assert asked == ["Discard unsaved changes to Alpha?"]
    page.select("emp-b")
    assert page.current_id() == "emp-b" and page.name_edit.text() == "Beta"
    page.select("emp-a")
    assert page.name_edit.text() == "Alpha" and len(asked) == 2


def test_history_restore(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.006.M01.T01: 2 saves list 3 versions; restoring v1 makes v4 with its prompt."""
    folder = _hire(tmp_path, "emp-a", "Alpha", "First words.")
    asked: list[str] = []
    page = _page(qtbot, tmp_path, None, asked)
    for words in ("Second words.", "Third words."):
        page.prompt_edit.setPlainText(words)
        page.save_btn.click()
    assert page.history_list.count() == 3
    assert page.history_list.item(0).text().endswith("· current")
    assert page.history_list.item(0).text().startswith("v 3 · ")
    page.history_list.setCurrentRow(2)
    assert page.history_view.toPlainText() == "First words."
    page.restore_btn.click()
    assert asked == ["Restore version 1 as a new version?"]
    emp = de.load(folder)
    assert emp.spec.version == 4 and emp.prompt == "First words."
    assert page.history_list.count() == 4 and page.prompt_edit.toPlainText() == "First words."


def test_test_on_yesterday(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-036.007.M01.T01: off with a note when no run; else shows the answer with a bar."""
    _hire(tmp_path, "emp-a", "Alpha")
    seen: list[str] = []

    def runner(home: Path, emp_id: str, text: str) -> de.DraftResult:
        seen.append(text)
        return de.DraftResult(True, '{"word": "new"}')

    page = _page(qtbot, tmp_path, runner=runner)
    assert not page.test_btn.isEnabled()
    assert page.test_btn.toolTip() == "No recorded run yet"
    assert page.result_label.text() == "No recorded run yet"
    call(tmp_path, 1, "emp-a", "16:26:00", True)
    page.reload()
    assert page.test_btn.isEnabled()
    page.prompt_edit.setPlainText("Draft words.")
    page.test_btn.click()
    assert page.test_btn.text() == "Testing…" and not page.test_btn.isEnabled()
    qtbot.waitUntil(lambda: page.test_btn.text() == "Test on yesterday", timeout=5000)
    assert page.result_label.text() == 'Valid answer\n{"word": "new"}'
    assert f"border-left: 3px solid {C.GREEN}" in page.result_label.styleSheet()
    assert de.parse(seen[0]).prompt == "Draft words."
    assert de.load(tmp_path / "employees" / "emp-a").prompt == "You are {name}."
