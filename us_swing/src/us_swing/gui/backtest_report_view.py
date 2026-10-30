"""
Module: MD-GUI-031.040.M04 — Backtest Report tab
Parent SRD: SRD-GUI-031.040, SRD-GUI-031.041, SRD-GUI-031.042, SRD-GUI-031.043,
            SRD-GUI-031.044, SRD-GUI-031.045

Step 4 view: KPI row, equity vs benchmark chart with drawdown, all stats, monthly
P&L heat map, breakdown by group, variant picker with compare table, CSV export.
Shows ``Report`` objects built by ``BacktestService.build_reports``.
"""
from __future__ import annotations

import logging
import math
import re
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.backtest.steps.report import (
    GROUPS,
    Report,
    Stat,
    breakdown,
    compare,
    heat_map,
)
from us_swing.gui.icons import set_icon
from us_swing.gui.strategy_pnl_chart import nice_ticks
from us_swing.gui.theme import C

_log = logging.getLogger(__name__)

KPIS = ("Net P&L", "Return", "Max drawdown", "Win rate", "Profit factor", "Trades")
_SIGNED = ("Net P&L", "Return")
_GROUP_NAMES = {"strategy": "Strategy", "symbol": "Stock", "sector": "Sector",
                "exit_reason": "Exit reason", "hour": "Entry hour", "weekday": "Weekday",
                "hold": "Hold time", "score_bucket": "Score bucket", "rank": "Rank"}
RISK_STATS = ("Average MAE", "Average MFE", "Profit given back", "Median hold",
              "Longest hold", "Monte Carlo drawdown, bad 5%", "Monte Carlo drawdown, median",
              "Monte Carlo drawdown, good 5%", "First half P&L", "Second half P&L",
              "P&L without top 5 trades")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_AXIS_W = 70
_AXIS_H = 20
_DD_SHARE = 0.3


