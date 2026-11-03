"""Tests for the frameless popups (SRD-GUI-000.009)."""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QPushButton

import us_swing.gui.main_window  # noqa: F401  — loads the GUI package in app order
import us_swing.gui.screener_panel as sp
from us_swing.gui import popups
from us_swing.gui.active_cycles_panel import _ConfirmDialog
from us_swing.gui.screener_views import PresetItem

_GUI = Path(popups.__file__).parent


@pytest.fixture
def shown(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Record each popup instead of opening it; ``accept`` decides the answer."""
    rec = SimpleNamespace(dialogs=[], accept=True)

    def fake_exec(self: _ConfirmDialog) -> int:
        rec.dialogs.append(self)
        return QDialog.DialogCode.Accepted.value if rec.accept else 0

    monkeypatch.setattr(_ConfirmDialog, "exec", fake_exec)
    return rec


def _buttons(dialog: _ConfirmDialog) -> list[str]:
    return [b.text() for b in dialog.findChildren(QPushButton) if b.text() != "✕"]


def test_confirm_returns_the_choice(qtbot, shown):
    """UT-GUI-000.009.M01.T01: confirm is a frameless Yes / Cancel popup that returns the choice."""
    assert popups.confirm(None, "Delete Strategy", "Delete strategy 'A'?", confirm_text="Delete")
    shown.accept = False
    assert not popups.confirm(None, "Delete Strategy", "Delete strategy 'A'?")
    dialog = shown.dialogs[0]
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert _buttons(dialog) == ["Cancel", "Delete"]


def test_notify_has_one_ok_button(qtbot, shown):
    """UT-GUI-000.009.M01.T02: notify shows one OK button in the frameless style."""
    popups.notify(None, "Export Failed", "Could not save the file", "error")
    assert len(shown.dialogs) == 1
    assert shown.dialogs[0].windowFlags() & Qt.WindowType.FramelessWindowHint
    assert _buttons(shown.dialogs[0]) == ["OK"]


def test_no_native_message_boxes_left():
    """UT-GUI-000.009.M02.T01: No GUI module opens a native QMessageBox."""
    calls = re.compile(r"QMessageBox\s*[.(]")
    users = [p.name for p in _GUI.glob("*.py") if calls.search(p.read_text(encoding="utf-8"))]
    assert users == []


def test_delete_preset_names_the_preset(qtbot, monkeypatch):
    """UT-GUI-000.009.M02.T02: Delete Preset asks with the preset's name, not an empty one."""
    asked: list[str] = []
    monkeypatch.setattr(sp, "confirm", lambda _p, _t, text, **_k: asked.append(text) or False)
    panel = sp.ScreenerPanel.__new__(sp.ScreenerPanel)
    panel._mgr = MagicMock()
    panel._preset_list = QListWidget()
    qtbot.addWidget(panel._preset_list)
    item = QListWidgetItem()
    item.setData(Qt.ItemDataRole.UserRole, "p1")
    panel._preset_list.addItem(item)
    panel._preset_list.setItemWidget(item, PresetItem("Momentun_Price", "Not run yet"))
    panel._preset_list.setCurrentItem(item)

    panel._on_delete_preset()

    assert asked == ['Delete preset "Momentun_Price"?\nThis cannot be undone.']
    panel._mgr.delete_preset.assert_not_called()
