"""
Module: MD-GUI-026.005.M03 — Chart Inspector
Parent SRD: SRD-GUI-026.005

Collapsible sections beside the Charts chart. Sections come from one registry,
``SECTIONS``; a new chart feature is one more section class in that tuple.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt
import talib
from PyQt6.QtCore import QSettings, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.indicator_rules import BarArrays
from us_swing.core.price_patterns import PATTERNS, Direction, default_pattern_rule, evaluate_pattern
from us_swing.gui.icons import icon, set_icon
from us_swing.gui.theme import active_palette

_log = logging.getLogger(__name__)

_DASH = "—"
_SPIN_W = 110
_PERIOD = 14
_REL_VOL_BARS = 20
PATTERN_LOOKBACK = 5
_PIVOT_WING = 3
_PIVOT_WINDOW = 120
_LEVEL_COUNT = 3

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


@dataclass(frozen=True)
class PatternHit:
    """A catalogue pattern found ``bars_ago`` bars before the last bar."""

    name: str
    bars_ago: int
    direction: Direction
    time: Any


def _arrays(candles: Sequence[Candle]) -> BarArrays:
    o, h, lo, c, v = (_column(candles, k) for k in ("open", "high", "low", "close", "volume"))
    return BarArrays(o, h, lo, c, v)


def pattern_hits(candles: Sequence[Candle],
                 lookback: int = PATTERN_LOOKBACK) -> list[PatternHit]:
    """Patterns true on one of the last ``lookback`` bars, newest hit per pattern first."""
    full = _arrays(candles)
    windows = [
        BarArrays(*(getattr(full, k)[:len(candles) - ago]
                    for k in ("open", "high", "low", "close", "volume")))
        for ago in range(min(lookback, len(candles)))
    ]
    hits: list[PatternHit] = []
    for spec in PATTERNS:
        if not spec.available:
            continue
        rule = default_pattern_rule(spec)
        for bars_ago, arrays in enumerate(windows):
            try:
                found = evaluate_pattern(rule, arrays)
            except Exception:  # noqa: BLE001
                _log.debug("[Charts] Pattern check failed for %s", spec.name, exc_info=True)
                break
            if found:
                time = candles[len(candles) - 1 - bars_ago]["time"]
                hits.append(PatternHit(spec.name, bars_ago, spec.direction, time))
                break
    return sorted(hits, key=lambda h: (h.bars_ago, h.name))


def key_levels(candles: Sequence[Candle], wing: int = _PIVOT_WING,
               window: int = _PIVOT_WINDOW,
               count: int = _LEVEL_COUNT) -> tuple[list[float], list[float]]:
    """Nearest swing levels above and below the last close (pivots ``wing`` bars each side)."""
    if len(candles) < 2 * wing + 2:
        return [], []
    bars = candles[-window:]
    highs, lows = _column(bars, "high"), _column(bars, "low")
    pivots: set[float] = set()
    for i in range(wing, len(bars) - wing):
        span = slice(i - wing, i + wing + 1)
        if highs[i] == highs[span].max():
            pivots.add(round(float(highs[i]), 2))
        if lows[i] == lows[span].min():
            pivots.add(round(float(lows[i]), 2))
    close = float(bars[-1]["close"])
    above = sorted(p for p in pivots if p > close)[:count]
    below = sorted((p for p in pivots if p < close), reverse=True)[:count]
    return above, below


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
    send_requested = pyqtSignal(str)    # symbol (SRD-GUI-026.010)

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
            spin.setFixedWidth(_SPIN_W)
            spin.hide()
            self.spins[key] = spin
            self.rows.grid.addWidget(spin, row, 1, Qt.AlignmentFlag.AlignRight)
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
        self.send_btn = QPushButton("Send to Execution")
        self.send_btn.setObjectName("primary_btn")
        set_icon(self.send_btn, "send", "inverse")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._on_send)
        buttons.addWidget(self.send_btn, 1)
        box.addLayout(buttons)
        self.message_lbl = QLabel()
        self.message_lbl.setWordWrap(True)
        self.message_lbl.hide()
        box.addWidget(self.message_lbl)

    def widget(self) -> QWidget:
        return self

    def set_context(self, ctx: ChartContext) -> None:
        self._ctx = ctx
        self._plan = ctx.plan
        self.send_btn.setEnabled(bool(ctx.symbol))
        self.message_lbl.hide()
        self._set_editing(False)
        self._show()

    def show_message(self, text: str) -> None:
        """Show why Send to Execution did not add the symbol."""
        ct: Any = active_palette()
        self.message_lbl.setStyleSheet(f"color:{ct.YELLOW};")
        self.message_lbl.setText(text)
        self.message_lbl.show()

    def _on_send(self) -> None:
        if self._ctx is not None and self._ctx.symbol:
            self.send_requested.emit(self._ctx.symbol)

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
        # Save, Cancel and Send do not fit the Inspector width side by side.
        self.send_btn.setVisible(not editing)
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


class PatternsSection(QWidget):
    """Patterns found on the last bars; the eye on a row marks it on the chart (SRD-GUI-026.008)."""

    key = "patterns"
    title = "Patterns Found"
    markers_changed = pyqtSignal(list)   # chart markers, oldest first

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(0, 0, 0, 0)
        self.column.setSpacing(4)
        self.lines: list[QLabel] = []
        self.eyes: dict[str, QToolButton] = {}
        self.hits: list[PatternHit] = []
        self.shown: set[str] = set()   # kept across reloads so a chosen pattern stays marked
        self._rows: list[QWidget] = []
        self._colour: dict[Direction, str] = {}

    def widget(self) -> QWidget:
        return self

    def set_context(self, ctx: ChartContext) -> None:
        self.hits = pattern_hits(ctx.candles)
        for row in self._rows:
            row.deleteLater()
        ct: Any = active_palette()
        self._colour = {Direction.BULLISH: ct.GREEN, Direction.BEARISH: ct.RED,
                        Direction.NEUTRAL: ct.YELLOW}
        self.lines, self.eyes, self._rows = [], {}, []
        for hit in self.hits:
            self._add_row(
                f"<span style='color:{self._colour[hit.direction]}'>●</span> {hit.name}"
                f" <span style='color:{ct.SUBTEXT}'>· "
                f"{'today' if hit.bars_ago == 0 else f'{hit.bars_ago} bars ago'}</span>",
                hit.name)
        if not self.hits:
            self._add_row(f"<span style='color:{ct.SUBTEXT}'>No patterns in the last "
                          f"{PATTERN_LOOKBACK} bars</span>", None)
        self._emit()

    def _add_row(self, text: str, name: str | None) -> None:
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.RichText)
        line.addWidget(label, 1)
        if name is not None:
            eye = QToolButton()
            eye.setCheckable(True)
            eye.setChecked(name in self.shown)
            eye.setAutoRaise(True)
            eye.setStyleSheet("QToolButton { border: none; background: transparent; "
                              "outline: none; } QToolButton:focus { outline: none; }")
            _style_eye(eye)
            eye.toggled.connect(lambda on, n=name: self._on_eye(n, on))
            line.addWidget(eye)
            self.eyes[name] = eye
        self.column.addWidget(row)
        self.lines.append(label)
        self._rows.append(row)

    def _on_eye(self, name: str, on: bool) -> None:
        if on:
            self.shown.add(name)
        else:
            self.shown.discard(name)
        _style_eye(self.eyes[name])
        self._emit()

    def _emit(self) -> None:
        markers = [
            {"time": hit.time,
             "position": "aboveBar" if hit.direction == Direction.BEARISH else "belowBar",
             "shape": "arrowDown" if hit.direction == Direction.BEARISH else "arrowUp",
             "color": self._colour[hit.direction], "id": hit.name, "text": ""}
            for hit in sorted(self.hits, key=lambda h: h.time) if hit.name in self.shown
        ]
        self.markers_changed.emit(markers)


def _style_eye(eye: QToolButton) -> None:
    """Bright eye when the pattern is on the chart, dimmed eye when it is not."""
    on = eye.isChecked()
    base = icon("eye", "info")
    eye.setIcon(base if on else QIcon(base.pixmap(QSize(14, 14), QIcon.Mode.Disabled)))
    eye.setIconSize(QSize(14, 14))
    tip = "Hide from chart" if on else "Show on chart"
    eye.setToolTip(tip)
    eye.setAccessibleName(tip)


class KeyLevelsSection(QWidget):
    """Nearest swing highs and lows; can draw them on the chart (SRD-GUI-026.009)."""

    key = "levels"
    title = "Key Levels"
    levels_changed = pyqtSignal(list)   # prices to draw, [] to clear

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        self.above_lbl = QLabel(_DASH)
        self.below_lbl = QLabel(_DASH)
        self.rows = _Rows([("above", "Above"), ("below", "Below")])
        self.rows.grid.addWidget(self.above_lbl, 0, 1)
        self.rows.grid.addWidget(self.below_lbl, 1, 1)
        for key in ("above", "below"):
            self.rows.values[key].hide()
        self.above_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.below_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        box.addWidget(self.rows)
        self.show_box = QCheckBox("Show on chart")
        self.show_box.toggled.connect(self._emit)
        box.addWidget(self.show_box)
        self.above: list[float] = []
        self.below: list[float] = []

    def widget(self) -> QWidget:
        return self

    def set_context(self, ctx: ChartContext) -> None:
        self.above, self.below = key_levels(ctx.candles)
        self.above_lbl.setText(", ".join(f"{p:,.2f}" for p in self.above) or _DASH)
        self.below_lbl.setText(", ".join(f"{p:,.2f}" for p in self.below) or _DASH)
        self._emit()

    def _emit(self) -> None:
        shown = self.show_box.isChecked()
        self.levels_changed.emit([*self.above, *self.below] if shown else [])


SECTIONS: tuple[Callable[[], InspectorSection], ...] = (
    TradePlanSection, PatternsSection, KeyLevelsSection, IndicatorsSection,
)
# Signals an Inspector passes on from any section that has them.
_FORWARDED = ("plan_changed", "send_requested", "markers_changed", "levels_changed")


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
    send_requested = pyqtSignal(str)    # symbol to add to Execution
    markers_changed = pyqtSignal(list)  # pattern markers for the chart
    levels_changed = pyqtSignal(list)   # key level prices for the chart

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
        scroll.setFrameShape(QFrame.Shape.NoFrame)
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
            for name in _FORWARDED:
                source = getattr(section, name, None)
                if source is not None:
                    source.connect(getattr(self, name))
        column.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        self.restyle()

    def update_context(self, ctx: ChartContext) -> None:
        """Hand a freshly loaded chart to every section."""
        for section in self.sections:
            section.set_context(ctx)

    def show_message(self, text: str) -> None:
        """Show a Send to Execution message in the Trade Plan section."""
        for section in self.sections:
            if isinstance(section, TradePlanSection):
                section.show_message(text)

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
