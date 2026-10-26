"""
Module: MD-GUI-029.001.M01 — Scheduler task table
Parent SRD: SRD-GUI-029.001

Settings → Scheduler task table (FO-GUI-029): one row each for Start TWS, Start USSwing
and Close both with a Windows status pill, a folded TWS login and Remove all tasks.
Windows calls (schtasks, Credential Manager) run on background threads.
"""
from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import (
    QCoreApplication,
    QObject,
    QThread,
    Qt,
    QTime,
    pyqtBoundSignal,
    pyqtSignal,
)
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui import scheduler_dialog as sd
from us_swing.gui.icons import set_icon
from us_swing.gui.scheduler_store import (
    CloseConfig,
    SchedulerConfig,
    USSwingConfig,
    load_close_config,
    load_scheduler_config,
    load_usswing_config,
)
from us_swing.gui.theme import C

_log = logging.getLogger(__name__)

_DAYS = (("Mon–Fri", "weekdays"), ("Every day", "daily"))
_PILL_TEXT = {"installed": "INSTALLED", "missing": "MISSING", "changed": "CHANGED",
              "off": "OFF", "checking": "…", "failed": "FAILED"}
_ROW_LABEL = {"tws": "Start TWS", "app": "Start USSwing", "close": "Close both"}


def _repolish(widget: QWidget, state: str) -> None:
    widget.setProperty("state", state)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


def _to_qtime(text: str) -> QTime:
    hour, _, minute = text.partition(":")
    try:
        return QTime(int(hour), int(minute))
    except ValueError:
        return QTime(9, 0)


