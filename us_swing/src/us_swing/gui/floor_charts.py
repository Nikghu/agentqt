"""
Module: MD-GUI-034.047.M27 — Floor chart views
Parent SRD: SRD-GUI-034.047
Also: SRD-GUI-034.048–.051 — heat map, line, rotation views and idea cell delegates

Painted Market Floor panel views. Each view takes product rows (dicts) and draws them with
``QPainter`` in theme colours; no web view is used.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PyQt6.QtCore import QModelIndex, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPaintEvent, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.theme import C

Rows = Sequence[dict[str, Any]]
HEAT_COLUMNS = 4
_HEAT_FULL = 5.0
_PAD = 8.0


def number(value: object) -> float | None:
    """Read ``value`` such as ``+4.3%`` or ``57`` as a float; ``None`` when it is not a number."""
    text = str(value).replace("%", "").replace("+", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def mix(base: str, top: str, weight: float) -> QColor:
    """Return ``base`` blended toward ``top`` by ``weight`` (0 to 1)."""
    a, b = QColor(base), QColor(top)
    w = max(0.0, min(1.0, weight))
    return QColor(
        round(a.red() + (b.red() - a.red()) * w),
        round(a.green() + (b.green() - a.green()) * w),
        round(a.blue() + (b.blue() - a.blue()) * w),
    )


def heat_colour(value: float) -> QColor:
    """Return the heat map colour for a strength ``value`` in percent against SPY."""
    if value == 0:
        return QColor(C.SURFACE)
    weight = min(abs(value) / _HEAT_FULL, 1.0) * 0.8 + 0.2
    return mix(C.SURFACE, C.GREEN if value > 0 else C.RED, weight * 0.45)


def empty_note() -> QLabel:
    """Return the muted note shown when a view has no rows."""
    note = QLabel("No data yet")
    note.setAlignment(Qt.AlignmentFlag.AlignCenter)
    note.setStyleSheet(f"color: {C.MUTED};")
    return note


class TilesView(QWidget):
    """A row of tiles: muted title, large value and a muted note per row."""

    def __init__(self, rows: Rows, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        line = QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(6)
        for row in rows:
            line.addWidget(self._tile(row), 1)

    @staticmethod
    def _tile(row: dict[str, Any]) -> QFrame:
        tile = QFrame()
        tile.setObjectName("floor_tile")
        tile.setStyleSheet(
            f"QFrame#floor_tile {{ background: {C.BG}; border: 1px solid {C.OVERLAY};"
            " border-radius: 4px; }"
        )
        box = QVBoxLayout(tile)
        box.setContentsMargins(10, 6, 10, 6)
        box.setSpacing(2)
        for key, style in (("title", f"color: {C.MUTED}; font-size: 8pt;"),
                           ("value", f"color: {C.TEXT}; font-size: 15pt; font-weight: 600;"),
                           ("note", f"color: {C.MUTED}; font-size: 8pt;")):
            label = QLabel(str(row.get(key, "")))
            label.setObjectName(f"tile_{key}")
            label.setStyleSheet(f"{style} border: none; background: transparent;")
            box.addWidget(label)
        box.addStretch(1)
        return tile


class _Painted(QWidget):
    """Base for painted views: keeps the rows and sets a sensible minimum size."""

    def __init__(self, rows: Rows, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows = list(rows)
        self.setMinimumSize(120, 80)

    def _painter(self) -> QPainter:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        return painter


class HeatMapView(_Painted):
    """Sector cells coloured by 1-month strength against SPY."""

    def cells(self) -> list[tuple[str, float]]:
        """Return ``(label, value)`` per row that has a readable value."""
        out: list[tuple[str, float]] = []
        for row in self.rows:
            raw = row.get("rel_1m", row.get("change_5d"))
            value = number(raw)
            if value is not None:
                out.append((str(row.get("sector", "")), value))
        return out

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw one rounded cell per sector, 4 to a row."""
        cells = self.cells()
        if not cells:
            return
        painter = self._painter()
        rows = (len(cells) + HEAT_COLUMNS - 1) // HEAT_COLUMNS
        w = (self.width() - (HEAT_COLUMNS - 1) * 4) / HEAT_COLUMNS
        h = max(min((self.height() - (rows - 1) * 4) / rows, 56.0), 12.0)
        bold = QFont(self.font())
        bold.setBold(True)
        for i, (label, value) in enumerate(cells):
            rect = QRectF((i % HEAT_COLUMNS) * (w + 4), (i // HEAT_COLUMNS) * (h + 4), w, h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(heat_colour(value))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(QColor(C.TEXT))
            painter.setFont(bold)
            inner = rect.adjusted(6, 4, -4, -4)
            painter.drawText(inner, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                             painter.fontMetrics().elidedText(
                                 label, Qt.TextElideMode.ElideRight, int(inner.width())))
            painter.setFont(self.font())
            painter.drawText(inner, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                             f"{value:+.1f}")
        painter.end()


class LineView(_Painted):
    """Line of ``value`` (0 to 100) over ``date``, oldest on the left."""

    def values(self) -> list[float]:
        """Return the readable values in row order."""
        return [v for v in (number(r.get("value")) for r in self.rows) if v is not None]

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw guide lines at 20, 50 and 80, the line, a light fill and the last value."""
        values = self.values()
        if not values:
            return
        painter = self._painter()
        left, top = 28.0, _PAD
        plot = QRectF(left, top, self.width() - left - 34, self.height() - top - _PAD)

        def point(i: int, v: float) -> QPointF:
            x = plot.left() + plot.width() * (i / max(len(values) - 1, 1))
            return QPointF(x, plot.bottom() - plot.height() * max(0.0, min(v, 100.0)) / 100)

        painter.setPen(QPen(QColor(C.OVERLAY), 1, Qt.PenStyle.DashLine))
        for guide in (20, 50, 80):
            y = point(0, guide).y()
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(C.MUTED))
            painter.drawText(QRectF(0, y - 8, left - 4, 16), Qt.AlignmentFlag.AlignRight
                             | Qt.AlignmentFlag.AlignVCenter, f"{guide}%")
            painter.setPen(QPen(QColor(C.OVERLAY), 1, Qt.PenStyle.DashLine))
        path = QPainterPath(point(0, values[0]))
        for i, v in enumerate(values[1:], start=1):
            path.lineTo(point(i, v))
        fill = QPainterPath(path)
        fill.lineTo(QPointF(plot.right(), plot.bottom()))
        fill.lineTo(QPointF(plot.left(), plot.bottom()))
        shade = QColor(C.ORANGE)
        shade.setAlpha(40)
        painter.fillPath(fill, shade)
        painter.setPen(QPen(QColor(C.ORANGE), 2))
        painter.drawPath(path)
        last = point(len(values) - 1, values[-1])
        painter.setBrush(QColor(C.ORANGE))
        painter.drawEllipse(last, 3, 3)
        painter.drawText(QRectF(last.x() + 4, last.y() - 9, 32, 18),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         f"{values[-1]:.0f}%")
        painter.end()


SECTOR_TICKERS = {
    "Communication Services": "XLC", "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP", "Energy": "XLE", "Financials": "XLF", "Health Care": "XLV",
    "Industrials": "XLI", "Information Technology": "XLK", "Technology": "XLK",
    "Materials": "XLB", "Real Estate": "XLRE", "Utilities": "XLU",
}
_QUADRANTS = (("Improving", "TEAL", 0, 0), ("Leading", "GREEN", 1, 0),
              ("Lagging", "RED", 0, 1), ("Weakening", "YELLOW", 1, 1))


class RotationView(_Painted):
    """Four quadrants around (100, 100) with one dot per sector."""

    def points(self) -> list[tuple[str, float, float]]:
        """Return ``(sector, rs_ratio, rs_momentum)`` per row with both numbers."""
        out: list[tuple[str, float, float]] = []
        for row in self.rows:
            x, y = number(row.get("rs_ratio")), number(row.get("rs_momentum"))
            if x is not None and y is not None:
                out.append((str(row.get("sector", "")), x, y))
        return out

    def plot_rect(self) -> QRectF:
        """Return the drawing area inside the padding."""
        return QRectF(_PAD, _PAD, self.width() - 2 * _PAD, self.height() - 2 * _PAD)

    def to_screen(self, x: float, y: float) -> QPointF:
        """Map an RS ratio and momentum to a point in the plot (momentum up)."""
        span = max([2.0] + [max(abs(px - 100), abs(py - 100)) * 1.15 + 0.5
                            for _s, px, py in self.points()])
        plot = self.plot_rect()
        return QPointF(plot.center().x() + (x - 100) / span * plot.width() / 2,
                       plot.center().y() - (y - 100) / span * plot.height() / 2)

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw the tinted quadrants with names, then a dot and label per sector."""
        points = self.points()
        if not points:
            return
        painter = self._painter()
        plot = self.plot_rect()
        half_w, half_h = plot.width() / 2, plot.height() / 2
        small = QFont(self.font())
        small.setPointSizeF(max(small.pointSizeF() - 1.5, 6.0))
        for name, colour, col, row in _QUADRANTS:
            rect = QRectF(plot.left() + col * half_w, plot.top() + row * half_h, half_w, half_h)
            painter.fillRect(rect, mix(C.BG, getattr(C, colour), 0.08))
            painter.setPen(QColor(C.MUTED))
            painter.setFont(small)
            align = (Qt.AlignmentFlag.AlignRight if col else Qt.AlignmentFlag.AlignLeft) | (
                Qt.AlignmentFlag.AlignBottom if row else Qt.AlignmentFlag.AlignTop)
            painter.drawText(rect.adjusted(4, 2, -4, -2), align, name.upper())
        painter.setFont(self.font())
        for sector, x, y in points:
            spot = self.to_screen(x, y)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(C.TEXT))
            painter.drawEllipse(spot, 3.5, 3.5)
            painter.setPen(QColor(C.SUBTEXT))
            name = SECTOR_TICKERS.get(sector, sector)
            width = painter.fontMetrics().horizontalAdvance(name)
            left = spot.x() + 6 if spot.x() + 6 + width < plot.right() else spot.x() - 6 - width
            painter.drawText(QPointF(left, spot.y() + 4), name)
        painter.end()


def _paint_background(delegate: QStyledItemDelegate, painter: QPainter,
                      option: QStyleOptionViewItem, index: QModelIndex) -> None:
    """Paint the cell background (selection, hover) without its text."""
    plain = QStyleOptionViewItem(option)
    delegate.initStyleOption(plain, index)
    plain.text = ""
    widget = plain.widget
    style = widget.style() if widget is not None else None
    if style is not None:
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, plain, painter, widget)


