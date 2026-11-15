"""Tests for the tool builder in the AI Desk (AI Desk v3 M7b): the request box, the request and
built tool lists, the review detail with the code, Enable and Disable (MD-GUI-041.001.M01) and
the Tool builder switch (MD-GUI-034.016.M15).

Stock and employee names here are made up.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from pytestqt.qtbot import QtBot

from tests.desk import builder_support as bs
from us_swing.core.desk_ai_settings import SETTINGS_FILE, load_settings, save_settings
from us_swing.core.desk_built_tools import add_request, tool_requests
from us_swing.gui import ai_desk_tools
from us_swing.gui.ai_desk_settings import DeskAiSettingsForm
from us_swing.gui.ai_desk_tools import (
    CHANGED_LINE,
    MISSING_FILE,
    NO_BUILT,
    OFF_NOTE,
    READ_FAILED,
    ToolsView,
)

NOW = bs.NOW


def _view(qtbot: QtBot, home: Path) -> ToolsView:
    view = ToolsView("Tools", home, clock=lambda: NOW)
    qtbot.addWidget(view)
    return view


def _cells(view: ToolsView, table: str) -> list[list[str]]:
    widget = getattr(view, table)
    return [[widget.item(r, c).text() for c in range(widget.columnCount())]
            for r in range(widget.rowCount())]


def _choose(view: ToolsView, tool_id: int) -> None:
    row = next(i for i, t in enumerate(view._built) if t.id == tool_id)
    view.built_table.selectRow(row)


def _picked(view: ToolsView) -> tuple[int, str]:
    tool = view._picked_tool()
    assert tool is not None
    return tool.id, tool.state


# ── request box (SRD-GUI-041.006) ───────────────────────────────────────────


def test_request_a_tool(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.006.M01.T01: With the tool builder on, a typed request is saved, the box clears
    and the note names the request number."""
    bs.on(tmp_path)
    view = _view(qtbot, tmp_path)
    assert view.request_btn.isEnabled()
    view.request_edit.setText("Percent below the 52-week high")
    view.request_btn.click()
    (req,) = tool_requests(tmp_path)
    assert (req.source, req.text) == ("tools", "Percent below the 52-week high")
    assert view.request_edit.text() == ""
    assert view.request_note.text() == f"Request #{req.id} saved. The builder starts at its " \
                                       "next turn."
    assert _cells(view, "requests_table")[0][:4] == [f"#{req.id}", "16-11-2026 09:00", "You",
                                                     "New"]


