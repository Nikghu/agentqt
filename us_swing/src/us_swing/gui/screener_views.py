"""
Module: MD-GUI-022.001.M01 — Screener result views
Parent SRD: SRD-GUI-022.001

Result rows, sorting and CSV rows, the List / Cards switch, the List + detail
view and the Signal cards view shown by the screener panel (FO-GUI-022).
"""
from __future__ import annotations

import datetime
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from PyQt6.QtCore import QEvent, QRectF, QSettings, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPaintEvent, QResizeEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C, active_palette, colors

STRONG_MIN = 0.70
WATCH_MIN = 0.40
VIEWS = ("list", "cards")
SORT_KEYS: tuple[tuple[str, str], ...] = (
    ("score", "AI score"),
    ("rr", "Reward : risk"),
    ("rules", "Rules passed"),
)
CSV_HEADER = ["Symbol", "Score", "Details", "AI Reasoning", "Entry", "Stop", "Target", "R:R"]

_MONO = "'IBM Plex Mono', Consolas, monospace"
_CARD_MIN_W = 320
_DASH = "—"


# ── Rows ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RuleCheck:
    """One preset rule result for a stock; ``passed`` is None for a numeric value."""

    name: str
    passed: bool | None
    value: str = ""


@dataclass
class ResultRow:
    """One screener result, shared by both views."""

    symbol: str
    score: float
    rank: int = 0
    rules: list[RuleCheck] = field(default_factory=list)
    reasoning: str = ""
    entry: float | None = None
    stop: float | None = None
    target: float | None = None

    @property
    def rr(self) -> float | None:
        """Reward : risk for a long-shaped plan (stop < entry < target), else None."""
        if self.entry is None or self.stop is None or self.target is None:
            return None
        if not self.stop < self.entry < self.target:
            return None
        return (self.target - self.entry) / (self.entry - self.stop)

    @property
    def tier(self) -> str:
        if self.score >= STRONG_MIN:
            return "Strong"
        if self.score >= WATCH_MIN:
            return "Watch"
        return "Weak"

    @property
    def passed_count(self) -> int:
        return sum(1 for rule in self.rules if rule.passed)

    @property
    def details_text(self) -> str:
        """Compact rule text, as the old Details column showed it."""
        parts = [
            f"{r.name}:{r.value}" if r.passed is None else f"{r.name}:{'✔' if r.passed else '✘'}"
            for r in self.rules
        ]
        return "  ·  ".join(parts) or _DASH


def _rule_check(key: str, value: Any) -> RuleCheck:
    name = key.split("_")[0]
    if isinstance(value, bool):
        return RuleCheck(name, value)
    if isinstance(value, (int, float)):
        return RuleCheck(name, None, f"{float(value):.2f}")
    return RuleCheck(name, None, str(value))


def _price(plan: Any, key: str) -> float | None:
    if not isinstance(plan, Mapping):
        return None
    try:
        value = float(plan.get(key))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def rows_from_result(results: Mapping[str, Mapping[str, Any]]) -> list[ResultRow]:
    """Build ranked rows from ``ScreenerRunResult.results``.

    Args:
        results: Symbol → result metadata (``score``, ``details``, ``ai_reasoning``, ``ai_plan``).

    Returns:
        Rows sorted by score, highest first, with ``rank`` set from 1.
    """
    rows: list[ResultRow] = []
    for symbol, meta in results.items():
        plan = meta.get("ai_plan")
        details = meta.get("details") or {}
        rows.append(ResultRow(
            symbol=symbol,
            score=float(meta.get("score", 0.0)),
            rules=[_rule_check(k, v) for k, v in details.items()],
            reasoning=str(meta.get("ai_reasoning", "") or ""),
            entry=_price(plan, "entry"),
            stop=_price(plan, "stop"),
            target=_price(plan, "target"),
        ))
    rows.sort(key=lambda r: r.score, reverse=True)
    for rank, row in enumerate(rows, start=1):
        row.rank = rank
    return rows


def sort_rows(rows: list[ResultRow], key: str) -> list[ResultRow]:
    """Return ``rows`` ordered by ``key`` (``score``, ``rr`` or ``rules``)."""
    if key == "rr":
        return sorted(rows, key=lambda r: (r.rr is None, -(r.rr or 0.0), r.rank))
    if key == "rules":
        return sorted(rows, key=lambda r: (-r.passed_count, r.rank))
    return sorted(rows, key=lambda r: r.rank)