class _Job(QThread):
    """Runs one slow Windows call off the GUI thread and hands back its result."""

    result_ready = pyqtSignal(object)

    def __init__(self, fn: Callable[[], object], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 — shown on the pills, never crashes the dialog
            result = exc
        self.result_ready.emit(result)


@dataclasses.dataclass
class _Row:
    """Widgets of one task row; ``days`` and ``exe`` are None for Close both."""

    on: QCheckBox
    time: QTimeEdit
    days: QComboBox | None
    exe: QLineEdit | None
    pill: QLabel


class SchedulerTable(QWidget):
    """Task table, status pills, TWS login and Remove all (SRD-GUI-029.001–.006)."""

    repair_needed = pyqtSignal()   # a switched-on task is missing in Windows

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._jobs: list[_Job] = []
        self._status_job: _Job | None = None
        self._status_gen = 0          # bumped on apply / remove / load; older results dropped
        self._recheck = False         # a status check was asked for while one ran
        self._busy = False            # a write or remove job is running
        self._apply_again = False
        self._load_after = False
        self._fill_worker: QThread | None = None
        self._states: dict[str, str] = {}
        self._changed: set[str] = set()
        self._errors: dict[str, str] = {}
        self._us = USSwingConfig()
        self._ibkr = SchedulerConfig()
        self._close = CloseConfig()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for col, head in enumerate(("ON", "TASK", "TIME", "DAYS", "PROGRAM", "WINDOWS")):
            label = QLabel(head)
            label.setObjectName("panel_group")
            grid.addWidget(label, 0, col)
        self._rows: dict[str, _Row] = {}
        for index, key in enumerate(("tws", "app", "close"), start=1):
            self._rows[key] = self._build_row(grid, index, key)
        grid.setColumnStretch(4, 1)
        layout.addLayout(grid)

        # ── TWS login, folded (SRD-GUI-029.003) ───────────────────────────────
        self._login_btn = QPushButton()
        self._login_btn.setObjectName("login_fold")
        self._login_btn.setCheckable(True)
        self._login_btn.toggled.connect(self._on_login_toggled)
        self._login_box = QWidget()
        box = QGridLayout(self._login_box)
        box.setContentsMargins(22, 0, 0, 0)
        box.setHorizontalSpacing(10)
        box.setVerticalSpacing(6)
        self._user = QLineEdit()
        self._user.setPlaceholderText("IBKR username")
        self._pwd = QLineEdit()
        self._pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd.setPlaceholderText("Password")
        self._eye = QPushButton()
        set_icon(self._eye, "eye", "neutral")
        self._eye.setCheckable(True)
        self._eye.setFixedWidth(C.BTN_H)
        self._eye.setToolTip("Show password")
        self._eye.toggled.connect(self._on_eye_toggled)
        self._auto = QCheckBox("Fill in the TWS login automatically")
        self._fill_btn = QPushButton("Fill TWS login now")
        self._fill_btn.clicked.connect(self._on_fill_now)
        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(6)
        pwd_row.addWidget(self._pwd, 1)
        pwd_row.addWidget(self._eye)
        hint = QLabel("Saved in Windows Credential Manager. You still approve the IBKR 2FA "
                      "on your phone.")
        hint.setObjectName("details_key")
        hint.setWordWrap(True)
        box.addWidget(QLabel("Username"), 0, 0)
        box.addWidget(self._user, 0, 1)
        box.addWidget(QLabel("Password"), 1, 0)
        box.addLayout(pwd_row, 1, 1)
        box.addWidget(self._auto, 2, 1)
        fill_row = QHBoxLayout()
        fill_row.addWidget(self._fill_btn)
        fill_row.addStretch()
        box.addLayout(fill_row, 3, 1)
        box.addWidget(hint, 4, 1)
        box.setColumnStretch(1, 1)
        self._login_box.hide()
        layout.addWidget(self._login_btn)
        layout.addWidget(self._login_box)

        # ── Footer (SRD-GUI-029.004–.005) ─────────────────────────────────────
        footer = QHBoxLayout()
        self._note = QLabel("Apply writes these tasks to Windows.")
        self._note.setObjectName("details_key")
        self._note.setWordWrap(True)
        self._remove_btn = QPushButton("Remove all tasks…")
        self._remove_btn.setObjectName("link_danger")
        set_icon(self._remove_btn, "trash-2", "danger")
        self._remove_btn.clicked.connect(self.remove_all)
        footer.addWidget(self._note, 1)
        footer.addWidget(self._remove_btn)
        layout.addLayout(footer)

        for key, row in self._rows.items():
            for widget in self._row_inputs(row):
                _edited_signal(widget).connect(lambda *_a, k=key: self._on_edited(k))
        for widget in (self._user, self._pwd, self._auto):
            _edited_signal(widget).connect(lambda *_a: self._on_edited("tws"))

        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._wait_for_jobs)
        self.load()

    def _build_row(self, grid: QGridLayout, index: int, key: str) -> _Row:
        on = QCheckBox()
        on.setToolTip(f"{_ROW_LABEL[key]} on or off")
        time = QTimeEdit()
        time.setDisplayFormat("HH:mm")
        time.setFixedWidth(80)
        grid.addWidget(on, index, 0)
        grid.addWidget(QLabel(_ROW_LABEL[key]), index, 1)
        grid.addWidget(time, index, 2)
        days: QComboBox | None = None
        exe: QLineEdit | None = None
        if key == "close":
            same = QLabel("Same as start")
            same.setObjectName("details_key")
            dash = QLabel("—")
            dash.setObjectName("details_key")
            grid.addWidget(same, index, 3)
            grid.addWidget(dash, index, 4)
        else:
            days = QComboBox()
            for text, value in _DAYS:
                days.addItem(text, value)
            exe = QLineEdit()
            exe.setPlaceholderText("Choose the program…")
            browse = QPushButton()
            set_icon(browse, "search", "neutral")
            browse.setFixedWidth(C.BTN_H)
            browse.setToolTip("Choose the program")
            browse.clicked.connect(lambda _c=False, e=exe: self._on_browse(e))
            program = QHBoxLayout()
            program.setSpacing(4)
            program.addWidget(exe, 1)
            program.addWidget(browse)
            grid.addWidget(days, index, 3)
            grid.addLayout(program, index, 4)
        pill = QLabel("…")
        pill.setObjectName("task_pill")
        grid.addWidget(pill, index, 5, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        return _Row(on, time, days, exe, pill)

    @staticmethod
    def _row_inputs(row: _Row) -> list[QWidget]:
        widgets: list[QWidget] = [row.on, row.time]
        if row.days is not None:
            widgets.append(row.days)
        if row.exe is not None:
            widgets.append(row.exe)
        return widgets

    @property
    def inputs(self) -> list[QWidget]:
        """Every field, for the Settings dialog's change tracking."""
        widgets = [w for row in self._rows.values() for w in self._row_inputs(row)]
        return [*widgets, self._user, self._pwd, self._auto]

    # ── Load and collect ──────────────────────────────────────────────────────

    def load(self) -> None:
        """Fill the table from the saved configs; never touches Windows tasks."""
        if self._busy:   # a write is saving these configs; reload once it ends
            self._load_after = True
            return
        self._status_gen += 1
        # Never set up before: the rows start switched off, so Apply creates nothing.
        us = load_usswing_config() or USSwingConfig(enabled=False)
        ibkr = load_scheduler_config() or SchedulerConfig(
            exe_path=sd.find_tws_exe() or "", enabled=False)
        self._us, self._ibkr, self._close = us, ibkr, load_close_config()
        for widget in self.inputs:
            widget.blockSignals(True)
        for key, cfg in (("tws", ibkr), ("app", us)):
            row = self._rows[key]
            row.on.setChecked(cfg.enabled)
            row.time.setTime(_to_qtime(cfg.launch_time))
            assert row.days is not None and row.exe is not None
            row.days.setCurrentIndex(0 if cfg.days == "weekdays" else 1)
            row.exe.setText(cfg.exe_path)
            row.exe.setCursorPosition(0)   # show the start of a long path
        self._rows["close"].on.setChecked(self._close.enabled)
        self._rows["close"].time.setTime(_to_qtime(self._close.close_time))
        self._user.setText(ibkr.ibkr_username)
        self._pwd.setText(sd.load_ibkr_password(ibkr.ibkr_username))
        self._auto.setChecked(ibkr.auto_login)
        for widget in self.inputs:
            widget.blockSignals(False)
        self._changed.clear()
        self._errors.clear()
        self._refresh_login_text()
        self._paint_pills()

    def _collect(self) -> tuple[USSwingConfig, SchedulerConfig, CloseConfig, str]:
        def hhmm(edit: QTimeEdit) -> str:
            return edit.time().toString("HH:mm")

        tws, app, close = self._rows["tws"], self._rows["app"], self._rows["close"]
        assert tws.days and tws.exe and app.days and app.exe
        ibkr = dataclasses.replace(
            self._ibkr, enabled=tws.on.isChecked(), launch_time=hhmm(tws.time),
            days=str(tws.days.currentData()), exe_path=tws.exe.text().strip(),
            ibkr_username=self._user.text().strip(), auto_login=self._auto.isChecked(),
        )
        us = dataclasses.replace(
            self._us, enabled=app.on.isChecked(), launch_time=hhmm(app.time),
            days=str(app.days.currentData()), exe_path=app.exe.text().strip(),
        )
        closing = CloseConfig(enabled=close.on.isChecked(), close_time=hhmm(close.time))
        return us, ibkr, closing, self._pwd.text()

    # ── Apply, status, remove ─────────────────────────────────────────────────

    def apply(self) -> None:
        """Write the table to Windows in the background (SRD-GUI-029.004)."""
        if self._busy:   # one write at a time; this one runs when the current one ends
            self._apply_again = True
            return
        self._set_busy(True)
        self._status_gen += 1
        us, ibkr, close, password = self._collect()
        self._us, self._ibkr, self._close = us, ibkr, close
        self._states = {key: "checking" for key in self._rows}
        self._changed.clear()
        self._paint_pills()
        self._note.setText("Writing tasks to Windows…")
        self._run(lambda: sd.write_tasks(us, ibkr, close, password), self._on_written)

    def _on_written(self, result: object) -> None:
        self._set_busy(False)
        errors = result if isinstance(result, dict) else {"tws": str(result)}
        self._errors = {str(k): str(v) for k, v in errors.items()}
        for key in self._errors:
            _log.warning("[Scheduler] Could not write the %s task to Windows", _ROW_LABEL[key])
        self._note.setText(
            "Some tasks could not be written. Hover the red pill to see why."
            if self._errors else "Tasks written to Windows.")
        self._after_job()

    def refresh_status(self) -> None:
        """Ask Windows which tasks exist, off the GUI thread (SRD-GUI-029.002)."""
        if self._status_job is not None:
            self._recheck = True
            return
        us, ibkr, close, gen = self._us, self._ibkr, self._close, self._status_gen
        self._status_job = self._run(lambda: sd.task_states(us, ibkr, close),
                                     lambda result: self._on_states(result, gen))

    def _on_states(self, result: object, gen: int = -1) -> None:
        self._status_job = None
        if self._recheck or gen not in (-1, self._status_gen):
            self._recheck = False   # stale: the table changed while this check ran
            self.refresh_status()
            return
        if not isinstance(result, dict):
            _log.warning("[Scheduler] Could not read the task list from Windows")
            self._states = {key: "failed" for key in self._rows}
        else:
            self._states = {str(k): str(v) for k, v in result.items()}
        self._paint_pills()
        if any(self._states.get(key) == "missing" for key in self._rows
               if key not in self._errors):
            self.repair_needed.emit()

    def remove_all(self) -> None:
        """Delete every task, the configs and the password after a confirm (SRD-GUI-029.005)."""
        # Imported here: the module pulls in the execution package, which must not load
        # before the app has set up the database modules.
        from us_swing.gui.active_cycles_panel import _ConfirmDialog

        dialog = _ConfirmDialog(
            "REMOVE ALL TASKS",
            "Remove all scheduled tasks?\n"
            "Deletes the start and close tasks from Windows and the saved TWS password.",
            confirm_text="Remove", accent=C.RED, parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if self._busy:
            return
        self._set_busy(True)
        us, ibkr = self._us, self._ibkr
        self._note.setText("Removing tasks…")
        self._run(lambda: sd.remove_tasks(us, ibkr), self._on_removed)

    def _on_removed(self, result: object) -> None:
        self._set_busy(False)
        failed = not isinstance(result, list) or bool(result)
        if failed:
            _log.warning("[Scheduler] Some tasks could not be removed from Windows")
        self._apply_again = False   # the configs are gone; nothing left to write
        self.load()
        self._note.setText("Some tasks could not be removed." if failed
                           else "All tasks removed.")
        self._after_job()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _run(self, fn: Callable[[], object], done: Callable[[object], None]) -> _Job:
        job = _Job(fn, self)
        job.result_ready.connect(done)
        job.finished.connect(lambda: self._jobs.remove(job) if job in self._jobs else None)
        self._jobs.append(job)
        job.start()
        return job

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._remove_btn.setEnabled(not busy)

    def _after_job(self) -> None:
        """Run what waited for the last write or remove, then re-check Windows."""
        if self._load_after:
            self._load_after = False
            self.load()
        if self._apply_again:
            self._apply_again = False
            self.apply()
            return
        self.refresh_status()

    def _wait_for_jobs(self) -> None:
        for job in list(self._jobs):
            job.wait(5000)

    def _paint_pills(self) -> None:
        for key, row in self._rows.items():
            if key in self._changed:
                state = "changed"
            elif key in self._errors:
                state = "failed"
            else:
                state = self._states.get(key, "checking")
            row.pill.setText(_PILL_TEXT[state])
            row.pill.setToolTip(self._errors.get(key, ""))
            _repolish(row.pill, state)

    def _on_edited(self, key: str) -> None:
        self._changed.add(key)
        self._errors.pop(key, None)
        self._refresh_login_text()
        self._paint_pills()

    def _refresh_login_text(self) -> None:
        user = self._user.text().strip() or "no username"
        mode = "fill in automatically" if self._auto.isChecked() else "typed by hand"
        arrow = "▾" if self._login_btn.isChecked() else "▸"
        self._login_btn.setText(f"{arrow}  TWS login · {user} · {mode}")

    def _on_login_toggled(self, shown: bool) -> None:
        self._login_box.setVisible(shown)
        self._refresh_login_text()

    def _on_eye_toggled(self, shown: bool) -> None:
        self._pwd.setEchoMode(QLineEdit.EchoMode.Normal if shown
                              else QLineEdit.EchoMode.Password)

    def _on_browse(self, edit: QLineEdit) -> None:
        start = str(Path(edit.text()).parent) if edit.text() else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Choose program", start, "Programs (*.exe)")
        if path:
            edit.setText(path)

    def _on_fill_now(self) -> None:
        if self._fill_worker is not None and self._fill_worker.isRunning():
            return
        username, password = self._user.text().strip(), self._pwd.text()
        if not username or not password:
            self._note.setText("Enter the TWS username and password first.")
            return
        self._fill_btn.setEnabled(False)
        self._fill_btn.setText("Filling…")
        worker = sd.FillWorker(username, password, self)
        worker.done.connect(self._on_fill_done)
        self._fill_worker = worker
        worker.start()

    def _on_fill_done(self, error: str) -> None:
        self._fill_btn.setEnabled(True)
        self._fill_btn.setText("Fill TWS login now")
        self._note.setText(error.splitlines()[0] if error
                           else "Login typed. Approve the 2FA prompt on your phone.")

    def showEvent(self, event: QShowEvent | None) -> None:
        super().showEvent(event)
        self.refresh_status()


def _edited_signal(widget: QWidget) -> pyqtBoundSignal:
    """The signal a table field emits when the user changes it."""
    if isinstance(widget, QLineEdit):
        return widget.textEdited
    if isinstance(widget, QTimeEdit):
        return widget.timeChanged
    if isinstance(widget, QComboBox):
        return widget.currentIndexChanged
    assert isinstance(widget, QCheckBox)
    return widget.toggled
