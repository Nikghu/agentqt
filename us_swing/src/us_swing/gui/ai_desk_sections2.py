"""
Module: MD-GUI-034.009.M08 — AI Desk page list helper
Parent SRD: SRD-GUI-034.009

The plain page list used by Reports. Task board, Activity and Schedule moved to Team at work
(SRD-GUI-035.001).
"""
from __future__ import annotations

from PyQt6.QtWidgets import QListWidget


def page_list(names: list[str]) -> QListWidget:
    """Return a plain list of ``names`` (used by Reports)."""
    box = QListWidget()
    box.setStyleSheet("QListWidget { outline: none; }")
    box.addItems(names)
    return box