def _num(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}"


def csv_rows(rows: list[ResultRow]) -> list[list[str]]:
    """Return the CSV header followed by one line per row."""
    lines = [list(CSV_HEADER)]
    for r in rows:
        lines.append([r.symbol, f"{r.score:.4f}", r.details_text, r.reasoning,
                      _num(r.entry), _num(r.stop), _num(r.target), _num(r.rr)])
    return lines


def filter_presets(presets: Iterable[Any], text: str) -> list[Any]:
    """Keep presets whose name contains ``text`` (case-insensitive)."""
    needle = text.strip().casefold()
    return [p for p in presets if needle in str(getattr(p, "name", "")).casefold()]


def last_run_text(run_timestamp: str | None, matches: int, today: datetime.date,
                  tz: datetime.tzinfo | None = None) -> str:
    """Describe a preset's latest run, e.g. ``Today 13:18 · 5 matches``.

    Args:
        run_timestamp: ISO-8601 run time (``...Z`` for UTC), or None when never run.
        matches: Number of stocks in that run.
        today: Today's date in ``tz``.
        tz: Display time zone; None means the computer's local zone.
    """
    if not run_timestamp:
        return "Not run yet"
    try:
        when = datetime.datetime.fromisoformat(run_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return "Not run yet"
    if when.tzinfo is not None:
        when = when.astimezone(tz)
    noun = "match" if matches == 1 else "matches"
    if when.date() == today:
        return f"Today {when:%H:%M} · {matches} {noun}"
    return f"{when:%b} {when.day} · {matches} {noun}"


def _price_text(value: float | None) -> str:
    return _DASH if value is None else f"${value:,.2f}"


def _rr_text(row: ResultRow) -> str:
    return _DASH if row.rr is None else f"{row.rr:.1f} R"


def _tier_colours(tier: str) -> tuple[str, str]:
    _T: Any = active_palette()
    if tier == "Strong":
        return _T.GREEN, _T.PNL_POS_BG
    if tier == "Watch":
        return _T.YELLOW, colors()["score_cell_warning_bg"]
    return _T.RED, _T.PNL_NEG_BG


def _tier_chip(tier: str) -> QLabel:
    fg, bg = _tier_colours(tier)
    chip = QLabel(tier)
    chip.setStyleSheet(
        f"color: {fg}; background: {bg}; border-radius: 3px; padding: 1px 7px;"
        " font-size: 8pt; font-weight: bold;"
    )
    return chip


def _rule_chip(rule: RuleCheck) -> QLabel:
    _T: Any = active_palette()
    if rule.passed is None:
        text, fg, bg, border = f"{rule.name} {rule.value}", _T.TEXT, "transparent", _T.OVERLAY2
    elif rule.passed:
        text, fg, bg, border = f"✓ {rule.name}", _T.GREEN, _T.PNL_POS_BG, _T.PNL_POS_BG
    else:
        text, fg, bg, border = f"– {rule.name}", _T.MUTED, "transparent", _T.OVERLAY2
    chip = QLabel(text)
    chip.setStyleSheet(
        f"color: {fg}; background: {bg}; border: 1px solid {border};"
        " border-radius: 3px; padding: 2px 8px; font-size: 8pt;"
    )
    return chip


def _mono(text: str, colour: str = "", size: str = "9pt", bold: bool = False) -> QLabel:
    label = QLabel(text)
    weight = "font-weight: bold;" if bold else ""
    tint = f"color: {colour};" if colour else ""
    label.setStyleSheet(f"font-family: {_MONO}; font-size: {size}; {weight} {tint}")
    return label


def _key_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("view_key")
    return label


def _action_button(text: str, icon_name: str, role: str) -> QPushButton:
    button = QPushButton(text)
    set_icon(button, icon_name, role, 14)
    button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    return button


def _clear_layout(layout: Any) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


# ── Small painted widgets ─────────────────────────────────────────────────────

class _ScoreBar(QWidget):
    """Thin rounded bar filled to the score."""

    def __init__(self, score: float, colour: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fraction = max(0.0, min(1.0, score))
        self._colour = colour
        self.setFixedHeight(6)

    def paintEvent(self, event: QPaintEvent | None) -> None:
        _T: Any = active_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        rect = QRectF(self.rect())
        painter.setBrush(QColor(_T.OVERLAY))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setBrush(QColor(self._colour))
        painter.drawRoundedRect(QRectF(0, 0, rect.width() * self._fraction, rect.height()), 3, 3)
        painter.end()


class _RuleDots(QWidget):
    """One small square per rule: green pass, grey fail, blue value."""

    _SIZE = 8
    _GAP = 3

    def __init__(self, rules: list[RuleCheck], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rules = rules
        step = self._SIZE + self._GAP
        self.setFixedSize(max(0, len(rules) * step - self._GAP), self._SIZE)
        self.setToolTip("  ·  ".join(
            r.name if r.passed is None else f"{r.name} {'pass' if r.passed else 'no'}"
            for r in rules
        ))

    def paintEvent(self, event: QPaintEvent | None) -> None:
        _T: Any = active_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for i, rule in enumerate(self._rules):
            colour = _T.TEAL if rule.passed is None else (_T.GREEN if rule.passed else _T.OVERLAY2)
            painter.setBrush(QColor(colour))
            painter.drawRoundedRect(
                QRectF(i * (self._SIZE + self._GAP), 0, self._SIZE, self._SIZE), 2, 2
            )
        painter.end()


# ── View switch ───────────────────────────────────────────────────────────────

class ViewSwitch(QWidget):
    """List / Cards toggle that remembers the choice in ``settings``."""

    view_changed = pyqtSignal(str)

    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        saved = str(settings.value("view", "list"))
        self._view = saved if saved in VIEWS else "list"

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for name, icon_name, tip in (("list", "list", "List view"),
                                     ("cards", "layout-grid", "Cards view")):
            button = QPushButton()
            button.setObjectName("view_btn")
            button.setCheckable(True)
            button.setChecked(name == self._view)
            set_icon(button, icon_name, "neutral", 16)
            button.setFixedWidth(C.BTN_H + 6)
            button.setToolTip(tip)
            button.setAccessibleName(tip)
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _checked=False, n=name: self._select(n))
            self._group.addButton(button)
            self.buttons[name] = button
            row.addWidget(button)

    @property
    def view(self) -> str:
        return self._view

    def _select(self, name: str) -> None:
        if name == self._view:
            return
        self._view = name
        self._settings.setValue("view", name)
        self.view_changed.emit(name)


# ── Preset rail pieces (SRD-GUI-022.007) ─────────────────────────────────────

class ChipGroup(QWidget):
    """Row of exclusive pill buttons; ``value`` is the checked option's value."""

    changed = pyqtSignal()

    def __init__(self, options: list[tuple[str, str | None]],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._values: list[str | None] = []
        self.buttons: list[QPushButton] = []
        for index, (label, value) in enumerate(options):
            button = QPushButton(label)
            button.setObjectName("filter_chip")
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._group.addButton(button, index)
            self._values.append(value)
            self.buttons.append(button)
            row.addWidget(button)
        row.addStretch(1)
        self._group.idClicked.connect(lambda _id: self.changed.emit())

    @property
    def value(self) -> str | None:
        index = self._group.checkedId()
        return self._values[index] if 0 <= index < len(self._values) else None


class PresetItem(QWidget):
    """Preset list entry: name, type tag and last-run line."""

    def __init__(self, name: str, type_tag: str, meta: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preset_item")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        body = QVBoxLayout(self)
        body.setContentsMargins(10, 6, 10, 6)
        body.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.name_lbl = QLabel(name)
        self.name_lbl.setObjectName("preset_name")
        top.addWidget(self.name_lbl, 1)
        self.type_lbl = QLabel(type_tag)
        self.type_lbl.setObjectName("preset_tag")
        top.addWidget(self.type_lbl)
        body.addLayout(top)
        self.meta_lbl = _key_label(meta)
        body.addWidget(self.meta_lbl)

    def set_meta(self, text: str) -> None:
        self.meta_lbl.setText(text)


# ── List + detail view ────────────────────────────────────────────────────────

class _ChartLike(Protocol):
    def show_symbol(self, symbol: str, timeframe: str | None = None) -> None: ...


class _ListRow(QWidget):
    """One line of the ranked list: rank, symbol, score bar, rule dots."""

    def __init__(self, row: ResultRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("result_row")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        _T: Any = active_palette()
        tier_fg, _ = _tier_colours(row.tier)
        line = QHBoxLayout(self)
        line.setContentsMargins(10, 0, 10, 0)
        line.setSpacing(10)
        rank = _mono(str(row.rank), _T.MUTED)
        rank.setFixedWidth(20)
        line.addWidget(rank)
        line.addWidget(_mono(row.symbol, _T.BLUE, "10pt", bold=True), 1)
        score = _mono(f"{row.score:.2f}", tier_fg, bold=True)
        score.setFixedWidth(34)
        line.addWidget(score)
        bar = _ScoreBar(row.score, tier_fg)
        bar.setFixedWidth(64)
        line.addWidget(bar)
        line.addWidget(_RuleDots(row.rules))


class ListDetailView(QWidget):
    """Ranked list on the left, detail of the selected stock on the right."""

    chart_requested = pyqtSignal(str)
    watchlist_requested = pyqtSignal(str)
    selection_changed = pyqtSignal(str)

    def __init__(self, chart_factory: Callable[[], QWidget] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[ResultRow] = []
        self._timeframe = "1d"
        self._chart_factory = chart_factory
        self._chart: QWidget | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.list = QListWidget()
        self.list.setObjectName("result_list")
        self.list.setMinimumWidth(300)
        self.list.setMaximumWidth(380)
        self.list.setSpacing(1)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.currentRowChanged.connect(self._show_row)
        layout.addWidget(self.list)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        detail = QWidget()
        detail.setObjectName("result_detail")
        body = QVBoxLayout(detail)
        body.setContentsMargins(20, 16, 20, 16)
        body.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(10)
        self.symbol_lbl = QLabel()
        self.symbol_lbl.setObjectName("detail_symbol")
        head.addWidget(self.symbol_lbl)
        self._tier_slot = QHBoxLayout()
        head.addLayout(self._tier_slot)
        self.meta_lbl = _key_label("")
        head.addWidget(self.meta_lbl)
        head.addStretch(1)
        self.chart_btn = _action_button("Open chart", "chart-candlestick", "info")
        self.chart_btn.clicked.connect(lambda: self._emit_selected(self.chart_requested))
        head.addWidget(self.chart_btn)
        self.watch_btn = _action_button("Watchlist", "plus", "add")
        self.watch_btn.clicked.connect(lambda: self._emit_selected(self.watchlist_requested))
        head.addWidget(self.watch_btn)
        body.addLayout(head)

        self.chart_slot = QFrame()
        self.chart_slot.setObjectName("chart_slot")
        self.chart_slot.setMinimumHeight(260)
        self._chart_layout = QVBoxLayout(self.chart_slot)
        self._chart_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_slot.setVisible(chart_factory is not None)
        body.addWidget(self.chart_slot)

        tiles = QGridLayout()
        tiles.setSpacing(10)
        self.tiles: dict[str, QLabel] = {}
        for col, (key, title) in enumerate((("entry", "Entry"), ("stop", "Stop"),
                                            ("target", "Target"), ("rr", "Reward : risk"))):
            tile = QFrame()
            tile.setObjectName("detail_tile")
            box = QVBoxLayout(tile)
            box.setContentsMargins(12, 8, 12, 8)
            box.setSpacing(2)
            box.addWidget(_key_label(title))
            value = _mono(_DASH, size="12pt", bold=True)
            box.addWidget(value)
            self.tiles[key] = value
            tiles.addWidget(tile, 0, col)
        body.addLayout(tiles)

        lower = QHBoxLayout()
        lower.setSpacing(24)
        rules_col = QVBoxLayout()
        rules_col.setSpacing(6)
        rules_head = QLabel("RULES")
        rules_head.setObjectName("view_head")
        rules_col.addWidget(rules_head)
        self._rules_box = QVBoxLayout()
        self._rules_box.setSpacing(4)
        rules_col.addLayout(self._rules_box)
        rules_col.addStretch(1)
        lower.addLayout(rules_col, 1)
        why_col = QVBoxLayout()
        why_col.setSpacing(6)
        why_head = QLabel("AI REASONING")
        why_head.setObjectName("view_head")
        why_col.addWidget(why_head)
        self.reasoning_lbl = QLabel()
        self.reasoning_lbl.setWordWrap(True)
        self.reasoning_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        why_col.addWidget(self.reasoning_lbl)
        why_col.addStretch(1)
        lower.addLayout(why_col, 3)
        body.addLayout(lower)
        body.addStretch(1)

        scroll.setWidget(detail)
        layout.addWidget(scroll, 1)

    def load(self, rows: list[ResultRow], timeframe: str = "1d") -> None:
        """Show ``rows`` and select the first one."""
        self._rows = rows
        self._timeframe = timeframe
        self.list.blockSignals(True)
        self.list.clear()
        for row in rows:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 46))
            self.list.addItem(item)
            self.list.setItemWidget(item, _ListRow(row))
        self.list.blockSignals(False)
        if rows:
            self.list.setCurrentRow(0)
        else:
            self._show_row(-1)

    def selected_symbol(self) -> str | None:
        index = self.list.currentRow()
        return self._rows[index].symbol if 0 <= index < len(self._rows) else None

    def _emit_selected(self, signal: Any) -> None:
        symbol = self.selected_symbol()
        if symbol:
            signal.emit(symbol)

    def _show_row(self, index: int) -> None:
        if self._fill_detail(index):
            symbol = self._rows[index].symbol
            self._show_chart(symbol)
            self.selection_changed.emit(symbol)

    def _fill_detail(self, index: int) -> bool:
        """Fill the detail panel for row ``index``; False when there is no such row."""
        if not 0 <= index < len(self._rows):
            self.symbol_lbl.setText("")
            self.meta_lbl.setText("")
            _clear_layout(self._tier_slot)
            _clear_layout(self._rules_box)
            self.reasoning_lbl.setText("")
            for value in self.tiles.values():
                value.setText(_DASH)
            return False
        row = self._rows[index]
        _T: Any = active_palette()
        self.symbol_lbl.setText(row.symbol)
        _clear_layout(self._tier_slot)
        self._tier_slot.addWidget(_tier_chip(row.tier))
        self.meta_lbl.setText(
            f"Rank {row.rank} of {len(self._rows)}  ·  AI score {row.score:.2f}"
            f"  ·  {row.passed_count} of {len(row.rules)} rules"
        )
        self.tiles["entry"].setText(_price_text(row.entry))
        self.tiles["stop"].setText(_price_text(row.stop))
        self.tiles["target"].setText(_price_text(row.target))
        self.tiles["rr"].setText(_rr_text(row))
        _clear_layout(self._rules_box)
        for rule in row.rules:
            self._rules_box.addWidget(self._rule_line(rule, _T))
        self.reasoning_lbl.setText(row.reasoning or "No AI reasoning for this run.")
        return True

    @staticmethod
    def _rule_line(rule: RuleCheck, palette: Any) -> QWidget:
        line = QWidget()
        box = QHBoxLayout(line)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        box.addWidget(_RuleDots([rule]))
        text_clr = palette.MUTED if rule.passed is False else palette.TEXT
        name = QLabel(rule.name)
        name.setStyleSheet(f"color: {text_clr};")
        box.addWidget(name, 1)
        word = rule.value if rule.passed is None else ("Pass" if rule.passed else "No")
        result = QLabel(word)
        result.setStyleSheet(f"color: {text_clr};")
        box.addWidget(result)
        return line

    def _show_chart(self, symbol: str) -> None:
        if self._chart_factory is None:
            return
        if self._chart is None:
            self._chart = self._chart_factory()
            self._chart_layout.addWidget(self._chart)
        chart: _ChartLike = self._chart  # type: ignore[assignment]
        chart.show_symbol(symbol, self._timeframe)

    def changeEvent(self, event: QEvent | None) -> None:
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.StyleChange and self._rows:
            self._restyle()

    def _restyle(self) -> None:
        """Redraw rows and detail in the new theme without reloading the chart."""
        for index, row in enumerate(self._rows):
            item = self.list.item(index)
            if item is not None:
                self.list.setItemWidget(item, _ListRow(row))
        self._fill_detail(self.list.currentRow())


# ── Cards view ────────────────────────────────────────────────────────────────

class _Card(QFrame):
    """Signal card for one stock."""

    chart_requested = pyqtSignal(str)
    watchlist_requested = pyqtSignal(str)

    def __init__(self, row: ResultRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("result_card")
        _T: Any = active_palette()
        tier_fg, _ = _tier_colours(row.tier)
        body = QVBoxLayout(self)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.rank_lbl = _mono(f"#{row.rank}", _T.MUTED)
        head.addWidget(self.rank_lbl)
        self.symbol_lbl = _mono(row.symbol, _T.BLUE, "12pt", bold=True)
        head.addWidget(self.symbol_lbl)
        self.tier_lbl = _tier_chip(row.tier)
        head.addWidget(self.tier_lbl)
        head.addStretch(1)
        head.addWidget(_mono(f"{row.score:.2f}", tier_fg, "14pt", bold=True))
        body.addLayout(head)
        body.addWidget(_ScoreBar(row.score, tier_fg))

        chips = QGridLayout()
        chips.setSpacing(6)
        for i, rule in enumerate(row.rules):
            chips.addWidget(_rule_chip(rule), i // 2, i % 2)
        body.addLayout(chips)

        why = QLabel(row.reasoning or "No AI reasoning for this run.")
        why.setObjectName("view_key")
        why.setWordWrap(True)
        why.setToolTip(row.reasoning)
        why.ensurePolished()
        why.setMaximumHeight(why.fontMetrics().lineSpacing() * 3)
        why.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body.addWidget(why)

        plan = QGridLayout()
        plan.setHorizontalSpacing(8)
        plan.setVerticalSpacing(0)
        for col, (title, text, colour) in enumerate((
            ("Entry", _price_text(row.entry), ""),
            ("Stop", _price_text(row.stop), _T.RED),
            ("Target", _price_text(row.target), _T.GREEN),
            ("R:R", _DASH if row.rr is None else f"{row.rr:.1f}", ""),
        )):
            plan.addWidget(_key_label(title), 0, col)
            plan.addWidget(_mono(text, colour, bold=True), 1, col)
        body.addLayout(plan)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.chart_btn = _action_button("Chart", "chart-candlestick", "info")
        self.chart_btn.clicked.connect(lambda: self.chart_requested.emit(row.symbol))
        actions.addWidget(self.chart_btn)
        self.watch_btn = _action_button("Watchlist", "plus", "add")
        self.watch_btn.clicked.connect(lambda: self.watchlist_requested.emit(row.symbol))
        actions.addWidget(self.watch_btn)
        body.addLayout(actions)


class CardsView(QScrollArea):
    """Grid of signal cards whose column count follows the width."""

    chart_requested = pyqtSignal(str)
    watchlist_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        host.setObjectName("cards_host")
        self._grid = QGridLayout(host)
        self._grid.setContentsMargins(16, 16, 16, 16)
        self._grid.setSpacing(14)
        self.setWidget(host)
        self._rows: list[ResultRow] = []
        self.cards: list[_Card] = []
        self._cols = 0

    def load(self, rows: list[ResultRow]) -> None:
        """Replace the cards with one per row."""
        self._rows = rows
        for card in self.cards:
            card.hide()
            card.setParent(None)
            card.deleteLater()
        self.cards = []
        for row in rows:
            card = _Card(row)
            card.chart_requested.connect(self.chart_requested)
            card.watchlist_requested.connect(self.watchlist_requested)
            self.cards.append(card)
        self._cols = 0
        self._relayout()

    def _relayout(self) -> None:
        viewport = self.viewport()
        width = viewport.width() if viewport is not None else _CARD_MIN_W
        cols = max(1, width // _CARD_MIN_W)
        if cols == self._cols:
            return
        self._cols = cols
        while self._grid.count():
            self._grid.takeAt(0)
        for i, card in enumerate(self.cards):
            self._grid.addWidget(card, i // cols, i % cols, Qt.AlignmentFlag.AlignTop)
        for col in range(cols):
            self._grid.setColumnStretch(col, 1)
        self._grid.setRowStretch((len(self.cards) + cols - 1) // cols, 1)

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        self._relayout()

    def changeEvent(self, event: QEvent | None) -> None:
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.StyleChange and self._rows:
            bar = self.verticalScrollBar()
            position = bar.value() if bar is not None else 0
            self.load(self._rows)
            if bar is not None:
                bar.setValue(position)
