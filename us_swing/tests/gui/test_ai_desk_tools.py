"""Tests for MD-GUI-041.001.M01 (AI Desk Tools section) and MD-GUI-041.001.M08 (section list)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pytestqt.qtbot import QtBot

from tests.desk.test_hiring import _emp
from us_swing.core.desk_memory import log_failure
from us_swing.core.desk_registry import fill_registry, list_tools
from us_swing.core.desk_tasks import CardPart, close_card, fill_plans, note_result, open_card
from us_swing.gui.ai_desk import SECTIONS, AiDeskWorkspace
from us_swing.gui.ai_desk_tools import PICK_CARD, ToolsView, plan_label
from us_swing.gui.desk_control import DeskPoller

NOW = datetime(2026, 11, 13, 9, 0, tzinfo=ZoneInfo("America/New_York"))


def _cells(view: ToolsView, table: str) -> list[list[str]]:
    widget = getattr(view, table)
    rows = []
    for r in range(widget.rowCount()):
        rows.append([widget.item(r, c).text() for c in range(widget.columnCount())])
    return rows


def _view(qtbot: QtBot, home: Path) -> ToolsView:
    view = ToolsView("Tools", home)
    qtbot.addWidget(view)
    return view


def _card(home: Path, status: str, rows: int, secs: float,
          parts: list[CardPart] | None = None) -> int:
    card_id = open_card(home, 1, "emp-901", "emp-902", "setup_table.v1", ["rs_rank"], ["AAA"],
                        NOW)
    close_card(home, card_id, status, parts or [], rows, "", NOW, secs)
    return card_id


def test_tools_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.001.M01.T01: Tools list."""
    home = tmp_path / "desk"
    fill_registry(home, NOW)
    view = _view(qtbot, home)
    rows = _cells(view, "tools_table")
    assert len(rows) == len(list_tools(home))
    by_name = {r[0]: r for r in rows}
    assert by_name["technical.rs_rank"] == [
        "technical.rs_rank", "Technical tools", "code", "No", "10 s", "Active"]
    assert by_name["research.post_mortem"][3] == "Yes"
    mcp = [r for r in rows if r[0].startswith("mcp:")]
    assert mcp and all(r[1] == "MCP" for r in mcp)
    assert view.tools_empty.isHidden()
    assert not view.tools_table.isHidden()


def test_tools_view_no_data(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.001.M01.T02: No data."""
    view = _view(qtbot, tmp_path / "desk")
    for label in (view.tools_empty, view.formats_empty, view.cards_empty, view.failures_empty):
        assert not label.isHidden()
    for table in (view.tools_table, view.formats_table, view.cards_table, view.failures_table):
        assert table.isHidden()
    assert view.parts.isHidden()


def test_tools_section_listed(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.001.M08.T01: Tools section."""
    assert SECTIONS[SECTIONS.index("Desk settings") - 1] == "Tools"
    page = AiDeskWorkspace(DeskPoller(tmp_path))
    qtbot.addWidget(page)
    page.select_section("Tools")
    assert page.current_section() == "Tools"
    frame = page._stack.currentWidget()
    assert frame is not None and frame.findChild(ToolsView) is not None


def test_formats_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.002.M01.T01: Formats list."""
    home = tmp_path / "desk"
    fill_registry(home, NOW)
    fill_plans(home, NOW)
    view = _view(qtbot, home)
    rows = {r[0]: r for r in _cells(view, "formats_table")}
    assert "rs_rank ← technical.rs_rank" in rows["setup_table.v1"][2]
    assert rows["setup_table.v1"][1] == "Active"
    assert rows["scores.v1"][1] == "No plan"
    for _ in range(3):
        note_result(home, "setup_table.v1", True, "connection timed out", NOW)
    view.refresh()
    rows = {r[0]: r for r in _cells(view, "formats_table")}
    assert rows["setup_table.v1"][1] == "Retired: connection timed out"
    assert plan_label(None) == "No plan"


def test_cards_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.003.M01.T01: Cards list."""
    home = tmp_path / "desk"
    _emp(home, "emp-901", "Zed Quill")
    _card(home, "done", 5, 1.25)
    _card(home, "partial", 3, 2.5)
    _card(home, "failed", 0, 0.4)
    view = _view(qtbot, home)
    rows = _cells(view, "cards_table")
    assert [r[0] for r in rows] == ["TC-3", "TC-2", "TC-1"]
    assert rows[0][2] == "Zed Quill"
    assert rows[0][3] == "setup_table.v1"
    assert [r[4] for r in rows] == ["0", "3", "5"]
    assert [r[5] for r in rows] == ["Failed", "Partial", "Done"]
    assert rows[0][6] == "0.4"
    assert rows[1][6] == "2.5"
    assert view.cards_empty.isHidden()


def test_card_parts(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.004.M01.T01: Card parts."""
    home = tmp_path / "desk"
    parts = [
        CardPart(id="A", wave=1, group="data", tools=["data.bars"], cols=["close"], rows=4,
                 status="ok", secs=1.2),
        CardPart(id="B", wave=1, group="calendar", tools=["calendar.earnings"], cols=["earn"],
                 rows=0, status="failed", secs=3.0, reason="connection timed out"),
        CardPart(id="C", wave=2, group="technical", tools=["technical.rs_rank"],
                 cols=["rs_rank"], rows=4, status="ok", secs=0.5),
    ]
    _card(home, "partial", 4, 4.7, parts)
    view = _view(qtbot, home)
    assert view.parts.text() == PICK_CARD
    view.cards_table.selectRow(0)
    lines = view.parts.text().split("\n")
    assert len(lines) == 3
    for line, label in zip(lines, ("Data tools", "Calendar tools", "Technical tools")):
        assert label in line
    assert "4 rows" in lines[0] and "ok" in lines[0] and "1.2 s" in lines[0]
    assert "failed" in lines[1] and "3.0 s" in lines[1]
    assert lines[1].endswith("connection timed out")


def test_failure_log(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-041.005.M01.T01: Failure log."""
    home = tmp_path / "desk"
    log_failure(home, "emp-901", "first failure text", "2026-11-12", NOW)
    log_failure(home, "emp-901", "second failure text", "2026-11-13", NOW)
    view = _view(qtbot, home)
    rows = _cells(view, "failures_table")
    assert len(rows) == 2
    assert "second failure text" in rows[0][1]
    assert "first failure text" in rows[1][1]
    assert "2026-11-13" in rows[0][0]
    assert view.failures_empty.isHidden()
