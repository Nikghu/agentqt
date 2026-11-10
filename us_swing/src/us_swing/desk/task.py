"""
Module: MD-DSK-001.018.M05 — desk/task.py
Parent SRD: SRD-DSK-001.018

The desk has no Windows tasks of its own: it lives with the app. This module deletes the
old desk tasks once and launches a detached desk for ``desk start``.
"""
from __future__ import annotations

import subprocess
from collections.abc import Callable

from us_swing.core.desk_contract import launch_desk

OLD_TASKS = ("USSwing_Desk", "USSwing_Desk_Evening")
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

Runner = Callable[..., tuple[bool, str]]


def run_schtasks(*args: str) -> tuple[bool, str]:
    """Run ``schtasks.exe`` with no console window; return (ok, output or error)."""
    try:
        result = subprocess.run(
            ["schtasks", *args],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, (result.stderr.strip() or result.stdout.strip())


def remove_old_tasks(runner: Runner = run_schtasks) -> tuple[bool, str]:
    """Delete the old desk tasks; a task that is already gone is not an error."""
    errors = []
    for name in OLD_TASKS:
        ok, msg = runner("/delete", "/tn", name, "/f")
        if not ok and "cannot find" not in msg.lower():
            errors.append(msg)
    return (not errors), "; ".join(errors)


def launch(resume: bool = True, parent: int | None = None) -> None:
    """Start the desk as a detached process with no console window."""
    launch_desk(resume, parent)
