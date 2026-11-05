"""
Module: MD-DSK-001.001.M02 — desk/store.py
Parent SRD: SRD-DSK-001.001

The desk process's only connection to ``desk.db``: tables, state, heartbeat,
commands and runs.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from us_swing.core.desk_contract import DB_NAME, SCHEMA_VERSION, DeskState, parse_utc, utc_text

_SCHEMA = """
CREATE TABLE IF NOT EXISTS desk_state (
    id INTEGER PRIMARY KEY CHECK (id = 1), state TEXT NOT NULL, heartbeat_at TEXT,
    pid INTEGER, message TEXT, resume_point TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, created_at TEXT NOT NULL,
    status TEXT NOT NULL, done_at TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, started_at TEXT NOT NULL,
    ended_at TEXT, result TEXT NOT NULL, note TEXT
);
"""


@dataclass(frozen=True)
class Command:
    """A pending command row."""

    id: int
    kind: str


@dataclass(frozen=True)
class SavedState:
    """The stored ``desk_state`` row."""

    state: DeskState
    resume_point: dict[str, Any]


class DeskStore:
    """Read and write ``desk.db`` for the desk process."""

    def __init__(self, home: Path) -> None:
        """Open (and create when needed) ``desk.db`` in ``home``.

        Raises:
            OSError: When ``home`` cannot be used as a folder.
            ValueError: When the file was made by a newer app version.
        """
        home.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(home / DB_NAME, timeout=5)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA busy_timeout=5000")
        version = int(self._con.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            self._con.close()
            raise ValueError("newer desk data: update the app")
        with self._con:
            self._con.executescript(_SCHEMA)
            self._con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        """Close the connection."""
        self._con.close()

    # ── state ─────────────────────────────────────────────────────────────

    def saved_state(self) -> SavedState | None:
        """Return the stored state row, or ``None`` before the first write."""
        row = self._con.execute(
            "SELECT state, resume_point FROM desk_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return SavedState(DeskState(row[0]), json.loads(row[1]) if row[1] else {})

    def set_state(
        self, state: DeskState, now: datetime, message: str = "", pid: int | None = None
    ) -> None:
        """Write the state, message and heartbeat; keep the saved resume point."""
        stamp = utc_text(now)
        with self._con:
            self._con.execute(
                "INSERT INTO desk_state (id, state, heartbeat_at, pid, message, updated_at) "
                "VALUES (1, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET state = excluded.state, "
                "heartbeat_at = excluded.heartbeat_at, pid = COALESCE(excluded.pid, pid), "
                "message = excluded.message, updated_at = excluded.updated_at",
                (state.value, stamp, pid, message, stamp),
            )

    def beat(self, now: datetime) -> None:
        """Write the heartbeat time."""
        with self._con:
            self._con.execute(
                "UPDATE desk_state SET heartbeat_at = ? WHERE id = 1", (utc_text(now),)
            )

    def heartbeat_at(self) -> datetime | None:
        """Return the stored heartbeat time."""
        row = self._con.execute("SELECT heartbeat_at FROM desk_state WHERE id = 1").fetchone()
        return parse_utc(row[0]) if row else None

    def save_resume_point(self, point: dict[str, Any]) -> None:
        """Store the resume point as JSON."""
        with self._con:
            self._con.execute(
                "UPDATE desk_state SET resume_point = ? WHERE id = 1", (json.dumps(point),)
            )

    # ── commands ──────────────────────────────────────────────────────────

    def pending_commands(self) -> list[Command]:
        """Return pending commands, oldest first."""
        rows = self._con.execute(
            "SELECT id, kind FROM commands WHERE status = 'pending' ORDER BY id"
        ).fetchall()
        return [Command(int(r[0]), str(r[1])) for r in rows]

    def finish_command(self, command_id: int, ok: bool, now: datetime, note: str = "") -> None:
        """Mark a command done or rejected."""
        with self._con:
            self._con.execute(
                "UPDATE commands SET status = ?, done_at = ?, note = ? WHERE id = ?",
                ("done" if ok else "rejected", utc_text(now), note, command_id),
            )

    # ── runs ──────────────────────────────────────────────────────────────

    def start_run(self, kind: str, now: datetime) -> int:
        """Insert a running run row and return its id."""
        with self._con:
            cur = self._con.execute(
                "INSERT INTO runs (kind, started_at, result) VALUES (?, ?, 'running')",
                (kind, utc_text(now)),
            )
        return int(cur.lastrowid or 0)

    def end_run(self, run_id: int, result: str, now: datetime, note: str = "") -> None:
        """Close a run with ``ok``, ``failed`` or ``interrupted``."""
        with self._con:
            self._con.execute(
                "UPDATE runs SET ended_at = ?, result = ?, note = ? WHERE id = ?",
                (utc_text(now), result, note, run_id),
            )

    def interrupt_open_runs(self, now: datetime) -> int:
        """Mark every run with no end as interrupted; return how many."""
        with self._con:
            cur = self._con.execute(
                "UPDATE runs SET ended_at = ?, result = 'interrupted' WHERE ended_at IS NULL",
                (utc_text(now),),
            )
        return cur.rowcount

    def last_run_start(self, kind: str) -> datetime | None:
        """Return the start of the newest run of ``kind``."""
        row = self._con.execute(
            "SELECT started_at FROM runs WHERE kind = ? ORDER BY id DESC LIMIT 1", (kind,)
        ).fetchone()
        return parse_utc(row[0]) if row else None

    def last_run_id(self) -> int | None:
        """Return the newest run id."""
        row = self._con.execute("SELECT MAX(id) FROM runs").fetchone()
        return int(row[0]) if row and row[0] is not None else None
