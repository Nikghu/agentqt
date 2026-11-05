"""
Module: MD-DSK-001.020.M06 — desk/cli.py
Parent SRD: SRD-DSK-001.020

``python -m us_swing desk [sub-command]``. With no sub-command the desk process runs.
"""
from __future__ import annotations

from datetime import date, datetime, tzinfo
from pathlib import Path

from us_swing.core.desk_contract import (
    LIVE_STATES,
    NOT_RESPONDING,
    CommandKind,
    DeskState,
    desk_home,
    read_status,
    send_command,
)
from us_swing.core.desk_steps import load_steps
from us_swing.desk import task
from us_swing.desk.process import DeskProcess

USAGE = (
    "usage: desk [--resume] | desk start | status | pause | resume | stop | run-now"
    " | install | uninstall"
)
_COMMANDS = {
    "pause": CommandKind.PAUSE,
    "resume": CommandKind.RESUME,
    "stop": CommandKind.STOP,
    "run-now": CommandKind.RUN_NOW,
}


def _local_tz() -> tzinfo:
    zone = datetime.now().astimezone().tzinfo
    if zone is None:
        raise RuntimeError("no local time zone")
    return zone


def _sync_task() -> None:
    task.sync_evening_task(date.today(), _local_tz())


def _is_alive(state: DeskState, message: str) -> bool:
    return state in LIVE_STATES and message != NOT_RESPONDING


def main(argv: list[str], home: Path | None = None) -> int:
    """Run a desk sub-command and return the exit code."""
    home = home or desk_home()
    if not argv or argv == ["--resume"]:
        return DeskProcess(
            home, load_steps(), resume=bool(argv), daily_check=_sync_task
        ).run()
    name = argv[0]
    if name == "status":
        status = read_status(home)
        print(f"Desk is {status.state.value}" + (f": {status.message}" if status.message else ""))
        return 0
    if name in _COMMANDS:
        return _send(_COMMANDS[name], home)
    if name == "start":
        status = read_status(home)
        if _is_alive(status.state, status.message):
            print("Desk is already running")
            return 0
        task.launch(resume=True)
        print("Desk is starting")
        return 0
    if name == "install":
        ok, msg = task.install(date.today(), _local_tz())
        print("Desk tasks installed" if ok else f"Could not install desk tasks: {msg}")
        return 0 if ok else 1
    if name == "uninstall":
        ok, msg = task.uninstall()
        print("Desk tasks removed" if ok else f"Could not remove desk tasks: {msg}")
        return 0 if ok else 1
    print(USAGE)
    return 2


def _send(kind: CommandKind, home: Path) -> int:
    status = read_status(home)
    if not _is_alive(status.state, status.message):
        print(f"Desk is {status.state.value.lower()}")
        return 1
    send_command(kind, home)
    print(f"Sent {kind.value.replace('_', '-')} to the desk")
    return 0
