"""
Module: MD-GUI-031.080.M13 — Backtest report chart
Parent SRD: SRD-GUI-031.041, SRD-GUI-031.080, SRD-GUI-031.081

Equity and benchmark lines over a start-capital line, with the drawdown band below:
$ axis on the left, month ticks, end labels and a max drawdown marker. A vertical line
follows the mouse and shows that day's date, equity, benchmark and drawdown.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PyQt6.QtWidgets import QWidget

from us_swing.core.dates import show_date
from us_swing.gui.strategy_pnl_chart import nice_ticks
from us_swing.gui.theme import C

_LEFT = 64
_RIGHT = 78
_LEGEND = 30
_DATES = 20
_GAP = 22
_DD_SHARE = 0.28
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass(frozen=True)
class _Layout:
    line: QRectF
    dd: QRectF


def _money(value: float) -> str:
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"


def _axis_money(value: float) -> str:
    return f"${value / 1000:,.1f}k" if abs(value) >= 1000 else f"${value:,.0f}"


class ReportChart(QWidget):
    """SRD-GUI-031.041 / .080 / .081 — equity vs benchmark, drawdown band, hover line."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.daily = pd.DataFrame(columns=["date", "equity", "drawdown", "benchmark"])
        self.capital = math.nan
        self.hover: int | None = None
        self.setMinimumHeight(300)
        self.setMouseTracking(True)

    def set_daily(self, daily: pd.DataFrame, capital: float | None = None) -> None:
        """Show ``daily`` rows; ``capital`` draws the start line (first equity when None)."""
        self.daily = daily.reset_index(drop=True)
        first = float(daily["equity"].iloc[0]) if len(daily) else math.nan
        self.capital = first if capital is None else capital
        self.hover = None
        self.update()

    # ── Hover (SRD-GUI-031.081) ─────────────────────────────────────────────

    def index_at(self, x: float) -> int | None:
        """Day index under the pixel ``x``, or None outside the plot."""
        if len(self.daily) < 2:
            return None
        line = self._layout().line
        if not line.left() <= x <= line.right():
            return None
        return round((x - line.left()) / line.width() * (len(self.daily) - 1))

    def hover_lines(self, index: int) -> list[str]:
        """Date, strategy, benchmark and drawdown text for one day."""
        row = self.daily.iloc[index]
        bench = float(row["benchmark"])
        return [show_date(pd.Timestamp(row["date"])), f"Strategy   {_money(float(row['equity']))}",
                f"Benchmark  {'—' if math.isnan(bench) else _money(bench)}",
                f"Drawdown   {float(row['drawdown']):.1%}"]

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if event is not None:
            index = self.index_at(event.position().x())
            if index != self.hover:
                self.hover = index
                self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent | None) -> None:  # noqa: N802
        self.hover = None
        self.update()
        super().leaveEvent(event)

    # ── Painting ────────────────────────────────────────────────────────────

    def _layout(self) -> _Layout:
        width = self.width() - _LEFT - _RIGHT
        plots = self.height() - _LEGEND - _DATES - _GAP
        line = QRectF(_LEFT, _LEGEND, width, plots * (1 - _DD_SHARE))
        dd = QRectF(_LEFT, line.bottom() + _GAP, width, plots * _DD_SHARE)
        return _Layout(line, dd)

    def _x(self, plot: QRectF, i: int) -> float:
        return plot.left() + i / max(len(self.daily) - 1, 1) * plot.width()

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if len(self.daily) < 2:
            painter.setPen(QColor(C.MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Run a backtest to see the equity curve")
            painter.end()
            return
        lay = self._layout()
        self._months(painter, lay)
        y = self._line_panel(painter, lay.line)
        self._drawdown_panel(painter, lay.dd)
        self._legend(painter, lay.line)
        if self.hover is not None:
            self._hover(painter, lay, y)
        painter.end()

    def _months(self, painter: QPainter, lay: _Layout) -> None:
        dates = pd.to_datetime(self.daily["date"])
        months = dates.dt.to_period("M")
        starts = [0, *[i for i in range(1, len(dates)) if months.iloc[i] != months.iloc[i - 1]]]
        last_label = -1e9
        for i in starts:
            x = self._x(lay.line, i)
            painter.setPen(QPen(QColor(C.OVERLAY), 1))
            painter.drawLine(QPointF(x, lay.line.top()), QPointF(x, lay.dd.bottom()))
            stamp = dates.iloc[i]
            text = _MONTHS[stamp.month - 1]
            if i == 0 or stamp.month == 1:
                text += f" ’{stamp.year % 100:02d}"
            if x - last_label >= 46:
                painter.setPen(QColor(C.SUBTEXT))
                painter.drawText(QRectF(x + 3, lay.dd.bottom() + 3, 60, _DATES - 4),
                                 Qt.AlignmentFlag.AlignLeft, text)
                last_label = x

    def _line_panel(self, painter: QPainter, plot: QRectF) -> list[float]:
        equity = self.daily["equity"].astype(float)
        bench = self.daily["benchmark"].astype(float)
        values = [*equity, *bench.dropna()]
        if not math.isnan(self.capital):
            values.append(self.capital)
        ticks = nice_ticks(min(values), max(values), steps=4)
        lo, hi = ticks[0], ticks[-1]

        def y(v: float) -> float:
            return plot.bottom() - (v - lo) / ((hi - lo) or 1.0) * plot.height()

        for t in ticks:
            painter.setPen(QPen(QColor(C.OVERLAY), 1))
            painter.drawLine(QPointF(plot.left(), y(t)), QPointF(plot.right(), y(t)))
            painter.setPen(QColor(C.SUBTEXT))
            painter.drawText(QRectF(0, y(t) - 8, _LEFT - 8, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             _axis_money(t))
        if not math.isnan(self.capital):
            painter.setPen(QPen(QColor(C.OVERLAY2), 1, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(plot.left(), y(self.capital)),
                             QPointF(plot.right(), y(self.capital)))
        area = self._path(plot, equity, y)
        if area is not None:
            fill = QPainterPath(area)
            fill.lineTo(QPointF(plot.right(), plot.bottom()))
            fill.lineTo(QPointF(plot.left(), plot.bottom()))
            fill.closeSubpath()
            tint = QColor(C.BLUE)
            tint.setAlphaF(0.08)
            painter.fillPath(fill, tint)
        for series, colour, style in ((bench, C.MUTED, Qt.PenStyle.DashLine),
                                      (equity, C.BLUE, Qt.PenStyle.SolidLine)):
            path = self._path(plot, series, y)
            if path is not None:
                painter.setPen(QPen(QColor(colour), 1.8, style))
                painter.drawPath(path)
        self._end_labels(painter, plot, equity, bench, y)
        return [lo, hi]

    def _path(self, plot: QRectF, series: pd.Series,
              y: Callable[[float], float]) -> QPainterPath | None:
        path: QPainterPath | None = None
        for i, v in enumerate(series):
            if math.isnan(v):
                continue
            point = QPointF(self._x(plot, i), y(v))
            if path is None:
                path = QPainterPath(point)
            else:
                path.lineTo(point)
        return path

    def _end_labels(self, painter: QPainter, plot: QRectF, equity: pd.Series,
                    bench: pd.Series, y: Callable[[float], float]) -> None:
        tops: list[float] = []
        for series, colour in ((equity, C.BLUE), (bench, C.MUTED)):
            value = float(series.iloc[-1])
            if math.isnan(value):
                continue
            top = y(value)
            if tops and abs(top - tops[0]) < 16:
                top = tops[0] + (16 if top >= tops[0] else -16)
            tops.append(top)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colour))
            painter.drawEllipse(QPointF(plot.right(), y(value)), 3.5, 3.5)
            painter.setPen(QColor(colour))
            painter.drawText(QRectF(plot.right() + 7, top - 8, _RIGHT - 8, 16),
                             Qt.AlignmentFlag.AlignVCenter, f"${value:,.0f}")

    def _drawdown_panel(self, painter: QPainter, plot: QRectF) -> None:
        dd = self.daily["drawdown"].astype(float)
        low = min(float(dd.min()), -0.0001)

        def y(v: float) -> float:
            return plot.top() + v / low * plot.height()

        area = QPainterPath(QPointF(self._x(plot, 0), y(0)))
        for i, v in enumerate(dd):
            area.lineTo(QPointF(self._x(plot, i), y(v)))
        area.lineTo(QPointF(self._x(plot, len(dd) - 1), y(0)))
        area.closeSubpath()
        fill = QColor(C.RED)
        fill.setAlphaF(0.35)
        painter.fillPath(area, fill)
        painter.setPen(QPen(QColor(C.RED), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(area)
        painter.setPen(QPen(QColor(C.OVERLAY2), 1))
        painter.drawLine(QPointF(plot.left(), plot.top()), QPointF(plot.right(), plot.top()))
        painter.setPen(QColor(C.SUBTEXT))
        for value, top in ((0.0, plot.top()), (low, plot.bottom())):
            painter.drawText(QRectF(0, top - 8, _LEFT - 8, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"{value:.0%}")
        painter.drawText(QRectF(plot.left() + 6, plot.top() + 3, 120, 16), "Drawdown")
        worst = int(dd.idxmin())
        point = QPointF(self._x(plot, worst), y(float(dd.iloc[worst])))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(C.RED))
        painter.drawEllipse(point, 3.5, 3.5)
        painter.setPen(QColor(C.RED))
        left = point.x() + 6 if point.x() < plot.right() - 90 else point.x() - 90
        painter.drawText(QRectF(left, point.y() - 16, 90, 14), Qt.AlignmentFlag.AlignLeft,
                         f"{low:.1%} max")

    def _legend(self, painter: QPainter, plot: QRectF) -> None:
        equity = self.daily["equity"].astype(float)
        bench = self.daily["benchmark"].astype(float).dropna()
        start = self.capital if not math.isnan(self.capital) else float(equity.iloc[0])
        items = [(C.BLUE, Qt.PenStyle.SolidLine,
                  f"Strategy {float(equity.iloc[-1]) / start - 1:+.1%}")]
        if len(bench):
            items.append((C.MUTED, Qt.PenStyle.DashLine,
                          f"Same stocks, equal weight {float(bench.iloc[-1]) / start - 1:+.1%}"))
        x = plot.left()
        metrics = QFontMetrics(painter.font())
        for colour, style, text in items:
            painter.setPen(QPen(QColor(colour), 2, style))
            painter.drawLine(QPointF(x, 10), QPointF(x + 18, 10))
            painter.setPen(QColor(C.SUBTEXT))
            painter.drawText(QPointF(x + 24, 14), text)
            x += 24 + metrics.horizontalAdvance(text) + 20
        painter.setPen(QColor(C.MUTED))
        painter.drawText(QRectF(plot.right() - 200, 2, 200, 16), Qt.AlignmentFlag.AlignRight,
                         f"Start ${start:,.0f}")

    def _hover(self, painter: QPainter, lay: _Layout, y_range: list[float]) -> None:
        i = self.hover if self.hover is not None else 0
        x = self._x(lay.line, i)
        painter.setPen(QPen(QColor(C.TEXT), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x, lay.line.top()), QPointF(x, lay.dd.bottom()))
        lo, hi = y_range
        row = self.daily.iloc[i]
        for column, colour in (("equity", C.BLUE), ("benchmark", C.MUTED)):
            value = float(row[column])
            if math.isnan(value):
                continue
            yy = lay.line.bottom() - (value - lo) / ((hi - lo) or 1.0) * lay.line.height()
            painter.setPen(QPen(QColor(C.BG), 2))
            painter.setBrush(QColor(colour))
            painter.drawEllipse(QPointF(x, yy), 4, 4)
        self._hover_readout(painter, lay, x, i)

    def _hover_readout(self, painter: QPainter, lay: _Layout, x: float, i: int) -> None:
        """Values in the legend row and a date tag on the time axis; nothing covers a line."""
        date, *values = self.hover_lines(i)
        painter.fillRect(QRectF(0, 0, self.width(), _LEGEND - 6), QColor(C.BG))
        font = QFont(painter.font())
        font.setFamily("IBM Plex Mono")
        painter.setFont(font)
        metrics = QFontMetrics(font)
        left = lay.line.left()
        for text, colour in zip([date, *[" ".join(v.split()) for v in values]],
                                [C.TEXT, C.BLUE, C.SUBTEXT, C.RED], strict=True):
            painter.setPen(QColor(colour))
            painter.drawText(QPointF(left, 14), text)
            left += metrics.horizontalAdvance(text) + 22
        tag_w = metrics.horizontalAdvance(date) + 12
        tag = QRectF(min(max(x - tag_w / 2, lay.dd.left()), lay.dd.right() - tag_w),
                     lay.dd.bottom() + 1, tag_w, _DATES - 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(C.OVERLAY2))
        painter.drawRoundedRect(tag, 3, 3)
        painter.setPen(QColor(C.TEXT))
        painter.drawText(tag, Qt.AlignmentFlag.AlignCenter, date)