def fmt(value: float, kind: str) -> str:
    """Show a stat value: $ with sign, %, ratio, count or days; NaN as a dash."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if kind == "usd":
        return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"
    if kind == "pct":
        return f"{value:.1%}"
    if kind == "ratio":
        return f"{value:.2f}"
    if kind == "days":
        return f"{value:.0f} days"
    if kind == "hours":
        return f"{value:.1f} h"
    return f"{value:,.0f}"


def _head(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("view_head")
    return label


def _table(headers: Sequence[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
    table.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    return table


def _fill(table: QTableWidget, rows: Sequence[Sequence[str]]) -> None:
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(value))
    table.resizeColumnsToContents()


def _pnl_brush(value: float, scale: float) -> QBrush:
    colour = QColor(C.GREEN if value > 0 else C.RED)
    colour.setAlphaF(0.15 + 0.55 * min(1.0, abs(value) / scale) if scale else 0.15)
    return QBrush(colour)


class ReportChart(QWidget):
    """Equity and benchmark lines, with the drawdown area below (SRD-GUI-031.041)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.daily = pd.DataFrame(columns=["date", "equity", "drawdown", "benchmark"])
        self.setMinimumHeight(260)

    def set_daily(self, daily: pd.DataFrame) -> None:
        self.daily = daily
        self.update()

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if len(self.daily) < 2:
            painter.setPen(QColor(C.MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Run a backtest to see the equity curve")
            painter.end()
            return
        width = self.width() - _AXIS_W - 8
        top_h = (self.height() - _AXIS_H - 20) * (1 - _DD_SHARE)
        equity = QRectF(4, 8, width, top_h)
        dd = QRectF(4, equity.bottom() + 24, width, self.height() - equity.bottom() - _AXIS_H - 24)
        bench = self.daily["benchmark"].astype(float)
        values = [*self.daily["equity"].astype(float), *bench.dropna()]
        ticks = nice_ticks(min(values), max(values))
        self._line_panel(painter, equity, ticks)
        self._drawdown_panel(painter, dd)
        self._dates(painter, dd)
        painter.end()

    def _x(self, plot: QRectF) -> Callable[[int], float]:
        span = max(len(self.daily) - 1, 1)
        return lambda i: plot.left() + i / span * plot.width()

    def _line_panel(self, painter: QPainter, plot: QRectF, ticks: list[float]) -> None:
        lo, hi = ticks[0], ticks[-1]

        def y(v: float) -> float:
            return plot.bottom() - (v - lo) / ((hi - lo) or 1.0) * plot.height()

        for t in ticks:
            painter.setPen(QPen(QColor(C.OVERLAY), 1))
            painter.drawLine(QPointF(plot.left(), y(t)), QPointF(plot.right(), y(t)))
            painter.setPen(QColor(C.SUBTEXT))
            painter.drawText(QRectF(plot.right() + 4, y(t) - 8, _AXIS_W - 4, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"${t:,.0f}")
        x = self._x(plot)
        for column, colour, style in (("benchmark", C.MUTED, Qt.PenStyle.DashLine),
                                      ("equity", C.BLUE, Qt.PenStyle.SolidLine)):
            path: QPainterPath | None = None
            for i, v in enumerate(self.daily[column].astype(float)):
                if math.isnan(v):
                    continue
                point = QPointF(x(i), y(v))
                if path is None:
                    path = QPainterPath(point)
                else:
                    path.lineTo(point)
            if path is not None:
                painter.setPen(QPen(QColor(colour), 1.8, style))
                painter.drawPath(path)
        painter.setPen(QColor(C.BLUE))
        painter.drawText(QRectF(plot.left() + 6, plot.top(), 200, 16), "— Strategy")
        painter.setPen(QColor(C.MUTED))
        painter.drawText(QRectF(plot.left() + 90, plot.top(), 260, 16),
                         "- - S&P 500 (equal weight)")

    def _drawdown_panel(self, painter: QPainter, plot: QRectF) -> None:
        dd = self.daily["drawdown"].astype(float)
        low = min(float(dd.min()), -0.0001)
        x = self._x(plot)

        def y(v: float) -> float:
            return plot.top() + v / low * plot.height()

        area = QPainterPath(QPointF(x(0), y(0)))
        for i, v in enumerate(dd):
            area.lineTo(QPointF(x(i), y(v)))
        area.lineTo(QPointF(x(len(dd) - 1), y(0)))
        area.closeSubpath()
        fill = QColor(C.RED)
        fill.setAlphaF(0.35)
        painter.fillPath(area, fill)
        painter.setPen(QPen(QColor(C.OVERLAY), 1))
        painter.drawLine(QPointF(plot.left(), plot.top()), QPointF(plot.right(), plot.top()))
        painter.setPen(QColor(C.SUBTEXT))
        painter.drawText(QRectF(plot.right() + 4, plot.top() - 2, _AXIS_W - 4, 16),
                         Qt.AlignmentFlag.AlignRight, "0%")
        painter.drawText(QRectF(plot.right() + 4, plot.bottom() - 14, _AXIS_W - 4, 16),
                         Qt.AlignmentFlag.AlignRight, f"{low:.1%}")
        painter.drawText(QRectF(plot.left() + 6, plot.top() + 2, 200, 16), "Drawdown")

    def _dates(self, painter: QPainter, plot: QRectF) -> None:
        x = self._x(plot)
        last = len(self.daily) - 1
        painter.setPen(QColor(C.SUBTEXT))
        for i in sorted({0, last // 2, last}):
            left = min(max(x(i) - 40, 0.0), plot.right() - 80)
            painter.drawText(QRectF(left, plot.bottom() + 4, 80, _AXIS_H - 4),
                             Qt.AlignmentFlag.AlignCenter, str(self.daily["date"].iloc[i]))


class ReportView(QWidget):
    """SRD-GUI-031.040–.045 — the Report tab of the Backtest screen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reports: list[Report] = []
        body = QVBoxLayout(self)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(10)

        top = QHBoxLayout()
        self.head = _head("REPORT")
        self.variant = QComboBox()
        self.variant.setFixedWidth(300)
        self.variant.currentIndexChanged.connect(self._render)
        self.export_btn = QPushButton("Export CSV")
        set_icon(self.export_btn, "download")
        self.export_btn.clicked.connect(self._on_export)
        self.export_btn.setEnabled(False)
        top.addWidget(self.head, 1)
        top.addWidget(self.variant)
        top.addWidget(self.export_btn)
        body.addLayout(top)

        kpis = QHBoxLayout()
        kpis.setSpacing(8)
        self.kpi_values: dict[str, QLabel] = {}
        for name in KPIS:
            kpis.addWidget(self._kpi(name), 1)
        body.addLayout(kpis)
        self.skips_label = QLabel("")
        self.skips_label.setObjectName("details_key")
        body.addWidget(self.skips_label)

        self.chart = ReportChart()
        body.addWidget(self.chart, 2)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        self.stats_table = _table(["Measure", "Value"])
        self.month_table = _table(["Year", *_MONTHS, "Year total"])
        self.group_pick = QComboBox()
        for key in GROUPS:
            self.group_pick.addItem(_GROUP_NAMES[key], key)
        self.group_pick.setFixedWidth(160)
        self.group_pick.currentIndexChanged.connect(self._render_breakdown)
        self.group_table = _table(["Group", "Trades", "Net P&L", "Win rate", "Avg P&L"])
        group_head = QHBoxLayout()
        group_head.addWidget(_head("BREAKDOWN · GROUP BY"))
        group_head.addWidget(self.group_pick)
        group_head.addStretch()
        grid.addWidget(_head("ALL STATS"), 0, 0)
        grid.addWidget(self.stats_table, 1, 0, 3, 1)
        grid.addWidget(_head("MONTHLY P&L"), 0, 1)
        grid.addWidget(self.month_table, 1, 1)
        grid.addLayout(group_head, 2, 1)
        grid.addWidget(self.group_table, 3, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 3)
        body.addLayout(grid, 3)

        self.compare_head = _head("COMPARE VARIANTS")
        self.compare_table = _table(["Variant"])
        body.addWidget(self.compare_head)
        body.addWidget(self.compare_table, 1)
        self.heat_head = _head("RETURN BY CAPITAL × PER-TRADE %")
        self.heat_table = _table(["Capital"])
        body.addWidget(self.heat_head)
        body.addWidget(self.heat_table, 1)
        self.set_reports([])

    def _kpi(self, name: str) -> QFrame:
        box = QFrame()
        box.setObjectName("stat_card")
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        content.setObjectName("stat_card_inner")
        outer.addWidget(content)
        inner = QVBoxLayout(content)
        inner.setContentsMargins(4, 2, 4, 2)
        inner.setSpacing(2)
        key = QLabel(name.upper())
        key.setObjectName("view_head")
        value = QLabel("—")
        value.setObjectName("card_symbol")
        inner.addWidget(key)
        inner.addWidget(value)
        self.kpi_values[name] = value
        return box

    def set_reports(self, reports: Sequence[Report]) -> None:
        """Show a run's reports; the first variant is selected (SRD-GUI-031.044)."""
        self.reports = list(reports)
        self.variant.blockSignals(True)
        self.variant.clear()
        self.variant.addItems([r.label for r in self.reports])
        self.variant.blockSignals(False)
        self.variant.setVisible(len(self.reports) > 1)
        self.export_btn.setEnabled(bool(self.reports))
        many = len(self.reports) > 1
        self.compare_head.setVisible(many)
        self.compare_table.setVisible(many)
        grid = heat_map(self.reports) if many else pd.DataFrame()
        self.heat_head.setVisible(not grid.empty)
        self.heat_table.setVisible(not grid.empty)
        if many:
            self._render_compare()
        if not grid.empty:
            self._render_heat(grid)
        self._render()

    def current(self) -> Report | None:
        i = self.variant.currentIndex()
        return self.reports[i] if 0 <= i < len(self.reports) else None

    def _render(self) -> None:
        rep = self.current()
        self.head.setText("REPORT" if rep is None else f"REPORT · {rep.label}")
        for name, label in self.kpi_values.items():
            stat = None if rep is None else next(s for s in rep.stats if s.name == name)
            label.setText("—" if stat is None else fmt(stat.value, stat.kind))
            colour = C.TEXT
            if stat is not None and stat.name in _SIGNED and not math.isnan(stat.value):
                colour = C.GREEN if stat.value > 0 else C.RED if stat.value < 0 else C.TEXT
            label.setStyleSheet(f"color: {colour};")
        if rep is None:
            self.skips_label.setText("")
            self.chart.set_daily(self.chart.daily.iloc[0:0])
            _fill(self.stats_table, [])
            _fill(self.month_table, [])
            _fill(self.group_table, [])
            return
        self.skips_label.setText(skips_text(rep.skips))
        self.chart.set_daily(rep.daily)
        _fill(self.stats_table, [[s.name, fmt(s.value, s.kind)] for s in rep.stats])
        self._render_months(rep)
        self._render_breakdown()

    def _render_months(self, rep: Report) -> None:
        """Year × month heat map, green gains and red losses (SRD-GUI-031.042)."""
        table = rep.monthly.pivot_table(index="year", columns="month", values="pnl",
                                        aggfunc="sum")
        scale = float(rep.monthly["pnl"].abs().max()) if not rep.monthly.empty else 0.0
        self.month_table.setRowCount(len(table))
        for r, (year, row) in enumerate(table.iterrows()):
            self.month_table.setItem(r, 0, QTableWidgetItem(str(year)))
            for m in range(1, 13):
                value = row.get(m)
                item = QTableWidgetItem("" if value is None or pd.isna(value)
                                        else f"{value:,.0f}")
                if value is not None and not pd.isna(value) and value != 0:
                    item.setBackground(_pnl_brush(float(value), scale))
                self.month_table.setItem(r, m, item)
            total = float(row.sum())
            self.month_table.setItem(r, 13, QTableWidgetItem(f"{total:,.0f}"))
        self.month_table.resizeColumnsToContents()

    def _render_breakdown(self) -> None:
        """Breakdown of the selected variant by the picked group (SRD-GUI-031.043)."""
        rep = self.current()
        if rep is None:
            return
        frame = breakdown(rep.trades, str(self.group_pick.currentData()))
        _fill(self.group_table, [
            [str(g), str(int(n)), fmt(p, "usd"), fmt(w, "pct"), fmt(a, "usd")]
            for g, n, p, w, a in frame.itertuples(index=False)
        ])

    def _render_compare(self) -> None:
        table = compare(self.reports)
        kinds = {s.name: s.kind for s in self.reports[0].stats}
        headers = ["Variant", *table.columns[1:]]
        self.compare_table.setColumnCount(len(headers))
        self.compare_table.setHorizontalHeaderLabels(headers)
        _fill(self.compare_table, [
            [str(row["variant"]), *[fmt(float(row[c]), kinds[c]) for c in headers[1:]]]
            for _, row in table.iterrows()
        ])

    def _render_heat(self, grid: pd.DataFrame) -> None:
        """Return per capital (rows) and per-trade % (columns) (SRD-GUI-031.048)."""
        headers = ["Capital", *[f"{c:g}% per trade" for c in grid.columns]]
        values = grid.to_numpy(dtype=float)
        self.heat_table.setColumnCount(len(headers))
        self.heat_table.setHorizontalHeaderLabels(headers)
        _fill(self.heat_table, [[fmt(cap, "usd"), *[fmt(v, "pct") for v in row]]
                                for cap, row in zip(grid.index.astype(float), values,
                                                    strict=True)])
        scale = float(np.nanmax(np.abs(values))) or 1.0
        for r, row in enumerate(values):
            for c, value in enumerate(row, start=1):
                item = self.heat_table.item(r, c)
                if item is not None and not math.isnan(value):
                    item.setBackground(_pnl_brush(value, scale))

    def _on_export(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Export report")
        if not folder:
            return
        try:
            self.export_to(Path(folder))
        except OSError as exc:
            _log.warning("[Backtest] Could not save the report: %s", exc.strerror or exc)

    def export_to(self, folder: Path) -> list[Path]:
        """Write the selected variant's stats and trades as CSV (SRD-GUI-031.045)."""
        rep = self.current()
        if rep is None:
            return []
        stem = re.sub(r"[^A-Za-z0-9]+", "_", rep.label).strip("_") or "report"
        stats_path, trades_path = folder / f"{stem}_stats.csv", folder / f"{stem}_trades.csv"
        stats_rows: list[Stat] = list(rep.stats)
        pd.DataFrame([(s.name, s.value) for s in stats_rows],
                     columns=["measure", "value"]).to_csv(stats_path, index=False)
        rep.trades.to_csv(trades_path, index=False)
        _log.info("[Backtest] Report saved to %s", folder)
        return [stats_path, trades_path]


def skips_text(skips: pd.DataFrame) -> str:
    """"Entries taken 4 · skipped: no_margin 2" from the skip counts (SRD-BKT-002.045)."""
    counts = dict(zip(skips["decision"], skips["count"]))
    taken = int(counts.pop("entered", 0))
    rest = " · ".join(f"{k.replace('_', ' ')} {int(v)}" for k, v in counts.items())
    return f"Entries taken {taken}" + (f" · skipped: {rest}" if rest else "")


class RiskFacts(QWidget):
    """SRD-GUI-031.046 — MAE, MFE, profit given back, hold time and robustness."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setVerticalSpacing(4)
        self.values: dict[str, QLabel] = {}
        for row, name in enumerate(RISK_STATS):
            key = QLabel(name)
            key.setObjectName("details_key")
            value = QLabel("—")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(key, row, 0)
            grid.addWidget(value, row, 1)
            self.values[name] = value
        grid.setRowStretch(len(RISK_STATS), 1)

    def set_report(self, rep: Report | None) -> None:
        """Show the variant's values, or dashes."""
        stats = {} if rep is None else {s.name: s for s in rep.stats}
        for name, label in self.values.items():
            stat = stats.get(name)
            label.setText("—" if stat is None else fmt(stat.value, stat.kind))
