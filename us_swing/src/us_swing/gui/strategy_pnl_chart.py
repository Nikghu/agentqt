"""
Module: MD-GUI-024.006.M05 — Strategy P&L chart and card
Parent SRD: SRD-GUI-024.006

Running-total line (or one bar per trade) of a strategy's realized P&L, the
largest drawdown drawn in red, range buttons and a stats column.  Data comes
from ``AppService.get_strategy_pnl`` (FO-EXE-019) through a provider callable.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPaintEvent, QPen
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from us_swing.execution.trade_cycle import StrategyPnlSummary
from us_swing.gui.screener_views import ChipGroup
from us_swing.gui.theme import C

PnlProvider = Callable[[str | None], StrategyPnlSummary]

_AXIS_W = 56
_AXIS_H = 20
_MONO = '"IBM Plex Mono", Consolas, monospace'
RANGES: list[tuple[str, str | None]] = [("1W", "7"), ("1M", "30"), ("3M", "90"), ("All", None)]


def money(value: float) -> str:
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def nice_ticks(lo: float, hi: float, steps: int = 3) -> list[float]:
    """Round axis ticks covering [lo, hi] with about ``steps`` intervals."""
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / steps
    power = 10 ** math.floor(math.log10(raw))
    step = next(m * power for m in (1, 1.5, 2, 2.5, 5, 10) if m * power >= raw)
    start = math.floor(lo / step) * step
    end = math.ceil(hi / step) * step
    count = round((end - start) / step)
    return [start + i * step for i in range(count + 1)]


def since_iso(days: str | None, now: datetime | None = None) -> str | None:
    """UTC ISO start for a range button value (days), ``None`` for All."""
    if days is None:
        return None
    start = (now or datetime.now(timezone.utc)) - timedelta(days=int(days))
    return start.strftime("%Y-%m-%dT%H:%M:%S")


class StrategyPnlChart(QWidget):
    """Running-total line or per-trade bars (SRD-GUI-024.006)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._summary = StrategyPnlSummary()
        self._bars = False
        self.setMinimumHeight(140)

    def set_summary(self, summary: StrategyPnlSummary, *, bars: bool = False) -> None:
        self._summary = summary
        self._bars = bars
        self.update()

    @property
    def is_empty(self) -> bool:
        return not self._summary.points

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.is_empty:
            painter.setPen(QColor(C.MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No closed trades yet")
            painter.end()
            return
        plot = QRectF(4, 8, self.width() - _AXIS_W - 8, self.height() - _AXIS_H - 12)
        values = [p.pnl for p in self._summary.points] if self._bars else [
            p.cumulative for p in self._summary.points
        ]
        low, high = min(0.0, *values), max(0.0, *values)
        ticks = nice_ticks(low, high)
        hi = ticks[-1]
        # Start just under the lowest value, not at a far-away round tick.
        lo = low if low == 0 else max(ticks[0], low - 0.05 * (hi - low))
        ticks = [t for t in ticks if t >= lo]

        def y(v: float) -> float:
            return plot.bottom() - (v - lo) / (hi - lo) * plot.height()

        self._draw_axes(painter, plot, ticks, y)
        if self._bars:
            self._draw_bars(painter, plot, y)
        else:
            self._draw_line(painter, plot, y)
        painter.end()

    def _x(self, plot: QRectF, i: int) -> float:
        """x of point *i*; -1 is the zero start on the left edge."""
        n = len(self._summary.points)
        return plot.left() + (i + 1) / max(n, 1) * plot.width()

    def _draw_axes(
        self, painter: QPainter, plot: QRectF, ticks: list[float], y: Callable[[float], float]
    ) -> None:
        painter.setPen(QPen(QColor(C.OVERLAY), 1))
        for t in ticks:
            painter.drawLine(QPointF(plot.left(), y(t)), QPointF(plot.right(), y(t)))
            painter.save()
            painter.setPen(QColor(C.SUBTEXT))
            painter.drawText(
                QRectF(plot.right() + 4, y(t) - 8, _AXIS_W - 4, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"${t:,.0f}",
            )
            painter.restore()
        zero = QPen(QColor(C.MUTED), 1, Qt.PenStyle.DashLine)
        painter.setPen(zero)
        painter.drawLine(QPointF(plot.left(), y(0)), QPointF(plot.right(), y(0)))

        painter.setPen(QColor(C.SUBTEXT))
        last_x = -1e9
        last_month = ""
        for i, p in enumerate(self._summary.points):
            month = p.closed_at[:7]
            if month == last_month:
                continue
            last_month = month
            x = self._x(plot, i)
            if x - last_x < 44:
                continue
            last_x = x
            label = datetime.strptime(month, "%Y-%m").strftime("%b") if month else ""
            painter.drawText(
                QRectF(x - 22, plot.bottom() + 4, 44, _AXIS_H - 4),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )

    def _path(self, plot: QRectF, y: Callable[[float], float], start: int, end: int) -> QPainterPath:
        path = QPainterPath()
        for i in range(start, end + 1):
            value = 0.0 if i < 0 else self._summary.points[i].cumulative
            point = QPointF(self._x(plot, i), y(value))
            if i == start:
                path.moveTo(point)
            else:
                path.lineTo(point)
        return path

    def _draw_line(self, painter: QPainter, plot: QRectF, y: Callable[[float], float]) -> None:
        s = self._summary
        colour = QColor(C.GREEN if s.total >= 0 else C.RED)
        line = self._path(plot, y, -1, len(s.points) - 1)

        area = QPainterPath(line)
        area.lineTo(QPointF(self._x(plot, len(s.points) - 1), plot.bottom()))
        area.lineTo(QPointF(self._x(plot, -1), plot.bottom()))
        area.closeSubpath()
        gradient = QLinearGradient(0, plot.top(), 0, plot.bottom())
        top = QColor(colour)
        top.setAlphaF(0.28)
        bottom = QColor(colour)
        bottom.setAlphaF(0.0)
        gradient.setColorAt(0, top)
        gradient.setColorAt(1, bottom)
        painter.fillPath(area, gradient)

        painter.setPen(QPen(colour, 1.6))
        painter.drawPath(line)
        if s.dd_end >= 0:
            painter.setPen(QPen(QColor(C.RED), 2))
            painter.drawPath(self._path(plot, y, s.dd_start, s.dd_end))

    def _draw_bars(self, painter: QPainter, plot: QRectF, y: Callable[[float], float]) -> None:
        n = len(self._summary.points)
        width = max(2.0, min(12.0, plot.width() / max(n, 1) * 0.6))
        painter.setPen(Qt.PenStyle.NoPen)
        for i, p in enumerate(self._summary.points):
            x = self._x(plot, i) - width / 2
            top, bottom = sorted((y(0), y(p.pnl)))
            painter.setBrush(QColor(C.GREEN if p.pnl >= 0 else C.RED))
            painter.drawRect(QRectF(x, top, width, max(bottom - top, 1.0)))


class StrategyPnlCard(QFrame):
    """Strategy P&L card: total, toggles, chart and stats (SRD-GUI-024.006)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detail_tile")
        self._provider: PnlProvider | None = None

        head = QLabel("STRATEGY P&L")
        head.setObjectName("view_head")
        self.total_lbl = QLabel("—")
        self.total_lbl.setStyleSheet(f"font-family: {_MONO}; font-size: 12pt; font-weight: bold;")
        self.meta_lbl = QLabel("")
        self.meta_lbl.setObjectName("view_key")
        self.mode_group = ChipGroup([("P&&L curve", "curve"), ("Per trade", "bars")])
        self.mode_group.changed.connect(self._redraw)
        self.range_group = ChipGroup(RANGES)
        self.range_group.buttons[-1].setChecked(True)
        self.range_group.changed.connect(self.refresh)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(head)
        top.addWidget(self.total_lbl)
        top.addWidget(self.meta_lbl)
        top.addStretch(1)
        top.addWidget(self.mode_group)
        top.addWidget(self.range_group)

        self.chart = StrategyPnlChart()
        stats = QWidget()
        stats.setFixedWidth(210)
        grid = QGridLayout(stats)
        grid.setContentsMargins(12, 0, 0, 0)
        grid.setVerticalSpacing(8)
        self.stats: dict[str, QLabel] = {}
        for row, name in enumerate(("Win rate", "Avg win", "Avg loss", "Max drawdown", "Today")):
            key = QLabel(name)
            key.setObjectName("details_key")
            value = QLabel("—")
            value.setStyleSheet(f"font-family: {_MONO};")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(key, row, 0)
            grid.addWidget(value, row, 1)
            self.stats[name] = value
        grid.setRowStretch(5, 1)

        body = QHBoxLayout()
        body.addWidget(self.chart, 1)
        body.addWidget(stats)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        root.addLayout(top)
        root.addLayout(body, 1)
        self._summary = StrategyPnlSummary()

    def set_provider(self, provider: PnlProvider | None) -> None:
        self._provider = provider
        self.refresh()

    def refresh(self) -> None:
        if self._provider is None:
            self.show_summary(StrategyPnlSummary())
            return
        self.show_summary(self._provider(since_iso(self.range_group.value)))

    def show_summary(self, s: StrategyPnlSummary) -> None:
        self._summary = s
        self._redraw()
        if not s.points:
            self.total_lbl.setText("—")
            self.total_lbl.setStyleSheet(
                f"font-family: {_MONO}; font-size: 12pt; font-weight: bold; color: {C.SUBTEXT};"
            )
            self.meta_lbl.setText("No closed trades in this range")
            for value in self.stats.values():
                value.setText("—")
            return
        colour = C.GREEN if s.total >= 0 else C.RED
        self.total_lbl.setText(money(s.total))
        self.total_lbl.setStyleSheet(
            f"font-family: {_MONO}; font-size: 12pt; font-weight: bold; color: {colour};"
        )
        first = datetime.strptime(s.points[0].closed_at[:10], "%Y-%m-%d").strftime("%d %b")
        self.meta_lbl.setText(f"since {first} · {s.trades} trade{'s' if s.trades != 1 else ''}")
        self._set_stat("Win rate", f"{s.win_rate:.0%}  {s.wins} / {s.trades}", C.TEXT)
        self._set_stat("Avg win", money(s.avg_win), C.GREEN)
        self._set_stat("Avg loss", money(s.avg_loss), C.RED)
        self._set_stat("Max drawdown", money(s.max_drawdown), C.RED)
        today_colour = C.GREEN if s.today > 0 else C.RED if s.today < 0 else C.TEXT
        self._set_stat("Today", money(s.today), today_colour)

    def _set_stat(self, name: str, text: str, colour: str) -> None:
        self.stats[name].setText(text)
        self.stats[name].setStyleSheet(f"font-family: {_MONO}; color: {colour};")

    def _redraw(self) -> None:
        self.chart.set_summary(self._summary, bars=self.mode_group.value == "bars")
