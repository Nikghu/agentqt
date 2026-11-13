"""Tests for AI Desk v3 M1 in the GUI: messages switch, message events, Threads tab."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from pytestqt.qtbot import QtBot

from tests.gui.team_fixtures import DAY, NEEDS, NOW, desk
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_messages import Person, accept
from us_swing.core.desk_msg import Draft, Verdict
from us_swing.core.desk_team import day_events, team
from us_swing.desk.recorder import Attempt, Recorder
from us_swing.gui.ai_desk_settings import DeskAiSettingsForm
from us_swing.gui.ai_desk_team_log import EventLogView, woke_text
from us_swing.gui.ai_desk_threads import ThreadsView, empty_text

ROSTER = [Person("emp-a", "Alpha", "regime_view"), Person("emp-b", "Beta", "sector_flow_view"),
          Person("emp-c", "Gamma", "risk_check")]
NAMES = {p.id: p.name for p in ROSTER}


def _ask(home: Path, sender: str, to: str, subject: str, minutes: int = 0) -> int:
    draft = Draft(type="ask", to=to, subject=subject, text="Please look at this")
    (line,) = accept(home, [draft], sender, ROSTER, NOW + timedelta(minutes=minutes), DAY)
    assert line.startswith("stored #"), line
    return int(line.split("#")[1])


def test_messages_switch_saves(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.070.M15.T01: Ticking Agent messages and saving writes messages_on true."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    form.messages_on.setChecked(True)
    assert form.save()
    assert load_settings(tmp_path).messages_on is True
    assert '"messages_on": true' in (tmp_path / "desk_ai.json").read_text(encoding="utf-8")


def test_messages_off_by_default(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.070.M15.T02: A new desk folder shows the box unticked; saving keeps false."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.messages_on.isChecked()
    assert form.save()
    assert load_settings(tmp_path).messages_on is False


def test_message_event_detail(tmp_path: Path) -> None:
    """UT-GUI-035.015.M02.T01: A message event has the receiver, a detail line and its calls."""
    desk(tmp_path, finished=True)
    mid = _ask(tmp_path, "emp-c", "emp-a", "Check the sector")
    rec = Recorder(tmp_path)
    try:
        rec.add(Attempt(0, "emp-a", "Alpha", 1, DAY, f"{DAY}T16:27:40-05:00", "claude", "m", 1,
                        "p", "a", True, "", 10, 5, 0.0, 2.0, message=mid))
    finally:
        rec.close()
    members = team(tmp_path, NEEDS)
    events = day_events(tmp_path, date(2026, 11, 9), members, NOW)
    (event,) = [e for e in events if e.kind == "message"]
    assert event.target == "emp-a"
    assert event.detail == "ask from Gamma to Alpha: Check the sector (submitted)"
    assert [c.employee for c in event.calls] == ["emp-a"]


def test_other_events_unchanged(tmp_path: Path) -> None:
    """UT-GUI-035.015.M02.T02: An after_run event has no target and no detail; calls as before."""
    run_id = desk(tmp_path, finished=True)
    _ask(tmp_path, "emp-c", "emp-a", "Check the sector")
    members = team(tmp_path, NEEDS)
    events = day_events(tmp_path, date(2026, 11, 9), members, NOW)
    after = next(e for e in events if e.kind == "after_run")
    assert after.target == "" and after.detail == ""
    assert [c.run_id for c in after.calls] == [run_id] * 3


def test_log_row_shows_message(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.015.M03.T01: The log row shows the receiver's name and the detail."""
    desk(tmp_path, finished=True)
    _ask(tmp_path, "emp-c", "emp-b", "Check the sector")
    members = team(tmp_path, NEEDS)
    events = day_events(tmp_path, date(2026, 11, 9), members, NOW)
    event = next(e for e in events if e.kind == "message")
    assert woke_text(event, members) == "Beta"
    view = EventLogView()
    qtbot.addWidget(view)
    view.set_events(date(2026, 11, 9), events, members, date(2026, 11, 9))
    rows = [view.tree.topLevelItem(i) for i in range(view.tree.topLevelItemCount())]
    item = next(r for r in rows if r is not None and r.text(4) == "Beta")
    assert item.text(2) == event.detail


def test_threads_table_and_detail(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.016.M05.T01: Two threads show newest first; selecting one lists its messages."""
    first = _ask(tmp_path, "emp-c", "emp-a", "Check the sector")
    reply = Draft(type="reply", parent=first, verdict=Verdict(result="done"), text="All fine")
    accept(tmp_path, [reply], "emp-a", ROSTER, NOW + timedelta(minutes=1), DAY)
    _ask(tmp_path, "emp-a", "emp-b", "Second question", minutes=5)
    view = ThreadsView()
    qtbot.addWidget(view)
    view.show_threads(tmp_path, DAY, NAMES, True)
    assert view.table.rowCount() == 2
    assert [view.table.item(i, 1).text() for i in range(2)] == ["Alpha", "Gamma"]
    assert view.detail.count() == 1
    view.table.selectRow(1)
    assert view.detail.count() == 2
    assert "ask" in view.detail.item(0).text() and "reply" in view.detail.item(1).text()


def test_threads_empty_text(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.016.M05.T02: No threads: the text names the switch when off, plain when on."""
    view = ThreadsView()
    qtbot.addWidget(view)
    view.show_threads(tmp_path, DAY, {}, False)
    assert view.table.rowCount() == 0 and view.note.text() == empty_text(False)
    assert "Desk settings" in view.note.text()
    view.show_threads(tmp_path, DAY, {}, True)
    assert view.note.text() == "No messages today"


# ── AI Desk v3 M2 ────────────────────────────────────────────────────────────


def test_escalation_switch_saves(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.071.M15.T01: Ticking Agent messages and Escalation saves escalation_on."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    form.messages_on.setChecked(True)
    form.escalation_on.setChecked(True)
    assert form.save()
    assert load_settings(tmp_path).escalation_on is True


def test_escalation_greyed_while_messages_off(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.071.M15.T02: Escalation is greyed out while Agent messages is unticked."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.messages_on.isChecked() and not form.escalation_on.isEnabled()
    form.messages_on.setChecked(True)
    assert form.escalation_on.isEnabled()


def test_moved_up_line(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.017.M05.T01: A moved escalation shows its reason under the message."""
    from us_swing.core.desk_messages import expire_due

    roster = [Person("emp-a", "Alpha", "regime_view", boss="emp-b"),
              Person("emp-b", "Beta", "sector_flow_view", boss="emp-c"),
              Person("emp-c", "Gamma", "risk_check")]
    esc = Draft(type="escalate", to="boss", subject="AAPL plan broken", text="Stop touched")
    (line,) = accept(tmp_path, [esc], "emp-a", roster, NOW, DAY, True, lambda text: True)
    assert line.startswith("stored #"), line
    expire_due(tmp_path, NOW + timedelta(minutes=6), roster, lambda text: True)
    view = ThreadsView()
    qtbot.addWidget(view)
    view.show_threads(tmp_path, DAY, NAMES, True)
    texts = [view.detail.item(i).text() for i in range(view.detail.count())]
    assert len(texts) == 2 and "escalate" in texts[0] and "Gamma" in texts[0]
    assert texts[1].strip() == "Beta did not answer in 5 minutes"