class ScoreDelegate(QStyledItemDelegate):
    """Draws a 0–100 score as its number and a bar."""

    def paint(self, painter: QPainter | None, option: QStyleOptionViewItem,
              index: QModelIndex) -> None:
        """Paint the number on the left and the bar to its right."""
        value = number(index.data())
        if painter is None or value is None:
            super().paint(painter, option, index)
            return
        _paint_background(self, painter, option, index)
        rect = QRectF(option.rect)
        painter.save()
        painter.setPen(QColor(C.TEXT))
        painter.drawText(rect.adjusted(6, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, f"{value:.0f}")
        bar = QRectF(rect.left() + 32, rect.center().y() - 2.5, max(rect.width() - 40, 10), 5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(C.OVERLAY))
        painter.drawRoundedRect(bar, 2, 2)
        painter.setBrush(QColor(C.ORANGE))
        painter.drawRoundedRect(QRectF(bar.left(), bar.top(),
                                       bar.width() * max(0.0, min(value, 100.0)) / 100,
                                       bar.height()), 2, 2)
        painter.restore()


class SideDelegate(QStyledItemDelegate):
    """Draws ``long`` / ``short`` as a green Long or red Short label."""

    def paint(self, painter: QPainter | None, option: QStyleOptionViewItem,
              index: QModelIndex) -> None:
        """Paint a rounded label coloured by side."""
        side = str(index.data() or "").lower()
        if painter is None or side not in ("long", "short"):
            super().paint(painter, option, index)
            return
        _paint_background(self, painter, option, index)
        colour = C.GREEN if side == "long" else C.RED
        text = side.title()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = painter.fontMetrics().horizontalAdvance(text) + 14
        rect = QRectF(option.rect.left() + 6, option.rect.center().y() - 9, width, 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(mix(C.SURFACE, colour, 0.25))
        painter.drawRoundedRect(rect, 9, 9)
        painter.setPen(QColor(colour))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


def view_body(view: str, rows: Rows) -> QWidget | None:
    """Return the painted body for ``view``, an empty note, or ``None`` for other views."""
    makers: dict[str, Callable[[Rows], QWidget]] = {"tiles": TilesView, "heatmap": HeatMapView,
                                         "line": LineView, "rotation": RotationView}
    maker = makers.get(view)
    if maker is None:
        return None
    return maker(rows) if rows else empty_note()
