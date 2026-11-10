"""
Module: MD-DSK-001.020.M06 — desk/cli.py
Parent SRD: SRD-DSK-001.020
Also: SRD-DSK-001.022 — ``desk proof``; SRD-DSK-005.005 — ``desk replay``;
SRD-DSK-008.008 — ``desk replay --draft FILE --out FILE``;
SRD-DSK-003.008 — the desk loop gets the event handler

``python -m us_swing desk [sub-command]``. With no sub-command the desk process runs.
"""
from __future__ import annotations

import json
from collections.abc import Callable
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
from us_swing.core.desk_employee import parse
from us_swing.core.desk_steps import load_proof, load_steps
from us_swing.desk import task
from us_swing.desk.process import DeskProcess, EventHandler
from us_swing.desk.replay import replay, report

USAGE = (
    "usage: desk [--resume] | desk start | status | pause | resume | stop | run-now"
    " | install | uninstall | proof | replay RUN [--employee ID] [--model NAME]"
    " [--draft FILE --out FILE]"
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


def main(
    argv: list[str],
    home: Path | None = None,
    proof: Callable[[], Callable[[Path], str | None]] = load_proof,
) -> int:
    """Run a desk sub-command and return the exit code; ``proof`` loads the proof runner."""
    home = home or desk_home()
    if not argv or argv == ["--resume"]:
        steps = load_steps()
        events = next((s for s in steps if isinstance(s, EventHandler)), None)
        return DeskProcess(
            home, steps, resume=bool(argv), daily_check=_sync_task, events=events
        ).run()
    name = argv[0]
    if name == "replay":
        return _replay(argv[1:], home)
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
    if name == "proof":
        report = proof()(home)
        if report is None:
            print("No daily candles to test; download them in Settings > Backtest Data")
            return 1
        print(report)
        return 0
    print(USAGE)
    return 2


def _replay(args: list[str], home: Path) -> int:
    if not args or not args[0].isdigit():
        print(USAGE)
        return 2
    options = dict(zip(args[1::2], args[2::2], strict=False))
    if set(options) - {"--employee", "--model", "--draft", "--out"} or len(args[1:]) % 2:
        print(USAGE)
        return 2
    run_id = int(args[0])
    if "--draft" in options:
        return _draft(home, run_id, options)
    lines = replay(home, run_id, options.get("--employee"), options.get("--model"))
    if lines is None:
        print(f"Desk run {run_id} has no recorded AI tries")
        return 1
    print(report(run_id, lines))
    return 0


def _draft(home: Path, run_id: int, options: dict[str, str]) -> int:
    out = Path(options.get("--out") or "draft-result.json")
    try:
        draft = parse(Path(options["--draft"]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        out.write_text(json.dumps({"valid": False, "note": str(exc)}), encoding="utf-8")
        return 1
    lines = replay(home, run_id, options.get("--employee") or draft.spec.id,
                   options.get("--model"), draft=draft) or []
    line = lines[0] if lines else None
    result = {"valid": bool(line and line.new_valid), "answer": line.answer if line else "",
              "note": (line.note if line else "no recorded AI tries in that run")}
    out.write_text(json.dumps(result), encoding="utf-8")
    return 0


def _send(kind: CommandKind, home: Path) -> int:
    status = read_status(home)
    if not _is_alive(status.state, status.message):
        print(f"Desk is {status.state.value.lower()}")
        return 1
    send_command(kind, home)
    print(f"Sent {kind.value.replace('_', '-')} to the desk")
    return 0
