"""
Module: MD-GUI-017.003.M01 — Icons
Parent SRD: SRD-GUI-017.003

Role-coloured line icons from ``assets/icons`` (Lucide, ISC licence).

Roles map to theme tokens so the icon colour carries meaning:
neutral → TEXT, add → GREEN, go → BLUE (amber in Carbon), danger → RED,
info → TEAL, inverse → BG (for icons on filled accent buttons).
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QAbstractButton, QPushButton, QTabWidget, QWidget

from us_swing.gui.theme import C, asset_dir, load_theme_id

_log = logging.getLogger(__name__)

_ROLE_TOKEN: dict[str, str] = {
    "neutral": "TEXT",
    "add":     "GREEN",
    "go":      "BLUE",
    "danger":  "RED",
    "info":    "TEAL",
    "inverse": "BG",
}
_PIXMAP_SIZES = (13, 16, 17, 26, 32, 34)
_cache: dict[tuple[str, str, str], QIcon] = {}


def _render(svg: str, colour: str, size: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg.replace("currentColor", colour).encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def icon(name: str, role: str = "neutral") -> QIcon:
    """Return a cached icon for ``name`` coloured by ``role`` in the active theme.

    Args:
        name: Icon file name without ``.svg`` (e.g. ``"plus"``).
        role: One of neutral, add, go, danger, info, inverse.

    Returns:
        The icon, or an empty ``QIcon`` when the file is missing.
    """
    key = (load_theme_id(), name, role)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        svg = (asset_dir("icons") / f"{name}.svg").read_text(encoding="utf-8")
    except OSError:
        _log.warning("[Theme] Icon %s is missing", name)
        return QIcon()
    colour = getattr(C, _ROLE_TOKEN.get(role, "TEXT"))
    result = QIcon()
    for size in _PIXMAP_SIZES:
        result.addPixmap(_render(svg, colour, size), QIcon.Mode.Normal)
        result.addPixmap(_render(svg, C.MUTED, size), QIcon.Mode.Disabled)
    _cache[key] = result
    return result


def clear_cache() -> None:
    """Drop all cached icons so the next call uses the new theme colours."""
    _cache.clear()


def set_icon(button: QAbstractButton, name: str, role: str = "neutral", size: int = 16) -> None:
    """Set a role-coloured icon on ``button`` and remember it for theme refresh."""
    button.setIcon(icon(name, role))
    button.setIconSize(QSize(size, size))
    button.setProperty("icon_spec", (name, role, size))


def set_tab_icon(tabs: QTabWidget, index: int, name: str, role: str = "neutral") -> None:
    """Set a role-coloured icon on tab ``index`` and remember it for theme refresh."""
    tabs.setTabIcon(index, icon(name, role))
    specs = dict(tabs.property("tab_icon_specs") or {})
    specs[index] = (name, role)
    tabs.setProperty("tab_icon_specs", specs)


def icon_button(name: str, role: str, tip: str, parent: QWidget | None = None) -> QPushButton:
    """Build an icon-only button with a tooltip and accessible name."""
    button = QPushButton(parent)
    set_icon(button, name, role)
    button.setToolTip(tip)
    button.setAccessibleName(tip)
    return button


def mark_danger(button: QAbstractButton) -> None:
    """Style ``button`` as a risky action (red text, border and icon) in every theme."""
    button.setProperty("role", "danger")
    style = button.style()
    if style is not None:
        style.unpolish(button)
        style.polish(button)


def refresh_icons(root: QWidget) -> None:
    """Re-apply every remembered icon under ``root`` after a theme change."""
    clear_cache()
    for button in root.findChildren(QAbstractButton):
        spec = button.property("icon_spec")
        if spec:
            set_icon(button, *spec)
    for tabs in root.findChildren(QTabWidget):
        for index, (name, role) in dict(tabs.property("tab_icon_specs") or {}).items():
            tabs.setTabIcon(index, icon(name, role))
