"""Tests for AI Desk v3 M4 in MD-GUI-034.016.M15 (Chat sessions switch) and MD-GUI-034.039.M26
(session list, New discussion, update bubbles, team note). Employee names here are made up."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtWidgets import QLabel, QWidget
from pytestqt.qtbot import QtBot

from tests.desk.test_hiring import _emp
from us_swing.core import desk_chat as dc
from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings, save_settings
from us_swing.core.desk_contract import DeskState
from us_swing.core.desk_messages import Person, accept
from us_swing.core.desk_msg import Draft
from us_swing.data.market_calendar import ET
from us_swing.gui.ai_desk_chat import ChatPanel
from us_swing.gui.ai_desk_settings import DeskAiSettingsForm

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=ET)
ROSTER = [Person("lead", "Lead", "lead_chat"), Person("exp", "Expert", "other")]
_ALIVE: list[QWidget] = []


def _panel(qtbot: QtBot, home: Path) -> ChatPanel:
    panel = ChatPanel(home, lambda: DeskState.RUNNING, lambda: NOW)
    qtbot.addWidget(panel)
    _ALIVE.append(panel)
    return panel


def _texts(panel: ChatPanel) -> list[str]:
    return [w.text() for w in panel.findChildren(QLabel)]


def _on(home: Path, on: bool = True) -> None:
    save_settings(DeskAiSettings(sessions_on=on), home)


def _session(home: Path, title: str, when: datetime) -> int:
    sid = dc.session_for(home, when, None, title, new=True)
    qid = dc.ask_question(home, title, when, session=sid)
    dc.add_reply(home, qid, f"Answer to {title}", True, when)
    return sid


def _replied(home: Path) -> int:
    qid = dc.ask_question(home, "Why?", NOW)
    dc.add_reply(home, qid, "First answer.", True, NOW)
    return qid


def test_sessions_switch(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.073.M15.T01: ticking Chat sessions saves sessions_on."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    form.sessions_on.setChecked(True)
    assert form.save()
    assert load_settings(tmp_path).sessions_on is True


def test_sessions_switch_off_by_default(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.073.M15.T02: with no settings file the box is unticked."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.sessions_on.isChecked()


def test_session_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.074.M26.T01: two rows newest first; the older shows its turns and takes the ask."""
    _on(tmp_path)
    old = _session(tmp_path, "Old topic", NOW - timedelta(hours=3))
    new = _session(tmp_path, "New topic", NOW - timedelta(hours=1))
    panel = _panel(qtbot, tmp_path)
    ids = [panel.session_list.item(i).data(0x100) for i in range(panel.session_list.count())]
    assert ids == [new, old]
    panel.session_list.itemClicked.emit(panel.session_list.item(1))
    qtbot.wait(50)
    texts = " ".join(_texts(panel))
    assert "Answer to Old topic" in texts and "Answer to New topic" not in texts
    panel.entry.setText("More on old")
    panel.ask()
    last = dc.chat_turns(tmp_path)[-1]
    assert (last.text, last.session) == ("More on old", old)


def test_list_hidden_when_off(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.074.M26.T02: with sessions off there is no list and all turns show."""
    _on(tmp_path, False)
    _replied(tmp_path)
    dc.add_reply(tmp_path, dc.ask_question(tmp_path, "Second?", NOW), "Second answer.", True, NOW)
    panel = _panel(qtbot, tmp_path)
    assert panel.side.isHidden() and panel.session_list.count() == 0
    texts = " ".join(_texts(panel))
    assert "First answer." in texts and "Second answer." in texts


def test_new_discussion(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.075.M26.T01: New discussion closes the shown session; the ask starts a new one."""
    _on(tmp_path)
    old = _session(tmp_path, "Old topic", NOW - timedelta(minutes=10))
    panel = _panel(qtbot, tmp_path)
    panel.new_btn.click()
    assert dc.get_session(tmp_path, old).state == "closing"  # type: ignore[union-attr]
    panel.entry.setText("Fresh start")
    panel.ask()
    last = dc.chat_turns(tmp_path)[-1]
    assert last.text == "Fresh start" and last.session not in (None, old)


def test_no_new_button_when_off(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.075.M26.T02: with sessions off the button is hidden and no session closes."""
    old = _session(tmp_path, "Old topic", NOW - timedelta(minutes=10))
    _on(tmp_path, False)
    panel = _panel(qtbot, tmp_path)
    assert not panel.new_btn.isVisibleTo(panel)
    assert dc.get_session(tmp_path, old).state == "open"  # type: ignore[union-attr]


def test_update_bubble(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.076.M26.T01: an update row shows as a lead bubble marked Update."""
    _emp(tmp_path, "emp-008", "Chat Person", level="lead", skill="lead_chat")
    qid = _replied(tmp_path)
    dc.add_update(tmp_path, qid, "Team says calm.", NOW)
    texts = [t for t in _texts(_panel(qtbot, tmp_path)) if "Team says calm." in t]
    assert len(texts) == 1 and "Chat Person" in texts[0] and "Update" in texts[0]


def test_team_note(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.076.M26.T02: a replied question with an open team ask shows the note and checks."""
    qid = _replied(tmp_path)
    accept(tmp_path, [Draft(type="ask", to="exp", subject=dc.team_subject(qid), text="View?")],
           "lead", ROSTER, NOW, "2026-11-07")
    panel = _panel(qtbot, tmp_path)
    assert panel.note.text() == dc.TEAM and panel._timer.isActive()


def test_plain_reply(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.076.M26.T03: a reply with no team ask has no Update mark and an empty note."""
    _emp(tmp_path, "emp-008", "Chat Person", level="lead", skill="lead_chat")
    _replied(tmp_path)
    panel = _panel(qtbot, tmp_path)
    reply = [t for t in _texts(panel) if "First answer." in t]
    assert len(reply) == 1 and "Update" not in reply[0]
    assert panel.note.text() == ""
