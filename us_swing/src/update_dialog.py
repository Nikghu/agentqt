"""Update progress dialog — shown at startup when a new version is available."""
from __future__ import annotations

import subprocess
import sys

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from us_swing.gui.theme import C
from updater_stub import UpdateInfo, check_update_available, download_and_verify_update


class _CheckWorker(QThread):
    """Runs the update check off the GUI thread so the network call never freezes the UI."""

    found: pyqtSignal = pyqtSignal(object)  # emits UpdateInfo
    up_to_date: pyqtSignal = pyqtSignal()
    failed: pyqtSignal = pyqtSignal(str)

    def run(self) -> None:
        try:
            info = check_update_available(force=True)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        if info is None:
            self.up_to_date.emit()
        else:
            self.found.emit(info)


class _DownloadWorker(QThread):
    progress: pyqtSignal = pyqtSignal(int, int)
    finished: pyqtSignal = pyqtSignal(str)
    failed: pyqtSignal = pyqtSignal(str)

    def __init__(self, info: UpdateInfo) -> None:
        super().__init__()
        self._info = info

    def run(self) -> None:
        try:
            stable = download_and_verify_update(self._info, progress_cb=self._on_progress)
            self.finished.emit(str(stable))
        except Exception as exc:
            self.failed.emit(str(exc))

    def _on_progress(self, received: int, total: int) -> None:
        self.progress.emit(received, total)


def _dialog_qss() -> str:
    return f"""
        QDialog {{
            background: {C.SURFACE};
            border: 1px solid {C.OVERLAY2};
            border-radius: 10px;
        }}
        QLabel {{ color: {C.TEXT}; background: transparent; }}
        QProgressBar {{
            background: {C.OVERLAY};
            border: none;
            border-radius: 4px;
        }}
        QProgressBar::chunk {{
            background: {C.BLUE};
            border-radius: 4px;
        }}
        QPushButton {{
            background: {C.OVERLAY};
            color: {C.SUBTEXT};
            border: 1px solid {C.OVERLAY2};
            border-radius: 4px;
            padding: 4px 14px;
            font-size: 12px;
            min-height: {C.BTN_H}px;
            max-height: {C.BTN_H}px;
            outline: none;
        }}
        QPushButton:hover {{ background: {C.OVERLAY2}; color: {C.TEXT}; }}
        QPushButton:focus {{ outline: none; }}
    """


class _UpdateDialog(QDialog):
    def __init__(self, info: UpdateInfo) -> None:
        super().__init__()
        self._worker = _DownloadWorker(info)
        self._setup_ui(info.remote_version)
        self._wire()
        self._center()
        self._worker.start()

    def _setup_ui(self, remote_version: str) -> None:
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedWidth(400)
        self.setStyleSheet(_dialog_qss())

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(f"USSwing v{remote_version} Available")
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {C.TEXT};")
        self._skip_btn = QPushButton("Skip")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._skip_btn)
        root.addLayout(header)

        self._status = QLabel("Downloading update...")
        self._status.setStyleSheet(f"font-size: 12px; color: {C.SUBTEXT};")
        root.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)
        root.addWidget(self._bar)

        self._size_label = QLabel("Starting...")
        self._size_label.setStyleSheet(f"font-size: 11px; color: {C.MUTED};")
        root.addWidget(self._size_label)

    def _wire(self) -> None:
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._skip_btn.clicked.connect(self._on_skip)

    def _center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            geo = self.frameGeometry()
            geo.moveCenter(center)
            self.move(geo.topLeft())

    def _on_progress(self, received: int, total: int) -> None:
        if total > 0:
            self._bar.setValue(int(received * 100 / total))
            self._size_label.setText(
                f"{received / 1_048_576:.1f} MB / {total / 1_048_576:.1f} MB"
            )
        else:
            self._size_label.setText(f"{received / 1_048_576:.1f} MB downloaded")

    def _on_finished(self, stable_path: str) -> None:
        self.accept()
        subprocess.Popen(  # noqa: S603 — path comes from verified download
            [stable_path, "/SILENT", "/NORESTART"],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        sys.exit(0)

    def _on_failed(self, msg: str) -> None:
        self._status.setText("Update failed — starting normally")
        self._status.setStyleSheet(f"font-size: 12px; color: {C.RED};")
        self._size_label.setText(msg)
        self._skip_btn.setText("Continue")

    def _on_skip(self) -> None:
        self._worker.quit()
        self.reject()


def check_for_updates_gui() -> None:
    """Check for updates and show a progress dialog if a download is needed.

    Returns immediately (no dialog shown) when already up to date.
    Must be called after QApplication is created.
    """
    info = check_update_available()
    if info is None:
        return
    dialog = _UpdateDialog(info)
    dialog.exec()