def test_request_off_or_empty(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.006.M01.T02: Off, the button is disabled with the note; on with an empty box
    the reason shows; no row either way."""
    off, on = tmp_path / "off", tmp_path / "on"
    bs.on(off, tool_builder_on=False)
    bs.on(on)
    off_view = _view(qtbot, off)
    assert not off_view.request_btn.isEnabled() and off_view.request_note.text() == OFF_NOTE
    on_view = _view(qtbot, on)
    on_view.request_btn.click()
    assert on_view.request_note.text() == "A request needs 1 to 300 characters."
    assert tool_requests(off) == [] and tool_requests(on) == []


# ── lists (SRD-GUI-041.007, .008) ───────────────────────────────────────────


def test_requests_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.007.M01.T01: A Master request and a chat request, newest first, with who
    asked, state and reason."""
    bs.on(tmp_path)
    bs.team(tmp_path)
    add_request(tmp_path, "tools", None, "master", "Gap today", [], NOW)
    add_request(tmp_path, "chat", 7, bs.ASKER, "Volume ratio", ["ZZA"], NOW)
    view = _view(qtbot, tmp_path)
    rows = _cells(view, "requests_table")
    assert [(r[0], r[2], r[3], r[5]) for r in rows] == [("#2", "Quill", "New", "Volume ratio"),
                                                        ("#1", "You", "New", "Gap today")]


def test_built_tools_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.008.M01.T01: A version in review and a failed one, newest first, with version,
    state and checks passed."""
    bs.version(tmp_path)
    bs.version(tmp_path, name="gap_tool", ok=False)
    view = _view(qtbot, tmp_path)
    rows = _cells(view, "built_table")
    assert [(r[0], r[1], r[2], r[4]) for r in rows] == [
        ("gap_tool", "v1", "Failed", "4 of 5"), (bs.NAME, "v1", "Review", "5 of 5")]
    assert view.built_empty.isHidden()


def test_no_built_tools(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.008.M01.T02: With no built tool the empty note shows."""
    view = _view(qtbot, tmp_path)
    assert view.built_empty.text() == NO_BUILT and not view.built_empty.isHidden()
    assert view.built_table.isHidden() and view.code_box.isHidden()


def test_built_tools_read_error(qtbot: QtBot, tmp_path: Path,
                                monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-041.008.M01.T03: A database that cannot be read shows the read-failed note and
    raises nothing."""
    def locked(_home: Path, _limit: int = 50) -> list[object]:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(ai_desk_tools, "built_tool_rows", locked)
    view = _view(qtbot, tmp_path)
    assert view.note.text() == READ_FAILED and not view.note.isHidden()
    assert view.code_box.isHidden() and view.enable_btn.isHidden()


# ── review detail (SRD-GUI-041.009) ─────────────────────────────────────────


def test_review_detail(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.009.M01.T01: The chosen version shows its request, about, columns, 5 check
    lines and sample rows; the code box holds the file text and is read-only."""
    bs.on(tmp_path)
    rid = add_request(tmp_path, "tools", None, "master", "Below the high", [], NOW)
    tool = bs.version(tmp_path, request=rid)
    view = _view(qtbot, tmp_path)
    _choose(view, tool.id)
    lines = view.tool_detail.text().splitlines()
    assert lines[0] == f"Request #{rid}: Below the high"
    assert lines[1].startswith("About: ") and lines[2].startswith("Columns: below_high (number)")
    assert [line[:1] for line in lines[3:8]] == ["✓"] * 5
    assert lines[8:] == ["Sample rows:", "ZZA: below_high 3.2"]
    assert view.code_box.toPlainText() == bs.GOOD_CODE and view.code_box.isReadOnly()
    assert view.tool_detail.textFormat() == Qt.TextFormat.PlainText


def test_missing_or_changed_file(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.009.M01.T02: A deleted file shows the missing note; an edited one adds the
    changed line."""
    gone = bs.version(tmp_path, name="gone_tool")
    edited = bs.version(tmp_path, name="edited_tool")
    (tmp_path / gone.file).unlink()
    (tmp_path / edited.file).write_text(bs.GOOD_CODE + "# edited\n", encoding="utf-8")
    view = _view(qtbot, tmp_path)
    _choose(view, gone.id)
    assert view.code_box.toPlainText() == MISSING_FILE
    _choose(view, edited.id)
    assert view.tool_detail.text().endswith(CHANGED_LINE)


# ── Enable and Disable (SRD-GUI-041.010) ────────────────────────────────────


def test_enable_and_disable(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.010.M01.T01: Enable turns the version on and its format shows Active; Disable
    turns it off and the format goes; the version stays chosen."""
    tool = bs.version(tmp_path)
    bs.version(tmp_path, name="other_tool")
    view = _view(qtbot, tmp_path)
    _choose(view, tool.id)
    assert view.enable_btn.isEnabled() and not view.disable_btn.isEnabled()
    view.enable_btn.click()
    assert _picked(view) == (tool.id, "enabled")
    assert view.tool_note.text() == f"Enabled {bs.NAME} v1."
    formats = {r[0]: r[1] for r in _cells(view, "formats_table")}
    assert formats[f"{bs.NAME}.v1"] == "Active"
    assert view.disable_btn.isEnabled() and not view.enable_btn.isEnabled()
    view.disable_btn.click()
    assert _picked(view) == (tool.id, "disabled")
    assert f"{bs.NAME}.v1" not in {r[0] for r in _cells(view, "formats_table")}
    assert view.tool_note.text() == f"Disabled {bs.NAME} v1."


def test_buttons_follow_the_state(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.010.M01.T02: A failed version cannot be enabled; a version whose file changed
    after the view was built shows the refusal reason."""
    failed = bs.version(tmp_path, name="gap_tool", ok=False)
    good = bs.version(tmp_path)
    view = _view(qtbot, tmp_path)
    _choose(view, failed.id)
    assert not view.enable_btn.isEnabled() and not view.disable_btn.isEnabled()
    _choose(view, good.id)
    assert view.enable_btn.isEnabled()
    (tmp_path / good.file).write_text(bs.GOOD_CODE + "# edited\n", encoding="utf-8")
    view.enable_btn.click()
    assert view.tool_note.text() == "The code changed after review."
    assert _picked(view) == (good.id, "review")


# ── switch (SRD-GUI-034.085) ────────────────────────────────────────────────


def test_tool_builder_switch(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.085.M15.T01: Ticking Tool builder saves tool_builder_on; it is off by
    default."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.tool_builder_on.isChecked()
    form.tool_builder_on.setChecked(True)
    assert form.save()
    assert load_settings(tmp_path).tool_builder_on is True


def test_switch_not_tied_to_messages(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.085.M15.T02: The Tool builder box is enabled while Agent messages is
    unticked."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    form.messages_on.setChecked(False)
    assert form.tool_builder_on.isEnabled()


def test_old_settings_file(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.085.M15.T03: A settings file with no tool_builder_on loads as off; saving keeps
    it false."""
    save_settings(load_settings(tmp_path), tmp_path)
    path = tmp_path / SETTINGS_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("tool_builder_on")
    path.write_text(json.dumps(data), encoding="utf-8")
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.tool_builder_on.isChecked()
    assert form.save()
    assert json.loads(path.read_text(encoding="utf-8"))["tool_builder_on"] is False
