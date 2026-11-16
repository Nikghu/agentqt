"""
Module: MD-GUI-034.047.M27 — Floor chart views
Parent SRD: SRD-GUI-034.047
Also: SRD-GUI-034.048–.051 — heat map, line, rotation views and idea cell delegates
Also: SRD-GUI-034.090 — readable rotation map (names, colours, tails, hover) and a Map /
List switch whose List shows strength bars
Also: SRD-GUI-034.091 — values shown as % with a line that says what they mean

Painted Market Floor panel views. Each view takes product rows (dicts) and draws them with
``QPainter`` in theme colours; no web view is used.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QModelIndex, QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
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
_SHORT_NAMES = {"Communication Services": "Communication",
                "Consumer Discretionary": "Discretionary", "Consumer Staples": "Staples",
                "Information Technology": "Technology"}
_QUADRANTS = (("Improving", "TEAL", 0, 0), ("Leading", "GREEN", 1, 0),
              ("Lagging", "RED", 0, 1), ("Weakening", "YELLOW", 1, 1))
_QUAD_COLOUR = {name: colour for name, colour, _col, _row in _QUADRANTS}
_LABEL_STEPS = (0, -1, 1, -2, 2, -3, 3)
MAP_NOTE = ("Right: stronger against the S&P 500 than its own 50-day average · Up: that "
            "strength is rising (last 10 days) · Dashed tail: 5 trading days ago")
LIST_NOTE = ("% above or below its own 50-day average strength against the S&P 500 · each "
             "sector is an equal-weight mix of its S&P 500 stocks, from daily closes")


def sector_name(sector: str) -> str:
    """Short plain sector name, e.g. ``Staples`` for Consumer Staples."""
    return _SHORT_NAMES.get(sector, sector)


def quadrant_of(ratio: float, momentum: float) -> str:
    """Leading, Weakening, Lagging or Improving around (100, 100)."""
    if ratio >= 100:
        return "Leading" if momentum >= 100 else "Weakening"
    return "Improving" if momentum >= 100 else "Lagging"


def quadrant_colour(ratio: float, momentum: float) -> QColor:
    """Theme colour of the quadrant a point sits in."""
    return QColor(getattr(C, _QUAD_COLOUR[quadrant_of(ratio, momentum)]))


@dataclass(frozen=True)
class RotationPoint:
    """One sector: RS ratio, RS momentum and where it was 5 trading days ago (if known)."""

    sector: str
    ratio: float
    momentum: float
    tail: tuple[float, float] | None


def rotation_points(rows: Rows) -> list[RotationPoint]:
    """Read the rows that have both numbers; the tail needs both tail numbers."""
    out: list[RotationPoint] = []
    for row in rows:
        x, y = number(row.get("rs_ratio")), number(row.get("rs_momentum"))
        if x is None or y is None:
            continue
        tx, ty = number(row.get("tail_ratio")), number(row.get("tail_momentum"))
        tail = (tx, ty) if tx is not None and ty is not None else None
        out.append(RotationPoint(str(row.get("sector", "")), x, y, tail))
    return out


def _tip(point: RotationPoint) -> str:
    lines = [f"{point.sector} · {quadrant_of(point.ratio, point.momentum)}",
             f"Strength {point.ratio - 100:+.1f}% against its 50-day average",
             f"Momentum {point.momentum - 100:+.1f}% over 10 days"]
    if point.tail is not None:
        lines.append(f"5 days ago: strength {point.tail[0] - 100:+.1f}%, "
                     f"momentum {point.tail[1] - 100:+.1f}%")
    return "\n".join(lines)


class RotationView(_Painted):
    """Four quadrants around (100, 100): one coloured dot per sector with its name, a dashed
    tail from where it was 5 trading days ago, and its numbers on hover."""

    def __init__(self, rows: Rows, parent: QWidget | None = None) -> None:
        super().__init__(rows, parent)
        self.setMouseTracking(True)

    def points(self) -> list[RotationPoint]:
        """Return the sectors that have both numbers."""
        return rotation_points(self.rows)

    def plot_rect(self) -> QRectF:
        """Return the drawing area inside the padding."""
        return QRectF(_PAD, _PAD, self.width() - 2 * _PAD, self.height() - 2 * _PAD)

    def to_screen(self, x: float, y: float) -> QPointF:
        """Map an RS ratio and momentum to a point in the plot (momentum up)."""
        values = [2.0]
        for p in self.points():
            values.append(max(abs(p.ratio - 100), abs(p.momentum - 100)) * 1.15 + 0.5)
            if p.tail is not None:
                values.append(max(abs(p.tail[0] - 100), abs(p.tail[1] - 100)) * 1.1 + 0.3)
        span = max(values)
        plot = self.plot_rect()
        return QPointF(plot.center().x() + (x - 100) / span * plot.width() / 2,
                       plot.center().y() - (y - 100) / span * plot.height() / 2)

    def label_rects(self, painter: QPainter) -> list[tuple[RotationPoint, QPointF, QRectF]]:
        """Place each name right or left of its dot, moving it up or down a line when it would
        cover another name or dot."""
        metrics = painter.fontMetrics()
        plot = self.plot_rect()
        spots = sorted(((p, self.to_screen(p.ratio, p.momentum)) for p in self.points()),
                       key=lambda item: item[1].y())
        dots = [QRectF(s.x() - 5, s.y() - 5, 10, 10) for _p, s in spots]
        placed: list[QRectF] = []
        out: list[tuple[RotationPoint, QPointF, QRectF]] = []
        for point, spot in spots:
            width = metrics.horizontalAdvance(sector_name(point.sector)) + 2
            height = metrics.height()
            choice: QRectF | None = None
            for step in _LABEL_STEPS:
                top = spot.y() - height / 2 + step * height
                for left in (spot.x() + 8, spot.x() - 8 - width):
                    rect = QRectF(left, top, width, height)
                    if (plot.contains(rect) and not any(rect.intersects(r) for r in placed)
                            and not any(rect.intersects(d) for d in dots)):
                        choice = rect
                        break
                if choice is not None:
                    break
            rect = choice or QRectF(spot.x() + 8, spot.y() - height / 2, width, height)
            placed.append(rect)
            out.append((point, spot, rect))
        return out

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw the tinted quadrants with names, then tails, dots and names."""
        if not self.points():
            return
        painter = self._painter()
        plot = self.plot_rect()
        half_w, half_h = plot.width() / 2, plot.height() / 2
        small = QFont(self.font())
        small.setPointSizeF(max(small.pointSizeF() - 1.5, 6.0))
        for name, colour, col, row in _QUADRANTS:
            rect = QRectF(plot.left() + col * half_w, plot.top() + row * half_h, half_w, half_h)
            painter.fillRect(rect, mix(C.BG, getattr(C, colour), 0.08))
            painter.setPen(mix(C.MUTED, getattr(C, colour), 0.5))
            painter.setFont(small)
            align = (Qt.AlignmentFlag.AlignRight if col else Qt.AlignmentFlag.AlignLeft) | (
                Qt.AlignmentFlag.AlignBottom if row else Qt.AlignmentFlag.AlignTop)
            painter.drawText(rect.adjusted(4, 2, -4, -2), align, name.upper())
        painter.setFont(self.font())
        labels = self.label_rects(painter)
        for point, spot, rect in labels:
            dot = quadrant_colour(point.ratio, point.momentum)
            if point.tail is not None:
                start = self.to_screen(*point.tail)
                faded = QColor(dot)
                faded.setAlphaF(0.6)
                painter.setPen(QPen(faded, 1.4, Qt.PenStyle.DashLine))
                painter.drawLine(start, spot)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(faded)
                painter.drawEllipse(start, 2.0, 2.0)
            near = QPointF(rect.left() if rect.left() > spot.x() else rect.right(),
                           rect.center().y())
            if abs(near.y() - spot.y()) > 3:
                painter.setPen(QPen(QColor(C.MUTED), 0.8))
                painter.drawLine(spot, near)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot)
            painter.drawEllipse(spot, 4.5, 4.5)
            painter.setPen(QColor(C.TEXT))
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             sector_name(point.sector))
        painter.end()

    def point_at(self, pos: QPointF) -> RotationPoint | None:
        """The sector whose dot is within 8 px of ``pos``."""
        best: tuple[float, RotationPoint] | None = None
        for point in self.points():
            spot = self.to_screen(point.ratio, point.momentum)
            gap = (spot.x() - pos.x()) ** 2 + (spot.y() - pos.y()) ** 2
            if gap <= 64 and (best is None or gap < best[0]):
                best = (gap, point)
        return best[1] if best else None

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Show the hovered sector's numbers."""
        if event is None:
            return
        point = self.point_at(event.position())
        if point is None:
            QToolTip.hideText()
        else:
            QToolTip.showText(event.globalPosition().toPoint(), _tip(point), self)


