"""Tests for the AI Desk design match (MD-GUI-034.059.M33 to MD-GUI-034.062.M36).
Employee names here are made up."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from tests.desk.test_hiring import _emp, _try
from tests.gui.test_ai_desk_hiring import _ready
from tests.gui.test_ai_desk_trades import FRI, SAT, _Sink, _two
from us_swing.core import desk_chat as dc
from us_swing.core.desk_overview import last_run, spend, team_counts, todays_runs
from us_swing.gui.ai_desk import SECTIONS, AiDeskWorkspace
from us_swing.gui.ai_desk_chat import ChatPanel
from us_swing.gui.ai_desk_hiring import approvals_box
from us_swing.gui.ai_desk_sections import runs_box, team_line
from us_swing.core.desk_contract import DeskState
from us_swing.gui.desk_control import DeskPoller

SAT_UTC = datetime(2026, 11, 7, 17, 0, tzinfo=UTC)


def _runs(home: Path) -> None:
    from us_swing.desk.store import DeskStore

    store = DeskStore(home)
    for kind, start, result in (("manual", 14, "ok"), ("event", 15, "ok"), ("event", 16, "failed"),
                                ("evening", 21, "ok")):
        run = store.start_run(kind, datetime(2026, 11, 7, start, 0, tzinfo=UTC))
        store.end_run(run, result, datetime(2026, 11, 7, start, 5, tzinfo=UTC))
    old = store.start_run("evening", datetime(2026, 11, 5, 21, 0, tzinfo=UTC))
    store.end_run(old, "ok", datetime(2026, 11, 5, 21, 5, tzinfo=UTC))
    store.close()


def _page(qtbot: QtBot, home: Path, sink: _Sink | None = None) -> AiDeskWorkspace:
    page = AiDeskWorkspace(DeskPoller(home), sink, clock=lambda: SAT)
    qtbot.addWidget(page)
    return page


def test_grouped_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.059.M33.T01: eleven sections in group order (Memory in step C, Research in step E), no
    headings; the list stays hidden (sections are tabs, SRD-GUI-034.067)."""
    page = _page(qtbot, tmp_path)
    assert page._list.isHidden()
    assert page._list.count() == len(SECTIONS)
    assert page.section_names() == list(SECTIONS) and len(SECTIONS) == 11
    page.select_section("Reports")
    assert page.current_section() == "Reports"
    assert page._stack.currentIndex() == SECTIONS.index("Reports")


