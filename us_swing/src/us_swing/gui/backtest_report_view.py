"""
Module: MD-GUI-031.040.M04 — Backtest Report tab
Parent SRD: SRD-GUI-031.040, SRD-GUI-031.041, SRD-GUI-031.042, SRD-GUI-031.044,
            SRD-GUI-031.045

Step 4 view: KPI row, equity vs benchmark chart with drawdown, all stats, monthly
P&L heat map, variant picker with compare table, CSV export.
Shows ``Report`` objects built by ``BacktestService.build_reports``.
"""
from __future__ import annotations

import logging
import math
import re
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.backtest.steps.report import Report, Stat, compare, heat_map
from us_swing.gui.backtest_report_chart import ReportChart
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C

_log = logging.getLogger(__name__)

KPIS = ("Net P&L", "Return", "Max drawdown", "Win rate", "Profit factor", "Sharpe")
STAT_GROUPS = (
    ("Returns", ("Net P&L", "Return", "CAGR", "Time invested", "First half P&L",
                 "Second half P&L")),
    ("Risk", ("Max drawdown", "Max drawdown $", "Longest drawdown", "Sharpe", "Sortino", "Calmar",
              "Worst day", "Worst trade")),
    ("Trades", ("Trades", "Win rate", "Average win", "Average loss", "Payoff", "Profit factor",
                "Expectancy", "Longest win streak", "Longest loss streak")),
    ("Exits and robustness", ("Average MAE", "Average MFE", "Profit given back", "Median hold",
                              "Longest hold", "Monte Carlo drawdown, bad 5%",
                              "Monte Carlo drawdown, median", "Monte Carlo drawdown, good 5%",
                              "P&L without top 5 trades")),
)
_NEUTRAL = frozenset({"Average MAE", "Average MFE", "Profit given back", "Win rate",
                      "Time invested"})
_DECISIONS = {"entered": "Entries", "no_margin": "No margin", "rex_limit": "Rex limit",
              "already_held": "Already held", "strategy_limit": "Strategy limit"}
RISK_STATS = ("Average MAE", "Average MFE", "Profit given back", "Median hold",
              "Longest hold", "Monte Carlo drawdown, bad 5%", "Monte Carlo drawdown, median",
              "Monte Carlo drawdown, good 5%", "First half P&L", "Second half P&L",
              "P&L without top 5 trades")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


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


