"""
Module: MD-GUI-031.002.M02 — Backtest builder
Parent SRD: SRD-GUI-031.002, SRD-GUI-031.010, SRD-GUI-031.020, SRD-GUI-031.030,
            SRD-GUI-031.060, SRD-GUI-031.072, SRD-GUI-031.073

Run plan fields, laid out as five setup pages (Run, Stocks, Screener, Strategies,
Account) of titled cards for the setup window. It only reads fields into a
``RunPlan``; estimating and running live in ``backtest.service``.
"""
from __future__ import annotations

import datetime
import re
from collections.abc import Mapping, Sequence
from typing import Any

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.backtest.spec import (
    AccountSpec,
    CostSpec,
    Period,
    RunPlan,
    ScreenerSpec,
    StrategySpec,
    UniverseSpec,
)
from us_swing.backtest.universe import UniverseRecord
from us_swing.core.backtest_bridge import PresetInfo
from us_swing.gui.screener_views import ChipGroup

SECTIONS = (("run", "Run"), ("stocks", "Stocks"), ("screener", "Screener"),
            ("strategies", "Strategies"), ("account", "Account"))
_MAX_TOP_N = 50
_LABEL_W = 160
_FIELD_W = 140
_MODE_TEXT = {"sp500": "S&P 500", "sector": "Sectors", "names": "Names"}


def _pydate(day: QDate) -> datetime.date:
    return datetime.date(day.year(), day.month(), day.day())


def _qdate(day: datetime.date) -> QDate:
    return QDate(day.year, day.month, day.day)


def _names(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(n.upper() for n in re.split(r"[\s,]+", text) if n))


def _key_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("details_key")
    return label


