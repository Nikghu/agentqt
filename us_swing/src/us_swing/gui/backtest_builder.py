"""
Module: MD-GUI-031.002.M02 — Backtest builder
Parent SRD: SRD-GUI-031.002, SRD-GUI-031.010

Left builder of the Backtest workspace. It only reads fields into a
``RunPlan``; estimating and running live in ``backtest.service``.
"""
from __future__ import annotations

import datetime
import re
from collections.abc import Sequence

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from us_swing.backtest.spec import Period, RunPlan, ScreenerSpec, UniverseSpec
from us_swing.backtest.universe import UniverseRecord
from us_swing.core.backtest_bridge import PresetInfo
from us_swing.gui.screener_views import ChipGroup

_WIDTH = 300
_MAX_TOP_N = 50


def _pydate(day: QDate) -> datetime.date:
    return datetime.date(day.year(), day.month(), day.day())


def _names(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(n.upper() for n in re.split(r"[\s,]+", text) if n))


def _group_label(title: str) -> QLabel:
    label = QLabel(title)
    label.setObjectName("panel_group")
    return label


def _key_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("details_key")
    return label


class BacktestBuilder(QWidget):
    """SRD-GUI-031.002 / .010 — run plan fields; ``changed`` fires on every edit."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(_WIDTH)
        body = QVBoxLayout(self)
        body.setContentsMargins(14, 14, 14, 14)
        body.setSpacing(8)

        self._name = QLineEdit("Backtest")
        self._start = self._date_edit()
        self._end = self._date_edit()
        today = QDate.currentDate()
        self._end.setDate(today)
        self._start.setDate(today.addYears(-1))
        self._mode = ChipGroup([("S&&P 500", "sp500"), ("Sectors", "sector"), ("Names", "names")])
        self._sectors = QListWidget()
        self._sectors.setObjectName("bt_sectors")
        self._names_edit = QLineEdit()
        self._names_edit.setPlaceholderText("AAPL, MSFT, NVDA")
        self._add = QLineEdit()
        self._add.setPlaceholderText("Add stocks")
        self._remove = QLineEdit()
        self._remove.setPlaceholderText("Remove stocks")
        self._preset = QComboBox()
        self._top_n = QSpinBox()
        self._top_n.setRange(0, _MAX_TOP_N)
        self._top_n.setSpecialValueText("All")
        self._top_n.setFixedWidth(80)
        self._ai = QCheckBox("Use AI ranking")
        self._ai.setEnabled(False)
        self._ai.setToolTip("Comes in a later phase")

        body.addWidget(_group_label("RUN"))
        body.addWidget(self._name)
        body.addLayout(self._row("From", self._start))
        body.addLayout(self._row("To", self._end))
        body.addWidget(_group_label("STOCKS"))
        body.addWidget(self._mode)
        body.addWidget(self._sectors, 1)
        body.addWidget(self._names_edit)
        body.addWidget(self._add)
        body.addWidget(self._remove)
        body.addWidget(_group_label("SCREENER"))
        body.addWidget(self._preset)
        body.addLayout(self._row("Stocks per day", self._top_n))
        body.addWidget(self._ai)
        body.addStretch()

        for edit in (self._name, self._names_edit, self._add, self._remove):
            edit.textChanged.connect(self.changed)
        for date_edit in (self._start, self._end):
            date_edit.dateChanged.connect(self.changed)
        self._mode.changed.connect(self._on_mode)
        self._sectors.itemChanged.connect(self.changed)
        self._preset.currentIndexChanged.connect(self.changed)
        self._top_n.valueChanged.connect(self.changed)
        self._on_mode()

    @staticmethod
    def _row(label: str, field: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(_key_label(label))
        row.addStretch()
        row.addWidget(field)
        return row

    @staticmethod
    def _date_edit() -> QDateEdit:
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setMinimumDate(QDate(2000, 1, 1))
        edit.setMaximumDate(QDate.currentDate())
        return edit

    def _on_mode(self) -> None:
        mode = self._mode.value
        self._sectors.setVisible(mode == "sector")
        self._names_edit.setVisible(mode == "names")
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
            ),
        )
