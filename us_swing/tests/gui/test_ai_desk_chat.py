"""Tests for MD-GUI-034.039.M26 (real lead chat in Command). Employee names here are made up."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtWidgets import QLabel, QWidget
from pytestqt.qtbot import QtBot

from tests.desk.test_hiring import _emp
from us_swing.core import desk_chat as dc
from us_swing.core.desk_contract import DeskState
from us_swing.data.market_calendar import ET
from us_swing.gui.ai_desk_chat import NO_TURNS, ChatPanel

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=ET)
_ALIVE: list[QWidget] = []


def _panel(qtbot: QtBot, home: Path, state: list[DeskState], clock: list[datetime]) -> ChatPanel:
    panel = ChatPanel(home, lambda: state[0], lambda: clock[0])
    qtbot.addWidget(panel)
    _ALIVE.append(panel)
    return panel


def _texts(panel: ChatPanel) -> list[str]:
    return [w.text() for w in panel.findChildren(QLabel)]


def test_turns_shown(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.039.M26.T01: Master and chat employee lines, oldest first."""
    _emp(tmp_path, "emp-008", "Chat Person", level="lead", skill="lead_chat")
    qid = dc.ask_question(tmp_path, "Why AAPL?", NOW)
    dc.add_reply(tmp_path, qid, "Strong sector.", True, NOW)
    texts = [t for t in _texts(_panel(qtbot, tmp_path, [DeskState.RUNNING], [NOW]))
             if "Why AAPL?" in t or "Strong sector." in t]
    assert len(texts) == 2
    assert "Master" in texts[0] and "Chat Person" in texts[1]


def test_no_turns(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.039.M26.T02: an empty desk shows the empty note and a ready Ask box."""
    panel = _panel(qtbot, tmp_path, [DeskState.RUNNING], [NOW])
    assert NO_TURNS in _texts(panel)
    assert panel.entry.isEnabled()


def test_ask(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.040.M26.T01: Ask saves the question, clears the box and waits."""
    panel = _panel(qtbot, tmp_path, [DeskState.RUNNING], [NOW])
    panel.entry.setText("What changed today?")
    assert panel.ask_btn.isEnabled()
    panel.ask_btn.click()
    assert [t.text for t in dc.chat_turns(tmp_path)] == ["What changed today?"]
    assert panel.entry.text() == "" and panel.note.text() == dc.WAITING
    assert not panel.ask_btn.isEnabled()


def test_empty_box(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.040.M26.T02: an empty or blank box cannot be sent."""
    panel = _panel(qtbot, tmp_path, [DeskState.RUNNING], [NOW])
    for text in ("", "   "):
        panel.entry.setText(text)
        assert not panel.ask_btn.isEnabled()
        panel.ask()
    assert dc.chat_turns(tmp_path) == []


def test_answer_arrives(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.041.M26.T01: the answer shows on the next check and the check stops."""
    panel = _panel(qtbot, tmp_path, [DeskState.RUNNING], [NOW])
    panel.entry.setText("Why?")
    panel.ask()
    qid = dc.chat_turns(tmp_path)[0].id
    dc.add_reply(tmp_path, qid, "Because the regime is calm.", True, NOW)
    panel._tick()
    assert any("Because the regime is calm." in t for t in _texts(panel))
    assert panel.note.text() == "" and not panel._timer.isActive()


def test_desk_stopped_or_expired(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.041.M26.T02: start-the-desk note, then the expired note and no more checks."""
    state, clock = [DeskState.STOPPED], [NOW]
    panel = _panel(qtbot, tmp_path, state, clock)
    panel.entry.setText("Why?")
    panel.ask()
    assert panel.note.text() == dc.START_DESK and panel._timer.isActive()
    clock[0] = NOW + timedelta(minutes=31)
    panel._tick()
    assert panel.note.text() == dc.EXPIRED and not panel._timer.isActive()


def test_resume_after_rebuild(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.041.M26.T03: a panel built while a question waits keeps checking for it."""
    dc.ask_question(tmp_path, "Still there?", NOW)
    panel = _panel(qtbot, tmp_path, [DeskState.RUNNING], [NOW])
    assert panel.note.text() == dc.WAITING and panel._timer.isActive()
    assert not panel.ask_btn.isEnabled()
