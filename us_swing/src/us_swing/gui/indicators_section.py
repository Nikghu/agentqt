"""
Module: MD-GUI-046.003.M02 — Settings Indicators section
Parent SRD: SRD-GUI-046.003

Lists the active user's custom indicators and lets the user import, export,
remove, reload and check them, and start a new one (SRD-GUI-046.003–.007).
"""
from __future__ import annotations

import logging
import math
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.indicator_plugins import (
    REGISTRY,
    NoCandleData,
    PluginSpec,
    PluginStatus,
    builtin_names,
    check_file,
    plugin_dir,
    run_plugin,
)
from us_swing.gui.frameless_dialog import FramelessDialog
from us_swing.gui.icons import mark_danger, set_icon
from us_swing.gui.indicator_guides import api_guide
from us_swing.gui.indicator_project import (
    check_command,
    create_project,
    ensure_project_files,
    env_python,
    list_projects,
    open_project,
)
from us_swing.gui.indicator_python import PythonSetupError, python_ready, setup_python
from us_swing.gui.popups import confirm, notify
from us_swing.gui.theme import C

CHECK_ROWS = 20
_MARKET_TZ = "America/New_York"

if TYPE_CHECKING:
    from us_swing.gui.app_service import AppService

_log = logging.getLogger(__name__)

_COLUMNS = ["Name", "Version", "Status", "Details"]


def strategies_using(name: str) -> list[str]:
    """Names of the saved strategies whose conditions use indicator ``name``."""
    from us_swing.execution.strategy_engine._engine import plugins_used
    from us_swing.gui.strategy_store import load_strategies

    return sorted(cfg.name for cfg in load_strategies() if name in plugins_used(cfg))


