"""
Module: MD-GUI-029.001.M01 — tests
Parent SRD: SRD-GUI-029.001

Scheduler task table (FO-GUI-029) and its Windows task helpers. Windows, keyring and the
scheduler store are faked by tests/gui/conftest.py and the fixtures below.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from PyQt6.QtCore import QTime
from PyQt6.QtWidgets import QDialog

from us_swing.gui import scheduler_dialog as sd
from us_swing.gui.scheduler_store import (
    CloseConfig,
    SchedulerConfig,
    USSwingConfig,
    load_usswing_config,
    save_close_config,
    save_scheduler_config,
    save_usswing_config,
)
from us_swing.gui.scheduler_table import SchedulerTable


class _Schtasks(list[tuple[str, ...]]):
    """Recorded schtasks calls; /query succeeds only for names in ``existing``."""

    def __init__(self) -> None:
        super().__init__()
        self.existing: set[str] = set()

    def __call__(self, *args: str) -> tuple[bool, str]:
        self.append(args)
        if args[0] == "/query":
            return args[2] in self.existing, ""
        return True, ""


@pytest.fixture()
def schtasks(monkeypatch: pytest.MonkeyPatch) -> _Schtasks:
    calls = _Schtasks()
    monkeypatch.setattr(sd, "_run_schtasks", calls)
    return calls


def _tws(**kw: Any) -> SchedulerConfig:
    return SchedulerConfig(exe_path=r"C:\Jts\tws.exe", launch_time="18:30", **kw)


def _app(**kw: Any) -> USSwingConfig:
    return USSwingConfig(exe_path=r"C:\x\USSwing.exe", launch_time="18:32", **kw)


def _created(calls: list[tuple[str, ...]]) -> list[str]:
    return [c[2] for c in calls if c[0] == "/create"]


def _deleted(calls: list[tuple[str, ...]]) -> list[str]:
    return [c[2] for c in calls if c[0] == "/delete"]


def test_write_switched_on_tasks(schtasks: list[tuple[str, ...]]) -> None:
    """UT-GUI-029.004.M02.T01: switched-on apps and their close tasks are created and saved."""
    errors = sd.write_tasks(_app(), _tws(), CloseConfig(enabled=True, close_time="01:30"), "")

    assert errors == {}
    assert _created(schtasks) == ["USSwing_IBKR", "USSwing_App",
                                  "USSwing_App_Close", "USSwing_IBKR_Close"]
    assert load_usswing_config() == _app()


def test_switched_off_task_is_deleted(schtasks: list[tuple[str, ...]]) -> None:
    """UT-GUI-029.004.M02.T02: a switched-off app and closed-off close tasks are deleted."""
    sd.write_tasks(_app(enabled=False), _tws(), CloseConfig(enabled=False), "")

    assert _created(schtasks) == ["USSwing_IBKR"]
    assert set(_deleted(schtasks)) == {"USSwing_App", "USSwing_App_Close",
                                       "USSwing_IBKR_Close"}


def test_task_states(schtasks: Any) -> None:
    """UT-GUI-029.002.M02.T01: an existing task reads installed, a gone one missing."""
    schtasks.existing.add("USSwing_IBKR")

    states = sd.task_states(_app(), _tws(), CloseConfig(enabled=False))

    assert states == {"tws": "installed", "app": "missing", "close": "off"}


@pytest.fixture()
def table(qtbot: Any, monkeypatch: pytest.MonkeyPatch) -> SchedulerTable:
    save_scheduler_config(_tws(ibkr_username="trader"))
    save_usswing_config(_app())
    save_close_config(CloseConfig(enabled=True, close_time="01:30"))
    # Run background jobs at once so the tests see their results.
    monkeypatch.setattr(SchedulerTable, "_run",
                        lambda self, fn, done: done(fn()))
    widget = SchedulerTable()
    qtbot.addWidget(widget)
    return widget


def test_table_loads_saved_tasks(table: SchedulerTable) -> None:
    """UT-GUI-029.001.M01.T01: the rows show the saved programs, times and days."""
    tws, close = table._rows["tws"], table._rows["close"]

    assert tws.on.isChecked()
    assert tws.time.time() == QTime(18, 30)
    assert tws.exe is not None and tws.exe.text() == r"C:\Jts\tws.exe"
    assert tws.days is not None and tws.days.currentText() == "Mon–Fri"
    assert close.on.isChecked() and close.time.time() == QTime(1, 30)
    assert close.days is None and close.exe is None
    assert table._user.text() == "trader"


def test_edit_marks_row_changed(table: SchedulerTable, schtasks: Any) -> None:
    """UT-GUI-029.002.M01.T01: editing a row shows CHANGED on that row only."""
    schtasks.existing.update({"USSwing_IBKR", "USSwing_App",
                              "USSwing_IBKR_Close", "USSwing_App_Close"})
    table.refresh_status()

    table._rows["app"].time.setTime(QTime(19, 0))

    assert table._rows["app"].pill.text() == "CHANGED"
    assert table._rows["tws"].pill.text() == "INSTALLED"


def test_missing_task_asks_for_repair(table: SchedulerTable, schtasks: Any, qtbot: Any) -> None:
    """UT-GUI-029.004.M01.T01: a switched-on task missing in Windows asks for a repair."""
    schtasks.existing.update({"USSwing_App", "USSwing_IBKR_Close", "USSwing_App_Close"})

    with qtbot.waitSignal(table.repair_needed, timeout=500):
        table.refresh_status()

    assert table._rows["tws"].pill.text() == "MISSING"


def test_remove_all_cancelled(table: SchedulerTable, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-029.005.M01.T01: Cancel in the confirm keeps every task."""
    removed: list[bool] = []
    monkeypatch.setattr(sd, "remove_tasks", lambda *_a: removed.append(True) or [])

    class _Dialog:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Rejected

    fake = types.ModuleType("us_swing.gui.active_cycles_panel")
    fake._ConfirmDialog = _Dialog  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "us_swing.gui.active_cycles_panel", fake)

    table.remove_all()

    assert removed == []



def test_apply_waits_for_running_write(table: SchedulerTable,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-029.004.M01.T02: an Apply during a write runs once the write ends."""
    writes: list[bool] = []
    monkeypatch.setattr(sd, "write_tasks", lambda *_a: writes.append(True) or {})
    table._set_busy(True)

    table.apply()
    assert writes == [] and not table._remove_btn.isEnabled()

    table._set_busy(False)
    table._after_job()
    assert writes == [True]


def test_stale_status_is_dropped(table: SchedulerTable, schtasks: Any) -> None:
    """UT-GUI-029.002.M01.T02: a status result from before a reload is not painted."""
    schtasks.existing.update({"USSwing_IBKR", "USSwing_App",
                              "USSwing_IBKR_Close", "USSwing_App_Close"})
    old_gen = table._status_gen
    table.load()

    table._on_states({"tws": "missing", "app": "missing", "close": "missing"}, old_gen)

    assert table._rows["tws"].pill.text() == "INSTALLED"
