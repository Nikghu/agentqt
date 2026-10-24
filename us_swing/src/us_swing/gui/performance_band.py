"""
Module: MD-GUI-025.013.M03 — Performance band and exposure bars
Parent SRD: SRD-GUI-025.013, SRD-GUI-025.015

Account Equity band (value, change for the range, range buttons, line-and-area chart)
and the Exposure view of the Open Positions tile (one vertical bar per symbol).
Data comes from ``AppService.get_equity_curve`` and the open positions.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPaintEvent, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from us_swing.gui.screener_views import ChipGroup
from us_swing.gui.strategy_pnl_chart import money, nice_ticks
from us_swing.gui.theme import C

RANGES = ("1D", "1W", "1M", "3M", "YTD")
MAX_BARS = 8
_SINCE_TEXT = {"1D": "today", "1W": "this week", "1M": "this month", "3M": "in 3 months",
               "YTD": "this year"}
_AXIS_W = 64
_AXIS_H = 20
_MONO = '"IBM Plex Mono", Consolas, monospace'
_ISO = "%Y-%m-%dT%H:%M:%S"


class _Point(Protocol):
    @property
    def at(self) -> str: ...
    @property
    def value(self) -> float: ...


def _seconds(iso: str) -> float:
    return datetime.strptime(iso[:19], _ISO).replace(tzinfo=timezone.utc).timestamp()


def change_text(points: Sequence[_Point], range_key: str) -> tuple[str, float]:
    """"+$41.75 (+0.17%) today" and the signed change; empty text without two points."""
    if len(points) < 2:
        return "", 0.0
    first, last = points[0].value, points[-1].value
    diff = last - first
    pct = diff / first * 100 if first else 0.0
    sign = "+" if pct > 0 else "−" if pct < 0 else ""
    return f"{money(diff)} ({sign}{abs(pct):.2f}%) {_SINCE_TEXT.get(range_key, '')}", diff


class EquityChart(QWidget):
    """Line-and-area equity curve over time with a dashed start line (SRD-GUI-025.013)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.points: tuple[_Point, ...] = ()
        self._label: Callable[[str], str] = lambda iso: iso[11:16]
        self.setMinimumHeight(120)

    def set_points(self, points: Iterable[_Point], label: Callable[[str], str]) -> None:
        self.points = tuple(points)
        self._label = label
        self.update()

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if len(self.points) < 2:
            painter.setPen(QColor(C.MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No equity data for this range yet")
            painter.end()
            return
        plot = QRectF(4, 8, self.width() - _AXIS_W - 8, self.height() - _AXIS_H - 12)
        values = [p.value for p in self.points]
        ticks = nice_ticks(min(values), max(values))
        lo, hi = ticks[0], ticks[-1]
        times = [_seconds(p.at) for p in self.points]
        t0, span = times[0], (times[-1] - times[0]) or 1.0

        def x(t: float) -> float:
            return plot.left() + (t - t0) / span * plot.width()

        def y(v: float) -> float:
            return plot.bottom() - (v - lo) / ((hi - lo) or 1.0) * plot.height()

        self._draw_axes(painter, plot, ticks, y, [x(t) for t in times])
        colour = QColor(C.GREEN if values[-1] >= values[0] else C.RED)
        line = QPainterPath(QPointF(x(times[0]), y(values[0])))
        for t, v in zip(times[1:], values[1:]):
            line.lineTo(QPointF(x(t), y(v)))
        area = QPainterPath(line)
        area.lineTo(QPointF(x(times[-1]), plot.bottom()))
        area.lineTo(QPointF(x(times[0]), plot.bottom()))
        area.closeSubpath()
        gradient = QLinearGradient(0, plot.top(), 0, plot.bottom())
        top, bottom = QColor(colour), QColor(colour)
        top.setAlphaF(0.22)
        bottom.setAlphaF(0.0)
        gradient.setColorAt(0, top)
        gradient.setColorAt(1, bottom)
        painter.fillPath(area, gradient)
        painter.setPen(QPen(QColor(C.MUTED), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(plot.left(), y(values[0])), QPointF(plot.right(), y(values[0])))
        painter.setPen(QPen(colour, 1.8))
        painter.drawPath(line)
        painter.end()

    def _draw_axes(self, painter: QPainter, plot: QRectF, ticks: list[float],
                   y: Callable[[float], float], xs: list[float]) -> None:
        for t in ticks:
            painter.setPen(QPen(QColor(C.OVERLAY), 1))
            painter.drawLine(QPointF(plot.left(), y(t)), QPointF(plot.right(), y(t)))
            painter.setPen(QColor(C.SUBTEXT))
            painter.drawText(QRectF(plot.right() + 4, y(t) - 8, _AXIS_W - 4, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"${t:,.0f}")
        painter.setPen(QColor(C.SUBTEXT))
        last_x = -1e9
        for px, point in zip(xs, self.points):
            left = min(max(px - 35, 0.0), plot.right() - 70)
            if left - last_x < 70:
                continue
            last_x = left
            painter.drawText(QRectF(left, plot.bottom() + 4, 70, _AXIS_H - 4),
                             Qt.AlignmentFlag.AlignCenter, self._label(point.at))


class PerformanceBand(QWidget):
    """Account Equity value, change, range buttons and chart (SRD-GUI-025.013)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        name = QLabel("ACCOUNT EQUITY")
        name.setStyleSheet(
            f"color:{C.MUTED}; font-size:7.5pt; font-weight:bold; letter-spacing:1px;")
        self.value_lbl = QLabel("—")
        self.value_lbl.setStyleSheet(f"color:{C.TEXT}; font-family:{_MONO}; font-size:18pt;")
        self.change_lbl = QLabel("")
        self.ranges = ChipGroup([(key, key) for key in RANGES])
        self.chart = EquityChart()

        values = QHBoxLayout()
        values.setSpacing(12)
        values.addWidget(self.value_lbl)
        values.addWidget(self.change_lbl, 0, Qt.AlignmentFlag.AlignBottom)
        values.addStretch()
        head = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(2)
        title.addWidget(name)
        title.addLayout(values)
        head.addLayout(title, 1)
        head.addWidget(self.ranges, 0, Qt.AlignmentFlag.AlignTop)

        box = QVBoxLayout(self)
        box.setContentsMargins(16, 10, 12, 8)
        box.setSpacing(6)
        box.addLayout(head)
        box.addWidget(self.chart, 1)
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    @property
    def range_key(self) -> str:
        return self.ranges.value or "1D"

    def set_range(self, key: str) -> None:
        index = RANGES.index(key) if key in RANGES else 0
        self.ranges.buttons[index].setChecked(True)

    def show_curve(self, points: Sequence[_Point], label: Callable[[str], str]) -> None:
        """Header value is the curve's last point, so number, change and line agree."""
        self.value_lbl.setText(f"${points[-1].value:,.2f}" if points else "—")
        text, diff = change_text(points, self.range_key)
        colour = C.GREEN if diff > 0 else C.RED if diff < 0 else C.MUTED
        self.change_lbl.setText(text)
        self.change_lbl.setStyleSheet(f"color:{colour}; font-family:{_MONO}; font-size:9pt;")
        self.chart.set_points(points, label)


# ── Exposure (SRD-GUI-025.015) ────────────────────────────────────────────────

class _Position(Protocol):
    @property
    def symbol(self) -> str: ...
    @property
    def quantity(self) -> int: ...
    @property
    def current_price(self) -> float: ...
    @property
    def average_price(self) -> float: ...
    @property
    def direction(self) -> str: ...


@dataclass(frozen=True, slots=True)
class ExposureBar:
    symbol: str
    side: str     # "Long" | "Short"
    value: float


def market_value(pos: _Position) -> float:
    """Shares × last price, or × entry price before the first quote."""
    return abs(pos.quantity) * (pos.current_price or pos.average_price)


def exposure_bars(positions: Iterable[_Position]) -> list[ExposureBar]:
    """Market value per symbol and side, largest first; last price, else entry price.

    More than ``MAX_BARS`` bars: the smallest are joined into one "N others" bar.
    """
    totals: dict[tuple[str, str], float] = {}
    for pos in positions:
        side = "Short" if pos.direction == "SHORT" else "Long"
        key = (pos.symbol, side)
        totals[key] = totals.get(key, 0.0) + market_value(pos)
    bars = sorted((ExposureBar(sym, side, value) for (sym, side), value in totals.items()),
                  key=lambda b: b.value, reverse=True)
    if len(bars) > MAX_BARS:
        rest = bars[MAX_BARS - 1:]
        bars = bars[:MAX_BARS - 1] + [
            ExposureBar(f"{len(rest)} others", "Mixed", sum(b.value for b in rest))]
    return bars


class ExposureChart(QWidget):
    """Vertical bar per symbol, value on top, symbol and side below."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bars: list[ExposureBar] = []
        self.labels: list[str] = []
        self.setMinimumHeight(140)

    def set_bars(self, bars: list[ExposureBar], labels: list[str]) -> None:
        self.bars, self.labels = bars, labels
        self.update()

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.bars:
            painter.setPen(QColor(C.MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No open positions")
            painter.end()
            return
        top, bottom = 22.0, self.height() - 36.0
        peak = max(b.value for b in self.bars) or 1.0
        slot = self.width() / len(self.bars)
        width = min(84.0, slot * 0.6)
        painter.setPen(QPen(QColor(C.OVERLAY2), 1))
        painter.drawLine(QPointF(0, bottom), QPointF(self.width(), bottom))
        for i, (bar, label) in enumerate(zip(self.bars, self.labels)):
            cx = slot * (i + 0.5)
            height = bar.value / peak * (bottom - top)
            colour = QColor({"Long": C.BLUE, "Short": C.ORANGE}.get(bar.side, C.OVERLAY2))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            painter.drawRoundedRect(QRectF(cx - width / 2, bottom - height, width, height), 3, 3)
            painter.setPen(QColor(C.TEXT))
            if painter.fontMetrics().horizontalAdvance(label) <= slot - 4:
                painter.drawText(QRectF(cx - slot / 2, bottom - height - 18, slot, 16),
                                 Qt.AlignmentFlag.AlignCenter, label)
            painter.drawText(QRectF(cx - slot / 2, bottom + 4, slot, 16),
                             Qt.AlignmentFlag.AlignCenter, bar.symbol)
            painter.setPen(QColor(C.MUTED))
            painter.drawText(QRectF(cx - slot / 2, bottom + 18, slot, 14),
                             Qt.AlignmentFlag.AlignCenter, bar.side)
        painter.end()


class ExposureView(QWidget):
    """Long / Short / Net / Gross ÷ Equity totals beside the bar chart."""

    TOTALS = ("Long", "Short", "Net", "Gross ÷ Equity")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values: dict[str, QLabel] = {}
        side = QVBoxLayout()
        side.setSpacing(10)
        for name in self.TOTALS:
            caption = QLabel(name.upper())
            caption.setStyleSheet(
                f"color:{C.MUTED}; font-size:7.5pt; font-weight:bold; letter-spacing:1px;")
            value = QLabel("—")
            value.setStyleSheet(f"color:{C.TEXT}; font-family:{_MONO}; font-size:12pt;")
            self.values[name] = value
            side.addWidget(caption)
            side.addWidget(value)
            side.addSpacing(4)
        side.addStretch()
        self.chart = ExposureChart()
        box = QHBoxLayout(self)
        box.setContentsMargins(16, 12, 16, 8)
        box.setSpacing(20)
        box.addLayout(side)
        box.addWidget(self.chart, 1)

    def show_positions(self, positions: Iterable[_Position], equity: float,
                       as_percent: bool) -> None:
        positions = list(positions)
        bars = exposure_bars(positions)
        long_v = sum(market_value(p) for p in positions if p.direction != "SHORT")
        short_v = sum(market_value(p) for p in positions if p.direction == "SHORT")
        self.values["Long"].setText(f"${long_v:,.0f}")
        self.values["Short"].setText(f"${short_v:,.0f}")
        self.values["Net"].setText(f"${long_v - short_v:,.0f}")
        gross = (long_v + short_v) / equity * 100 if equity else 0.0
        self.values["Gross ÷ Equity"].setText(f"{gross:.1f}%" if equity else "—")
        if as_percent and equity:
            labels = [f"{b.value / equity * 100:.1f}%" for b in bars]
        else:
            labels = [f"${b.value:,.0f}" for b in bars]
        self.chart.set_bars(bars, labels)