class IndicatorsSection(QWidget):
    """Settings "Indicators" section (SRD-GUI-046.003–.005)."""

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = demo
        self._statuses: tuple[PluginStatus, ...] = ()

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        vertical = self.table.verticalHeader()
        header = self.table.horizontalHeader()
        assert vertical is not None and header is not None
        vertical.setVisible(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, 80)
        self.table.itemSelectionChanged.connect(self._sync_buttons)

        self.import_btn = QPushButton("Import")
        self.export_btn = QPushButton("Export")
        self.remove_btn = QPushButton("Remove")
        self.reload_btn = QPushButton("Reload")
        self.check_btn = QPushButton("Check")
        self.new_btn = QPushButton("New indicator")
        self.python_btn = QPushButton("Set up Python")
        self.help_btn = QPushButton("Help")
        set_icon(self.import_btn, "plus", "add")
        set_icon(self.export_btn, "download")
        set_icon(self.remove_btn, "trash-2", "danger")
        set_icon(self.reload_btn, "refresh-cw")
        set_icon(self.check_btn, "play", "go")
        set_icon(self.new_btn, "folder")
        mark_danger(self.remove_btn)
        self.import_btn.clicked.connect(self._on_import)
        self.export_btn.clicked.connect(self._on_export)
        self.remove_btn.clicked.connect(self._on_remove)
        self.reload_btn.clicked.connect(self._on_reload)
        self.check_btn.clicked.connect(self._on_check)
        self.new_btn.clicked.connect(self._on_new)
        self.python_btn.clicked.connect(lambda: PythonSetupDialog(self).exec())
        self.help_btn.clicked.connect(lambda: HelpDialog(self).exec())

        buttons = QHBoxLayout()
        for btn in (self.import_btn, self.export_btn, self.remove_btn, self.reload_btn,
                    self.check_btn):
            buttons.addWidget(btn)
        buttons.addStretch()
        for btn in (self.new_btn, self.python_btn, self.help_btn):
            buttons.addWidget(btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)
        self.refresh()

    def showEvent(self, event: QShowEvent | None) -> None:  # noqa: N802
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        """Show the registry's files for the active user."""
        self._statuses = REGISTRY.statuses()
        self.table.setRowCount(len(self._statuses))
        for row, status in enumerate(self._statuses):
            details = status.notes if status.ok else status.reasons
            cells = [status.name, status.version, "Loaded" if status.ok else "Refused",
                     details[0] if details else ""]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 3 and details:
                    item.setToolTip("\n".join(details))
                if col in (1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
        self._sync_buttons()

    def selected(self) -> PluginStatus | None:
        model = self.table.selectionModel()
        rows = model.selectedRows() if model is not None else []
        return self._statuses[rows[0].row()] if rows else None

    def _sync_buttons(self) -> None:
        status = self.selected()
        self.export_btn.setEnabled(status is not None)
        self.remove_btn.setEnabled(status is not None)
        self.check_btn.setEnabled(status is not None and status.ok)

    def _folder(self) -> Path:
        return plugin_dir(self._demo.get_active_user().user_id, REGISTRY.root)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _pick_import_file(self) -> str:
        path, _ = QFileDialog.getOpenFileName(self, "Import indicator", str(Path.home()),
                                              "Python files (*.py)")
        return path

    def _pick_export_file(self, file_name: str) -> str:
        path, _ = QFileDialog.getSaveFileName(self, "Export indicator",
                                              str(Path.home() / file_name),
                                              "Python files (*.py)")
        return path

    def _on_import(self) -> None:
        picked = self._pick_import_file()
        if not picked:
            return
        source = Path(picked)
        warning = ("An indicator file runs Python code on this PC.\n"
                   "Import only files you wrote or trust.")
        target = self._folder() / source.name
        if target.exists():
            warning += f"\nThe indicator file {source.name} you have now will be replaced."
        if not confirm(self, "Import indicator", warning, confirm_text="Import", danger=True):
            return
        taken = [s.name for s in REGISTRY.statuses() if s.ok and s.file != source.name]
        report = check_file(source, builtin_names=builtin_names(), taken_names=taken,
                            candle_probe=self._demo.indicator_probe)
        if not report.ok or report.spec is None:
            notify(self, "Import indicator",
                   f"{source.name} was not added\n" + "\n".join(report.reasons), "warning")
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
        _log.info("[Indicators] Added %s %s", report.spec.name, report.spec.version)
        self._demo.reload_indicators()
        self.refresh()

    def _on_export(self) -> None:
        status = self.selected()
        if status is None:
            return
        picked = self._pick_export_file(status.file)
        if not picked:
            return
        try:
            shutil.copyfile(self._folder() / status.file, picked)
        except OSError as exc:
            notify(self, "Export indicator", f"Could not save the copy\n{exc}", "error")

    def _on_remove(self) -> None:
        status = self.selected()
        if status is None:
            return
        users = strategies_using(status.name)
        text = f"Remove {status.name}?"
        if users:
            text += f"\nThese strategies use it and will be stopped: {', '.join(users)}"
        if not confirm(self, "Remove indicator", text, confirm_text="Remove", danger=True):
            return
        if users:
            self._demo.stop_strategies(users)
        (self._folder() / status.file).unlink(missing_ok=True)
        _log.info("[Indicators] Removed %s", status.name)
        self._demo.reload_indicators()
        self.refresh()

    def _on_reload(self) -> None:
        self._demo.reload_indicators()
        self.refresh()

    def _on_check(self) -> None:
        status = self.selected()
        spec = REGISTRY.get(status.name) if status is not None else None
        if spec is None:
            return
        dialog = CheckDialog(spec, self._demo.get_candle_symbols(), self._demo.candle_frames,
                             self)
        dialog.exec()

    def _on_new(self) -> None:
        dialog = ProjectDialog(self._demo.get_active_user().user_id, self)
        if dialog.exec() != FramelessDialog.DialogCode.Accepted or dialog.folder is None:
            return
        folder = dialog.folder
        if dialog.created:
            _log.info("[Indicators] Made a new indicator project in %s", folder)
        else:
            added = ensure_project_files(folder)
            if added:
                _log.info("[Indicators] Added %d missing file(s) to the %s project",
                          len(added), folder.name.upper())
        if open_project(folder):
            text = f"The project was opened in VS Code\n{folder}"
        else:
            text = f"VS Code was not found, so the project folder was opened\n{folder}"
        notify(self, "New indicator",
               text + "\nWhen the indicator is ready, add it here with Import")


def _cell(value: Any) -> str:
    if isinstance(value, pd.Timestamp):
        shown = value.tz_convert(_MARKET_TZ) if value.tzinfo is not None else value
        return shown.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, float):
        return "" if math.isnan(value) else f"{value:,.4f}"
    return str(value)