class ReportView(QWidget):
    """SRD-GUI-031.040–.045 — the Report tab of the Backtest screen."""

    report_changed = pyqtSignal(object)  # selected Report, or None (feeds the Breakdown panel)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reports: list[Report] = []
        body = QVBoxLayout(self)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.head = QLabel("Report")
        self.head.setObjectName("page_title")
        self.context = QLabel("")
        self.context.setObjectName("details_key")
        self.variant = QComboBox()
        self.variant.setFixedWidth(300)
        self.variant.currentIndexChanged.connect(self._render)
        self.export_btn = QPushButton("Export CSV")
        set_icon(self.export_btn, "download")
        self.export_btn.clicked.connect(self._on_export)
        self.export_btn.setEnabled(False)
        top.addWidget(self.head)
        top.addWidget(self.context, 1)
        top.addWidget(self.variant)
        top.addWidget(self.export_btn)
        body.addLayout(top)

        kpis = QHBoxLayout()
        kpis.setSpacing(8)
        self.kpi_values: dict[str, QLabel] = {}
        self.kpi_notes: dict[str, QLabel] = {}
        for name in KPIS:
            kpis.addWidget(self._kpi(name), 1)
        body.addLayout(kpis)
        self.signals = QHBoxLayout()
        self.signals.setSpacing(6)
        self.skips_label = QLabel("")
        self.skips_label.setObjectName("details_key")
        body.addLayout(self.signals)

        self.chart = ReportChart()
        body.addWidget(self.chart, 2)

        self.stat_values: dict[str, QLabel] = {}
        self.groups = QHBoxLayout()
        self.groups.setSpacing(10)
        body.addLayout(self.groups)
        self.month_table = _table(["Year", *_MONTHS, "Total"])
        month_head = self.month_table.horizontalHeader()
        if month_head is not None:
            month_head.setStretchLastSection(False)
            month_head.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        body.addWidget(_head("MONTHLY P&L"))
        body.addWidget(self.month_table)

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
        note = QLabel("")
        note.setObjectName("details_key")
        inner.addWidget(key)
        inner.addWidget(value)
        inner.addWidget(note)
        self.kpi_values[name] = value
        self.kpi_notes[name] = note
        return box

    def set_reports(self, reports: Sequence[Report], context: str = "") -> None:
        """Show a run's reports; the first variant is selected (SRD-GUI-031.044).

        ``context`` is the run's stocks and period, shown beside the title (SRD-GUI-031.079).
        """
        self.reports = list(reports)
        self.context.setText(context)
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
        self.head.setText("Report" if rep is None else rep.label)
        stats = {} if rep is None else {s.name: s for s in rep.stats}
        notes = {} if rep is None else kpi_notes(rep)
        for name, label in self.kpi_values.items():
            stat = stats.get(name)
            label.setText("—" if stat is None else fmt(stat.value, stat.kind))
            label.setStyleSheet(f"color: {_tone(stat) if stat is not None else C.TEXT};")
            self.kpi_notes[name].setText(notes.get(name, ""))
        self._render_signals(rep)
        self._render_groups(rep)
        if rep is None:
            self.chart.set_daily(self.chart.daily.iloc[0:0])
            _fill(self.month_table, [])
            self._fit_months()
            self.report_changed.emit(None)
            return
        self.chart.set_daily(rep.daily, rep.capital)
        self._render_months(rep)
        self.report_changed.emit(rep)

    def _render_signals(self, rep: Report | None) -> None:
        """Entries and skip reasons as pills, then "N of M entry signals were taken"."""
        _clear(self.signals)
        self.skips_label = QLabel("")
        if rep is None or rep.skips.empty:
            return
        counts = {str(k): int(v) for k, v in zip(rep.skips["decision"], rep.skips["count"],
                                                  strict=True)}
        self.signals.addWidget(_head("SIGNALS"))
        taken = counts.pop("entered", 0)
        for key, count in (("entered", taken), *counts.items()):
            name = _DECISIONS.get(key, key.replace("_", " ").capitalize())
            pill = QLabel(f"{name} <b>{count}</b>")
            pill.setObjectName("exec_chip")
            self.signals.addWidget(pill)
        total = taken + sum(counts.values())
        self.skips_label.setText(f"{taken} of {total} entry signals were taken")
        self.skips_label.setObjectName("details_key")
        self.signals.addWidget(self.skips_label)
        self.signals.addStretch(1)

    def _render_groups(self, rep: Report | None) -> None:
        """All stats in named group cards; no scroll box (SRD-GUI-031.079)."""
        _clear(self.groups)
        self.stat_values = {}
        if rep is None:
            return
        stats = {s.name: s for s in rep.stats}
        known = {n for _g, names in STAT_GROUPS for n in names}
        groups = [*STAT_GROUPS, ("Other", tuple(n for n in stats if n not in known))]
        for title, names in groups:
            present = [stats[n] for n in names if n in stats]
            if not present:
                continue
            card = QFrame()
            card.setObjectName("stat_card")
            card.setStyleSheet("QLabel { background: transparent; }")
            grid = QGridLayout(card)
            grid.setContentsMargins(12, 10, 12, 10)
            grid.setVerticalSpacing(4)
            grid.addWidget(_head(title.upper()), 0, 0, 1, 2)
            for row, stat in enumerate(present, start=1):
                key = QLabel(stat.name.replace("Monte Carlo", "MC"))
                key.setObjectName("details_key")
                value = QLabel(fmt(stat.value, stat.kind))
                value.setAlignment(Qt.AlignmentFlag.AlignRight)
                value.setStyleSheet(f"color: {_tone(stat)}; font-family: 'IBM Plex Mono';")
                grid.addWidget(key, row, 0)
                grid.addWidget(value, row, 1)
                self.stat_values[stat.name] = value
            grid.setRowStretch(len(present) + 1, 1)
            self.groups.addWidget(card, 1)

    def _fit_months(self) -> None:
        """Size the monthly table to its rows, so it has no empty space."""
        table = self.month_table
        head = table.horizontalHeader()
        rows = sum(table.rowHeight(r) for r in range(table.rowCount()))
        table.setFixedHeight((head.height() if head is not None else 24) + rows + 4)

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
                                        else _whole_usd(float(value)))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if value is not None and not pd.isna(value) and value != 0:
                    item.setBackground(_pnl_brush(float(value), scale))
                self.month_table.setItem(r, m, item)
            total = float(row.sum())
            total_item = QTableWidgetItem(_whole_usd(total))
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            total_item.setForeground(QColor(C.GREEN if total > 0 else C.RED))
            self.month_table.setItem(r, 13, total_item)
        self._fit_months()

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


def _clear(layout: QHBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.deleteLater()


def _whole_usd(value: float) -> str:
    return f"-${-value:,.0f}" if value < 0 else f"${value:,.0f}"


def _tone(stat: Stat) -> str:
    """Green / red only for money and return values; neutral for everything else."""
    if stat.name in _NEUTRAL or stat.kind not in ("usd", "pct") or math.isnan(stat.value):
        return str(C.TEXT)
    return str(C.GREEN if stat.value > 0 else C.RED if stat.value < 0 else C.TEXT)


def kpi_notes(rep: Report) -> dict[str, str]:
    """Second line of each KPI tile: the context that makes the number readable."""
    stats = {s.name: s.value for s in rep.stats}

    def get(name: str) -> float:
        return float(stats.get(name, math.nan))

    notes = {"Net P&L": f"ending equity {_whole_usd(rep.capital + get('Net P&L'))}",
             "Max drawdown": f"lasted {fmt(get('Longest drawdown'), 'days')}",
             "Win rate": f"{round(get('Win rate') * get('Trades')):.0f} of "
                         f"{get('Trades'):.0f} trades won",
             "Profit factor": f"payoff {fmt(get('Payoff'), 'ratio')} · avg win "
                              f"{fmt(get('Average win'), 'usd')}",
             "Sharpe": f"Sortino {fmt(get('Sortino'), 'ratio')} · Calmar "
                       f"{fmt(get('Calmar'), 'ratio')}"}
    bench = rep.daily["benchmark"].astype(float).dropna() if not rep.daily.empty else None
    if bench is not None and len(bench) and rep.capital:
        gap = (get("Return") - (float(bench.iloc[-1]) / rep.capital - 1)) * 100
        notes["Return"] = f"vs benchmark {gap:+.1f} pts"
    else:
        notes["Return"] = f"CAGR {fmt(get('CAGR'), 'pct')}"
    if math.isnan(get("Trades")) or math.isnan(get("Win rate")):
        notes["Win rate"] = ""
    return notes


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
