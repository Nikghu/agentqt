"""
Module: MD-GUI-034.005.M05 — Floor grid widget
Parent SRD: SRD-GUI-034.005

Draws Market Floor panels with absolute geometry on a 12-column grid. Panels move and resize
only in edit mode; the cell maths lives in ``floor_grid_model``.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QWidget

from us_swing.gui.cards import GAP
from us_swing.gui.floor_grid_model import COLUMNS, GridModel, clamp_rect, snap_delta
from us_swing.gui.floor_panel import ROW_PX, PanelFrame
from us_swing.gui.theme import C

FrameFactory = Callable[[Any], PanelFrame]
_MIN_RESIZE_PX = 40


class PanelGrid(QWidget):
    """Hosts one tab's panels; build with a factory that makes a frame for a spec."""

    layout_changed = pyqtSignal()

    def __init__(self, factory: FrameFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._factory = factory
        self._model = GridModel()
        self._frames: dict[str, PanelFrame] = {}
        self._edit = False
        self._drag: tuple[PanelFrame, str, QPoint, QRect] | None = None
        self._ghost = QFrame(self)
        self._ghost.setStyleSheet(
            f"background: transparent; border: 2px dashed {C.BLUE}; border-radius: 6px;"
        )
        self._ghost.hide()

    @property
    def model(self) -> GridModel:
        """The model whose panels are drawn."""
        return self._model

    def frames(self) -> list[PanelFrame]:
        """Return the panel frames in model order."""
        return [self._frames[p.id] for p in self._model.panels if p.id in self._frames]

    def set_model(self, model: GridModel) -> None:
        """Show the panels of ``model`` (all frames are rebuilt)."""
        self._cancel_drag()
        for frame in self._frames.values():
            frame.deleteLater()
        self._frames.clear()
        self._model = model
        self.sync()

    def sync(self) -> None:
        """Add frames for new panels, drop frames of removed ones and lay out again."""
        self._cancel_drag()
        live = {p.id for p in self._model.panels}
        for pid in [k for k in self._frames if k not in live]:
            self._frames.pop(pid).deleteLater()
        for spec in self._model.panels:
            if spec.id not in self._frames:
                frame = self._factory(spec)
                frame.setParent(self)
                frame.set_edit(self._edit)
                frame.title_bar.installEventFilter(self)
                frame.grip.installEventFilter(self)
                frame.show()
                self._frames[spec.id] = frame
        self._relayout()

    def set_edit(self, on: bool) -> None:
        """Turn edit mode (drag, resize, remove) on or off."""
        self._edit = on
        if not on:
            self._cancel_drag()
        for frame in self._frames.values():
            frame.set_edit(on)

    def _cancel_drag(self) -> None:
        if self._drag is not None:
            frame = self._drag[0]
            self._drag = None
            spec = frame.spec
            if self._frames.get(spec.id) is frame:
                frame.setGeometry(self._rect(spec.x, spec.y, spec.w, spec.h))
        self._ghost.hide()

    def is_edit(self) -> bool:
        """Return whether edit mode is on."""
        return self._edit

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        """Recompute cell sizes when the width changes."""
        super().resizeEvent(event)
        self._relayout()

    def _cell_w(self) -> float:
        return max((self.width() - (COLUMNS - 1) * GAP) / COLUMNS, 1.0)

    def _rect(self, x: int, y: int, w: int, h: int) -> QRect:
        cw = self._cell_w()
        return QRect(
            round(x * (cw + GAP)), y * (ROW_PX + GAP),
            round(w * cw + (w - 1) * GAP), h * ROW_PX + (h - 1) * GAP,
        )

    def _relayout(self) -> None:
        for spec in self._model.panels:
            frame = self._frames.get(spec.id)
            if frame is not None:
                frame.setGeometry(self._rect(spec.x, spec.y, spec.w, spec.h))
        bottom = self._model.bottom()
        self.setMinimumHeight(max(bottom * (ROW_PX + GAP), 0))
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        """Width is free; height follows the lowest panel."""
        return QSize(400, self._model.bottom() * (ROW_PX + GAP))

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:  # noqa: N802
        """Handle drag and resize from the title bar and the corner grip."""
        if not self._edit or obj is None or event is None or not isinstance(obj, QWidget):
            return False
        kind = obj.property("floor_handle")
        frame = self._frames.get(str(obj.property("panel_id")))
        if kind not in ("move", "resize") or frame is None:
            return False
        if not isinstance(event, QMouseEvent):
            return False
        left = event.button() == Qt.MouseButton.LeftButton
        if event.type() == QEvent.Type.MouseButtonPress:
            if not left or self._drag is not None:
                return False
            self._drag = (frame, str(kind), event.globalPosition().toPoint(), frame.geometry())
            frame.raise_()
            return True
        if self._drag is not None and event.type() == QEvent.Type.MouseMove:
            self._drag_to(event.globalPosition().toPoint())
            return True
        if left and self._drag is not None and event.type() == QEvent.Type.MouseButtonRelease:
            self._drop(event.globalPosition().toPoint())
            return True
        return False

    def _target(self, pos: QPoint) -> tuple[int, int, int, int]:
        frame, kind, start, _geom = self._drag  # type: ignore[misc]
        spec = frame.spec
        dx, dy = snap_delta(
            pos.x() - start.x(), pos.y() - start.y(), self._cell_w() + GAP, ROW_PX + GAP
        )
        if kind == "move":
            return clamp_rect(spec.x + dx, spec.y + dy, spec.w, spec.h)
        return clamp_rect(spec.x, spec.y, spec.w + dx, spec.h + dy, keep_x=True)

    def _drag_to(self, pos: QPoint) -> None:
        assert self._drag is not None
        frame, kind, start, geom = self._drag
        delta = pos - start
        if kind == "move":
            frame.move(geom.topLeft() + delta)
        else:
            frame.resize(max(geom.width() + delta.x(), _MIN_RESIZE_PX),
                max(geom.height() + delta.y(), _MIN_RESIZE_PX))
        self._ghost.setGeometry(self._rect(*self._target(pos)))
        self._ghost.show()
        self._ghost.lower()
        frame.raise_()

    def _drop(self, pos: QPoint) -> None:
        assert self._drag is not None
        frame, kind, _start, _geom = self._drag
        x, y, w, h = self._target(pos)
        self._drag = None
        self._ghost.hide()
        if kind == "move":
            self._model.move(frame.spec.id, x, y)
        else:
            self._model.resize(frame.spec.id, w, h)
        self._relayout()
        self.layout_changed.emit()
