"""
Module: MD-GUI-027.001.M01 — Settings Dialog
Parent SRD: SRD-GUI-027.001

Frameless modal dialog around the settings panel, opened from the sidebar.
One dialog is built at start-up and reused, so the candle database panel
inside it lives as long as the main window.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.scheduler_dialog import _DialogTitleBar
from us_swing.gui.settings_panel import SettingsPanel


class SettingsDialog(QDialog):
    """Settings in a frameless modal dialog with Restore defaults, Cancel, Apply and OK."""

    def __init__(self, panel: SettingsPanel, parent: QWidget | None = None) -> None:
        """Wrap ``panel`` in the dialog.

        Args:
            panel: The settings panel shown in the dialog body.
            parent: Main window the dialog is centred on.
        """
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(900, 600)
        self._panel = panel

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(panel)

        self._defaults_btn = QPushButton("Restore defaults")
        self._cancel_btn = QPushButton("Cancel")
        self._apply_btn = QPushButton("Apply")
        self._ok_btn = QPushButton("OK")
        self._ok_btn.setObjectName("run_btn")
        self._ok_btn.setDefault(True)
        for btn in (self._defaults_btn, self._cancel_btn, self._apply_btn, self._ok_btn):
            btn.setFixedWidth(130 if btn is self._defaults_btn else 90)
        self._apply_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.reject)
        self._ok_btn.clicked.connect(self._on_ok)
        self._apply_btn.clicked.connect(self._on_apply)
        self._defaults_btn.clicked.connect(panel.restore_defaults)
        # panel → dirty_changed / section_changed → footer buttons
        panel.dirty_changed.connect(self._apply_btn.setEnabled)
        panel.section_changed.connect(
            lambda name: self._defaults_btn.setEnabled(panel.can_restore(name))
        )
        self._defaults_btn.setEnabled(panel.can_restore(panel.current_section))

        footer = QFrame()
        footer.setObjectName("dialog_footer")
        row = QHBoxLayout(footer)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)
        row.addWidget(self._defaults_btn)
        row.addStretch(1)
        row.addWidget(self._cancel_btn)
        row.addWidget(self._apply_btn)
        row.addWidget(self._ok_btn)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        title_bar = _DialogTitleBar("Settings", self)
        # A minimised application-modal dialog would leave the main window locked.
        title_bar._btn_min.hide()
        root.addWidget(title_bar)
        root.addWidget(scroll, 1)
        root.addWidget(footer)

    @property
    def panel(self) -> SettingsPanel:
        return self._panel

    def open_at(self, section: str | None = None) -> None:
        """Show the dialog centred on its parent, at ``section`` when given.

        Args:
            section: Section name such as ``"Telegram"``; ``None`` keeps the last one.
        """
        if section is not None:
            self._panel.show_section(section)
        self._panel.revert()
        self._panel.refresh_states()
        parent = self.parentWidget()
        if parent is not None:
            centre = parent.frameGeometry().center()
            self.move(centre.x() - self.width() // 2, centre.y() - self.height() // 2)
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_apply(self) -> None:
        self._panel.apply()
        self._panel.refresh_states()

    def _on_ok(self) -> None:
        self._panel.apply()
        self.accept()

    def reject(self) -> None:
        """Cancel, Esc and the close button drop unsaved edits (SRD-GUI-027.010)."""
        self._panel.revert()
        super().reject()
