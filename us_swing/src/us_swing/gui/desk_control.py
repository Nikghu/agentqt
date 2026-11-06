"""
Module: MD-GUI-034.002.M02 — Desk control
Parent SRD: SRD-GUI-034.002
"""
from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from us_swing.core.desk_contract import (
    LIVE_STATES,
    NOT_RESPONDING,
    CommandKind,
    DeskState,
    DeskStatus,
    launch_desk,
    read_status,
    send_command,
)
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C

_log = logging.getLogger(__name__)

_POLL_MS = 2000
_FAST_MS = 1000
_FAST_TICKS = 5
_SHUTDOWN_WAIT_MS = 1500


def _is_alive(state: DeskState, message: str) -> bool:
    """True when a desk process is running; a stale heartbeat means it is dead."""
    return state in LIVE_STATES and not (state is DeskState.ERROR and message == NOT_RESPONDING)


def allowed_actions(state: DeskState, message: str = "") -> frozenset[str]:
    """Return the desk buttons that may be used in ``state``.

    Start is allowed when Off, Stopped, or Error with the "not responding" message
    (the process is dead). Any other Error is a live desk that failed a run, so
    Pause and Stop work and Start does not.

    Args:
        state: Current desk state.
        message: Status message from the desk.

    Returns:
        A subset of ``start``, ``pause``, ``resume`` and ``stop``.
    """
    if state in (DeskState.OFF, DeskState.STOPPED):
        return frozenset({"start"})
    if state is DeskState.ERROR:
        if message == NOT_RESPONDING:
            return frozenset({"start"})
        return frozenset({"pause", "stop"})
    if state in (DeskState.RUNNING, DeskState.SLEEPING):
        return frozenset({"pause", "stop"})
    if state is DeskState.PAUSED:
        return frozenset({"resume", "stop"})
    return frozenset()


_JOBS: set[_Job] = set()


class _Job(QThread):
    """Runs one desk call off the GUI thread and hands back its result."""

    result_ready = pyqtSignal(object)

    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 — logged by the poller, never crashes the GUI
            result = exc
        self.result_ready.emit(result)


def _release_job(job: _Job) -> None:
    _JOBS.discard(job)
    job.deleteLater()