def card(title: str, help_text: str, rows: Sequence[tuple[str | None, QWidget]]) -> QFrame:
    """Titled card with one help line and label-left / control-right rows (SRD-GUI-031.072).

    A row whose label is ``None`` spans the whole card width.
    """
    frame = QFrame()
    frame.setObjectName("settings_card")
    body = QVBoxLayout(frame)
    body.setContentsMargins(12, 10, 12, 12)
    body.setSpacing(4)
    head = QLabel(title)
    head.setObjectName("data_summary")
    body.addWidget(head)
    if help_text:
        body.addWidget(_key_label(help_text))
    grid = QGridLayout()
    grid.setContentsMargins(0, 6, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(8)
    grid.setColumnMinimumWidth(0, _LABEL_W)
    grid.setColumnStretch(1, 1)
    for row, (label, field) in enumerate(rows):
        if label is None:
            grid.addWidget(field, row, 0, 1, 2)
            continue
        key = _key_label(label)
        key.setFixedWidth(_LABEL_W)
        grid.addWidget(key, row, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        grid.addWidget(field, row, 1, Qt.AlignmentFlag.AlignLeft)
        field.setProperty("row_label", key)
    body.addLayout(grid)
    return frame


def _page(*cards: QFrame) -> QWidget:
    page = QWidget()
    body = QVBoxLayout(page)
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(10)
    for c in cards:
        body.addWidget(c)
    body.addStretch()
    return page


def _show_row(field: QWidget, shown: bool) -> None:
    field.setVisible(shown)
    label = field.property("row_label")
    if isinstance(label, QLabel):
        label.setVisible(shown)


class BacktestBuilder(QWidget):
    """SRD-GUI-031.002 / .010 / .072 — run plan fields; ``changed`` fires on every edit.

    ``pages`` holds one page per section for the setup window.
    """

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = QLineEdit("Backtest")
        self._name.setFixedWidth(260)
        self._start = self._date_edit()
        self._end = self._date_edit()
        today = QDate.currentDate()
        self._end.setDate(today)
        self._start.setDate(today.addYears(-1))
        self._mode = ChipGroup([("S&&P 500", "sp500"), ("Sectors", "sector"), ("Names", "names")])
        self._mode.setFixedWidth(300)
        self._sectors = QListWidget()
        self._sectors.setObjectName("bt_sectors")
        self._sectors.setFixedSize(300, 220)
        self._names_edit = QLineEdit()
        self._names_edit.setPlaceholderText("AAPL, MSFT, NVDA")
        self._names_edit.setFixedWidth(300)
        self._add = QLineEdit()
        self._add.setPlaceholderText("e.g. SHOP, TSM")
        self._add.setFixedWidth(300)
        self._remove = QLineEdit()
        self._remove.setPlaceholderText("e.g. TSLA")
        self._remove.setFixedWidth(300)
        self._preset = QComboBox()
        self._preset.setFixedWidth(260)
        self._top_n = QSpinBox()
        self._top_n.setRange(0, _MAX_TOP_N)
        self._top_n.setSpecialValueText("All")
        self._top_n.setFixedWidth(_FIELD_W)
        self._source = ChipGroup([("Replay the screener", "replay"), ("Saved lists", "saved")])
        self._source.setFixedWidth(300)
        self._saved_count = _key_label("")
        self._ai = QCheckBox("Use AI ranking")
        self._ai.setEnabled(False)
        self._ai.setToolTip("Comes in a later phase")
        self._strategies = QTableWidget(0, 4)
        self._strategies.setObjectName("bt_strategies")
        self._strategies.setHorizontalHeaderLabels(["Use", "Strategy", "Allocation %",
                                                    "Per trade %"])
        self._strategies.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self._strategies.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        self._strategies.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._strategies.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._strategies.setMinimumHeight(180)
        self._capital = self._money(100, 10_000_000, 0, "$ ", 10_000)
        self._loss = self._money(0, 100, 1, "", 2.0)
        self._loss.setSuffix(" %")
        self._loss.setSpecialValueText("Off")
        self._when = QComboBox()
        self._when.addItem("First signal", "first_signal")
        self._when.addItem("Highest score", "highest_score")
        self._when.setFixedWidth(_FIELD_W)
        self._commission = self._money(0, 100, 2, "$ ", 1.0)
        self._slippage = QSpinBox()
        self._slippage.setRange(0, 500)
        self._slippage.setSuffix(" bps")
        self._slippage.setValue(5)
        self._slippage.setFixedWidth(_FIELD_W)
        self.pages = self._build_pages()

        for edit in (self._name, self._names_edit, self._add, self._remove):
            edit.textChanged.connect(self.changed)
        for date_edit in (self._start, self._end):
            date_edit.dateChanged.connect(self.changed)
        self._mode.changed.connect(self._on_mode)
        self._sectors.itemChanged.connect(self.changed)
        self._preset.currentIndexChanged.connect(self.changed)
        self._top_n.valueChanged.connect(self.changed)
        self._source.changed.connect(self.changed)
        self._strategies.itemChanged.connect(self.changed)
        for spin in (self._capital, self._loss, self._commission):
            spin.valueChanged.connect(self.changed)
        self._slippage.valueChanged.connect(self.changed)
        self._when.currentIndexChanged.connect(self.changed)
        self._on_mode()

    def _build_pages(self) -> dict[str, QWidget]:
        """One page of cards per section (SRD-GUI-031.072, .073)."""
        return {
            "run": _page(
                card("Name", "Shown in the Reports list.", [("Run name", self._name)]),
                card("Period", "First and last session to test.",
                     [("From", self._start), ("To", self._end)]),
            ),
            "stocks": _page(
                card("Which stocks", "All S&P 500 stocks, some sectors or your own names.",
                     [("Stock list", self._mode), ("Sectors", self._sectors),
                      ("Names", self._names_edit)]),
                card("Adjust the list", "Optional names to add or leave out, comma separated.",
                     [("Add stocks", self._add), ("Remove stocks", self._remove)]),
            ),
            "screener": _page(
                card("Preset", "The screener that makes each day's stock list.",
                     [("Screener preset", self._preset), ("Stocks per day", self._top_n)]),
                card("Source", "Run the screener again, or use the lists the app saved "
                     "(AI picks included).",
                     [("Daily lists", self._source), ("", self._saved_count)]),
                card("Ranking", "", [("AI ranking", self._ai)]),
            ),
            "strategies": _page(
                card("Strategies", "Tick the live strategies to test. Allocation and per-trade "
                     "% come from Execution.", [(None, self._strategies)]),
            ),
            "account": _page(
                card("Money", "Start values come from the active user's risk settings.",
                     [("Capital", self._capital), ("Daily loss stop", self._loss),
                      ("When money short", self._when)]),
                card("Costs", "Added to every fill.",
                     [("Commission per order", self._commission),
                      ("Slippage", self._slippage)]),
            ),
        }

    @staticmethod
    def _money(low: float, high: float, decimals: int, prefix: str, value: float
               ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(low, high)
        spin.setDecimals(decimals)
        spin.setPrefix(prefix)
        spin.setValue(value)
        spin.setFixedWidth(_FIELD_W)
        return spin

    def set_account_defaults(self, capital: float, daily_loss_pct: float) -> None:
        """SRD-GUI-031.030 — start values from the user's Max capital and max daily loss."""
        self._capital.setValue(capital)
        self._loss.setValue(daily_loss_pct)

    @staticmethod
    def _date_edit() -> QDateEdit:
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setMinimumDate(QDate(2000, 1, 1))
        edit.setMaximumDate(QDate.currentDate())
        edit.setFixedWidth(_FIELD_W)
        return edit

    def _on_mode(self) -> None:
        mode = self._mode.value
        _show_row(self._sectors, mode == "sector")
        _show_row(self._names_edit, mode == "names")
        self.changed.emit()

    def set_universe(self, records: Sequence[UniverseRecord]) -> None:
        """Fill the sector list, keeping ticked sectors ticked."""
        ticked = self._ticked_sectors()
        self._sectors.blockSignals(True)
        self._sectors.clear()
        for sector in sorted({r.sector for r in records if r.sector}):
            item = QListWidgetItem(sector)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if sector in ticked else Qt.CheckState.Unchecked
            )
            self._sectors.addItem(item)
        self._sectors.blockSignals(False)
        self.changed.emit()

    def set_presets(self, presets: Sequence[PresetInfo]) -> None:
        """Fill the screener picker; weekly presets are marked."""
        current = self._preset.currentData()
        self._preset.blockSignals(True)
        self._preset.clear()
        for info in presets:
            label = info.name if info.timeframe == "1d" else f"{info.name} (weekly)"
            self._preset.addItem(label, info.id)
        index = self._preset.findData(current)
        self._preset.setCurrentIndex(max(index, 0))
        self._preset.blockSignals(False)
        self.changed.emit()

    def set_strategies(self, strategies: Sequence[Mapping[str, Any]]) -> None:
        """SRD-GUI-031.020 / .073 — fill the strategy table, keeping ticked names ticked."""
        self._fill_strategies(strategies, {spec.id for spec in self._ticked_strategies()})
        self.changed.emit()

    def _fill_strategies(self, strategies: Sequence[Mapping[str, Any]], ticked: set[str]) -> None:
        table = self._strategies
        table.blockSignals(True)
        table.setRowCount(len(strategies))
        for row, cfg in enumerate(strategies):
            name, alloc, per = str(cfg["name"]), float(cfg["capital_max"]), float(cfg["per_trade_pct"])
            use = QTableWidgetItem("")
            use.setData(Qt.ItemDataRole.UserRole, (name, alloc, per))
            use.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            use.setCheckState(Qt.CheckState.Checked if name in ticked else Qt.CheckState.Unchecked)
            table.setItem(row, 0, use)
            for col, text in ((1, name), (2, f"{alloc:g}"), (3, f"{per:g}")):
                table.setItem(row, col, QTableWidgetItem(text))
        table.resizeColumnsToContents()
        table.blockSignals(False)

    def _strategy_rows(self) -> list[tuple[QTableWidgetItem, tuple[str, float, float]]]:
        rows = []
        for row in range(self._strategies.rowCount()):
            item = self._strategies.item(row, 0)
            if item is not None:
                rows.append((item, item.data(Qt.ItemDataRole.UserRole)))
        return rows

    def _ticked_strategies(self) -> tuple[StrategySpec, ...]:
        return tuple(StrategySpec(name, (alloc,), (per,))
                     for item, (name, alloc, per) in self._strategy_rows()
                     if item.checkState() == Qt.CheckState.Checked)

    def _ticked_sectors(self) -> tuple[str, ...]:
        return tuple(
            item.text()
            for i in range(self._sectors.count())
            if (item := self._sectors.item(i)) is not None
            and item.checkState() == Qt.CheckState.Checked
        )

    @property
    def top_n(self) -> int:
        """Stocks per day; 0 means all."""
        return self._top_n.value()

    @property
    def preset_id(self) -> str:
        """The picked screener preset's id."""
        return str(self._preset.currentData() or "")

    def set_saved_days(self, days: Sequence[datetime.date]) -> None:
        """Show how many saved lists the preset has (SRD-GUI-031.060)."""
        self._saved_count.setText(
            "No saved lists for this preset" if not days
            else f"{len(days)} saved days · {days[0]} → {days[-1]}")

    def quick_test(self, preset_id: str, first: datetime.date, last: datetime.date) -> None:
        """S&P 500, the preset, saved lists and their period (SRD-GUI-031.061)."""
        self._mode.buttons[0].click()
        self._preset.setCurrentIndex(max(self._preset.findData(preset_id), 0))
        self._source.buttons[1].click()
        self._start.setDate(_qdate(first))
        self._end.setDate(_qdate(last))

    def summaries(self) -> dict[str, str]:
        """One short line per section for the setup menu and the plan line (SRD-GUI-031.070)."""
        plan = self.plan()
        uni, scr, acc = plan.universe, plan.screener, plan.account
        stocks = {"sector": ", ".join(uni.sectors) or "No sector",
                  "names": ", ".join(uni.names[:4]) or "No names"}.get(uni.mode, "S&P 500")
        return {
            "run": f"{plan.name} · {plan.period.start} → {plan.period.end}",
            "stocks": stocks,
            "screener": f"{self._preset.currentText() or 'No preset'} · "
                        f"{'saved lists' if scr.recorded else 'replay'} · "
                        f"{scr.top_n or 'All'} a day",
            "strategies": ", ".join(s.id for s in plan.strategies) or "None picked",
            "account": f"${acc.capital[0]:,.0f} · loss stop {acc.max_daily_loss_pct:g}% · "
                       f"${plan.costs.per_order:g} · {plan.costs.slippage_bps:g} bps",
        }

    def load_plan(self, plan: RunPlan) -> None:
        """Put a plan back into the fields (Cancel in the setup window, SRD-GUI-031.074)."""
        self.blockSignals(True)
        self._name.setText(plan.name)
        self._start.setDate(_qdate(plan.period.start))
        self._end.setDate(_qdate(plan.period.end))
        modes = [b for b, v in zip(self._mode.buttons, ("sp500", "sector", "names"), strict=True)
                 if v == plan.universe.mode]
        if modes:
            modes[0].click()
        for i in range(self._sectors.count()):
            item = self._sectors.item(i)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked if item.text() in plan.universe.sectors
                                   else Qt.CheckState.Unchecked)
        self._names_edit.setText(", ".join(plan.universe.names))
        self._add.setText(", ".join(plan.universe.add))
        self._remove.setText(", ".join(plan.universe.remove))
        self._preset.setCurrentIndex(max(self._preset.findData(plan.screener.preset_id), 0))
        self._top_n.setValue(plan.screener.top_n)
        self._source.buttons[1 if plan.screener.recorded else 0].click()
        ticked = {s.id for s in plan.strategies}
        for use, (name, _alloc, _per) in self._strategy_rows():
            use.setCheckState(Qt.CheckState.Checked if name in ticked else Qt.CheckState.Unchecked)
        self._capital.setValue(plan.account.capital[0])
        self._loss.setValue(plan.account.max_daily_loss_pct)
        self._when.setCurrentIndex(max(self._when.findData(plan.account.when_full), 0))
        self._commission.setValue(plan.costs.per_order)
        self._slippage.setValue(int(plan.costs.slippage_bps))
        self.blockSignals(False)
        self._on_mode()

    def plan(self) -> RunPlan:
        """Return the run plan made from the fields."""
        return RunPlan(
            name=self._name.text().strip() or "Backtest",
            period=Period(_pydate(self._start.date()), _pydate(self._end.date())),
            universe=UniverseSpec(
                mode=self._mode.value or "sp500",
                sectors=self._ticked_sectors(),
                names=_names(self._names_edit.text()),
                add=_names(self._add.text()),
                remove=_names(self._remove.text()),
            ),
            screener=ScreenerSpec(
                preset_id=str(self._preset.currentData() or ""),
                top_n=self._top_n.value(),
                ai_ranking=self._ai.isChecked(),
                recorded=self._source.value == "saved",
            ),
            strategies=self._ticked_strategies(),
            account=AccountSpec(
                capital=(self._capital.value(),),
                max_daily_loss_pct=self._loss.value(),
                when_full=str(self._when.currentData()),
            ),
            costs=CostSpec(per_order=self._commission.value(),
                           slippage_bps=float(self._slippage.value())),
        )
