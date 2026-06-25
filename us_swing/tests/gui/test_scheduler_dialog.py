"""
Tests for scheduler_dialog auto-close task creation.
Module under test: MD-GUI-000.004 — scheduler_dialog.py
"""
from __future__ import annotations

import pytest

from us_swing.gui import scheduler_dialog as sd
from us_swing.gui.scheduler_store import SchedulerConfig, USSwingConfig


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    def fake_run(*args: str) -> tuple[bool, str]:
        calls.append(args)
        return True, ""

    monkeypatch.setattr(sd, "_run_schtasks", fake_run)
    return calls


def test_usswing_close_task_command(captured: list[tuple[str, ...]]) -> None:
    """UT-GUI-000.004.T01: USSwing close task force-kills the exe image on weekdays."""
    cfg = USSwingConfig(task_name="USSwing_App", exe_path=r"C:\x\USSwing.exe", days="weekdays")
    ok, _ = sd.create_usswing_close_task(cfg, "16:30")
    assert ok
    args = captured[0]
    assert "/tn" in args and "USSwing_App_Close" in args
    assert "taskkill /IM USSwing.exe /F" in args
    assert "/st" in args and "16:30" in args
    assert "weekly" in args and "MON,TUE,WED,THU,FRI" in args


def test_ibkr_close_task_daily(captured: list[tuple[str, ...]]) -> None:
    """UT-GUI-000.004.T02: IBKR close task uses the tws image name and a daily schedule."""
    cfg = SchedulerConfig(task_name="USSwing_IBKR", exe_path=r"C:\Jts\tws.exe", days="daily")
    ok, _ = sd.create_ibkr_close_task(cfg, "23:00")
    assert ok
    args = captured[0]
    assert "USSwing_IBKR_Close" in args
    assert "taskkill /IM tws.exe /F" in args
    assert "daily" in args
