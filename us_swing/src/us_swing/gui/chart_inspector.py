"""
Module: MD-GUI-026.005.M03 — Chart Inspector
Parent SRD: SRD-GUI-026.005

Collapsible sections beside the Charts chart. Sections come from one registry,
``SECTIONS``; a new chart feature is one more section class in that tuple.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt
import talib
from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.icons import set_icon
from us_swing.gui.theme import active_palette

_DASH = "—"
_PERIOD = 14
_REL_VOL_BARS = 20

Candle = Mapping[str, float]


# ── Plan and indicator maths ─────────────────────────────────────────────────

@dataclass(frozen=True)
class TradePlan:
    """Entry, stop and target prices for one symbol."""

    entry: float
    stop: float
    target: float

    @property
    def levels(self) -> tuple[float, float, float]:
        return self.entry, self.stop, self.target


@dataclass(frozen=True)
class ChartContext:
    """What every Inspector section gets when a chart loads."""

    symbol: str
    timeframe: str
    candles: Sequence[Candle]
    plan: TradePlan | None = None
    risk_pct: float = 1.0
    equity: float = 0.0


def plan_rr(entry: float, stop: float, target: float) -> float | None:
    """Reward : risk for a long-shaped plan (stop < entry < target), else None."""
    if not stop < entry < target:
        return None
    return (target - entry) / (entry - stop)


def plan_size(entry: float, stop: float, equity: float, risk_pct: float) -> int:
    """Shares so that a stop-out loses ``risk_pct`` % of ``equity``; 0 when stop ≥ entry."""
    risk_per_share = entry - stop
    if risk_per_share <= 0 or equity <= 0 or risk_pct <= 0:
        return 0
    return math.floor(equity * risk_pct / 100.0 / risk_per_share)


def _column(candles: Sequence[Candle], key: str) -> npt.NDArray[np.float64]:
    return np.asarray([float(c[key]) for c in candles], dtype=np.float64)


def _last(values: npt.NDArray[np.float64]) -> float | None:
    if len(values) == 0 or np.isnan(values[-1]):
        return None
    return float(values[-1])


def adx(candles: Sequence[Candle], period: int = _PERIOD) -> float | None:
    """Wilder ADX of the last bar, None without enough bars."""
    if len(candles) < 2 * period:
        return None
    high, low, close = (_column(candles, k) for k in ("high", "low", "close"))
    return _last(np.asarray(talib.ADX(high, low, close, timeperiod=period), dtype=np.float64))


def rel_volume(candles: Sequence[Candle], bars: int = _REL_VOL_BARS) -> float | None:
    """Last volume ÷ mean volume of the ``bars`` before it."""
    if len(candles) <= bars:
        return None
    volume = _column(candles, "volume")
    mean = float(volume[-bars - 1:-1].mean())
    return float(volume[-1]) / mean if mean > 0 else None


def indicator_values(candles: Sequence[Candle]) -> dict[str, float | None]:
    """RSI 14, ATR 14, ADX 14 and relative volume of the last bar (SRD-GUI-026.007)."""
    rsi = atr = None
    if len(candles) > _PERIOD:
        high, low, close = (_column(candles, k) for k in ("high", "low", "close"))
        rsi = _last(np.asarray(talib.RSI(close, timeperiod=_PERIOD), dtype=np.float64))
        atr = _last(np.asarray(talib.ATR(high, low, close, timeperiod=_PERIOD),
                               dtype=np.float64))
    return {"rsi": rsi, "atr": atr, "adx": adx(candles), "rel_volume": rel_volume(candles)}


def _money(value: float | None) -> str:
    return _DASH if value is None else f"{value:,.2f}"


# ── Sections ─────────────────────────────────────────────────────────────────

class InspectorSection(Protocol):
    """One collapsible Inspector section."""

    key: str
    title: str

    def widget(self) -> QWidget: ...

    def set_context(self, ctx: ChartContext) -> None: ...


def _value_label(text: str = _DASH) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return label


class _Rows(QWidget):
    """Name / value rows, with the values kept by key."""

    def __init__(self, names: Sequence[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(4)
        self.values: dict[str, QLabel] = {}
        self.names: list[QLabel] = []
        for row, (key, name) in enumerate(names):
            name_lbl = QLabel(name)
            self.names.append(name_lbl)
            self.grid.addWidget(name_lbl, row, 0)
            self.values[key] = _value_label()
            self.grid.addWidget(self.values[key], row, 1)

    def restyle(self) -> None:
        ct: Any = active_palette()
        for label in self.names:
            label.setStyleSheet(f"color:{ct.SUBTEXT};")


class TradePlanSection(QWidget):
    """Entry, stop, target, reward : risk and size; Edit changes them (SRD-GUI-026.006)."""

    key = "plan"
    title = "Trade Plan"
    plan_changed = pyqtSignal(object)   # TradePlan

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx: ChartContext | None = None
        self._plan: TradePlan | None = None
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        self.rows = _Rows([("entry", "Entry"), ("stop", "Stop"), ("target", "Target"),
                           ("rr", "Reward : risk"), ("size", "Size")])
        box.addWidget(self.rows)
        self.spins: dict[str, QDoubleSpinBox] = {}
        for row, key in enumerate(("entry", "stop", "target")):
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1_000_000.0)
            spin.setDecimals(2)
            spin.setAccessibleName(key.title())
            spin.hide()
            self.spins[key] = spin
            self.rows.grid.addWidget(spin, row, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.edit_btn = QPushButton("Edit")
        set_icon(self.edit_btn, "pencil")
        self.edit_btn.clicked.connect(self._on_edit)
        buttons.addWidget(self.edit_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(lambda: self._set_editing(False))
        self.cancel_btn.hide()
        buttons.addWidget(self.cancel_btn)
        box.addLayout(buttons)

    def widget(self) -> QWidget:
        return self

    def set_context(self, ctx: ChartContext) -> None:
        self._ctx = ctx
        self._plan = ctx.plan
        self._set_editing(False)
        self._show()

    @property
    def editing(self) -> bool:
        return not self.cancel_btn.isHidden()

    def _show(self) -> None:
        values = self.rows.values
        plan = self._plan
        risk_pct = self._ctx.risk_pct if self._ctx else 1.0
        self.rows.names[4].setText(f"Size ({risk_pct:g}% risk)")
        if plan is None:
            for label in values.values():
                label.setText(_DASH)
            return
        values["entry"].setText(_money(plan.entry))
        values["stop"].setText(_money(plan.stop))
        values["target"].setText(_money(plan.target))
        rr = plan_rr(*plan.levels)
        values["rr"].setText(_DASH if rr is None else f"{rr:.1f}")
        equity = self._ctx.equity if self._ctx else 0.0
        size = plan_size(plan.entry, plan.stop, equity, risk_pct)
        values["size"].setText(f"{size} sh" if rr is not None and size > 0 else _DASH)

    def _on_edit(self) -> None:
        if not self.editing:
            seed = self._plan or self._seed_plan()
            for key, value in zip(("entry", "stop", "target"), seed.levels):
                self.spins[key].setValue(value)
            self._set_editing(True)
            return
        self._plan = TradePlan(*(self.spins[k].value() for k in ("entry", "stop", "target")))
        self._set_editing(False)
        self._show()
        self.plan_changed.emit(self._plan)

    def _seed_plan(self) -> TradePlan:
        last = float(self._ctx.candles[-1]["close"]) if self._ctx and self._ctx.candles else 0.0
        return TradePlan(last, last, last)

    def _set_editing(self, editing: bool) -> None:
        for key, spin in self.spins.items():
            spin.setVisible(editing)
            self.rows.values[key].setVisible(not editing)
        self.cancel_btn.setVisible(editing)
        self.edit_btn.setText("Save" if editing else "Edit")
        set_icon(self.edit_btn, "save" if editing else "pencil")


class IndicatorsSection(QWidget):
    """RSI, ATR, ADX and relative volume of the last bar (SRD-GUI-026.007)."""

    key = "indicators"
    title = "Indicators"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        self.rows = _Rows([("rsi", "RSI 14"), ("atr", "ATR 14"), ("adx", "ADX 14"),
                           ("rel_volume", "Rel. volume")])
        box.addWidget(self.rows)

    def widget(self) -> QWidget:
        return self

    def set_context(self, ctx: ChartContext) -> None:
        values = indicator_values(ctx.candles)
        formats = {"rsi": "{:.1f}", "atr": "{:.2f}", "adx": "{:.1f}", "rel_volume": "{:.1f}×"}
        for key, fmt in formats.items():
            value = values[key]
            self.rows.values[key].setText(_DASH if value is None else fmt.format(value))


SECTIONS: tuple[Callable[[], InspectorSection], ...] = (TradePlanSection, IndicatorsSection)


# ── Inspector ────────────────────────────────────────────────────────────────

class _SectionBox(QWidget):
    """Header button with a chevron over the section body."""

    def __init__(self, section: InspectorSection, opened: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.section = section
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        self.header = QPushButton(section.title.upper())
        self.header.setObjectName("inspector_head")
        self.header.setCheckable(True)
        self.header.setChecked(opened)
        self.header.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        box.addWidget(self.header)
        self.body = QWidget()
        inner = QVBoxLayout(self.body)
        inner.setContentsMargins(14, 4, 14, 12)
        inner.addWidget(section.widget())
        box.addWidget(self.body)
        self.header.toggled.connect(self._apply)
        self._apply(opened)

    @property
    def opened(self) -> bool:
        return self.header.isChecked()

    def _apply(self, opened: bool) -> None:
        self.body.setVisible(opened)
        set_icon(self.header, "chevron-down" if opened else "chevron-right", size=13)


class Inspector(QWidget):
    """Collapsible sections from a registry; open sections are remembered."""

    plan_changed = pyqtSignal(object)   # TradePlan edited in the Trade Plan section

    def __init__(self, settings: QSettings,
                 sections: Sequence[Callable[[], InspectorSection]] = SECTIONS,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.sections = [factory() for factory in sections]
        saved = settings.value("open_sections")
        opened = set(str(saved).split(",")) if saved is not None else {
            s.key for s in self.sections}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._title = QLabel("Inspector")
        self._title.setObjectName("page_title")
        self._title.setContentsMargins(14, 10, 14, 10)
        root.addWidget(self._title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.boxes: list[_SectionBox] = []
        for section in self.sections:
            box = _SectionBox(section, section.key in opened)
            box.header.toggled.connect(self._save_open)
            column.addWidget(box)
            self.boxes.append(box)
            if isinstance(section, TradePlanSection):
                section.plan_changed.connect(self.plan_changed)
        column.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        self.restyle()

    def update_context(self, ctx: ChartContext) -> None:
        """Hand a freshly loaded chart to every section."""
        for section in self.sections:
            section.set_context(ctx)

    def is_open(self, key: str) -> bool:
        return any(box.opened for box in self.boxes if box.section.key == key)

    def _save_open(self) -> None:
        keys = ",".join(box.section.key for box in self.boxes if box.opened)
        self._settings.setValue("open_sections", keys)

    def restyle(self) -> None:
        ct: Any = active_palette()
        for box in self.boxes:
            box.header.setStyleSheet(
                f"QPushButton {{ text-align:left; padding:0 14px; border:none;"
                f" border-top:1px solid {ct.OVERLAY}; background:transparent; color:{ct.TEXT};"
                f" font-weight:600; outline:none; }}"
                f"QPushButton:hover {{ background:{ct.OVERLAY}; }}"
                f"QPushButton:focus {{ outline:none; }}"
            )
            rows = getattr(box.section, "rows", None)
            if isinstance(rows, _Rows):
                rows.restyle()
