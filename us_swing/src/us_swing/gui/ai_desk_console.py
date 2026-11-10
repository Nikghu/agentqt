"""
Module: MD-GUI-034.065.M39 — gui/ai_desk_console.py
Parent SRD: SRD-GUI-034.065
Also: SRD-GUI-034.066 — the same cards and tiles in the AI Desk sections

Console card look for the AI Desk header and sections: stat tiles, thin bars, icon
cards and the joined desk control group. Look only; no data is read here.
"""
from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.icons import icon
from us_swing.gui.theme import C

_PLAIN = "background: transparent; border: none;"


def stat_tile(title: str, value: str = "",
              bar: QWidget | None = None) -> tuple[QFrame, QLabel, QLabel]:
    """A small bordered tile: a muted ``title`` over a bold ``value``, then ``bar`` if given.

    Returns:
        The tile frame, its title label and its value label.
    """
    tile = QFrame()
    tile.setObjectName("stat_tile")
    tile.setStyleSheet(f"QFrame#stat_tile {{ background: {C.SURFACE};"
                       f" border: 1px solid {C.OVERLAY2}; border-radius: 8px; }}")
    box = QVBoxLayout(tile)
    box.setContentsMargins(12, 8, 12, 8)
    box.setSpacing(3)
    head = QLabel(title)
    head.setStyleSheet(f"color: {C.MUTED}; font-size: 11px; {_PLAIN}")
    body = QLabel(value)
    body.setStyleSheet(f"font-size: 15px; font-weight: bold; {_PLAIN}")
    box.addWidget(head)
    box.addWidget(body)
    if bar is not None:
        box.addWidget(bar)
    return tile, head, body


def tile_row(pairs: Sequence[tuple[str, str]]) -> tuple[QHBoxLayout, list[QLabel]]:
    """A row of equal stat tiles, one per ``(title, value)``; returns the value labels."""
    row = QHBoxLayout()
    row.setSpacing(10)
    values: list[QLabel] = []
    for title, value in pairs:
        tile, _head, body = stat_tile(title, value)
        values.append(body)
        row.addWidget(tile, 1)
    return row, values


def thin_bar(percent: int, tone: str = "BLUE") -> QProgressBar:
    """A 6 px rounded bar filled to ``percent`` in the theme colour ``tone``."""
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(max(0, min(100, percent)))
    bar.setTextVisible(False)
    bar.setMaximumHeight(6)
    bar_tone(bar, tone)
    return bar


def bar_tone(bar: QProgressBar, tone: str) -> None:
    """Fill ``bar`` with the theme colour ``tone``."""
    bar.setStyleSheet(
        f"QProgressBar {{ background: {C.OVERLAY}; border: none; border-radius: 3px; }}"
        f"QProgressBar::chunk {{ background: {getattr(C, tone)}; border-radius: 3px; }}")


def icon_badge(name: str, role: str = "info", size: int = 30) -> QLabel:
    """A rounded square holding the Lucide icon ``name``."""
    badge = QLabel()
    badge.setFixedSize(size, size)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    glyph = 20 if size > 32 else 16
    badge.setPixmap(icon(name, role).pixmap(QSize(glyph, glyph)))
    badge.setStyleSheet(f"background: {C.OVERLAY}; border: none;"
                        f" border-radius: {size // 4}px;")
    return badge


def icon_card(icon_name: str, title: str, role: str = "info",
              side: QWidget | None = None) -> tuple[QFrame, QVBoxLayout]:
    """A bordered card with an icon and bold ``title`` on top; ``side`` sits on the right.

    Returns:
        The card frame and the layout to add its content to.
    """
    frame = QFrame()
    frame.setObjectName("desk_card")
    frame.setStyleSheet(f"QFrame#desk_card {{ background: {C.BG};"
                        f" border: 1px solid {C.OVERLAY2}; border-radius: 10px; }}")
    body = QVBoxLayout(frame)
    body.setContentsMargins(14, 12, 14, 12)
    body.setSpacing(10)
    head = QHBoxLayout()
    head.setSpacing(10)
    head.addWidget(icon_badge(icon_name, role, 28))
    label = QLabel(title)
    label.setObjectName("card_title")
    label.setStyleSheet(f"font-weight: bold; font-size: 13px; {_PLAIN}")
    head.addWidget(label)
    head.addStretch(1)
    if side is not None:
        head.addWidget(side)
    body.addLayout(head)
    return frame, body


def primary(button: QPushButton) -> QPushButton:
    """Give ``button`` the filled accent look."""
    button.setObjectName("primary_btn")
    return button


def danger(button: QPushButton) -> QPushButton:
    """Give ``button`` the red outline look."""
    button.setProperty("role", "danger")
    return button


def seg_style() -> str:
    """Joined button group look: one border, thin dividers, Stop in red."""
    return (f"QFrame#desk_seg {{ background: {C.SURFACE}; border: 1px solid {C.OVERLAY2};"
            " border-radius: 8px; }"
            f" QFrame#desk_seg QPushButton {{ background: transparent; border: none;"
            f" border-right: 1px solid {C.OVERLAY2}; border-radius: 0; padding: 0 14px;"
            f" color: {C.TEXT}; outline: none; }}"
            f" QFrame#desk_seg QPushButton:hover {{ background: {C.OVERLAY}; }}"
            f" QFrame#desk_seg QPushButton:focus {{ outline: none; }}"
            f" QFrame#desk_seg QPushButton:disabled {{ color: {C.MUTED}; }}"
            f" QFrame#desk_seg QPushButton[seg=\"last\"] {{ border-right: none;"
            f" color: {C.RED}; }}"
            f" QFrame#desk_seg QPushButton[seg=\"last\"]:disabled {{ color: {C.MUTED}; }}")
