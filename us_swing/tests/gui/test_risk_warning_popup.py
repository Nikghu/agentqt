"""Tests for the risk warning pop-up (SRD-EXE-017.013)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from us_swing.gui.main_window import MainWindow  # noqa: I001 — must load before the panel
from us_swing.gui.active_cycles_panel import _ConfirmDialog


def test_risk_warning_is_frameless_and_non_blocking(qtbot):
    """UT-EXE-017.013.M09.T01: Risk warning uses the app's frameless pop-up, never blocks, debounced."""
    host = QWidget()
    qtbot.addWidget(host)
    host._risk_warning_last = {}  # type: ignore[attr-defined]
    MainWindow._on_risk_warning(host, "margin", "Margin Available differs from broker cash")
    MainWindow._on_risk_warning(host, "margin", "Margin Available differs from broker cash")
    boxes = host.findChildren(_ConfirmDialog)
    assert len(boxes) == 1
    box = boxes[0]
    assert box.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert box.isVisible() and not box.isModal()
