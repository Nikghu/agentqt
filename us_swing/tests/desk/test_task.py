"""Tests for MD-DSK-001.018.M05 — desk/task.py, and the desk launch in core/desk_contract.py."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from us_swing.core import desk_contract
from us_swing.core.desk_contract import desk_command, launch_desk
from us_swing.desk import task


class FakeRunner:
    """Records schtasks calls and returns set answers by task name."""

    def __init__(self, answers: dict[str, tuple[bool, str]] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._answers = answers or {}

    def __call__(self, *args: str) -> tuple[bool, str]:
        self.calls.append(args)
        return self._answers.get(args[2], (True, ""))


def test_desk_command_not_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-001.018.M05.T01: Desk command when not frozen."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    cmd = desk_command()
    assert cmd[1].endswith("run_gui.py") and Path(cmd[1]).exists()
    assert cmd[2] == "desk"
    assert cmd[0].lower().endswith(("pythonw.exe", "python.exe"))


def test_desk_command_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-001.018.M05.T02: Desk command when frozen."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert desk_command() == [sys.executable, "desk"]


def test_old_tasks_deleted() -> None:
    """UT-DSK-001.018.M05.T03: Old desk tasks deleted (SRD-DSK-001.018)."""
    runner = FakeRunner()
    assert task.remove_old_tasks(runner) == (True, "")
    assert runner.calls == [("/delete", "/tn", "USSwing_Desk", "/f"),
                            ("/delete", "/tn", "USSwing_Desk_Evening", "/f")]


def test_missing_task_is_not_an_error() -> None:
    """UT-DSK-001.018.M05.T04: Missing task is not an error; other failure is."""
    gone = (False, "ERROR: The system cannot find the file specified.")
    assert task.remove_old_tasks(FakeRunner({"USSwing_Desk": gone,
                                             "USSwing_Desk_Evening": gone})) == (True, "")
    denied = FakeRunner({"USSwing_Desk_Evening": (False, "access denied")})
    assert task.remove_old_tasks(denied) == (False, "access denied")


def _record_popen(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    seen: list[list[str]] = []

    def fake_popen(cmd: list[str], **_kw: Any) -> None:
        seen.append(cmd)

    monkeypatch.setattr(desk_contract.subprocess, "Popen", fake_popen)
    return seen


def test_launch_passes_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-001.018.M05.T05: Launch passes the parent pid (SRD-DSK-001.019, .020)."""
    seen = _record_popen(monkeypatch)
    launch_desk(True, parent=1234)
    assert seen[0][-3:] == ["--resume", "--parent", "1234"]


def test_launch_without_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-001.018.M05.T06: Launch without a parent (SRD-DSK-001.020)."""
    seen = _record_popen(monkeypatch)
    launch_desk(True)
    assert seen[0][-1] == "--resume" and "--parent" not in seen[0]