def test_command_badge(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.059.M33.T02: Command shows the waiting ask count, then plain Command."""
    _two(tmp_path)
    page = _page(qtbot, tmp_path, _Sink())
    assert page._item("Command").text() == "Command   2"  # type: ignore[union-attr]
    page.set_ask_count(0)
    assert page._item("Command").text() == "Command"  # type: ignore[union-attr]


def test_overview_data(tmp_path: Path) -> None:
    """UT-GUI-034.060.M34.T01: events summed with the worst result; last run; spend; team."""
    _runs(tmp_path)
    rows = todays_runs(tmp_path, SAT_UTC)
    assert [(r.name, r.result, r.count) for r in rows] == [
        ("Manual run", "ok", 1), ("Event runs", "failed", 2), ("Evening run", "ok", 1)]
    run = last_run(tmp_path)
    assert run is not None and run.name == "Evening run" and run.result == "ok"
    _try(tmp_path, "emp-002", "2026-11-07", {"a": 1}, 0, cost=0.25)
    _try(tmp_path, "emp-002", "2026-11-03", {"a": 1}, 0, cost=0.75)
    used = spend(tmp_path, SAT_UTC)
    assert used is not None and used.today_usd == 0.25 and used.month_usd == 1.0
    assert used.month_share == 1.0 / used.budget_usd
    _emp(tmp_path, "emp-002", "Tester A", status="active")
    _emp(tmp_path, "emp-003", "Tester B", status="shadow", hired="2026-10-01")
    assert team_counts(tmp_path) == {"active": 1, "shadow": 1}


def test_header_chips(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.060.M33.T01: last run tile, today's spend and the month bar percent."""
    _runs(tmp_path)
    _try(tmp_path, "emp-002", "2026-11-07", {"a": 1}, 0, cost=1.0)
    page = _page(qtbot, tmp_path)
    assert page.last_run_title.text() == "Last run · ok"
    assert page.last_run_chip.text().endswith("Evening run · Thu 05 Nov, 16:05 ET")
    assert page.spend_label.text() == "$1.00"
    share = round(spend(tmp_path, SAT).month_share * 100)  # type: ignore[union-attr]
    assert page.spend_bar.value() == share
    assert page.budget_title.text() == f"Month budget · {share}% used"


def test_header_no_data(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.060.M33.T02: with no desk data the tiles show no runs and zero spend."""
    page = _page(qtbot, tmp_path)
    assert page.last_run_chip.text() == "No runs yet"
    assert page.spend_label.text() == "$0.00"
    assert page.spend_bar.value() == 0


def test_chat_bubbles(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.061.M35.T01: Master bubble on the right, lead on the left, ET time shown."""
    qid = dc.ask_question(tmp_path, "Why AAA?", SAT_UTC)
    dc.add_reply(tmp_path, qid, "Strong sector.", True, SAT_UTC)
    panel = ChatPanel(tmp_path, lambda: DeskState.RUNNING, lambda: SAT)
    qtbot.addWidget(panel)
    bubbles = panel.findChildren(QFrame, "chat_bubble")
    assert [b.property("mine") for b in bubbles] == [True, False]
    text = bubbles[0].findChild(QLabel).text()  # type: ignore[union-attr]
    assert "Master" in text and "12:00 ET" in text
    assert panel.entry.placeholderText() == "Message the lead"


def test_approval_cards(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.062.M36.T01: heading count, pick cards with qty, Open Hiring opens Hiring."""
    _ready(tmp_path)
    _two(tmp_path)
    page = _page(qtbot, tmp_path, _Sink())
    box = page.findChild(type(approvals_box(tmp_path, lambda: None)))
    assert box is not None and box.count == 3
    heads = [w.text() for w in box.findChildren(QLabel) if w.objectName() == "view_head"]
    assert heads == ["Approvals waiting · 3"]
    assert [c.qty.text() for c in box.cards() if c.card.ref == "pick"] == ["Qty 45", "Qty 45"]
    hire = next(c for c in box.cards() if c.card.ref == "hire")
    next(b for b in hire.findChildren(QPushButton) if b.text() == "Open Hiring").click()
    assert page.current_section() == "Hiring"
    picks = [c.card.pick for c in box.cards() if c.card.pick is not None]
    assert all(FRI in p.subject for p in picks) and len(picks) == 2


def test_todays_runs_box(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.063.M36.T01: one line per run, events summed, no Sample tag on Command."""
    _runs(tmp_path)
    box = runs_box(todays_runs(tmp_path, SAT_UTC))
    qtbot.addWidget(box)
    texts = [w.text() for w in box.findChildren(QLabel)]
    assert "Event runs (×2)" in texts and "Evening run" in texts
    assert [w.text() for w in box.findChildren(QLabel, "run_result")] == ["ok", "failed", "ok"]
    page = _page(qtbot, tmp_path)
    frame = page._stack.currentWidget()
    assert frame is not None
    assert [w for w in frame.findChildren(QLabel) if w.objectName() == "sample_tag"
            and not w.isHidden()] == []


def test_team_line(qtbot: QtBot) -> None:
    """UT-GUI-034.064.M36.T01: the Team now line lists counts; hidden with no employees."""
    holder = QWidget()
    qtbot.addWidget(holder)
    label, empty = team_line({"active": 2, "shadow": 1}), team_line({})
    for line in (label, empty):
        line.setParent(holder)
    holder.show()
    assert label.text() == "Team now: 2 active · 1 shadow" and label.isVisible()
    assert not empty.isVisible()
