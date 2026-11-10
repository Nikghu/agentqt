"""
Module: MD-DSK-001.004.M01 — core/desk_contract.py
Parent SRD: SRD-DSK-001.004

Shared desk types, a read-only status reader and the command sender. The app uses
only this module to talk to the desk process, so ``gui`` never imports ``desk``.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

SCHEMA_VERSION = 1
DB_NAME = "desk.db"
STALE_AFTER_S = 60.0
EVENING_RUN = time(16, 25)  # New York time, Monday to Friday
NOT_RESPONDING = "not responding"
# The dev launcher adds src/ to sys.path, so the desk starts without an installed package.
_RUN_GUI = Path(__file__).resolve().parents[3] / "run_gui.py"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)


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
    home: Path | None = None


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
        return DeskStatus(DeskState.ERROR, NOT_RESPONDING, beat, row[3])
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


def desk_command() -> list[str]:
    """Return the command line that runs the desk process."""
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return [str(exe), "desk"]
    pythonw = exe.with_name("pythonw.exe")
    return [str(pythonw if pythonw.exists() else exe), str(_RUN_GUI), "desk"]


def launch_desk(resume: bool = True) -> None:
    """Start the desk as a detached process with no console window."""
    cmd = desk_command() + (["--resume"] if resume else [])
    subprocess.Popen(  # noqa: S603 — fixed command built from our own executable
        cmd, creationflags=_DETACHED | _NO_WINDOW, close_fds=True
    )


# ── Market Floor data interface (MD-GUI-034.003.M09) ─────────────────────────


@dataclass(frozen=True)
class ProductDescriptor:
    """One desk output the Market Floor can show as a panel."""

    id: str
    title: str
    kind: str
    views: tuple[str, ...] = ("table",)
    columns: tuple[str, ...] = ()
    filters: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    sample: bool = False


class FloorData(Protocol):
    """Where Market Floor panels get their products and rows."""

    def products(self) -> Sequence[ProductDescriptor]: ...

    def rows(
        self, product_id: str, filters: Mapping[str, str]
    ) -> list[dict[str, Any]]: ...
