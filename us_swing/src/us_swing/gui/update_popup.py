"""
Module: MD-GUI-027.005.M07 — Update popup
Parent SRD: SRD-GUI-027.005

Small popup from the sidebar Updates item: installed version, last check time and a
Check for Updates button.
"""
from __future__ import annotations

import datetime

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from us_swing import __version__
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C


def checked_text(stamp: float | None) -> str:
    """Describe the last update check, e.g. ``"last checked 25 Oct 09:14"``."""
    if stamp is None:
        return "not checked yet"
    return datetime.datetime.fromtimestamp(stamp).strftime("last checked %d %b %H:%M")


class UpdatePopup(QFrame):
    """Installed version, last check time and Check for Updates (SRD-GUI-027.005)."""

    update_found = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("update_popup")
        self._worker: QThread | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        title = QLabel("Updates")
        title.setObjectName("view_head")
        self._version = QLabel()
        self._version.setObjectName("details_key")
        self._check_btn = QPushButton("Check for Updates")
        set_icon(self._check_btn, "circle-arrow-up", "info")
        self._check_btn.clicked.connect(self._on_check)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self._check_btn)
        btn_row.addStretch()
        self._note = QLabel("")
        self._note.setWordWrap(True)
        self._note.hide()
        layout.addWidget(title)
        layout.addWidget(self._version)
        layout.addLayout(btn_row)
        layout.addWidget(self._note)
        self.setFixedWidth(280)

    def refresh(self) -> None:
        """Reread the last check time."""
        from updater_stub import last_check_time

        self._version.setText(f"Installed v{__version__} · {checked_text(last_check_time())}")

    def show_beside(self, anchor: QWidget) -> None:
        """Show the popup to the right of ``anchor``, bottom-aligned with it."""
        self.refresh()
        self.adjustSize()
        corner = anchor.mapToGlobal(anchor.rect().bottomRight())
        self.move(corner.x() + 8, corner.y() - self.height())
        self.show()

    def _set_note(self, text: str, colour: str) -> None:
        self._note.setStyleSheet(f"color: {colour}; font-size: 9pt;")
        self._note.setText(text)
        self._note.setVisible(bool(text))
        self.adjustSize()

    def _on_check(self) -> None:
        from update_dialog import _CheckWorker

        self._check_btn.setEnabled(False)
        self._set_note("Checking for updates…", C.GREEN)
        worker = _CheckWorker()
        worker.found.connect(self._on_found)
        worker.up_to_date.connect(self._on_up_to_date)
        worker.failed.connect(self._on_failed)
        worker.start()
        self._worker = worker

    def _on_found(self, info: object) -> None:
        from update_dialog import _UpdateDialog
        from updater_stub import UpdateInfo

        self._check_btn.setEnabled(True)
        self._set_note("", C.GREEN)
        self.refresh()
        self.update_found.emit()
        if isinstance(info, UpdateInfo):
            self.hide()
            _UpdateDialog(info).exec()

    def _on_up_to_date(self) -> None:
        self._check_btn.setEnabled(True)
        self.refresh()
        self._set_note("You're on the latest version", C.GREEN)

    def _on_failed(self, msg: str) -> None:
        self._check_btn.setEnabled(True)
        self.refresh()
        self._set_note(f"Could not check for updates — {msg}", C.RED)