class DeskPoller(QObject):
    """Reads the desk status every 2 seconds and runs desk commands off the UI thread."""

    status_changed = pyqtSignal(object)  # DeskStatus
    command_failed = pyqtSignal(str)
    busy_changed = pyqtSignal(bool)

    @property
    def home(self) -> Path | None:
        """The desk folder this poller reads (``None`` = the default folder)."""
        return self._home

    def __init__(self, home: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._home = home
        self._status = DeskStatus(DeskState.OFF)
        self._job: _Job | None = None
        self._queue: deque[Callable[[], object]] = deque()
        self._fast_left = 0
        self._busy = False
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        # timer → timeout → poller → _tick
        self._timer.timeout.connect(self._tick)

    @property
    def status(self) -> DeskStatus:
        """The last status read."""
        return self._status

    @property
    def busy(self) -> bool:
        """True while a command or launch is queued or running."""
        return self._busy

    def start(self) -> None:
        """Begin polling now and then every 2 seconds."""
        self._timer.start()
        self._tick()

    def command(self, kind: CommandKind) -> None:
        """Send ``kind`` to the desk, then read the status every second for 5 seconds."""

        def work() -> object:
            send_command(kind, self._home)
            return read_status(self._home)

        self._submit(work, fast=True)

    def start_desk(self) -> None:
        """Launch the desk unless a live one already exists (checked just before)."""

        def work() -> object:
            current = read_status(self._home)
            if not _is_alive(current.state, current.message):
                launch_desk()
            return read_status(self._home)

        self._submit(work, fast=True)

    def shutdown(self) -> None:
        """Stop polling and wait briefly; a job still running is left to finish on its own."""
        self._timer.stop()
        self._queue.clear()
        job = self._job
        if job is not None and job.isRunning():
            job.wait(_SHUTDOWN_WAIT_MS)

    def _tick(self) -> None:
        if self._fast_left > 0:
            self._fast_left -= 1
            if self._fast_left == 0:
                self._timer.setInterval(_POLL_MS)
        if self._job is None:
            self._start_job(lambda: read_status(self._home), action=False)

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busy_changed.emit(busy)

    def _submit(self, fn: Callable[[], object], fast: bool) -> None:
        if fast:
            self._fast_left = _FAST_TICKS
            self._timer.setInterval(_FAST_MS)
            self._set_busy(True)
        if self._job is not None:
            if fast:
                self._queue.append(fn)
            return
        self._start_job(fn, action=fast)

    def _start_job(self, fn: Callable[[], object], action: bool) -> None:
        job = _Job(fn)
        job.setProperty("action", action)
        self._job = job
        _JOBS.add(job)
        # job → result_ready → poller → _on_result
        job.result_ready.connect(self._on_result)
        # job → finished → module → _release_job
        job.finished.connect(lambda j=job: _release_job(j))
        job.start()

    def _on_result(self, result: object) -> None:
        job, self._job = self._job, None
        was_action = bool(job.property("action")) if job is not None else False
        if isinstance(result, DeskStatus):
            self._status = result
            self.status_changed.emit(result)
        elif isinstance(result, Exception):
            reason = _reason(result)
            _log.warning("[Desk] Desk call failed: %s", reason)
            if was_action:
                self.command_failed.emit(reason)
        if self._queue:
            self._start_job(self._queue.popleft(), action=True)
        elif was_action:
            self._set_busy(False)


def _reason(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "desk is off"
    return str(exc) or type(exc).__name__


_PILL_COLOURS: dict[DeskState, str] = {
    DeskState.RUNNING: "GREEN",
    DeskState.SLEEPING: "GREEN",
    DeskState.PAUSED: "YELLOW",
    DeskState.STOPPING: "ORANGE",
    DeskState.STOPPED: "MUTED",
    DeskState.OFF: "MUTED",
    DeskState.ERROR: "RED",
}


class DeskBar(QWidget):
    """State pill and Start, Pause, Resume and Stop buttons for the desk."""

    def __init__(self, poller: DeskPoller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._poller = poller
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.pill = QLabel()
        row.addWidget(self.pill)
        self.note = QLabel()
        self.note.setStyleSheet(f"color: {C.MUTED};")
        row.addWidget(self.note)
        self._status = poller.status
        self._pill_state: DeskState | None = None
        self._error = ""
        self.buttons: dict[str, QPushButton] = {}
        specs = (
            ("start", "Start", "play", "go"),
            ("pause", "Pause", "pause", "neutral"),
            ("resume", "Resume", "play", "go"),
            ("stop", "Stop", "square-x", "danger"),
        )
        for key, text, icon_name, role in specs:
            button = QPushButton(text)
            set_icon(button, icon_name, role)
            self.buttons[key] = button
            row.addWidget(button)
        # buttons → clicked → poller → start_desk / command
        self.buttons["start"].clicked.connect(self._poller.start_desk)
        self.buttons["pause"].clicked.connect(lambda: self._poller.command(CommandKind.PAUSE))
        self.buttons["resume"].clicked.connect(lambda: self._poller.command(CommandKind.RESUME))
        self.buttons["stop"].clicked.connect(lambda: self._poller.command(CommandKind.STOP))
        # poller → status_changed → bar → set_status
        self._poller.status_changed.connect(self.set_status)
        # poller → busy_changed → bar → _on_busy;  poller → command_failed → bar → _on_failed
        self._poller.busy_changed.connect(self._on_busy)
        self._poller.command_failed.connect(self._on_failed)
        self.set_status(self._poller.status)

    def set_status(self, status: DeskStatus) -> None:
        """Show ``status`` on the pill and enable the buttons it allows."""
        self._status = status
        self.pill.setText(status.state.value)
        if status.state is not self._pill_state:
            self._pill_state = status.state
            colour = getattr(C, _PILL_COLOURS[status.state])
            self.pill.setStyleSheet(
                f"color: {colour}; border: 1px solid {colour}; border-radius: 9px;"
                " padding: 2px 10px;"
            )
        self._refresh_tooltip()
        self._refresh_buttons()

    def _refresh_tooltip(self) -> None:
        status = self._status
        stamp = status.heartbeat_at
        beat = stamp.astimezone().strftime("%H:%M:%S") if stamp else "none"
        tip = f"{status.message or status.state.value}\nLast heartbeat: {beat}"
        if self._error:
            tip = f"{self._error}\n{tip}"
        self.pill.setToolTip(tip)

    def _refresh_buttons(self) -> None:
        allowed = allowed_actions(self._status.state, self._status.message)
        busy = self._poller.busy
        for key, button in self.buttons.items():
            button.setEnabled(key in allowed and not busy)

    def _on_busy(self, busy: bool) -> None:
        if busy:
            self._error = ""
            self.note.setText("")
        self._refresh_buttons()

    def _on_failed(self, reason: str) -> None:
        self._error = f"Could not send: {reason}"
        self.note.setText(self._error)
        self._refresh_tooltip()
