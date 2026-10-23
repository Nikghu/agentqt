"""
Module: MD-GUI-018.006.M02 — Reveal Controller
Parent SRD: SRD-GUI-018.006

One owner for every hide/show size animation. Widgets never animate
themselves: callers emit ``reveal_requested(name, show)`` and listen to
``revealed(name, show)``, which fires once the animation has finished.
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEasingCurve, QObject, QVariantAnimation, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QWidget

_DURATION_MS = 200


@dataclass
class _Entry:
    widget: QWidget
    closed: int
    opened: int
    horizontal: bool
    animation: QVariantAnimation
    target_open: bool = False


class RevealController(QObject):
    """Animates registered widgets between a closed and an open size."""

    reveal_requested = pyqtSignal(str, bool)
    revealed = pyqtSignal(str, bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: dict[str, _Entry] = {}
        self.reveal_requested.connect(self.on_reveal_requested)

    def register(self, name: str, widget: QWidget, closed: int, opened: int,
                 horizontal: bool = True, start_open: bool = True) -> None:
        """Register ``widget`` under ``name`` and set its starting size.

        Args:
            name: Key used in ``reveal_requested`` / ``revealed``.
            widget: Widget whose fixed width (or height) is animated.
            closed: Size in px when hidden or collapsed.
            opened: Size in px when shown or expanded.
            horizontal: Animate width when True, height when False.
            start_open: Initial state.
        """
        animation = QVariantAnimation(self)
        animation.setDuration(_DURATION_MS)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        entry = _Entry(widget, closed, opened, horizontal, animation, start_open)
        animation.valueChanged.connect(lambda value, e=entry: self._apply(e, int(value)))
        animation.finished.connect(lambda n=name, e=entry: self.revealed.emit(n, e.target_open))
        self._entries[name] = entry
        self._apply(entry, opened if start_open else closed)

    def is_open(self, name: str) -> bool:
        """Return the state the named widget is in or moving to."""
        entry = self._entries.get(name)
        return entry is not None and entry.target_open

    @pyqtSlot(str, bool)
    def on_reveal_requested(self, name: str, show: bool) -> None:
        """Animate ``name`` open or closed, starting from its current size."""
        entry = self._entries.get(name)
        if entry is None:
            return
        entry.target_open = show
        entry.animation.stop()
        current = entry.widget.width() if entry.horizontal else entry.widget.height()
        entry.animation.setStartValue(current)
        entry.animation.setEndValue(entry.opened if show else entry.closed)
        entry.animation.start()

    @staticmethod
    def _apply(entry: _Entry, size: int) -> None:
        if entry.horizontal:
            entry.widget.setFixedWidth(size)
        else:
            entry.widget.setFixedHeight(size)
