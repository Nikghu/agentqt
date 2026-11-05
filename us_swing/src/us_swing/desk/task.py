"""
Module: MD-DSK-001.018.M05 — desk/task.py
Parent SRD: SRD-DSK-001.018

Windows tasks that start the desk, and the detached launch used by ``desk start``.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import xml.etree.ElementTree as ET_XML
from collections.abc import Callable
from datetime import date, tzinfo
from pathlib import Path

from us_swing.desk.clock import evening_task_time

log = logging.getLogger(__name__)

# The dev launcher adds src/ to sys.path, so the task works without an installed package.
_RUN_GUI = Path(__file__).resolve().parents[3] / "run_gui.py"
LOGON_TASK = "USSwing_Desk"
EVENING_TASK = "USSwing_Desk_Evening"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)
_XML_DAYS = {
    "Monday": "MON", "Tuesday": "TUE", "Wednesday": "WED", "Thursday": "THU",
    "Friday": "FRI", "Saturday": "SAT", "Sunday": "SUN",
}

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


def desk_command() -> list[str]:
    """Return the command line that runs the desk process."""
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return [str(exe), "desk"]
    pythonw = exe.with_name("pythonw.exe")
    return [str(pythonw if pythonw.exists() else exe), str(_RUN_GUI), "desk"]


def _task_line() -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in desk_command())


def _create_evening(day: date, local: tzinfo, runner: Runner) -> tuple[bool, str]:
    hhmm, days = evening_task_time(day, local)
    return runner(
        "/create", "/tn", EVENING_TASK, "/tr", _task_line(),
        "/sc", "weekly", "/d", ",".join(days), "/st", hhmm, "/f",
    )


def install(day: date, local: tzinfo, runner: Runner = run_schtasks) -> tuple[bool, str]:
    """Create the logon task and the evening task.

    Returns:
        (True, "") on success, else (False, the first error message).
    """
    ok, msg = runner("/create", "/tn", LOGON_TASK, "/tr", _task_line(), "/sc", "onlogon", "/f")
    if not ok:
        return False, msg
    ok, msg = _create_evening(day, local, runner)
    return (True, "") if ok else (False, msg)


def uninstall(runner: Runner = run_schtasks) -> tuple[bool, str]:
    """Delete both desk tasks; a task that is already gone is not an error."""
    errors = []
    for name in (LOGON_TASK, EVENING_TASK):
        ok, msg = runner("/delete", "/tn", name, "/f")
        if not ok and "cannot find" not in msg.lower():
            errors.append(msg)
    return (not errors), "; ".join(errors)


def _task_schedule(xml_text: str) -> tuple[str, list[str]] | None:
    try:
        root = ET_XML.fromstring(xml_text.strip())
    except ET_XML.ParseError:
        return None
    start = next((el.text for el in root.iter() if el.tag.endswith("StartBoundary")), None)
    days = [
        _XML_DAYS[name]
        for el in root.iter()
        if el.tag.endswith("DaysOfWeek")
        for child in el
        if (name := child.tag.rsplit("}", 1)[-1]) in _XML_DAYS
    ]
    if not start or "T" not in start:
        return None
    return start.split("T", 1)[1][:5], days


def sync_evening_task(day: date, local: tzinfo, runner: Runner = run_schtasks) -> bool:
    """Re-create the evening task when its time or days no longer match; True if changed."""
    ok, xml_text = runner("/query", "/tn", EVENING_TASK, "/xml")
    if not ok:
        return False
    current = _task_schedule(xml_text)
    hhmm, days = evening_task_time(day, local)
    if current is not None and current[0] == hhmm and sorted(current[1]) == sorted(days):
        return False
    ok, msg = _create_evening(day, local, runner)
    if ok:
        log.info("[Desk] Evening task moved to %s local time", hhmm)
    else:
        log.warning("[Desk] Could not update the evening task: %s", msg)
    return ok


def launch(resume: bool = True) -> None:
    """Start the desk as a detached process with no console window."""
    cmd = desk_command() + (["--resume"] if resume else [])
    subprocess.Popen(  # noqa: S603 — fixed command built from our own executable
        cmd, creationflags=_DETACHED | _NO_WINDOW, close_fds=True
    )