class _CheckRun(QObject):
    """Runs the indicator on one stock away from the screen thread."""

    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, spec: PluginSpec, symbol: str,
                 frames: Callable[[str], dict[str, pd.DataFrame]]) -> None:
        super().__init__()
        self._spec = spec
        self._symbol = symbol
        self._frames = frames

    def run(self) -> None:
        try:
            result = run_plugin(self._spec, {}, self._frames(self._symbol))
        except NoCandleData as exc:
            self.failed.emit(f"{self._symbol}: {exc}")
        except Exception as exc:  # noqa: BLE001 — user code; show what went wrong
            self.failed.emit(f"{self._spec.name} failed on {self._symbol}: "
                             f"{exc or type(exc).__name__}")
        else:
            self.done.emit(result.table().tail(CHECK_ROWS))


class CheckDialog(FramelessDialog):
    """Run one indicator on a chosen stock and show its last values (SRD-GUI-046.006)."""

    def __init__(self, spec: PluginSpec, symbols: list[str],
                 frames: Callable[[str], dict[str, pd.DataFrame]],
                 parent: QWidget | None = None) -> None:
        super().__init__(f"Check {spec.name}", min_width=620, min_height=520, parent=parent)
        self._spec = spec
        self._frames = frames
        self._thread: QThread | None = None
        self._run: _CheckRun | None = None

        self.stock = QComboBox()
        self.stock.setEditable(True)
        self.stock.addItems(symbols)
        self.stock.setFixedWidth(140)
        self.run_btn = QPushButton("Run")
        set_icon(self.run_btn, "play", "go")
        self.run_btn.clicked.connect(self.start)
        self.status = QLabel(f"Last {CHECK_ROWS} candles with default values")
        self.status.setWordWrap(True)
        self.table = QTableWidget(0, 0)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        vertical = self.table.verticalHeader()
        if vertical is not None:
            vertical.setVisible(False)

        top = QHBoxLayout()
        top.addWidget(QLabel("Stock"))
        top.addWidget(self.stock)
        top.addWidget(self.run_btn)
        top.addStretch()
        layout = self.content_layout()
        layout.addLayout(top)
        layout.addWidget(self.status)
        layout.addWidget(self.table, 1)

    def start(self) -> None:
        symbol = self.stock.currentText().strip().upper()
        if not symbol or self._thread is not None:
            return
        self.run_btn.setEnabled(False)
        self.status.setText(f"Running {self._spec.name} on {symbol}")
        self._thread = QThread(self)
        self._run = _CheckRun(self._spec, symbol, self._frames)
        self._run.moveToThread(self._thread)
        self._thread.started.connect(self._run.run)
        self._run.done.connect(self._show)
        self._run.failed.connect(self._fail)
        self._run.done.connect(self._thread.quit)
        self._run.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._finished)
        self._thread.start()

    def _show(self, table: pd.DataFrame) -> None:
        self.table.setColumnCount(len(table.columns))
        self.table.setHorizontalHeaderLabels([str(c) for c in table.columns])
        self.table.setRowCount(len(table))
        for row, values in enumerate(table.itertuples(index=False)):
            for col, value in enumerate(values):
                item = QTableWidgetItem(_cell(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                      | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.status.setText(f"Last {len(table)} candles of {self.stock.currentText().upper()}")

    def _fail(self, message: str) -> None:
        self.table.setRowCount(0)
        self.status.setText(message)

    def _finished(self) -> None:
        self._thread = None
        self._run = None
        self.run_btn.setEnabled(True)

    def reject(self) -> None:
        if self._thread is not None:
            self.status.setText("Still running; close again when it finishes")
            return
        super().reject()


class ProjectDialog(FramelessDialog):
    """Open an existing indicator project or make a new one (SRD-GUI-046.007, .009)."""

    def __init__(self, user_id: int, parent: QWidget | None = None) -> None:
        super().__init__("New indicator", min_width=380, min_height=420, parent=parent)
        self._user_id = user_id
        self.folder: Path | None = None
        self.created = False

        self.projects = QListWidget()
        for folder in list_projects(user_id):
            item = QListWidgetItem(folder.name.upper())
            item.setData(Qt.ItemDataRole.UserRole, str(folder))
            self.projects.addItem(item)
        self.open_btn = QPushButton("Open")
        set_icon(self.open_btn, "folder")
        self.open_btn.setEnabled(False)
        self.projects.itemSelectionChanged.connect(
            lambda: self.open_btn.setEnabled(bool(self.projects.selectedItems())))
        self.projects.itemDoubleClicked.connect(lambda _item: self._open())
        self.open_btn.clicked.connect(self._open)
        empty = QLabel("No projects yet")
        empty.setVisible(self.projects.count() == 0)
        self.projects.setVisible(self.projects.count() > 0)

        self.name = QLineEdit()
        self.name.setPlaceholderText("MY_ST")
        self.name.setStyleSheet("QLineEdit { outline: none; } QLineEdit:focus { outline: none; }")
        self.error = QLabel("")
        self.error.setStyleSheet(f"color: {C.RED};")
        self.error.setWordWrap(True)
        create = QPushButton("Create")
        create.clicked.connect(self._create)
        self.name.returnPressed.connect(self._create)

        layout = self.content_layout()
        layout.addWidget(_heading("Open a project"))
        layout.addWidget(self.projects, 1)
        layout.addWidget(empty)
        open_row = QHBoxLayout()
        open_row.addStretch()
        open_row.addWidget(self.open_btn)
        layout.addLayout(open_row)
        layout.addSpacing(8)
        layout.addWidget(_heading("Create a project"))
        layout.addWidget(QLabel("Indicator name"))
        layout.addWidget(self.name)
        layout.addWidget(self.error)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(create)
        layout.addLayout(row)

    def _open(self) -> None:
        items = self.projects.selectedItems()
        if not items:
            return
        self.folder = Path(items[0].data(Qt.ItemDataRole.UserRole))
        self.created = False
        self.accept()

    def _create(self) -> None:
        try:
            self.folder = create_project(self._user_id, self.name.text())
        except (ValueError, FileExistsError, OSError) as exc:
            self.error.setText(str(exc))
            return
        self.created = True
        self.accept()


class HelpDialog(FramelessDialog):
    """The indicator API guide (SRD-GUI-046.010)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Indicator guide", min_width=760, min_height=640, parent=parent)
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        self.text.setMarkdown(api_guide(check_command("my_st.py")))
        self.content_layout().addWidget(self.text, 1)


class _SetupRun(QObject):
    """Makes the shared Python environment away from the screen thread."""

    step = pyqtSignal(str)
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            python = setup_python(step=self.step.emit)
        except PythonSetupError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 — show any problem instead of crashing
            self.failed.emit(f"Python setup failed: {exc}")
        else:
            self.done.emit(str(python))


class PythonSetupDialog(FramelessDialog):
    """Make the shared Python for indicator tests and charts (SRD-GUI-046.013)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Set up Python", min_width=520, parent=parent)
        self._thread: QThread | None = None
        self._run: _SetupRun | None = None
        intro = QLabel("Only the test file and the chart preview need Python. Writing and "
                       "checking an indicator works without it.\nThis makes one Python "
                       "environment for all your indicator projects, with pandas, numpy and "
                       "pytest, from the Python installed on this PC.")
        intro.setWordWrap(True)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.start_btn = QPushButton()
        set_icon(self.start_btn, "play", "go")
        self.start_btn.clicked.connect(self.start)
        self._show_state()

        layout = self.content_layout()
        layout.addWidget(intro)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.start_btn)
        layout.addLayout(row)

    def _show_state(self) -> None:
        if python_ready():
            self.status.setText(f"Python is ready:\n{env_python()}")
            self.start_btn.setText("Set up again")
        else:
            self.status.setText("Not set up yet")
            self.start_btn.setText("Set up")

    def start(self) -> None:
        if self._thread is not None:
            return
        self.start_btn.setEnabled(False)
        self.status.setText("Looking for Python on this PC")
        self._thread = QThread(self)
        self._run = _SetupRun()
        self._run.moveToThread(self._thread)
        self._thread.started.connect(self._run.run)
        self._run.step.connect(self.status.setText)
        self._run.done.connect(self._done)
        self._run.failed.connect(self._failed)
        self._run.done.connect(self._thread.quit)
        self._run.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._finished)
        self._thread.start()

    def _done(self, python: str) -> None:
        _log.info("[Indicators] Python for indicator projects is ready")
        self.status.setText(f"Python is ready:\n{python}\nYour indicator projects now use "
                            "it. Reopen them in VS Code.")
        self.start_btn.setText("Set up again")

    def _failed(self, message: str) -> None:
        _log.warning("[Indicators] Python setup failed: %s", message)
        self.status.setText(message)
        self.start_btn.setText("Set up again")

    def _finished(self) -> None:
        self._thread = None
        self._run = None
        self.start_btn.setEnabled(True)

    def reject(self) -> None:
        if self._thread is not None:
            return
        super().reject()


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label
