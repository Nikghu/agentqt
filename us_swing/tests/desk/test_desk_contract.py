"""Tests for MD-DSK-001.004.M01 — core/desk_contract.py."""
from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from tests.desk.conftest import THU_1500_ET
from us_swing.core.desk_contract import (
    CommandKind,
    DeskState,
    read_status,
    send_command,
)
from us_swing.desk.store import DeskStore


def _db(home: Path) -> Path:
    return home / "desk.db"


def test_seven_states() -> None:
    """UT-DSK-001.004.M01.T01: Seven states exist."""
    assert [s.value for s in DeskState] == [
        "Running", "Sleeping", "Paused", "Stopping", "Stopped", "Off", "Error",
    ]


def test_off_when_no_file(home: Path) -> None:
    """UT-DSK-001.004.M01.T02: Off when no file."""
    assert read_status(home).state is DeskState.OFF
    assert not _db(home).exists()


def test_off_when_no_state_row(store: DeskStore, home: Path) -> None:
    """UT-DSK-001.004.M01.T03: Off when no state row."""
    assert read_status(home).state is DeskState.OFF


def test_fresh_heartbeat(store: DeskStore, home: Path) -> None:
    """UT-DSK-001.004.M01.T04: Live state with fresh heartbeat."""
    store.set_state(DeskState.SLEEPING, THU_1500_ET)
    status = read_status(home, THU_1500_ET + timedelta(seconds=5))
    assert status.state is DeskState.SLEEPING


def test_stale_heartbeat(store: DeskStore, home: Path) -> None:
    """UT-DSK-001.004.M01.T05: Stale heartbeat."""
    store.set_state(DeskState.SLEEPING, THU_1500_ET)
    status = read_status(home, THU_1500_ET + timedelta(seconds=61))
    assert status.state is DeskState.ERROR
    assert status.message == "not responding"


def test_stopped_never_stale(store: DeskStore, home: Path) -> None:
    """UT-DSK-001.004.M01.T06: Stopped never stale."""
    store.set_state(DeskState.STOPPED, THU_1500_ET)
    assert read_status(home, THU_1500_ET + timedelta(days=1)).state is DeskState.STOPPED


def test_send_command_adds_pending_row(store: DeskStore, home: Path) -> None:
    """UT-DSK-001.004.M01.T07: Send command adds pending row."""
    send_command(CommandKind.PAUSE, home)
    cmds = store.pending_commands()
    assert len(cmds) == 1
    assert cmds[0].kind == "pause"


def test_send_command_with_no_desk(home: Path) -> None:
    """UT-DSK-001.004.M01.T08: Send command with no desk."""
    with pytest.raises(FileNotFoundError):
        send_command(CommandKind.STOP, home)
    assert not _db(home).exists()


def test_unknown_state_text(store: DeskStore, home: Path) -> None:
    """UT-DSK-001.004.M01.T09: Unknown state text."""
    store.set_state(DeskState.SLEEPING, THU_1500_ET)
    con = sqlite3.connect(_db(home))
    with con:
        con.execute("UPDATE desk_state SET state = 'Dancing'")
    con.close()
    status = read_status(home, THU_1500_ET)
    assert status.state is DeskState.ERROR
    assert status.message == "unknown state"
