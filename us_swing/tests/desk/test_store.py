"""Tests for MD-DSK-001.001.M02 — desk/store.py."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.desk.conftest import THU_1500_ET
from us_swing.core.desk_contract import DeskState
from us_swing.desk.store import DeskStore


def test_wal_mode_on_open(home: Path) -> None:
    """UT-DSK-001.001.M02.T01: WAL mode on open."""
    s = DeskStore(home)
    mode = s._con.execute("PRAGMA journal_mode").fetchone()[0]
    s.close()
    assert mode == "wal"
    assert (home / "desk.db").exists()


def test_tables_and_version(store: DeskStore) -> None:
    """UT-DSK-001.001.M02.T02: Tables and version."""
    names = {r[0] for r in store._con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"desk_state", "commands", "runs"} <= names
    assert store._con.execute("PRAGMA user_version").fetchone()[0] == 1


def test_reopen_keeps_rows(home: Path) -> None:
    """UT-DSK-001.001.M02.T03: Re-open keeps rows."""
    s = DeskStore(home)
    s.set_state(DeskState.PAUSED, THU_1500_ET)
    s.close()
    s = DeskStore(home)
    saved = s.saved_state()
    s.close()
    assert saved is not None and saved.state is DeskState.PAUSED


def test_write_state_and_heartbeat(store: DeskStore) -> None:
    """UT-DSK-001.001.M02.T04: Write state and heartbeat."""
    store.set_state(DeskState.SLEEPING, THU_1500_ET)
    later = THU_1500_ET + timedelta(seconds=10)
    store.beat(later)
    row = store._con.execute("SELECT state, heartbeat_at FROM desk_state").fetchone()
    assert row[0] == "Sleeping"
    assert row[1] == later.isoformat()
    assert store.heartbeat_at() == later


def test_resume_point_round_trip(store: DeskStore) -> None:
    """UT-DSK-001.001.M02.T05: Resume point round trip."""
    store.set_state(DeskState.STOPPED, THU_1500_ET)
    store.save_resume_point({"last_run_id": 3, "rerun": True})
    saved = store.saved_state()
    assert saved is not None
    assert saved.resume_point == {"last_run_id": 3, "rerun": True}


def test_run_row_life(store: DeskStore) -> None:
    """UT-DSK-001.001.M02.T06: Run row life."""
    run_id = store.start_run("evening", THU_1500_ET)
    store.end_run(run_id, "ok", THU_1500_ET + timedelta(minutes=1))
    row = store._con.execute(
        "SELECT kind, started_at, ended_at, result FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row[0] == "evening" and row[1] and row[2] and row[3] == "ok"


def test_open_runs_marked_interrupted(store: DeskStore) -> None:
    """UT-DSK-001.001.M02.T07: Open runs marked interrupted."""
    run_id = store.start_run("evening", THU_1500_ET)
    assert store.interrupt_open_runs(THU_1500_ET) == 1
    row = store._con.execute("SELECT result, ended_at FROM runs WHERE id = ?", (run_id,)).fetchone()
    assert row[0] == "interrupted" and row[1]


def test_pending_commands_in_order(store: DeskStore, home: Path) -> None:
    """UT-DSK-001.001.M02.T08: Pending commands in order."""
    with store._con:
        for kind in ("pause", "resume", "stop"):
            store._con.execute(
                "INSERT INTO commands (kind, created_at, status) VALUES (?, 'x', 'pending')",
                (kind,),
            )
    cmds = store.pending_commands()
    assert [c.kind for c in cmds] == ["pause", "resume", "stop"]
    store.finish_command(cmds[0].id, True, THU_1500_ET)
    row = store._con.execute("SELECT status, done_at FROM commands WHERE id = ?", (cmds[0].id,))
    status, done_at = row.fetchone()
    assert status == "done" and done_at
    assert len(store.pending_commands()) == 2


def test_root_path_is_a_file(tmp_path: Path) -> None:
    """UT-DSK-001.001.M02.T09: Root path is a file."""
    blocker = tmp_path / "desk"
    blocker.write_text("x")
    with pytest.raises(OSError):
        DeskStore(blocker)
    assert blocker.read_text() == "x"


def test_newer_schema_refused(home: Path) -> None:
    """UT-DSK-001.001.M02.T10: Newer schema refused."""
    home.mkdir(parents=True)
    con = sqlite3.connect(home / "desk.db")
    con.execute("PRAGMA user_version = 2")
    con.close()
    with pytest.raises(ValueError, match="newer desk data"):
        DeskStore(home)


def test_naive_time_refused(store: DeskStore) -> None:
    """UT-DSK-001.001.M02.T11: Naive time refused."""
    with pytest.raises(ValueError):
        store.set_state(DeskState.SLEEPING, datetime(2026, 11, 5, 15, 0))
