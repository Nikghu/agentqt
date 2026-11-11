"""Tests for MD-DSK-001.010.M04 — desk/process.py."""
from __future__ import annotations

import os
import logging
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from datetime import UTC, datetime

from tests.desk import test_harness as th
from tests.desk.conftest import FakeClock
from tests.desk.test_harness import _reset_state  # noqa: F401 - autouse fixture
from us_swing.core.desk_contract import CommandKind, DeskState, StepContext, send_command
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.process import DeskProcess, pid_alive
from us_swing.desk.store import DeskStore


class Step:
    """A desk step that records its calls."""

    def __init__(self, name: str, action: Callable[[StepContext], None] | None = None) -> None:
        self.name = name
        self.calls: list[StepContext] = []
        self._action = action

    def __call__(self, ctx: StepContext) -> None:
        self.calls.append(ctx)
        if self._action is not None:
            self._action(ctx)


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _state(home: Path) -> str:
    return str(_rows(home, "SELECT state FROM desk_state")[0][0])


def _desk(home: Path, clock: FakeClock, **kw: Any) -> DeskProcess:
    return DeskProcess(home, clock=clock, sleep=lambda _s: None, **kw)


def _saved(home: Path, state: DeskState, clock: FakeClock) -> None:
    s = DeskStore(home)
    s.set_state(state, clock())
    s.close()


