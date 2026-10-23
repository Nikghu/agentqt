"""
Module: MD-GUI-023.001.M01 — Card layout helpers
Parent SRD: SRD-GUI-023.001

Wraps a section in a rounded card on the page colour. Cards sit on "shell_gutter"
widgets, so the gaps between cards show the gutter colour; theme.py styles both names.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget

GAP = 4
GUTTER = "shell_gutter"
_PAD = 2  # keeps square child corners inside the 6 px rounded border


def card(child: QWidget) -> QFrame:
    """Return a rounded card frame holding ``child``."""
    frame = QFrame()
    frame.setObjectName("shell_card")
    box = QVBoxLayout(frame)
    box.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
    box.setSpacing(0)
    box.addWidget(child)
    return frame


def gutter(widget: QWidget) -> QWidget:
    """Mark ``widget`` as gutter so it paints the gap colour; returns it."""
    widget.setObjectName(GUTTER)
    return widget
