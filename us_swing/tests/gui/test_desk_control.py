"""Tests for the desk bar and poller (MD-GUI-034.002.M02)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pytestqt.qtbot import QtBot

from us_swing.core.desk_contract import NOT_RESPONDING, CommandKind, DeskState, DeskStatus
from us_swing.gui import desk_control
from us_swing.gui.desk_control import DeskBar, DeskPoller, allowed_actions


def test_pill_shows_state(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.002.M02.T01: a Sleeping status shows Sleeping on the pill."""
    bar = DeskBar(DeskPoller(tmp_path))
    qtbot.addWidget(bar)
    bar.set_status(DeskStatus(DeskState.SLEEPING))
    assert bar.pill.text() == "Sleeping"


def test_allowed_actions_per_state() -> None:
    """UT-GUI-034.003.M02.T01: buttons follow the desk state."""
    expected = {
        DeskState.OFF: {"start"},
        DeskState.STOPPED: {"start"},
        DeskState.ERROR: {"pause", "stop"},
        DeskState.RUNNING: {"pause", "stop"},
        DeskState.SLEEPING: {"pause", "stop"},
        DeskState.PAUSED: {"resume", "stop"},
        DeskState.STOPPING: set(),
    }
    for state, actions in expected.items():
        assert allowed_actions(state, "") == actions
    assert allowed_actions(DeskState.ERROR, "run failed") == {"pause", "stop"}
    assert allowed_actions(DeskState.ERROR, NOT_RESPONDING) == {"start"}


def test_start_does_not_launch_second_desk(
    qtbot: QtBot, tmp_path: Path, monkeypatch: Any
) -> None:
    """UT-GUI-034.003.M02.T02: Start with a Sleeping desk never calls launch."""
    launched: list[bool] = []
    monkeypatch.setattr(desk_control, "read_status", lambda _h=None: DeskStatus(DeskState.SLEEPING))
    monkeypatch.setattr(desk_control, "launch_desk", lambda *a, **k: launched.append(True))
    poller = DeskPoller(tmp_path)
    seen: list[DeskStatus] = []
    poller.status_changed.connect(seen.append)
    poller.start_desk()
    qtbot.waitUntil(lambda: bool(seen), timeout=5000)
    poller.shutdown()
    assert launched == []


def test_commands_sent_in_order(qtbot: QtBot, tmp_path: Path, monkeypatch: Any) -> None:
    """UT-GUI-034.003.M02.T03: pause then stop are both sent, in order, and buttons lock."""
    sent: list[CommandKind] = []
    monkeypatch.setattr(desk_control, "send_command", lambda kind, _h=None: sent.append(kind))
    monkeypatch.setattr(desk_control, "read_status", lambda _h=None: DeskStatus(DeskState.RUNNING))
    poller = DeskPoller(tmp_path)
    bar = DeskBar(poller)
    qtbot.addWidget(bar)
    poller.command(CommandKind.PAUSE)
    poller.command(CommandKind.STOP)
    assert poller.busy
    assert not any(b.isEnabled() for b in bar.buttons.values())
    qtbot.waitUntil(lambda: not poller.busy, timeout=5000)
    poller.shutdown()
    assert sent == [CommandKind.PAUSE, CommandKind.STOP]
    assert bar.buttons["stop"].isEnabled()


def test_failed_command_shows_reason(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.003.M02.T04: sending to a desk that never ran shows a reason on the bar."""
    poller = DeskPoller(tmp_path)
    bar = DeskBar(poller)
    qtbot.addWidget(bar)
    poller.command(CommandKind.PAUSE)
    qtbot.waitUntil(lambda: not poller.busy, timeout=5000)
    poller.shutdown()
    assert bar.note.text() == "Could not send: desk is off"
    assert "desk is off" in bar.pill.toolTip()


def test_app_start_launches_desk_with_pid(
    qtbot: QtBot, tmp_path: Path, monkeypatch: Any
) -> None:
    """UT-GUI-034.068.M02.T01: App start launches the desk with its pid (SRD-GUI-034.068)."""
    launched: list[tuple[bool, int | None]] = []
    monkeypatch.setattr(desk_control, "read_status", lambda _h=None: DeskStatus(DeskState.OFF))
    monkeypatch.setattr(desk_control, "launch_desk",
                        lambda resume=True, parent=None: launched.append((resume, parent)))
    poller = DeskPoller(tmp_path)
    poller.start_desk(parent=99)
    qtbot.waitUntil(lambda: not poller.busy, timeout=5000)
    poller.shutdown()
    assert launched == [(True, 99)]


def test_no_second_desk_at_app_start(qtbot: QtBot, tmp_path: Path, monkeypatch: Any) -> None:
    """UT-GUI-034.068.M02.T02: No second desk (SRD-GUI-034.068)."""
    launched: list[bool] = []
    monkeypatch.setattr(desk_control, "read_status",
                        lambda _h=None: DeskStatus(DeskState.SLEEPING))
    monkeypatch.setattr(desk_control, "launch_desk", lambda *a, **k: launched.append(True))
    poller = DeskPoller(tmp_path)
    poller.start_desk(parent=99)
    qtbot.waitUntil(lambda: not poller.busy, timeout=5000)
    poller.shutdown()
    assert launched == []


def test_close_sends_stop(tmp_path: Path, monkeypatch: Any) -> None:
    """UT-GUI-034.068.M02.T03: Close sends Stop without waiting for the run (SRD-GUI-034.068)."""
    sent: list[CommandKind] = []
    monkeypatch.setattr(desk_control, "read_status",
                        lambda _h=None: DeskStatus(DeskState.RUNNING))
    monkeypatch.setattr(desk_control, "send_command", lambda kind, _h=None: sent.append(kind))
    poller = DeskPoller(tmp_path)
    began = time.monotonic()
    poller.shutdown(stop_desk=True)
    assert sent == [CommandKind.STOP] and time.monotonic() - began < 2.5
    poller.shutdown()
    assert sent == [CommandKind.STOP]
