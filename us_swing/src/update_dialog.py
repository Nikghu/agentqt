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

from updater_stub import UpdateInfo, check_update_available, download_and_verify_update


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


class _UpdateDialog(QDialog):
    _QSS = """
        QDialog {
            background: #1a1a2e;
            border: 1px solid #2d2d4e;
            border-radius: 10px;
        }
        QLabel { color: #e0e0e0; background: transparent; }
        QProgressBar {
            background: #2d2d4e;
            border: none;
            border-radius: 4px;
        }
        QProgressBar::chunk {
            background: #4e9af1;
            border-radius: 4px;
        }
        QPushButton {
            background: #2d2d4e;
            color: #888888;
            border: none;
            border-radius: 4px;
            padding: 4px 14px;
            font-size: 12px;
            min-height: 28px;
            max-height: 28px;
            outline: none;
        }
        QPushButton:hover { background: #3d3d5e; color: #bbbbbb; }
        QPushButton:focus { outline: none; }
    """

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
        self.setStyleSheet(self._QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(f"USSwing v{remote_version} Available")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff;")
        self._skip_btn = QPushButton("Skip")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._skip_btn)
        root.addLayout(header)

        self._status = QLabel("Downloading update...")
        self._status.setStyleSheet("font-size: 12px; color: #aaaaaa;")
        root.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)
        root.addWidget(self._bar)

        self._size_label = QLabel("Starting...")
        self._size_label.setStyleSheet("font-size: 11px; color: #666666;")
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
        self._status.setStyleSheet("font-size: 12px; color: #e74c3c;")
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
