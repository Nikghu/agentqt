"""Tests for the card layout helpers (FO-GUI-023)."""
from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QWidget

from us_swing.gui.cards import GAP, GUTTER, card, gutter


def test_card_wraps_child_inside_padding(qtbot):
    """UT-GUI-023.001.M01.T01: Card holds the child inside its padding."""
    child = QLabel("x")
    frame = card(child)
    qtbot.addWidget(frame)
    layout = frame.layout()
    assert frame.objectName() == "shell_card"
    assert layout is not None and layout.indexOf(child) == 0
    margins = layout.contentsMargins()
    assert min(margins.left(), margins.top(), margins.right(), margins.bottom()) >= 2


def test_gutter_marks_widget(qtbot):
    """UT-GUI-023.001.M01.T02: Gutter sets the gap object name and returns the widget."""
    widget = QWidget()
    qtbot.addWidget(widget)
    assert gutter(widget) is widget
    assert widget.objectName() == GUTTER
    assert GAP == 4
