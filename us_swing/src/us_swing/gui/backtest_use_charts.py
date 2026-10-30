"""
Module: MD-GUI-031.054.M08 — Backtest screener and margin use
Parent SRD: SRD-GUI-031.054

Stacked daily bars with a facts line: picks per session (traded part first) and
money per day (deployed peak, then lowest margin left).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from us_swing.gui.strategy_pnl_chart import nice_ticks
from us_swing.gui.theme import C

_AXIS_W = 56
_ET = "America/New_York"


@dataclass(frozen=True)
class Use:
    """Daily stacked values: ``low`` drawn first, ``high`` on top, plus a facts line."""

    days: list[str]
    low: list[float]
    high: list[float]
    facts: str


def screener_use(days: list[date], picks: pd.DataFrame, trades: pd.DataFrame) -> Use:
    """Picks per session split into traded and not traded; every session gets a bar."""
    days = sorted(days)
    entry_days = pd.DatetimeIndex(pd.to_datetime(trades["entry_ts"], utc=True)).tz_convert(_ET)
    traded_keys = set(zip(entry_days.date, trades["symbol"], strict=True))
    is_traded = [(d, s) in traded_keys for d, s in zip(picks["date"], picks["symbol"],
                                                        strict=True)]
    marked = picks.assign(traded=is_traded)
    per_day = marked.groupby("date")["traded"].agg(["sum", "size"])
    traded = [float(per_day.loc[d, "sum"]) if d in per_day.index else 0.0 for d in days]
    total = [float(per_day.loc[d, "size"]) if d in per_day.index else 0.0 for d in days]
    with_picks = sum(1 for t in total if t)
    n_picks, n_traded = int(sum(total)), int(sum(traded))
    facts = (f"{len(days)} sessions · {with_picks} with picks · "
             f"{(n_picks / len(days) if days else 0):.1f} picks a day · "
             f"{n_traded} of {n_picks} picks traded")
    return Use([str(d) for d in days], traded, [t - x for t, x in zip(total, traded,
                                                                         strict=True)], facts)


def margin_use(money: pd.DataFrame) -> Use:
    """Deployed peak (start capital minus lowest margin) and lowest margin left per day."""
    money = money.sort_values("date")
    margin = money["margin_min"].clip(lower=0).astype(float)
    deployed = (money["start_capital"].astype(float) - margin).clip(lower=0).tolist()
    margin = margin.tolist()
    used = [d for d in deployed if d > 0]
    facts = (f"Money deployed on {len(used)} of {len(deployed)} days · average deployed peak "
             f"${(sum(used) / len(used) if used else 0):,.0f} · lowest margin "
             f"${(min(margin) if margin else 0):,.0f}")
    return Use([str(d) for d in money["date"]], deployed, margin, facts)


class StackedBars(QWidget):
    """One stacked bar per day: ``low`` in the first colour, ``high`` on top."""

    def __init__(self, colours: tuple[str, str], legend: tuple[str, str], money: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colours, self._legend, self._money = colours, legend, money
        self.use = Use([], [], [], "")
        self.setMinimumHeight(160)

    def set_use(self, use: Use) -> None:
        self.use = use
        self.update()

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        painter = QPainter(self)
        u = self.use
        if not u.days:
            painter.setPen(QColor(C.MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Run a backtest first")
            painter.end()
            return
        plot = QRectF(4, 22, self.width() - _AXIS_W - 8, self.height() - 44)
        tops = [lo + hi for lo, hi in zip(u.low, u.high, strict=True)]
        ticks = nice_ticks(0.0, max(max(tops), 1.0))
        top = ticks[-1]
        for t in ticks:
            y = plot.bottom() - t / top * plot.height()
            painter.setPen(QPen(QColor(C.OVERLAY), 1))
            painter.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            painter.setPen(QColor(C.SUBTEXT))
            painter.drawText(QRectF(plot.right() + 4, y - 8, _AXIS_W - 4, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"${t:,.0f}" if self._money else f"{t:,.0f}")
        step = plot.width() / len(u.days)
        width = max(step * 0.8, 1.0)
        for i, (lo, hi) in enumerate(zip(u.low, u.high, strict=True)):
            x = plot.left() + i * step + (step - width) / 2
            low_h = lo / top * plot.height()
            painter.fillRect(QRectF(x, plot.bottom() - low_h, width, low_h),
                             QColor(self._colours[0]))
            high_h = hi / top * plot.height()
            painter.fillRect(QRectF(x, plot.bottom() - low_h - high_h, width, high_h),
                             QColor(self._colours[1]))
        x = plot.left()
        for name, colour in zip(self._legend, self._colours, strict=True):
            painter.fillRect(QRectF(x, 6, 10, 10), QColor(colour))
            painter.setPen(QColor(C.SUBTEXT))
            painter.drawText(QRectF(x + 14, 2, 180, 18), Qt.AlignmentFlag.AlignVCenter, name)
            x += 190
        painter.setPen(QColor(C.SUBTEXT))
        painter.drawText(QRectF(plot.left(), plot.bottom() + 2, 120, 18),
                         Qt.AlignmentFlag.AlignLeft, u.days[0])
        painter.drawText(QRectF(plot.right() - 120, plot.bottom() + 2, 120, 18),
                         Qt.AlignmentFlag.AlignRight, u.days[-1])
        painter.end()


class UsePanel(QWidget):
    """A facts line above a stacked bar chart."""

    def __init__(self, colours: tuple[str, str], legend: tuple[str, str], money: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        self.facts = QLabel("")
        self.facts.setObjectName("details_key")
        self.facts.setWordWrap(True)
        self.chart = StackedBars(colours, legend, money)
        body.addWidget(self.facts)
        body.addWidget(self.chart, 1)

    def set_use(self, use: Use) -> None:
        self.facts.setText(use.facts)
        self.chart.set_use(use)