class StrengthBars(_Painted):
    """One bar per sector for its strength against the S&P 500 (RS ratio minus 100), strongest
    first, coloured by quadrant, with the value and quadrant name on the right."""

    def bars(self) -> list[tuple[RotationPoint, float]]:
        """Return ``(point, strength)`` strongest first."""
        points = sorted(rotation_points(self.rows), key=lambda p: p.ratio, reverse=True)
        return [(p, p.ratio - 100) for p in points]

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw names, bars from a centre line, values and quadrant names."""
        bars = self.bars()
        if not bars:
            return
        painter = self._painter()
        metrics = painter.fontMetrics()
        name_w = max(metrics.horizontalAdvance(sector_name(p.sector)) for p, _v in bars) + 12
        value_w = metrics.horizontalAdvance("+00.0%") + 12
        stage_w = metrics.horizontalAdvance("Weakening") + 8
        left, right = _PAD + name_w, self.width() - _PAD - value_w - stage_w
        row_h = min(26.0, (self.height() - 2 * _PAD) / len(bars))
        scale = max(max(abs(v) for _p, v in bars) * 1.1, 1.0)
        centre = (left + right) / 2
        painter.setPen(QPen(QColor(C.OVERLAY2), 1))
        painter.drawLine(QPointF(centre, _PAD), QPointF(centre, _PAD + row_h * len(bars)))
        for i, (point, value) in enumerate(bars):
            top = _PAD + i * row_h
            mid = top + row_h / 2
            colour = quadrant_colour(point.ratio, point.momentum)
            painter.setPen(QColor(C.TEXT))
            painter.drawText(QRectF(_PAD, top, name_w - 10, row_h),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             sector_name(point.sector))
            end = centre + value / scale * (right - centre)
            bar = QRectF(min(centre, end), mid - row_h * 0.3, max(abs(end - centre), 1.0),
                         row_h * 0.6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            painter.drawRoundedRect(bar, 2, 2)
            painter.setPen(QColor(C.SUBTEXT))
            painter.drawText(QRectF(right + 6, top, value_w, row_h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             f"{value:+.1f}%")
            painter.setPen(colour)
            painter.drawText(QRectF(right + value_w, top, stage_w, row_h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             quadrant_of(point.ratio, point.momentum))
        painter.end()


class RotationPanel(QWidget):
    """Sector rotation with a Map / List switch: the map, or strength bars. The choice is kept
    while the app runs, so a panel refresh does not reset it."""

    list_mode = False

    def __init__(self, rows: Rows, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lines = QVBoxLayout(self)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(4)
        switch = QFrame()
        switch.setObjectName("rotation_switch")
        switch.setStyleSheet(
            f"QFrame#rotation_switch {{ border: 1px solid {C.OVERLAY2}; border-radius: 6px; }}"
            " QFrame#rotation_switch QPushButton { background: transparent; border: none;"
            f" padding: 0 10px; color: {C.SUBTEXT}; outline: none; }}"
            " QFrame#rotation_switch QPushButton:focus { outline: none; }"
            f" QFrame#rotation_switch QPushButton:checked {{ background: {C.OVERLAY};"
            f" color: {C.TEXT}; }}")
        seg = QHBoxLayout(switch)
        seg.setContentsMargins(0, 0, 0, 0)
        seg.setSpacing(0)
        self.map_btn, self.list_btn = QPushButton("Map"), QPushButton("List")
        group = QButtonGroup(self)
        for button in (self.map_btn, self.list_btn):
            button.setCheckable(True)
            group.addButton(button)
            seg.addWidget(button)
        top = QHBoxLayout()
        top.addStretch(1)
        top.addWidget(switch)
        lines.addLayout(top)
        self.map = RotationView(rows)
        self.list = StrengthBars(rows)
        self._stack = QStackedWidget()
        self._stack.addWidget(self.map)
        self._stack.addWidget(self.list)
        lines.addWidget(self._stack, 1)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet(f"color: {C.MUTED};")
        lines.addWidget(self.note)
        # Map / List buttons → clicked → panel → show that view
        self.map_btn.clicked.connect(lambda: self.show_list(False))
        self.list_btn.clicked.connect(lambda: self.show_list(True))
        self.show_list(RotationPanel.list_mode)

    def show_list(self, on: bool) -> None:
        """Show the strength bars (``on``) or the map, and remember the choice."""
        RotationPanel.list_mode = on
        self._stack.setCurrentWidget(self.list if on else self.map)
        self.note.setText(LIST_NOTE if on else MAP_NOTE)
        self.list_btn.setChecked(on)
        self.map_btn.setChecked(not on)


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
                                         "line": LineView, "rotation": RotationPanel}
    maker = makers.get(view)
    if maker is None:
        return None
    return maker(rows) if rows else empty_note()
