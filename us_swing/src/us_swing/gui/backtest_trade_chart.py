"""
Module: MD-GUI-031.052.M06 — Backtest trade chart
Parent SRD: SRD-GUI-031.052

Candles of one stock for one session, with entry (▲/▼) and exit (✕) markers.
"""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from us_swing.gui.strategy_pnl_chart import nice_ticks
from us_swing.gui.theme import C

_AXIS_W = 56
_AXIS_H = 18
_ET = "America/New_York"
_Scale = Callable[[float], float]


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
        self._markers(painter, plot, step, y)
        self._times(painter, plot, step)
        painter.end()

    def _candles(self, painter: QPainter, plot: QRectF, step: float, y: _Scale) -> None:
        body = max(step * 0.6, 1.0)
        cols = [self.bars[c].astype(float).tolist() for c in ("open", "high", "low", "close")]
        for i, (o, h, lo, c) in enumerate(zip(*cols, strict=True)):
            colour = QColor(C.GREEN if c >= o else C.RED)
            x = plot.left() + (i + 0.5) * step
            painter.setPen(QPen(colour, 1))
            painter.drawLine(QPointF(x, y(h)), QPointF(x, y(lo)))
            top, bottom = y(max(o, c)), y(min(o, c))
            painter.fillRect(QRectF(x - body / 2, top, body, max(bottom - top, 1.0)), colour)

    def _index(self, ts: object) -> int | None:
        times = pd.DatetimeIndex(pd.to_datetime(self.bars["ts"], utc=True))
        pos = int(times.searchsorted(pd.Timestamp(str(ts)), side="right")) - 1
        return pos if 0 <= pos < len(times) else None

    def _markers(self, painter: QPainter, plot: QRectF, step: float, y: _Scale) -> None:
        t = self.trades
        for side, entry_ts, entry_px, exit_ts, exit_px in zip(
                t["direction"], t["entry_ts"], t["entry_px"].astype(float).tolist(),
                t["exit_ts"], t["exit_px"].astype(float).tolist(), strict=True):
            long = str(side).upper() == "LONG"
            entry, exit_ = self._index(entry_ts), self._index(exit_ts)
            if entry is not None:
                x, py = plot.left() + (entry + 0.5) * step, y(entry_px)
                tip = 7 if long else -7
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(C.BLUE))
                painter.drawPolygon(QPolygonF([QPointF(x, py), QPointF(x - 6, py + tip * 2),
                                               QPointF(x + 6, py + tip * 2)]))
            if exit_ is not None:
                x, py = plot.left() + (exit_ + 0.5) * step, y(exit_px)
                painter.setPen(QPen(QColor(C.TEAL), 2))
                painter.drawLine(QPointF(x - 5, py - 5), QPointF(x + 5, py + 5))
                painter.drawLine(QPointF(x - 5, py + 5), QPointF(x + 5, py - 5))

    def _times(self, painter: QPainter, plot: QRectF, step: float) -> None:
        times = pd.DatetimeIndex(pd.to_datetime(self.bars["ts"], utc=True)).tz_convert(_ET)
        painter.setPen(QColor(C.SUBTEXT))
        every = max(1, int(70 / max(step, 1.0)))
        for i in range(0, len(times), every):
            x = plot.left() + (i + 0.5) * step
            painter.drawText(QRectF(max(x - 30, 0.0), plot.bottom() + 2, 60, _AXIS_H),
                             Qt.AlignmentFlag.AlignCenter, times[i].strftime("%H:%M"))
