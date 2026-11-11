"""
Module: MD-DSK-001.020.M06 — desk/cli.py
Parent SRD: SRD-DSK-001.020
Also: SRD-DSK-001.022 — ``desk proof``; SRD-DSK-005.005 — ``desk replay``;
SRD-DSK-008.008 — ``desk replay --draft FILE --out FILE``;
SRD-DSK-003.008 — the desk loop gets the event handler;
SRD-DSK-001.019 — ``--parent PID`` gives the loop a parent watch;
SRD-DSK-003.023 — the desk loop gets the market watchers

``python -m us_swing desk [sub-command]``. With no sub-command the desk process runs.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from functools import partial
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
from us_swing.core.desk_steps import load_proof, load_steps, load_watch
from us_swing.desk import task
from us_swing.desk.process import DeskProcess, EventHandler, pid_alive
from us_swing.desk.replay import replay, report

log = logging.getLogger(__name__)

USAGE = (
    "usage: desk [--resume] [--parent PID] | desk start | status | pause | resume | stop"
    " | run-now | proof | replay RUN [--employee ID] [--model NAME]"
    " [--draft FILE --out FILE]"
)
_COMMANDS = {
    "pause": CommandKind.PAUSE,
    "resume": CommandKind.RESUME,
    "stop": CommandKind.STOP,
    "run-now": CommandKind.RUN_NOW,
}


def _remove_old_tasks() -> None:
    ok, msg = task.remove_old_tasks()
    if not ok:
        log.warning("[Desk] Could not delete the old desk Windows tasks: %s", msg)


def _run_options(argv: list[str]) -> tuple[bool, int | None] | None:
    """Return (resume, parent pid) for ``[--resume] [--parent PID]``, or ``None`` if bad."""
    resume, parent, rest = False, None, list(argv)
    while rest:
        flag = rest.pop(0)
        if flag == "--resume":
            resume = True
        elif flag == "--parent" and rest and rest[0].isdigit():
            parent = int(rest.pop(0))
        else:
            return None
    return resume, parent


def _is_alive(state: DeskState, message: str) -> bool:
    return state in LIVE_STATES and message != NOT_RESPONDING


def main(
    argv: list[str],
    home: Path | None = None,
    proof: Callable[[], Callable[[Path], str | None]] = load_proof,
    process: Callable[..., DeskProcess] = DeskProcess,
    watch: Callable[[], Callable[[Path, datetime], int]] = load_watch,
) -> int:
    """Run a desk sub-command and return the exit code.

    ``proof`` loads the proof runner; ``process`` builds the desk loop (a fake in tests).
    """
    home = home or desk_home()
    if not argv or argv[0].startswith("--"):
        options = _run_options(argv)
        if options is None:
            print(USAGE)
            return 2
        resume, parent = options
        steps = load_steps()
        events = next((s for s in steps if isinstance(s, EventHandler)), None)
        return process(
            home, steps, resume=resume, daily_check=_remove_old_tasks, events=events,
            parent_alive=None if parent is None else partial(pid_alive, parent),
            watch=watch(),
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
