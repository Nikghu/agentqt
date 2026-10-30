"""
Module: MD-GUI-031.052.M06 — Backtest trade chart
Parent SRD: SRD-GUI-031.052

Candles of one stock around a trade: ringed entry and exit dots joined by a path,
IN / OUT price callouts, a result badge, and candles outside the trade dimmed.
"""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QWidget

from us_swing.gui.strategy_pnl_chart import nice_ticks
from us_swing.gui.theme import C

_AXIS_W = 56
_AXIS_H = 18
_ET = "America/New_York"
_Scale = Callable[[float], float]
_DIM = 0.32
_RING = 6.5
_LEADER = 30.0
_BADGE_RISE = 60.0


class TradeChart(QWidget):
    """QPainter candle chart with the session's trade markers."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bars = pd.DataFrame(columns=["ts", "open", "high", "low", "close"])
        self.trades = pd.DataFrame(columns=["direction", "entry_ts", "entry_px", "exit_ts",
                                            "exit_px"])
        self.message = "Pick a trade to see it on the chart"
        self.setMinimumHeight(240)

    def set_data(self, bars: pd.DataFrame, trades: pd.DataFrame, message: str = "") -> None:
        """Show ``bars`` with markers for ``trades``; ``message`` when there are no bars."""
        self.bars = bars.reset_index(drop=True)
        self.trades = trades
        self.message = message
        self.update()

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.bars.empty:
            painter.setPen(QColor(C.MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.message)
            painter.end()
            return
        plot = QRectF(4, 8, self.width() - _AXIS_W - 8, self.height() - _AXIS_H - 12)
        prices = [*self.bars["low"], *self.bars["high"]]
        ticks = nice_ticks(min(prices), max(prices))
        lo, hi = ticks[0], ticks[-1]

        def y(v: float) -> float:
            return plot.bottom() - (v - lo) / ((hi - lo) or 1.0) * plot.height()

        for t in ticks:
            painter.setPen(QPen(QColor(C.OVERLAY), 1))
            painter.drawLine(QPointF(plot.left(), y(t)), QPointF(plot.right(), y(t)))
            painter.setPen(QColor(C.SUBTEXT))
            painter.drawText(QRectF(plot.right() + 4, y(t) - 8, _AXIS_W - 4, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"{t:,.2f}")
        step = plot.width() / len(self.bars)
        self._candles(painter, plot, step, y)
        painter.save()
        self._markers(painter, plot, step, y)
        painter.restore()
        self._times(painter, plot, step)
        painter.end()

    def _candles(self, painter: QPainter, plot: QRectF, step: float, y: _Scale) -> None:
        body = max(step * 0.6, 1.0)
        spans = self._spans()
        cols = [self.bars[c].astype(float).tolist() for c in ("open", "high", "low", "close")]
        for i, (o, h, lo, c) in enumerate(zip(*cols, strict=True)):
            colour = QColor(C.GREEN if c >= o else C.RED)
            if spans and not any(a <= i <= b for a, b in spans):
                colour.setAlphaF(_DIM)
            x = plot.left() + (i + 0.5) * step
            painter.setPen(QPen(colour, 1))
            painter.drawLine(QPointF(x, y(h)), QPointF(x, y(lo)))
            top, bottom = y(max(o, c)), y(min(o, c))
            painter.fillRect(QRectF(x - body / 2, top, body, max(bottom - top, 1.0)), colour)

    def _index(self, ts: object) -> int | None:
        times = pd.DatetimeIndex(pd.to_datetime(self.bars["ts"], utc=True))
        stamp = pd.Timestamp(str(ts))
        if pd.isna(stamp):
            return None
        pos = int(times.searchsorted(stamp, side="right")) - 1
        if pos < 0 or stamp > times[-1] + _bar_gap(times):
            return None
        return pos

    def _spans(self) -> list[tuple[int, int]]:
        """Bar index ranges each trade was held; open ends run to the chart edge."""
        spans = []
        for entry_ts, exit_ts in zip(self.trades["entry_ts"], self.trades["exit_ts"],
                                     strict=True):
            entry, exit_ = self._index(entry_ts), self._index(exit_ts)
            if entry is not None or exit_ is not None:
                spans.append((entry or 0, len(self.bars) - 1 if exit_ is None else exit_))
        return spans

    def _sessions(self, entry: int, exit_: int) -> int:
        times = pd.DatetimeIndex(pd.to_datetime(self.bars["ts"], utc=True))
        return len(set(times[entry:exit_ + 1].tz_convert(_ET).date)) - 1

    def _markers(self, painter: QPainter, plot: QRectF, step: float, y: _Scale) -> None:
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        for row in self.trades.to_dict("records"):
            entry, exit_ = self._index(row["entry_ts"]), self._index(row["exit_ts"])
            entry_px, exit_px = float(row["entry_px"]), float(row["exit_px"])
            pe = None if entry is None else QPointF(plot.left() + (entry + 0.5) * step,
                                                   y(entry_px))
            px = None if exit_ is None else QPointF(plot.left() + (exit_ + 0.5) * step,
                                                   y(exit_px))
            sign = -1 if str(row["direction"]).upper() == "SHORT" else 1
            win = sign * (exit_px - entry_px) >= 0
            if pe is not None and px is not None and entry is not None and exit_ is not None:
                path = QPen(QColor(C.GREEN if win else C.RED), 1.6, Qt.PenStyle.DotLine)
                painter.setPen(path)
                painter.drawLine(pe, px)
                badge = trade_badge(str(row["direction"]), entry_px, exit_px,
                                    row.get("net_pnl"), self._sessions(entry, exit_))
                spot = QPointF((pe.x() + px.x()) / 2,
                               max(min(pe.y(), px.y()) - _BADGE_RISE, plot.top() + 10))
                _pill(painter, spot, badge, QColor(C.PNL_POS_BG if win else C.PNL_NEG_BG),
                      QColor(C.GREEN if win else C.RED))
            for point, text, colour in ((pe, f"IN {entry_px:,.2f}", QColor(C.TEAL)),
                                        (px, f"OUT {exit_px:,.2f}", QColor(C.YELLOW))):
                if point is not None:
                    _callout(painter, plot, point, text, colour)
                    _ring(painter, point, colour)

    def _times(self, painter: QPainter, plot: QRectF, step: float) -> None:
        labels = time_labels(pd.DatetimeIndex(pd.to_datetime(self.bars["ts"], utc=True)))
        width = 84.0 if len(labels[0]) > 6 else 60.0
        painter.setPen(QColor(C.SUBTEXT))
        every = max(1, int((width + 10) / max(step, 1.0)))
        for i in range(0, len(labels), every):
            x = plot.left() + (i + 0.5) * step
            painter.drawText(QRectF(max(x - width / 2, 0.0), plot.bottom() + 2, width, _AXIS_H),
                             Qt.AlignmentFlag.AlignCenter, labels[i])


def _bar_gap(times: pd.DatetimeIndex) -> pd.Timedelta:
    return times[-1] - times[-2] if len(times) > 1 else pd.Timedelta(days=1)


def time_labels(times: pd.DatetimeIndex) -> list[str]:
    """Axis labels: dates for daily bars, times for one session, date + time otherwise."""
    if len(times) > 1 and (times[1:] - times[:-1]).min() >= pd.Timedelta(days=1):
        return list(times.strftime("%b %d"))
    local = times.tz_convert(_ET)
    fmt = "%H:%M" if len(set(local.date)) == 1 else "%m-%d %H:%M"
    return list(local.strftime(fmt))


def trade_badge(direction: str, entry_px: float, exit_px: float, net_pnl: object,
                sessions: int) -> str:
    """Result text such as ``+$18.94 · +1.06% · 15 sessions``."""
    sign = -1 if direction.upper() == "SHORT" else 1
    parts = [] if net_pnl is None or pd.isna(net_pnl) else [  # type: ignore[call-overload]
        f"{'+' if float(net_pnl) >= 0 else '-'}${abs(float(net_pnl)):,.2f}"]  # type: ignore[arg-type]
    parts.append(f"{sign * (exit_px - entry_px) / entry_px * 100:+.2f}%")
    parts.append("same day" if sessions == 0 else
                 f"{sessions} session{'s' if sessions != 1 else ''}")
    return " · ".join(parts)


def _pill(painter: QPainter, centre: QPointF, text: str, fill: QColor, fg: QColor) -> None:
    metrics = painter.fontMetrics()
    w, h = metrics.horizontalAdvance(text) + 12.0, metrics.height() + 4.0
    rect = QRectF(centre.x() - w / 2, centre.y() - h / 2, w, h)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(fill)
    painter.drawRoundedRect(rect, 3, 3)
    painter.setPen(fg)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


def _callout(painter: QPainter, plot: QRectF, point: QPointF, text: str,
             colour: QColor) -> None:
    """Leader line from the dot to an IN / OUT price pill, below unless near the bottom."""
    down = point.y() + _LEADER + 20 < plot.bottom()
    end = QPointF(point.x(), point.y() + (_LEADER if down else -_LEADER))
    painter.setPen(QPen(QColor(C.MUTED), 1))
    painter.drawLine(point, end)
    _pill(painter, QPointF(end.x(), end.y() + (10 if down else -10)), text, colour,
          QColor(C.BG))


def _ring(painter: QPainter, point: QPointF, colour: QColor) -> None:
    painter.setPen(QPen(colour, 2.5))
    painter.setBrush(QColor(C.BG))
    painter.drawEllipse(point, _RING, _RING)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(colour)
    painter.drawEllipse(point, 2.5, 2.5)
