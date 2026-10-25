"""
Module: MD-GUI-027.001.M01 — tests
Parent SRD: SRD-GUI-027.001

Settings dialog: frameless, modal, opened at a section, footer buttons (FO-GUI-027).
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QLabel, QWidget

# QWebEngineWidgets DLL is unavailable in the test environment — stub it so
# settings_panel.py can be imported without the DLL.
_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.gui.settings_dialog import SettingsDialog  # noqa: E402


class _FakePanel(QWidget):
    dirty_changed = pyqtSignal(bool)
    section_changed = pyqtSignal(str)
    current_section = "Users"

    def __init__(self) -> None:
        super().__init__()
        self.shown: list[str] = []
        self.calls: list[str] = []

    def show_section(self, name: str) -> None:
        self.shown.append(name)

    def can_restore(self, name: str) -> bool:
        return name == "Risk"

    def refresh_states(self) -> None:
        pass

    def apply(self) -> None:
        self.calls.append("apply")

    def revert(self) -> None:
        self.calls.append("revert")

    def restore_defaults(self) -> None:
        self.calls.append("defaults")


@pytest.fixture()
def dialog(qtbot: Any) -> SettingsDialog:
    dlg = SettingsDialog(_FakePanel())  # type: ignore[arg-type]
    qtbot.addWidget(dlg)
    return dlg


def test_dialog_is_frameless_and_modal(dialog: SettingsDialog) -> None:
    """UT-GUI-027.001.M01.T01: the dialog is frameless, application modal and titled Settings."""
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.windowModality() == Qt.WindowModality.ApplicationModal
    titles = [lbl.text() for lbl in dialog.findChildren(QLabel) if lbl.objectName() == "top_brand"]
    assert titles == ["Settings"]


def test_open_at_section(dialog: SettingsDialog) -> None:
    """UT-GUI-027.001.M01.T02: open_at shows the dialog at the named section."""
    dialog.open_at("Telegram")

    assert dialog.isVisible()
    assert dialog.panel.shown == ["Telegram"]  # type: ignore[attr-defined]
    dialog.reject()


def test_footer_buttons(dialog: SettingsDialog) -> None:
    """UT-GUI-027.003.M01.T01: Apply starts disabled; Cancel rejects and OK accepts."""
    results: list[int] = []
    dialog.finished.connect(results.append)

    dialog.open_at()
    assert not dialog._apply_btn.isEnabled()
    dialog._cancel_btn.click()
    dialog.open_at()
    dialog._ok_btn.click()

    assert results == [QDialog.DialogCode.Rejected, QDialog.DialogCode.Accepted]
    assert not dialog.isVisible()
    assert dialog.panel.calls == ["revert", "apply"]  # type: ignore[attr-defined]


def test_footer_follows_panel(dialog: SettingsDialog) -> None:
    """UT-GUI-027.003.M01.T02: Apply follows changes; Restore defaults follows the section."""
    panel = dialog.panel
    assert not dialog._defaults_btn.isEnabled()

    panel.dirty_changed.emit(True)  # type: ignore[attr-defined]
    panel.section_changed.emit("Risk")  # type: ignore[attr-defined]

    assert dialog._apply_btn.isEnabled() and dialog._defaults_btn.isEnabled()
    dialog._defaults_btn.click()
    assert panel.calls == ["defaults"]  # type: ignore[attr-defined]