def test_second_instance_exits(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T01: Second instance exits."""
    first = _desk(home, clock)
    assert first.start()
    second = _desk(home, clock)
    try:
        assert not second.start()
        assert second.state is DeskState.OFF
        assert _state(home) == "Sleeping"
    finally:
        second.close()
        first.close()


def test_heartbeat_written(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T02: Heartbeat written."""
    desk = _desk(home, clock)
    desk.start()
    clock.move(10)
    desk.tick()
    beat = _rows(home, "SELECT heartbeat_at FROM desk_state")[0][0]
    desk.close()
    assert beat == clock.now.isoformat()


def test_pause_then_resume(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T03: Pause then resume."""
    desk = _desk(home, clock)
    desk.start()
    send_command(CommandKind.PAUSE, home)
    desk.tick()
    assert desk.state is DeskState.PAUSED
    send_command(CommandKind.RESUME, home)
    desk.tick()
    desk.close()
    assert _state(home) == "Sleeping"
    assert [r[0] for r in _rows(home, "SELECT status FROM commands")] == ["done", "done"]


def test_resume_when_sleeping_rejected(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T04: Resume when Sleeping."""
    desk = _desk(home, clock)
    desk.start()
    send_command(CommandKind.RESUME, home)
    desk.tick()
    desk.close()
    status, note = _rows(home, "SELECT status, note FROM commands")[0]
    assert status == "rejected" and note
    assert _state(home) == "Sleeping"


def test_no_run_while_paused(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T05: No run while Paused, even in the morning window."""
    desk = _desk(home, clock)
    desk.start()
    send_command(CommandKind.PAUSE, home)
    desk.tick()
    clock.move(90 * 60)
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT COUNT(*) FROM runs")[0][0] == 0


def test_stop_saves_and_exits(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T06: Stop saves and exits."""
    desk = _desk(home, clock)
    desk.start()
    send_command(CommandKind.STOP, home)
    assert desk.tick() is False
    desk.close()
    assert _state(home) == "Stopped"
    assert _rows(home, "SELECT resume_point FROM desk_state")[0][0]


def test_stop_during_run(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T07: Stop during run ends after current step."""
    step1 = Step("one", lambda _c: send_command(CommandKind.STOP, home))
    step2 = Step("two")
    desk = _desk(home, clock, steps=[step1, step2])
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    assert desk.tick() is False
    desk.close()
    assert len(step1.calls) == 1 and step2.calls == []
    assert _rows(home, "SELECT result FROM runs")[0][0] == "interrupted"
    assert _state(home) == "Stopped"


def test_task_start_honours_stopped(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T08: Task start honours Stopped."""
    _saved(home, DeskState.STOPPED, clock)
    desk = _desk(home, clock)
    assert not desk.start()
    desk.close()
    assert _state(home) == "Stopped"


def test_start_clears_stopped(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T09: Start clears Stopped."""
    _saved(home, DeskState.STOPPED, clock)
    desk = _desk(home, clock, resume=True)
    assert desk.start()
    desk.close()
    assert _state(home) == "Sleeping"


def test_interrupted_run_is_rerun(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T10: Interrupted run is rerun."""
    s = DeskStore(home)
    s.start_run("evening", clock())
    s.close()
    desk = _desk(home, clock)
    desk.start()
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT kind, result FROM runs ORDER BY id") == [
        ("evening", "interrupted"), ("manual", "ok"),
    ]


def test_morning_run_calls_steps(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T11: Morning run calls steps (SRD-DSK-001.016, SRD-DSK-003.013)."""
    order: list[str] = []
    steps = [Step("a", lambda _c: order.append("a")), Step("b", lambda _c: order.append("b"))]
    desk = _desk(home, clock, steps=steps)
    desk.start()
    desk.tick()
    assert order == []
    clock.move(90 * 60)  # 04:00 ET Thursday
    desk.tick()
    desk.tick()
    desk.close()
    assert order == ["a", "b"]
    assert _rows(home, "SELECT kind, result FROM runs") == [("morning", "ok")]
    assert _state(home) == "Sleeping"


def test_zero_steps(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T12: Zero steps."""
    desk = _desk(home, clock)
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT result FROM runs") == [("ok",)]


def _boom(_ctx: StepContext) -> None:
    raise ValueError("bad data")


def test_failed_step_sets_error(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T13: Failed step sets Error."""
    desk = _desk(home, clock, steps=[Step("regime", _boom)])
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    assert desk.tick() is True
    desk.close()
    assert _rows(home, "SELECT result FROM runs") == [("failed",)]
    state, message = _rows(home, "SELECT state, message FROM desk_state")[0]
    assert state == "Error" and "regime" in message


def test_good_run_clears_error(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T14: Good run clears Error."""
    calls = {"n": 0}

    def once_bad(_ctx: StepContext) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("first time")

    desk = _desk(home, clock, steps=[Step("flaky", once_bad)])
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    desk.tick()
    assert desk.state is DeskState.ERROR
    send_command(CommandKind.RUN_NOW, home)
    desk.tick()
    desk.close()
    assert _state(home) == "Sleeping"


def test_first_instance_takes_lock(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T15: First instance takes the lock."""
    desk = _desk(home, clock)
    assert desk.start()
    desk.close()
    state, pid = _rows(home, "SELECT state, pid FROM desk_state")[0]
    assert state == "Sleeping" and pid == os.getpid()


def test_no_heartbeat_before_ten_seconds(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T16: No heartbeat before 10 s."""
    desk = _desk(home, clock)
    desk.start()
    started = clock.now
    clock.move(9)
    desk.tick()
    beat = _rows(home, "SELECT heartbeat_at FROM desk_state")[0][0]
    desk.close()
    assert beat == started.isoformat()


def test_unknown_command_kind(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T17: Unknown command kind."""
    desk = _desk(home, clock)
    desk.start()
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("INSERT INTO commands (kind, created_at, status) VALUES ('dance', 'x', 'pending')")
    con.close()
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT status, note FROM commands") == [("rejected", "unknown command")]
    assert _state(home) == "Sleeping"


def test_command_after_stop_in_same_batch(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T18: Command after stop in same batch."""
    desk = _desk(home, clock)
    desk.start()
    send_command(CommandKind.STOP, home)
    send_command(CommandKind.PAUSE, home)
    desk.tick()
    desk.close()
    assert [r[0] for r in _rows(home, "SELECT status FROM commands ORDER BY id")] == [
        "done", "rejected",
    ]
    assert _state(home) == "Stopped"


def test_task_start_runs_when_not_stopped(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T19: Task start runs when not Stopped."""
    _saved(home, DeskState.SLEEPING, clock)
    desk = _desk(home, clock)
    assert desk.start()
    assert desk.tick() is True
    desk.close()
    assert _state(home) == "Sleeping"


def test_no_rerun_when_runs_closed(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T20: No rerun when runs closed."""
    s = DeskStore(home)
    s.end_run(s.start_run("evening", clock()), "ok", clock())
    s.close()
    desk = _desk(home, clock)
    desk.start()
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT COUNT(*) FROM runs")[0][0] == 1


def test_run_now_while_paused(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T21: Run-now while Paused."""
    desk = _desk(home, clock)
    desk.start()
    send_command(CommandKind.PAUSE, home)
    desk.tick()
    send_command(CommandKind.RUN_NOW, home)
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT status FROM commands ORDER BY id")[-1] == ("rejected",)
    assert _rows(home, "SELECT COUNT(*) FROM runs")[0][0] == 0


def test_heartbeat_during_long_run(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T22: Heartbeat stays fresh during a long step."""
    seen: list[str] = []

    def long_step(_ctx: StepContext) -> None:
        clock.move(90)
        time.sleep(0.3)
        seen.append(_rows(home, "SELECT heartbeat_at FROM desk_state")[0][0])

    desk = _desk(home, clock, steps=[Step("slow", long_step)], beat_s=0.05)
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    desk.tick()
    desk.close()
    assert seen == [clock.now.isoformat()]


def test_stale_commands_rejected_on_start(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T23: Commands left from before start are rejected."""
    _saved(home, DeskState.STOPPED, clock)
    send_command(CommandKind.STOP, home)
    desk = _desk(home, clock, resume=True)
    desk.start()
    assert desk.tick() is True
    desk.close()
    assert _rows(home, "SELECT status, note FROM commands") == [
        ("rejected", "desk was not running"),
    ]
    assert _state(home) == "Sleeping"


def test_crash_writes_error(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T24: A crash in the loop is saved as Error."""

    def broken_sleep(_s: float) -> None:
        raise RuntimeError("disk gone")

    desk = DeskProcess(home, clock=clock, sleep=broken_sleep)
    assert desk.run() == 1
    state, message = _rows(home, "SELECT state, message FROM desk_state")[0]
    assert state == "Error" and "disk gone" in message


def test_pause_cleared_when_run_fails(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T25: A pause taken during a failed run is honoured once."""
    first = Step("first", lambda _c: send_command(CommandKind.PAUSE, home))
    desk = _desk(home, clock, steps=[first, Step("bad", _boom)])
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    desk.tick()
    assert desk.state is DeskState.PAUSED
    assert "bad failed" in _rows(home, "SELECT message FROM desk_state")[0][0]
    send_command(CommandKind.RESUME, home)
    desk.tick()
    desk._steps = [Step("good")]
    send_command(CommandKind.RUN_NOW, home)
    desk.tick()
    desk.close()
    assert _state(home) == "Sleeping"


def test_parent_gone_stops_desk(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T27: Parent gone stops the desk (SRD-DSK-001.019)."""
    alive = iter([True, False])
    desk = _desk(home, clock, parent_alive=lambda: next(alive))
    desk.start()
    assert desk.tick() is True
    assert desk.tick() is False
    desk.close()
    assert _state(home) == "Stopped"
    assert _rows(home, "SELECT resume_point FROM desk_state")[0][0]


def test_parent_gone_during_run(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T28: Parent gone during a run (SRD-DSK-001.019)."""
    state = {"alive": True}
    first = Step("first", lambda _c: state.update(alive=False))
    second = Step("second")
    desk = _desk(home, clock, steps=[first, second], parent_alive=lambda: state["alive"])
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    assert desk.tick() is False
    desk.close()
    assert second.calls == []
    assert _rows(home, "SELECT result FROM runs") == [("interrupted",)]
    assert '"rerun": true' in _rows(home, "SELECT resume_point FROM desk_state")[0][0]


def test_no_parent_watch_without_parent(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T29: No parent watch without a parent (SRD-DSK-001.019)."""
    desk = _desk(home, clock)
    desk.start()
    assert all(desk.tick() for _ in range(3))
    desk.close()
    assert _state(home) == "Sleeping"


def test_failed_morning_retried_after_15_min(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T30: Failed morning try is retried after 15 min (SRD-DSK-001.015)."""
    desk = _desk(home, clock, steps=[Step("bad", _boom)])
    desk.start()
    clock.move(90 * 60 + 31 * 60)   # 04:31 ET
    desk.tick()
    clock.move(9 * 60)              # 04:40 ET
    desk.tick()
    clock.move(7 * 60)              # 04:47 ET
    desk.tick()
    desk.close()
    starts = [r[0][11:16] for r in _rows(home, "SELECT started_at FROM runs ORDER BY id")]
    assert starts == ["09:31", "09:47"]   # UTC = ET + 5 h


def test_pid_alive() -> None:
    """UT-DSK-001.010.M04.T31: pid_alive for this process and a dead pid (SRD-DSK-001.019)."""
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    child = subprocess.Popen([sys.executable, "-c", "pass"])  # noqa: S603
    child.wait()
    assert pid_alive(os.getpid())
    assert not pid_alive(child.pid)


def test_run_now_then_pause_in_one_batch(home: Path, clock: FakeClock) -> None:
    """UT-DSK-001.010.M04.T26: Pause cancels a run-now from the same batch."""
    desk = _desk(home, clock)
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    send_command(CommandKind.PAUSE, home)
    desk.tick()
    send_command(CommandKind.RESUME, home)
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT COUNT(*) FROM runs")[0][0] == 0


FRI_1601_ET = datetime(2026, 11, 6, 21, 1, tzinfo=UTC)


def _event_desk(home: Path) -> tuple[DeskProcess, Step, FakeClock]:
    th.employee(home, "t-1", th.job("t-1").replace("trigger: after_run",
                                                   "trigger: market_close"))
    clock = FakeClock(FRI_1601_ET)
    events = EmployeesStep(lambda: th.SKILLS, lambda: [], lambda: th.ON, lambda: "key",
                           th.FakeCaller(th.GOOD), clock)
    market = Step("market")
    return _desk(home, clock, steps=[market], events=events), market, clock


def test_event_run_from_loop(home: Path) -> None:
    """UT-DSK-003.008.M04.T01: At 16:01 one event run wakes the employee; market steps stay idle."""
    desk, market, _ = _event_desk(home)
    desk.start()
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT kind FROM runs") == [("event",)]
    assert market.calls == [] and len(th.STATE.seen) == 1
    assert _rows(home, "SELECT kind, state FROM events WHERE kind != 'step_done'") == [
        ("market_close", "done")]


def test_no_event_run_when_paused(home: Path) -> None:
    """UT-DSK-003.008.M04.T02: A paused desk starts no event run at 16:01."""
    desk, _, _ = _event_desk(home)
    desk.start()
    send_command(CommandKind.PAUSE, home)
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT COUNT(*) FROM runs") == [(0,)]
    assert th.STATE.seen == []

def test_event_check_error_keeps_desk_alive(home: Path, monkeypatch: pytest.MonkeyPatch,
                                            caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.008.M04.T03: An error while checking events is logged; the desk keeps going."""
    desk, _, _ = _event_desk(home)

    def broken(_home: Path) -> bool:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(desk._events, "has_work", broken)
    desk.start()
    with caplog.at_level(logging.ERROR):
        assert desk.tick() is True
    desk.close()
    assert _rows(home, "SELECT COUNT(*) FROM runs") == [(0,)]
    assert "Could not check for AI events" in caplog.text
