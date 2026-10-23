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

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSettings,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QCursor, QKeyEvent, QPainter, QPaintEvent, QResizeEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.icons import icon, set_icon
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
    name: str = ""

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


def rows_from_result(results: Mapping[str, Mapping[str, Any]],
                     names: Mapping[str, str] | None = None) -> list[ResultRow]:
    """Build ranked rows from ``ScreenerRunResult.results``.

    Args:
        results: Symbol → result metadata (``score``, ``details``, ``ai_reasoning``, ``ai_plan``).
        names: Optional symbol → company name.

    Returns:
        Rows sorted by score, highest first, with ``rank`` set from 1.
    """
    names = names or {}
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
            name=names.get(symbol, ""),
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
    when = _run_time(run_timestamp, tz)
    if when is None:
        return "Not run yet"
    noun = "match" if matches == 1 else "matches"
    if when.date() == today:
        return f"Today {when:%H:%M} · {matches} {noun}"
    return f"{when:%b} {when.day} · {matches} {noun}"


def _run_time(run_timestamp: str | None,
              tz: datetime.tzinfo | None) -> datetime.datetime | None:
    if not run_timestamp:
        return None
    try:
        when = datetime.datetime.fromisoformat(run_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when.astimezone(tz) if when.tzinfo is not None else when


def run_date_text(date_key: str) -> str:
    """Show a saved run date (``2026-10-22``) as ``Oct 22, 2026``; other text is unchanged."""
    try:
        day = datetime.date.fromisoformat(date_key)
    except ValueError:
        return date_key
    return f"{day:%b} {day.day}, {day.year}"


def run_meta_text(count: int, run_timestamp: str | None, ai_ranked: bool,
                  tz: datetime.tzinfo | None = None) -> str:
    """Header line for a run, e.g. ``5 matches · ranked by AI score · run Oct 22, 2026 at 13:18``."""
    noun = "match" if count == 1 else "matches"
    parts = [f"{count} {noun}", "ranked by AI score" if ai_ranked else "ranked by score"]
    when = _run_time(run_timestamp, tz)
    if when is not None:
        parts.append(f"run {when:%b} {when.day}, {when.year} at {when:%H:%M}")
    return " · ".join(parts)


def transcript_pill_text(turns: list[Any], cost_per_1k_in: float,
                         cost_per_1k_out: float) -> str:
    """Pill text such as ``AI transcript · 5 steps · $0.04``; cost is left out without token data."""
    steps = len(turns)
    text = f"AI transcript · {steps} {'step' if steps == 1 else 'steps'}"
    tokens_in = sum(getattr(t, "tokens_input", 0) or 0 for t in turns)
    tokens_out = sum(getattr(t, "tokens_output", 0) or 0 for t in turns)
    if tokens_in or tokens_out:
        cost = (tokens_in * cost_per_1k_in + tokens_out * cost_per_1k_out) / 1000
        text += f" · ${cost:.2f}"
    return text


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
        text, fg = f"{rule.name} {rule.value}", _T.TEXT
    elif rule.passed:
        text, fg = f"✓ {rule.name}", _T.GREEN
    else:
        text, fg = f"✕ {rule.name}", _T.MUTED
    chip = QLabel(text)
    chip.setStyleSheet(
        f"color: {fg}; background: transparent; border: 1px solid {_T.OVERLAY2};"
        " border-radius: 10px; padding: 2px 9px; font-size: 8pt;"
    )
    return chip


def _value_label(text: str, colour: str = "", size: str = "9pt",
                 bold: bool = False) -> QLabel:
    label = QLabel(text)
    weight = "font-weight: bold;" if bold else ""
    tint = f"color: {colour};" if colour else ""
    label.setStyleSheet(f"font-size: {size}; {weight} {tint}")
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


class _RiskRewardBar(QWidget):
    """Stop-to-target bar: risk share in red, reward share in green, entry as a tick."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.risk_share = 0.0
        self.setFixedHeight(6)

    def set_row(self, row: ResultRow) -> None:
        """Show the plan of ``row``; hidden when it has no valid long plan."""
        if row.rr is None or row.entry is None or row.stop is None or row.target is None:
            self.setVisible(False)
            return
        self.risk_share = (row.entry - row.stop) / (row.target - row.stop)
        self.setVisible(True)
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        _T: Any = active_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        width, height = float(self.width()), float(self.height())
        split = width * self.risk_share
        risk, reward = QColor(_T.RED), QColor(_T.GREEN)
        risk.setAlphaF(0.45)
        reward.setAlphaF(0.45)
        painter.setBrush(risk)
        painter.drawRoundedRect(QRectF(0, 0, split, height), 3, 3)
        painter.setBrush(reward)
        painter.drawRoundedRect(QRectF(split, 0, width - split, height), 3, 3)
        painter.setBrush(QColor(_T.TEXT))
        painter.drawRect(QRectF(split - 1, 0, 2, height))
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
        self.setObjectName("seg_group")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(2)
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
            row.addWidget(button, 1)
        self._group.idClicked.connect(lambda _id: self.changed.emit())

    @property
    def value(self) -> str | None:
        index = self._group.checkedId()
        return self._values[index] if 0 <= index < len(self._values) else None


class PresetItem(QWidget):
    """Preset list entry: name and last-run line."""

    def __init__(self, name: str, meta: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preset_item")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        body = QVBoxLayout(self)
        body.setContentsMargins(10, 6, 10, 6)
        body.setSpacing(2)
        self.name_lbl = QLabel(name)
        self.name_lbl.setObjectName("preset_name")
        body.addWidget(self.name_lbl)
        self.meta_lbl = _key_label(meta)
        body.addWidget(self.meta_lbl)

    def set_meta(self, text: str) -> None:
        self.meta_lbl.setText(text)


# ── Page header pieces (SRD-GUI-022.009 / .010) ──────────────────────────────

class RunStepper(QFrame):
    """Older / newer arrows around the run date; the date opens a menu of saved runs.

    ``dates`` are saved run keys, newest first, as ``ScreenerResultsStorage.list_results``
    returns them; ``index`` 0 is the latest run.
    """

    index_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("run_stepper")
        self._dates: list[str] = []
        self._index = 0
        row = QHBoxLayout(self)
        row.setContentsMargins(1, 1, 1, 1)
        row.setSpacing(0)
        self.older_btn = self._arrow("chevron-left", "Older run", +1)
        row.addWidget(self.older_btn)
        self.date_btn = QPushButton("—")
        self.date_btn.setObjectName("stepper_date")
        set_icon(self.date_btn, "calendar", "neutral", 14)
        self.date_btn.setToolTip("Pick a saved run")
        self.date_btn.setAccessibleName("Pick a saved run")
        self.date_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._menu = QMenu(self.date_btn)
        self.date_btn.setMenu(self._menu)
        row.addWidget(self.date_btn)
        self.latest_lbl = QLabel("Latest")
        self.latest_lbl.setObjectName("latest_tag")
        row.addWidget(self.latest_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        self.newer_btn = self._arrow("chevron-right", "Newer run", -1)
        row.addWidget(self.newer_btn)
        self.set_runs([], 0)

    def _arrow(self, name: str, tip: str, step: int) -> QPushButton:
        button = QPushButton()
        button.setObjectName("stepper_btn")
        set_icon(button, name, "neutral", 14)
        button.setFixedWidth(C.BTN_H)
        button.setToolTip(tip)
        button.setAccessibleName(tip)
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.clicked.connect(lambda _checked=False: self._go(self._index + step))
        return button

    @property
    def index(self) -> int:
        return self._index

    def set_runs(self, dates: list[str], index: int = 0) -> None:
        """Show ``dates`` with ``index`` selected; an empty list shows ``—``."""
        self._dates = list(dates)
        self._index = max(0, min(index, len(self._dates) - 1)) if self._dates else 0
        self._menu.clear()
        for i, date in enumerate(self._dates):
            label = run_date_text(date) + ("   Latest" if i == 0 else "")
            action = self._menu.addAction(label)
            if action is not None:
                action.setCheckable(True)
                action.setChecked(i == self._index)
                action.triggered.connect(lambda _checked=False, n=i: self._go(n))
        self._refresh()

    def _go(self, index: int) -> None:
        if not 0 <= index < len(self._dates) or index == self._index:
            return
        self._index = index
        for i, action in enumerate(self._menu.actions()):
            action.setChecked(i == index)
        self._refresh()
        self.index_changed.emit(index)

    def _refresh(self) -> None:
        has_runs = bool(self._dates)
        self.date_btn.setText(run_date_text(self._dates[self._index]) if has_runs else "—")
        self.date_btn.setEnabled(has_runs)
        self.latest_lbl.setVisible(has_runs and self._index == 0)
        self.older_btn.setEnabled(self._index < len(self._dates) - 1)
        self.newer_btn.setEnabled(has_runs and self._index > 0)


class SideDrawer(QFrame):
    """Panel that slides in over the right edge of its parent; Esc or ✕ closes it."""

    WIDTH = 460
    closed = pyqtSignal()

    def __init__(self, title: str, body: QWidget, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("side_drawer")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._open = False
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_slide_done)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(16, 10, 10, 10)
        head.setSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("drawer_title")
        head.addWidget(title_lbl)
        head.addStretch(1)
        self.close_btn = QPushButton()
        set_icon(self.close_btn, "x", "neutral", 14)
        self.close_btn.setFixedWidth(C.BTN_H)
        self.close_btn.setToolTip("Close")
        self.close_btn.setAccessibleName("Close")
        self.close_btn.clicked.connect(self.close_drawer)
        head.addWidget(self.close_btn)
        layout.addLayout(head)
        layout.addWidget(body, 1)
        parent.installEventFilter(self)
        self.hide()

    @property
    def is_open(self) -> bool:
        return self._open

    def open_drawer(self) -> None:
        if not self.isVisible():
            self._place()
        self._open = True
        self.show()
        self.raise_()
        self.setFocus()
        self._slide()

    def close_drawer(self) -> None:
        if not self._open:
            return
        self._open = False
        self._slide()
        self.closed.emit()

    def toggle(self) -> None:
        if self._open:
            self.close_drawer()
        else:
            self.open_drawer()

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if watched is self.parentWidget() and event is not None \
                and event.type() == QEvent.Type.Resize:
            self._place()
        return False

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is not None and event.key() == Qt.Key.Key_Escape:
            self.close_drawer()
            return
        super().keyPressEvent(event)

    def _x(self, opened: bool) -> int:
        parent = self.parentWidget()
        parent_w = parent.width() if parent is not None else 0
        return parent_w - self._width() if opened else parent_w

    def _width(self) -> int:
        parent = self.parentWidget()
        parent_w = parent.width() if parent is not None else 0
        return min(self.WIDTH, parent_w) if parent_w > 0 else self.WIDTH

    def _place(self) -> None:
        """Snap to the open or closed spot; a resize mid-slide ends the slide there."""
        parent = self.parentWidget()
        if parent is None:
            return
        self._anim.stop()
        self.setGeometry(self._x(self._open), 0, self._width(), parent.height())
        self._on_slide_done()

    def _slide(self) -> None:
        self._anim.stop()
        parent = self.parentWidget()
        self.resize(self._width(), parent.height() if parent is not None else self.height())
        self._anim.setEndValue(QPoint(self._x(self._open), 0))
        self._anim.start()

    def _on_slide_done(self) -> None:
        if not self._open:
            self.hide()


# ── List + detail view ────────────────────────────────────────────────────────

class _ChartLike(Protocol):
    def show_symbol(self, symbol: str, timeframe: str | None = None) -> None: ...


class _ListRow(QWidget):
    """One line of the ranked list: rank, symbol and company, score bar, rules passed."""

    def __init__(self, row: ResultRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("result_row")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        _T: Any = active_palette()
        tier_fg, _ = _tier_colours(row.tier)
        line = QHBoxLayout(self)
        line.setContentsMargins(10, 0, 12, 0)
        line.setSpacing(10)
        rank = _value_label(str(row.rank), _T.MUTED)
        rank.setFixedWidth(18)
        line.addWidget(rank)
        names = QVBoxLayout()
        names.setSpacing(0)
        symbol = QLabel(row.symbol)
        symbol.setObjectName("row_symbol")
        names.addWidget(symbol)
        if row.name:
            company = _key_label(row.name)
            company.setToolTip(row.name)
            names.addWidget(company)
        line.addLayout(names, 1)
        score = _value_label(f"{row.score:.2f}", bold=True)
        score.setFixedWidth(32)
        line.addWidget(score)
        bar = _ScoreBar(row.score, tier_fg)
        bar.setFixedWidth(60)
        line.addWidget(bar)
        rules = _value_label(f"{row.passed_count}/{len(row.rules)}", _T.SUBTEXT)
        rules.setFixedWidth(30)
        rules.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        line.addWidget(rules)


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
        self.list.setMinimumWidth(320)
        self.list.setMaximumWidth(400)
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
        body.setContentsMargins(24, 18, 24, 18)
        body.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(10)
        title = QVBoxLayout()
        title.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(10)
        self.symbol_lbl = QLabel()
        self.symbol_lbl.setObjectName("detail_symbol")
        top.addWidget(self.symbol_lbl)
        self._tier_slot = QHBoxLayout()
        top.addLayout(self._tier_slot)
        top.addStretch(1)
        title.addLayout(top)
        self.meta_lbl = _key_label("")
        title.addWidget(self.meta_lbl)
        head.addLayout(title, 1)
        self.chart_btn = _action_button("Open in Charts", "chart-candlestick", "info")
        self.chart_btn.clicked.connect(lambda: self._emit_selected(self.chart_requested))
        head.addWidget(self.chart_btn)
        self.watch_btn = _action_button("Add to watchlist", "plus", "add")
        self.watch_btn.clicked.connect(lambda: self._emit_selected(self.watchlist_requested))
        head.addWidget(self.watch_btn)
        body.addLayout(head)

        self.chart_slot = QFrame()
        self.chart_slot.setObjectName("chart_slot")
        self.chart_slot.setMinimumHeight(260)
        self._chart_layout = QVBoxLayout(self.chart_slot)
        self._chart_layout.setContentsMargins(1, 1, 1, 1)
        self.chart_slot.setVisible(chart_factory is not None)
        body.addWidget(self.chart_slot)

        plan = QFrame()
        plan.setObjectName("detail_plan")
        plan_box = QVBoxLayout(plan)
        plan_box.setContentsMargins(16, 12, 16, 12)
        plan_box.setSpacing(10)
        values = QGridLayout()
        values.setHorizontalSpacing(12)
        values.setVerticalSpacing(2)
        self.tiles: dict[str, QLabel] = {}
        for col, (key, caption) in enumerate((("stop", "Stop"), ("entry", "Entry"),
                                              ("target", "Target"), ("rr", "Reward : risk"))):
            values.addWidget(_key_label(caption), 0, col)
            value = _value_label(_DASH, size="13pt", bold=True)
            values.addWidget(value, 1, col)
            values.setColumnStretch(col, 1)
            self.tiles[key] = value
        plan_box.addLayout(values)
        self.rr_bar = _RiskRewardBar()
        plan_box.addWidget(self.rr_bar)
        amounts = QHBoxLayout()
        self.risk_lbl = _key_label("")
        amounts.addWidget(self.risk_lbl)
        amounts.addStretch(1)
        self.reward_lbl = _key_label("")
        amounts.addWidget(self.reward_lbl)
        plan_box.addLayout(amounts)
        body.addWidget(plan)

        lower = QHBoxLayout()
        lower.setSpacing(24)
        rules_col = QVBoxLayout()
        rules_col.setSpacing(6)
        self.rules_head = QLabel("RULES")
        self.rules_head.setObjectName("view_head")
        rules_col.addWidget(self.rules_head)
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
            item.setSizeHint(QSize(0, 50))
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
        _T: Any = active_palette()
        _clear_layout(self._tier_slot)
        _clear_layout(self._rules_box)
        if not 0 <= index < len(self._rows):
            self.symbol_lbl.setText("")
            self.meta_lbl.setText("")
            self.reasoning_lbl.setText("")
            self.rules_head.setText("RULES")
            for value in self.tiles.values():
                value.setText(_DASH)
            self.rr_bar.setVisible(False)
            self.risk_lbl.setText("")
            self.reward_lbl.setText("")
            return False
        row = self._rows[index]
        self.symbol_lbl.setText(row.symbol)
        self._tier_slot.addWidget(_tier_chip(row.tier))
        parts = [row.name] if row.name else []
        parts += [f"rank {row.rank} of {len(self._rows)}", f"AI score {row.score:.2f}"]
        self.meta_lbl.setText(" · ".join(parts))
        self._fill_plan(row, _T)
        self.rules_head.setText(f"RULES · {row.passed_count} OF {len(row.rules)}")
        for rule in row.rules:
            self._rules_box.addWidget(self._rule_line(rule, _T))
        self.reasoning_lbl.setText(row.reasoning or "No AI reasoning for this run.")
        return True

    def _fill_plan(self, row: ResultRow, palette: Any) -> None:
        for key, text, colour in (("stop", _price_text(row.stop), palette.RED),
                                  ("entry", _price_text(row.entry), ""),
                                  ("target", _price_text(row.target), palette.GREEN),
                                  ("rr", _rr_text(row), "")):
            label = self.tiles[key]
            label.setText(text)
            tint = f"color: {colour};" if colour and text != _DASH else ""
            label.setStyleSheet(f"font-size: 13pt; font-weight: bold; {tint}")
        self.rr_bar.set_row(row)
        entry, stop, target = row.entry, row.stop, row.target
        if row.rr is not None and entry is not None and stop is not None and target is not None:
            self.risk_lbl.setText(f"Risk ${entry - stop:,.2f} per share")
            self.reward_lbl.setText(f"Reward ${target - entry:,.2f} per share")
        else:
            self.risk_lbl.setText("No trade plan from the AI for this stock")
            self.reward_lbl.setText("")

    @staticmethod
    def _rule_line(rule: RuleCheck, palette: Any) -> QWidget:
        line = QWidget()
        box = QHBoxLayout(line)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        mark = QLabel()
        if rule.passed is not None:
            name, role = ("check", "add") if rule.passed else ("x", "neutral")
            mark.setPixmap(icon(name, role).pixmap(14, 14))
            mark.setAccessibleName("Passed" if rule.passed else "Not passed")
        mark.setFixedWidth(14)
        box.addWidget(mark)
        text_clr = palette.MUTED if rule.passed is False else palette.TEXT
        label = QLabel(rule.name)
        label.setStyleSheet(f"color: {text_clr};")
        box.addWidget(label, 1)
        if rule.passed is None:
            box.addWidget(QLabel(rule.value))
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
        self.rank_lbl = _value_label(f"#{row.rank}", _T.MUTED)
        head.addWidget(self.rank_lbl)
        self.symbol_lbl = QLabel(row.symbol)
        self.symbol_lbl.setObjectName("card_symbol")
        head.addWidget(self.symbol_lbl)
        self.tier_lbl = _tier_chip(row.tier)
        head.addWidget(self.tier_lbl)
        head.addStretch(1)
        head.addWidget(_value_label(f"{row.score:.2f}", tier_fg, "14pt", bold=True))
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
            plan.addWidget(_value_label(text, colour, bold=True), 1, col)
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
