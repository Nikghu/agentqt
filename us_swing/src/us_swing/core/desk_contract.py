"""
Module: MD-DSK-001.004.M01 — core/desk_contract.py
Parent SRD: SRD-DSK-001.004

Shared desk types, a read-only status reader and the command sender. The app uses
only this module to talk to the desk process, so ``gui`` never imports ``desk``.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

SCHEMA_VERSION = 1
DB_NAME = "desk.db"
STALE_AFTER_S = 60.0


class DeskState(str, Enum):
    """The seven desk states."""

    RUNNING = "Running"
    SLEEPING = "Sleeping"
    PAUSED = "Paused"
    STOPPING = "Stopping"
    STOPPED = "Stopped"
    OFF = "Off"
    ERROR = "Error"


LIVE_STATES = frozenset(
    {DeskState.RUNNING, DeskState.SLEEPING, DeskState.PAUSED, DeskState.STOPPING, DeskState.ERROR}
)


class CommandKind(str, Enum):
    """Commands the app may send to the desk."""

    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    RUN_NOW = "run_now"


@dataclass(frozen=True)
class DeskStatus:
    """What the app shows about the desk."""

    state: DeskState
    message: str = ""
    heartbeat_at: datetime | None = None
    pid: int | None = None


@dataclass(frozen=True)
class StepContext:
    """Passed to every desk step during a run."""

    run_id: int
    kind: str
    started_at: datetime


class DeskStep(Protocol):
    """One unit of work in a desk run (added by tools such as MKT)."""

    name: str

    def __call__(self, ctx: StepContext) -> None: ...


def desk_home() -> Path:
    """Default desk folder: ``~/.usswing/desk``."""
    return Path.home() / ".usswing" / "desk"


def utc_text(moment: datetime) -> str:
    """Store a time-zone-aware moment as UTC ISO text.

    Raises:
        ValueError: When ``moment`` has no time zone.
    """
    if moment.tzinfo is None:
        raise ValueError("desk times must carry a time zone")
    return moment.astimezone(UTC).isoformat()


def parse_utc(text: str | None) -> datetime | None:
    """Read UTC ISO text back, or ``None``."""
    return datetime.fromisoformat(text) if text else None


@contextmanager
def _read_only(path: Path) -> Generator[sqlite3.Connection, None, None]:
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=5)
    try:
        yield con
    finally:
        con.close()


def read_status(home: Path | None = None, now: datetime | None = None) -> DeskStatus:
    """Return the desk status without creating or changing anything.

    Args:
        home: Desk folder; defaults to :func:`desk_home`.
        now: Current time (time-zone aware); defaults to now in UTC.

    Returns:
        Off when there is no data, Error when a live state has a stale heartbeat.
    """
    path = (home or desk_home()) / DB_NAME
    if not path.exists():
        return DeskStatus(DeskState.OFF)
    try:
        with _read_only(path) as con:
            row = con.execute(
                "SELECT state, message, heartbeat_at, pid FROM desk_state WHERE id = 1"
            ).fetchone()
    except sqlite3.Error:
        return DeskStatus(DeskState.OFF)
    if row is None:
        return DeskStatus(DeskState.OFF)
    beat = parse_utc(row[2])
    try:
        state = DeskState(row[0])
    except ValueError:
        return DeskStatus(DeskState.ERROR, "unknown state", beat, row[3])
    now = now or datetime.now(UTC)
    if state in LIVE_STATES and (beat is None or (now - beat).total_seconds() > STALE_AFTER_S):
        return DeskStatus(DeskState.ERROR, "not responding", beat, row[3])
    return DeskStatus(state, row[1] or "", beat, row[3])


def send_command(kind: CommandKind, home: Path | None = None) -> int:
    """Add a pending command for the desk and return its id.

    Raises:
        FileNotFoundError: When the desk has never run (no ``desk.db``).
    """
    path = (home or desk_home()) / DB_NAME
    if not path.exists():
        raise FileNotFoundError(path)
    con = sqlite3.connect(f"{path.as_uri()}?mode=rw", uri=True, timeout=5)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO commands (kind, created_at, status) VALUES (?, ?, 'pending')",
                (kind.value, utc_text(datetime.now(UTC))),
            )
        return int(cur.lastrowid or 0)
    finally:
        con.close()
