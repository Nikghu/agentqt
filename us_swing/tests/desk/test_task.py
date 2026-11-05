"""Tests for MD-DSK-001.018.M05 — desk/task.py."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from us_swing.desk import task

IST = ZoneInfo("Asia/Kolkata")
DAY = date(2026, 11, 5)


class FakeRunner:
    """Records schtasks calls and returns set answers."""

    def __init__(self, answers: dict[str, tuple[bool, str]] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._answers = answers or {}

    def __call__(self, *args: str) -> tuple[bool, str]:
        self.calls.append(args)
        return self._answers.get(args[0], (True, ""))


def _xml(start: str, days: list[str]) -> str:
    day_tags = "".join(f"<{d}/>" for d in days)
    return (
        '<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Triggers>'
        f"<CalendarTrigger><StartBoundary>2026-11-05T{start}:00</StartBoundary>"
        f"<ScheduleByWeek><DaysOfWeek>{day_tags}</DaysOfWeek></ScheduleByWeek>"
        "</CalendarTrigger></Triggers></Task>"
    )


_TUE_SAT = ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def test_desk_command_not_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-001.018.M05.T01: Desk command when not frozen."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    cmd = task.desk_command()
    assert cmd[1].endswith("run_gui.py") and Path(cmd[1]).exists()
    assert cmd[2] == "desk"
    assert cmd[0].lower().endswith(("pythonw.exe", "python.exe"))


def test_desk_command_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-001.018.M05.T02: Desk command when frozen."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert task.desk_command() == [sys.executable, "desk"]


def test_install_creates_two_tasks() -> None:
    """UT-DSK-001.018.M05.T03: Install creates two tasks."""
    runner = FakeRunner()
    assert task.install(DAY, IST, runner) == (True, "")
    logon, evening = runner.calls
    assert task.LOGON_TASK in logon and "onlogon" in logon
    assert task.EVENING_TASK in evening and "weekly" in evening
    assert "02:50" in evening and "TUE,WED,THU,FRI,SAT" in evening


def test_install_reports_failure() -> None:
    """UT-DSK-001.018.M05.T04: Install reports schtasks failure."""
    runner = FakeRunner({"/create": (False, "Access is denied.")})
    assert task.install(DAY, IST, runner) == (False, "Access is denied.")


def test_sync_recreates_on_mismatch() -> None:
    """UT-DSK-001.018.M05.T05: Sync re-creates on mismatch."""
    runner = FakeRunner({"/query": (True, _xml("01:50", _TUE_SAT))})
    assert task.sync_evening_task(DAY, IST, runner) is True
    creates = [c for c in runner.calls if c[0] == "/create"]
    assert len(creates) == 1 and "02:50" in creates[0]
    matching = FakeRunner({"/query": (True, _xml("02:50", _TUE_SAT))})
    assert task.sync_evening_task(DAY, IST, matching) is False


def test_sync_skips_when_not_installed() -> None:
    """UT-DSK-001.018.M05.T06: Sync skips when not installed."""
    runner = FakeRunner({"/query": (False, "ERROR: The system cannot find the file specified.")})
    assert task.sync_evening_task(DAY, IST, runner) is False
    assert [c for c in runner.calls if c[0] == "/create"] == []

