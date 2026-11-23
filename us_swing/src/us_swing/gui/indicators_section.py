"""
Module: MD-GUI-046.003.M02 — Settings Indicators section
Parent SRD: SRD-GUI-046.003

Lists the active user's custom indicators and lets the user import, export,
remove and reload them (SRD-GUI-046.003–.005).
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.indicator_plugins import (
    REGISTRY,
    PluginStatus,
    builtin_names,
    check_file,
    plugin_dir,
)
from us_swing.gui.icons import mark_danger, set_icon
from us_swing.gui.popups import confirm, notify

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
        set_icon(self.import_btn, "plus", "add")
        set_icon(self.export_btn, "download")
        set_icon(self.remove_btn, "trash-2", "danger")
        set_icon(self.reload_btn, "refresh-cw")
        mark_danger(self.remove_btn)
        self.import_btn.clicked.connect(self._on_import)
        self.export_btn.clicked.connect(self._on_export)
        self.remove_btn.clicked.connect(self._on_remove)
        self.reload_btn.clicked.connect(self._on_reload)

        buttons = QHBoxLayout()
        for btn in (self.import_btn, self.export_btn, self.remove_btn, self.reload_btn):
            buttons.addWidget(btn)
        buttons.addStretch()

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
        has = self.selected() is not None
        self.export_btn.setEnabled(has)
        self.remove_btn.setEnabled(has)

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
