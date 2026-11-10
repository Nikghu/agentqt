"""
Module: MD-GUI-029.001.M01 — tests
Parent SRD: SRD-GUI-029.001

Scheduler task table (FO-GUI-029) and its Windows task helpers. Windows, keyring and the
scheduler store are faked by tests/gui/conftest.py and the fixtures below.
"""
from __future__ import annotations

import sys
import types
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from PyQt6.QtCore import QTime
from PyQt6.QtWidgets import QDialog

from us_swing.gui import scheduler_dialog as sd
from us_swing.gui import scheduler_table
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
    return SchedulerConfig(**{"exe_path": r"C:\Jts\tws.exe", "launch_time": "18:30", **kw})


def _app(**kw: Any) -> USSwingConfig:
    return USSwingConfig(**{"exe_path": r"C:\x\USSwing.exe", "launch_time": "18:30", **kw})


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
    monkeypatch.setattr(scheduler_table, "_start_time", lambda: "18:30")
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


IST = ZoneInfo("Asia/Kolkata")


def test_before_open_time() -> None:
    """UT-GUI-029.007.M02.T01: Start time 60 min before open in local time (SRD-GUI-029.007)."""
    weekdays = ["MON", "TUE", "WED", "THU", "FRI"]
    assert sd.before_open_time(date(2026, 11, 12), IST) == ("19:00", weekdays)
    assert sd.before_open_time(date(2026, 7, 1), IST) == ("18:00", weekdays)
    assert sd.before_open_time(date(2026, 11, 12), ZoneInfo("Pacific/Auckland")) == (
        "02:30", ["TUE", "WED", "THU", "FRI", "SAT"])


def test_start_times_read_only(qtbot: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-029.007.M01.T01: Start times read-only, Close both editable (SRD-GUI-029.007)."""
    save_scheduler_config(_tws(launch_time="19:30"))
    save_usswing_config(_app(launch_time="19:30"))
    save_close_config(CloseConfig(enabled=True, close_time="02:45"))
    monkeypatch.setattr(scheduler_table, "_start_time", lambda: "19:00")
    widget = SchedulerTable()
    qtbot.addWidget(widget)
    for key in ("tws", "app"):
        row = widget._rows[key]
        assert row.time.time() == QTime(19, 0) and row.time.isReadOnly()
        assert row.pill.text() == "CHANGED"
    close = widget._rows["close"].time
    assert close.time() == QTime(2, 45) and not close.isReadOnly()


def _xml(start: str) -> str:
    days = "".join(f"<{d}/>" for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"))
    return ('<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Triggers>'
            f"<CalendarTrigger><StartBoundary>2026-11-05T{start}:00</StartBoundary>"
            f"<ScheduleByWeek><DaysOfWeek>{days}</DaysOfWeek></ScheduleByWeek>"
            "</CalendarTrigger></Triggers></Task>")


class _Query(_Schtasks):
    """schtasks fake whose /query /xml returns a task at ``start`` (or fails)."""

    def __init__(self, start: str | None) -> None:
        super().__init__()
        self.start = start

    def __call__(self, *args: str) -> tuple[bool, str]:
        self.append(args)
        if args[0] == "/query":
            return (self.start is not None), _xml(self.start or "")
        return True, ""


def test_sync_recreates_wrong_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-029.008.M02.T01: Start-up sync re-creates a wrong start task (SRD-GUI-029.008)."""
    calls = _Query("19:30")
    monkeypatch.setattr(sd, "_run_schtasks", calls)
    monkeypatch.setattr(sd, "_local_zone", lambda: IST)
    save_scheduler_config(_tws(launch_time="19:30", enabled=False))
    save_usswing_config(_app(launch_time="19:30"))
    assert sd.sync_start_tasks(date(2026, 11, 12), IST) == ["USSwing_App"]
    created = [c for c in calls if c[0] == "/create"]
    assert len(created) == 1 and "19:00" in created[0] and "MON,TUE,WED,THU,FRI" in created[0]
    assert load_usswing_config() == _app(launch_time="19:00")


def test_sync_leaves_good_missing_or_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-029.008.M02.T02: Sync leaves a right, missing or switched-off task."""
    save_scheduler_config(_tws(launch_time="19:00", enabled=False))
    save_usswing_config(_app(launch_time="19:00"))
    for start in ("19:00", None):
        calls = _Query(start)
        monkeypatch.setattr(sd, "_run_schtasks", calls)
        assert sd.sync_start_tasks(date(2026, 11, 12), IST) == []
        assert [c for c in calls if c[0] == "/create"] == []
