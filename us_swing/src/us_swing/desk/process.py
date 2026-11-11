"""
Module: MD-DSK-001.010.M04 — desk/process.py
Parent SRD: SRD-DSK-001.010
Also: SRD-DSK-003.008 (market clock events and event runs), SRD-DSK-001.015 (morning run),
SRD-DSK-001.019 (parent watch), SRD-DSK-003.013 (run kinds), SRD-DSK-009.008 (lesson edits),
SRD-DSK-003.020 (check-in events), SRD-DSK-003.023 (watchers every 5 minutes)

The desk main loop: one copy only, heartbeat, commands, runs, stop and resume. The morning
run is due by ``morning_due``; between runs the loop posts market clock events and starts a
short ``event`` run when one wakes an employee; only the morning and manual runs call the
market steps. A desk launched by the app stops when the app's process ends.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import IO, Protocol, runtime_checkable

from us_swing.core.desk_contract import CommandKind, DeskState, DeskStep, StepContext
from us_swing.core.desk_events import post_event
from us_swing.core.desk_lessons import apply_edits
from us_swing.desk.clock import (
    MANUAL,
    MORNING,
    checkins_due,
    in_market_hours,
    market_events_due,
    morning_due,
)
from us_swing.desk.store import DeskStore

if sys.platform == "win32":
    import ctypes
    import msvcrt

log = logging.getLogger(__name__)

LOCK_NAME = "desk.lock"
_MORNING = MORNING
_MANUAL = MANUAL
_EVENT = "event"
_RUN_LOOKBACK = timedelta(days=1)
WATCH_EVERY = timedelta(minutes=5)
_SYNCHRONIZE = 0x00100000
_WAIT_TIMEOUT = 0x00000102
_ACCESS_DENIED = 5


@runtime_checkable
class EventHandler(Protocol):
    """Handles waiting events between desk runs."""

    def has_work(self, home: Path) -> bool: ...

    def handle_events(self, ctx: StepContext) -> None: ...


class _EventStep:
    """The only step of an ``event`` run."""

    name = "AI events"

    def __init__(self, events: EventHandler) -> None:
        self._events = events

    def __call__(self, ctx: StepContext) -> None:
        self._events.handle_events(ctx)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _take_lock(path: Path) -> IO[bytes] | None:
    handle = open(path, "a+b")  # noqa: SIM115 — held open for the life of the process
    handle.seek(0)
    try:
        if sys.platform == "win32":
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def pid_alive(pid: int) -> bool:
    """True while the process ``pid`` is running."""
    if sys.platform == "win32":
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(_SYNCHRONIZE, False, pid)
        if not handle:
            return bool(kernel.GetLastError() == _ACCESS_DENIED)
        try:
            return bool(kernel.WaitForSingleObject(handle, 0) == _WAIT_TIMEOUT)
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _release_lock(handle: IO[bytes]) -> None:
    handle.seek(0)
    try:
        if sys.platform == "win32":
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()


class DeskProcess:
    """Runs the desk until a stop command; clock and sleep are injectable for tests."""

    def __init__(
        self,
        home: Path,
        steps: Sequence[DeskStep] = (),
        *,
        resume: bool = False,
        clock: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], None] = time.sleep,
        daily_check: Callable[[], object] | None = None,
        poll_s: float = 2.0,
        beat_s: float = 10.0,
        events: EventHandler | None = None,
        parent_alive: Callable[[], bool] | None = None,
        watch: Callable[[Path, datetime], int] | None = None,
    ) -> None:
        """Set up the desk; nothing is opened until :meth:`start`.

        ``daily_check`` runs once at start (old desk task clean-up).
        ``events`` handles market clock and other events between runs.
        ``parent_alive`` says whether the app that launched the desk still runs.
        ``watch`` runs the market watchers every 5 minutes in market hours.
        """
        self._events = events
        self._parent_alive = parent_alive
        self._posted: set[tuple[str, str, int]] = set()
        self._watch = watch
        self._last_watch: datetime | None = None
        self._home = home
        self._steps = list(steps)
        self._resume = resume
        self._clock = clock
        self._sleep = sleep
        self._daily_check = daily_check
        self._poll_s = poll_s
        self._beat_s = beat_s
        self._lock: IO[bytes] | None = None
        self._store: DeskStore | None = None
        self._state = DeskState.OFF
        self._last_beat = clock()
        self._rerun = False
        self._run_now = False
        self._pause_after_run = False

    @property
    def state(self) -> DeskState:
        """The current desk state."""
        return self._state

    # ── life cycle ────────────────────────────────────────────────────────

    def run(self) -> int:
        """Start, loop until stopped, then clean up; returns the exit code."""
        try:
            if self.start():
                while self.tick():
                    self._sleep(self._poll_s)
        except Exception as exc:  # noqa: BLE001 — record any crash before exiting
            log.exception("[Desk] Desk stopped by an unexpected error")
            self._record_crash(str(exc))
            return 1
        finally:
            self.close()
        return 0

    def _record_crash(self, reason: str) -> None:
        if self._store is None:
            return
        try:
            self._store.set_state(DeskState.ERROR, self._clock(), f"crashed: {reason}")
        except Exception:  # noqa: BLE001 — the database itself may be the problem
            log.warning("[Desk] Could not save the error state")

    def start(self) -> bool:
        """Take the lock and open the store; False means the process should exit."""
        self._home.mkdir(parents=True, exist_ok=True)
        self._lock = _take_lock(self._home / LOCK_NAME)
        if self._lock is None:
            log.info("[Desk] Desk is already running")
            return False
        store = self._store = DeskStore(self._home)
        saved = store.saved_state()
        if saved is not None and saved.state is DeskState.STOPPED and not self._resume:
            log.info("[Desk] Desk was stopped by the user and stays stopped")
            return False
        now = self._clock()
        for cmd in store.pending_commands():
            store.finish_command(cmd.id, False, now, "desk was not running")
        if store.interrupt_open_runs(now) or (saved and saved.resume_point.get("rerun")):
            self._rerun = True
        paused = saved is not None and saved.state is DeskState.PAUSED
        self._set(DeskState.PAUSED if paused else DeskState.SLEEPING, now, pid=os.getpid())
        log.info("[Desk] Desk started")
        self._run_daily_check()
        return True

    def _run_daily_check(self) -> None:
        if self._daily_check is None:
            return
        try:
            self._daily_check()
        except Exception:  # noqa: BLE001 — a failed check must not stop the desk
            log.warning("[Desk] Daily check failed", exc_info=True)

    def close(self) -> None:
        """Close the store and release the lock."""
        if self._store is not None:
            self._store.close()
            self._store = None
        if self._lock is not None:
            _release_lock(self._lock)
            self._lock = None

    def tick(self) -> bool:
        """Do one loop step; False when the desk has stopped."""
        now = self._clock()
        if (now - self._last_beat).total_seconds() >= self._beat_s:
            self._db.beat(now)
            self._last_beat = now
        self._apply_commands(now)
        self._apply_lesson_edits(now)
        if not self._stopping() and self._parent_gone():
            self._set(DeskState.STOPPING, now)
        if not self._stopping() and self._state is not DeskState.PAUSED:
            if self._rerun or self._run_now:
                self._do_run(_MANUAL)
            elif morning_due(now, self._db.runs_since(now - _RUN_LOOKBACK)):
                self._do_run(_MORNING)
            else:
                self._event_tick(now)
        if self._stopping():
            self._finish_stop()
            return False
        return True

    def _stopping(self) -> bool:
        return self._state is DeskState.STOPPING

    def _parent_gone(self) -> bool:
        if self._parent_alive is None or self._parent_alive():
            return False
        log.info("[Desk] The app has closed; stopping the desk")
        return True

    # ── commands ──────────────────────────────────────────────────────────

    def _apply_lesson_edits(self, now: datetime) -> None:
        """Apply the Master's lesson edits from the app (SRD-DSK-009.008)."""
        try:
            apply_edits(self._home, now)
        except Exception:  # noqa: BLE001 — a bad edit must never stop the desk
            log.exception("[Memory] Could not apply the lesson edits")

    def _apply_commands(self, now: datetime) -> None:
        for cmd in self._db.pending_commands():
            reason = self._apply(cmd.kind, now)
            self._db.finish_command(cmd.id, reason == "", now, reason)
            if reason:
                log.info("[Desk] Command %s not done: %s", cmd.kind, reason)

    def _apply(self, kind: str, now: datetime) -> str:
        """Apply one command; return the reason when it is rejected."""
        if self._state is DeskState.STOPPING:
            return "desk is stopping"
        try:
            command = CommandKind(kind)
        except ValueError:
            return "unknown command"
        if command is CommandKind.STOP:
            self._set(DeskState.STOPPING, now)
        elif command is CommandKind.PAUSE:
            if self._state is DeskState.PAUSED:
                return "desk is already paused"
            self._run_now = False
            self._set(DeskState.PAUSED, now)
        elif command is CommandKind.RESUME:
            if self._state is not DeskState.PAUSED:
                return "desk is not paused"
            self._set(DeskState.SLEEPING, now)
        else:
            if self._state is DeskState.PAUSED:
                return "desk is paused"
            self._run_now = True
        return ""

    def _commands_during_run(self, now: datetime) -> bool:
        """Read commands between steps; True when a stop was asked."""
        stop = False
        for cmd in self._db.pending_commands():
            if cmd.kind == CommandKind.STOP.value:
                stop, reason = True, ""
            elif cmd.kind == CommandKind.PAUSE.value:
                self._pause_after_run, reason = True, ""
            else:
                reason = "desk is busy with a run"
            self._db.finish_command(cmd.id, reason == "", now, reason)
        return stop or self._parent_gone()

    # ── runs ──────────────────────────────────────────────────────────────

    def _event_tick(self, now: datetime) -> None:
        """Post due market clock events, then run the event handler when it has work."""
        if self._events is None:
            return
        try:
            for kind, day in market_events_due(now):
                if (kind, day, 0) not in self._posted:
                    post_event(self._home, kind, day, now)
                    self._posted.add((kind, day, 0))
            for day, slot in checkins_due(now):
                if ("market_checkin", day, slot) not in self._posted:
                    post_event(self._home, "market_checkin", day, now, slot)
                    self._posted.add(("market_checkin", day, slot))
            self._watch_tick(now)
            work = self._events.has_work(self._home)
        except Exception:  # noqa: BLE001 — a bad event check must never stop the desk
            log.exception("[Desk] Could not check for AI events")
            return
        if work:
            self._do_run(_EVENT, [_EventStep(self._events)])

    def _watch_tick(self, now: datetime) -> None:
        """Run the watchers every 5 minutes in market hours (SRD-DSK-003.023)."""
        if self._watch is None or not in_market_hours(now):
            return
        if self._last_watch is not None and now - self._last_watch < WATCH_EVERY:
            return
        self._last_watch = now
        try:
            self._watch(self._home, now)
        except Exception:  # noqa: BLE001 — a watcher problem must never stop the desk
            log.exception("[Watch] The market watchers failed; trying again in 5 minutes")

    def _do_run(self, kind: str, steps: Sequence[DeskStep] | None = None) -> None:
        self._rerun = self._run_now = False
        start = self._clock()
        self._set(DeskState.RUNNING, start)
        run_id = self._db.start_run(kind, start)
        log.info("[Desk] Run %d started (%s)", run_id, kind)
        with self._beating():
            result, message = self._run_steps(StepContext(run_id, kind, start, self._home),
                                              self._steps if steps is None else steps)
        self._db.end_run(run_id, result, self._clock(), message)
        if result == "failed":
            failed_state = DeskState.PAUSED if self._pause_after_run else DeskState.ERROR
            self._pause_after_run = False
            self._set(failed_state, self._clock(), message)
            log.error("[Desk] Run %d failed: %s", run_id, message)
            return
        log.info("[Desk] Run %d ended: %s", run_id, result)
        if result == "interrupted" or message == "stop asked":
            next_state = DeskState.STOPPING
        elif self._pause_after_run:
            next_state = DeskState.PAUSED
        else:
            next_state = DeskState.SLEEPING
        self._pause_after_run = False
        self._set(next_state, self._clock())

    def _run_steps(self, ctx: StepContext, steps: Sequence[DeskStep]) -> tuple[str, str]:
        """Call each step; return (result, note) for the run row."""
        last = len(steps) - 1
        for index, step in enumerate(steps):
            try:
                step(ctx)
            except Exception as exc:  # noqa: BLE001 — any step failure ends the run
                return "failed", f"{getattr(step, 'name', 'step')} failed: {exc}"
            if self._commands_during_run(self._clock()):
                if index < last:
                    self._rerun = True
                    return "interrupted", "stopped by user"
                return "ok", "stop asked"
        return "ok", ""

    @contextmanager
    def _beating(self) -> Iterator[None]:
        """Keep the heartbeat fresh from a side thread while steps run."""
        done = threading.Event()

        def beat() -> None:
            store = DeskStore(self._home)
            try:
                while not done.wait(self._beat_s):
                    store.beat(self._clock())
            finally:
                store.close()

        thread = threading.Thread(target=beat, name="desk-heartbeat", daemon=True)
        thread.start()
        try:
            yield
        finally:
            done.set()
            thread.join()

    def _finish_stop(self) -> None:
        self._db.save_resume_point({"last_run_id": self._db.last_run_id(), "rerun": self._rerun})
        self._set(DeskState.STOPPED, self._clock(), "stopped by user")
        log.info("[Desk] Desk stopped and saved")

    # ── helpers ───────────────────────────────────────────────────────────

    @property
    def _db(self) -> DeskStore:
        if self._store is None:
            raise RuntimeError("desk is not started")
        return self._store

    def _set(
        self, state: DeskState, now: datetime, message: str = "", pid: int | None = None
    ) -> None:
        self._state = state
        self._db.set_state(state, now, message, pid)
        self._last_beat = now
