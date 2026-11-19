"""
Module: MD-GUI-022.001.M01 — Screener result views
Parent SRD: SRD-GUI-022.001, SRD-GUI-022.017, SRD-GUI-022.019, SRD-GUI-043.003

Result rows, sorting and CSV rows, and the List + detail view shown by the
screener panel (FO-GUI-022). The list sits in the panel's left pane (FO-GUI-043).
"""
from __future__ import annotations

import datetime
import html
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSettings,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QCursor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.stock_context import (
    StockContext,
    earnings_when,
    fundamentals_text,
    short_text,
    surprise_text,
)
from us_swing.data.market_calendar import ET
from us_swing.gui.icons import icon, icon_button, set_icon
from us_swing.gui.theme import C, active_palette, colors

STRONG_MIN = 0.70
WATCH_MIN = 0.40
SORT_KEYS: tuple[tuple[str, str], ...] = (
    ("score", "AI score"),
    ("rr", "Reward : risk"),
    ("rules", "Rules passed"),
)
CSV_HEADER = ["Symbol", "Score", "Details", "AI Reasoning", "Entry", "Stop", "Target", "R:R"]

_DASH = "—"
_RULE_NAME_W = 160
_TABS_H = 200
_TABS_MIN_H = 110
STOCK_ROW_H = 30
_TAB_RULES, _TAB_NEWS, _TAB_FUNDAMENTALS, _TAB_REVIEW = 1, 2, 3, 4
_SESSION_CLOSE = datetime.time(16, 0)
_ONE_DAY = datetime.timedelta(days=1)


# ── Rows ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RuleCheck:
    """One preset rule result for a stock; ``passed`` is None for a numeric value."""

    name: str
    passed: bool | None
    value: str = ""
    tip: str = ""


@dataclass(frozen=True)
class ContextChip:
    """One AI context line shown as a chip; ``level`` is red, yellow, green or ""."""

    text: str
    level: str = ""


_MARKET_LEVELS = {"risk-on": "green", "risk-off": "red", "mixed": "yellow"}


def _context_chips(context: Any) -> list[ContextChip]:
    """Earnings, sector and market chips from a saved ``ai_context`` (SRD-GUI-022.017)."""
    if not isinstance(context, Mapping):
        return []
    chips: list[ContextChip] = []
    days = context.get("earnings_days")
    if isinstance(days, int):
        when = context.get("earnings_date", "")
        try:
            shown = datetime.date.fromisoformat(when).strftime(" · %d %b")
        except (TypeError, ValueError):
            shown = ""
        chips.append(ContextChip(f"Earnings {earnings_when(days)}{shown}",
                                 str(context.get("earnings_level", ""))))
    surprise = context.get("eps_surprise_pct")
    if isinstance(surprise, (int, float)):
        chips.append(ContextChip(f"EPS {surprise_text(surprise)}",
                                 _shown_level(context.get("surprise_level"))))
    rank, move = context.get("sector_rank"), context.get("sector_move_pct")
    if isinstance(rank, int) and isinstance(move, (int, float)):
        level = str(context.get("sector_level", ""))
        chips.append(ContextChip(
            f"{context.get('sector', '')} #{rank} of {context.get('sector_count', '')}"
            f" · {move:+.1f}% vs RSP", "" if level == "neutral" else level))
    news = context.get("news") or []
    tone = context.get("news_tone")
    count = f"{len(news)} headline{'' if len(news) == 1 else 's'}"
    if isinstance(tone, (int, float)):
        level = str(context.get("news_level", ""))
        chips.append(ContextChip(f"News tone {tone:+.1f} · {count}",
                                 "" if level == "neutral" else level))
    elif news:
        chips.append(ContextChip(count))
    chips += _company_chips(context)
    market = str(context.get("market", ""))
    if market in _MARKET_LEVELS:
        chips.append(ContextChip(f"Market {market}", _MARKET_LEVELS[market]))
    return chips


def _shown_level(level: Any) -> str:
    return "" if level in (None, "neutral") else str(level)


def _company_chips(context: Mapping[str, Any]) -> list[ContextChip]:
    """Fundamentals, short interest and analyst tags (SRD-GUI-022.021)."""
    chips: list[ContextChip] = []
    pe, growth = context.get("pe"), context.get("revenue_growth_pct")
    parts = [f"P/E {pe:.0f}" if isinstance(pe, (int, float)) else "",
             f"Rev {growth:+.0f}%" if isinstance(growth, (int, float)) else ""]
    if any(parts):
        chips.append(ContextChip(" · ".join(part for part in parts if part)))
    short = context.get("short_pct")
    if isinstance(short, (int, float)):
        chips.append(ContextChip(f"Short {short:.0f}% of float",
                                 _shown_level(context.get("short_level"))))
    actions = [str(c.get("action", "")) for c in context.get("analyst_changes") or []
               if isinstance(c, Mapping)]
    ups, downs = actions.count("up"), actions.count("down")
    if ups or downs:
        chips.append(ContextChip(f"Analysts {ups} up · {downs} down",
                                 _shown_level(context.get("analyst_level"))))
    return chips


def _fundamentals_line(context: Any) -> str:
    """"revenue growth +62%, ... · short 1.1% of float, ..." from a saved ``ai_context``."""
    if not isinstance(context, Mapping):
        return ""
    numbers = {key: context.get(key) for key in (
        "revenue_growth_pct", "margin_pct", "pe", "debt_to_equity", "short_pct", "days_to_cover")}
    known: dict[str, Any] = {k: v for k, v in numbers.items() if isinstance(v, (int, float))}
    ctx = StockContext(**known)
    text = " · ".join(part for part in (fundamentals_text(ctx), short_text(ctx)) if part)
    return text[:1].upper() + text[1:]


_ACTION_WORDS = {"up": "upgrade to", "down": "downgrade to", "main": "kept at",
                 "init": "started at", "reit": "repeated"}


def _analyst_lines(context: Any) -> list[str]:
    """One line per saved analyst change, then the average target (SRD-GUI-022.021)."""
    if not isinstance(context, Mapping):
        return []
    lines = []
    for change in context.get("analyst_changes") or []:
        if not isinstance(change, Mapping):
            continue
        try:
            day = datetime.date.fromisoformat(str(change.get("day", ""))).strftime("%d %b")
        except ValueError:
            day = ""
        action = str(change.get("action", ""))
        words = f"{_ACTION_WORDS.get(action, action)} {change.get('grade', '')}".strip()
        target = change.get("target")
        tail = f" · target {target:.0f}" if isinstance(target, (int, float)) else ""
        lines.append(" · ".join(p for p in (day, str(change.get("firm", "")), words) if p) + tail)
    target_pct = context.get("analyst_target_pct")
    if isinstance(target_pct, (int, float)):
        lines.append(f"Average target {target_pct:+.0f}% vs price")
    return lines


def _saved_news(context: Any) -> list[Mapping[str, Any]]:
    news = context.get("news") if isinstance(context, Mapping) else None
    return [item for item in news or [] if isinstance(item, Mapping)]


def _news_html(item: Mapping[str, Any], link_colour: str) -> str:
    """One headline as rich text: linked title, then source and day (SRD-GUI-022.019)."""
    title = html.escape(str(item.get("title", "")))
    url = html.escape(str(item.get("url", "")), quote=True)
    try:
        day = datetime.date.fromisoformat(str(item.get("published", ""))[:10]).strftime("%d %b")
    except ValueError:
        day = ""
    head = f'<a href="{url}" style="color:{link_colour};">{title}</a>' if url else title
    tail = " · ".join(part for part in (html.escape(str(item.get("source", ""))), day) if part)
    return f"{head} — {tail}" if tail else head


def _source_links(sources: Iterable[Any], link_colour: str) -> str:
    links = []
    for url in sources:
        host = urlparse(str(url)).netloc.removeprefix("www.")
        if host:
            safe = html.escape(str(url), quote=True)
            links.append(f'<a href="{safe}" style="color:{link_colour};">{html.escape(host)} ↗</a>')
    return "  ·  ".join(links)


# Saved detail key → (shown name, unit, tooltip) for screeners that report numbers.
_DETAIL_NAMES: dict[str, tuple[str, str, str]] = {
    "RallyVol": ("Rally volume", "×",
                 "Average volume on rally days, compared with normal volume"),
    "DropVol": ("Drop volume", "×",
                "Average volume on drop days, compared with normal volume"),
    "UD": ("Up/down ratio", "",
           "Volume on rally days ÷ volume on drop days. "
           "Below 1: sellers heavier. Above 1: buyers heavier"),
}


@dataclass
class ResultRow:
    """One screener result, shown in the stock list and the detail."""

    symbol: str
    score: float
    rank: int = 0
    rules: list[RuleCheck] = field(default_factory=list)
    reasoning: str = ""
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    name: str = ""
    sector: str = ""
    chips: list[ContextChip] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    news: list[Mapping[str, Any]] = field(default_factory=list)
    research: Mapping[str, Any] = field(default_factory=dict)
    fundamentals: str = ""
    analysts: list[str] = field(default_factory=list)
    review: Mapping[str, Any] = field(default_factory=dict)

    @property
    def flag_text(self) -> str:
        """"⚑ 2" style count, or empty when the stock has no red flags."""
        return f"⚑ {len(self.flags)}" if self.flags else ""

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
    def rule_count(self) -> int:
        """Number of pass/fail rules; numeric details are not counted."""
        return sum(1 for rule in self.rules if rule.passed is not None)

    @property
    def rules_text(self) -> str:
        """"2/3" style count, or empty when the stock has no pass/fail rules."""
        return f"{self.passed_count}/{self.rule_count}" if self.rule_count else ""

    @property
    def details_text(self) -> str:
        """Compact rule text, as the old Details column showed it."""
        parts = [
            f"{r.name}:{r.value}" if r.passed is None else f"{r.name}:{'✔' if r.passed else '✘'}"
            for r in self.rules
        ]
        return "  ·  ".join(parts) or _DASH


def _rule_check(key: str, value: Any) -> RuleCheck:
    known = _DETAIL_NAMES.get(key)
    if known and isinstance(value, (int, float)) and not isinstance(value, bool):
        name, unit, tip = known
        return RuleCheck(name, None, f"{float(value):.2f}{unit}", tip)
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
                     names: Mapping[str, str] | None = None,
                     sectors: Mapping[str, str] | None = None) -> list[ResultRow]:
    """Build ranked rows from ``ScreenerRunResult.results``.

    Args:
        results: Symbol → result metadata (``score``, ``details``, ``ai_reasoning``, ``ai_plan``).
        names: Optional symbol → company name.
        sectors: Optional symbol → sector name.

    Returns:
        Rows sorted by score, highest first, with ``rank`` set from 1.
    """
    names = names or {}
    sectors = sectors or {}
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
            sector=sectors.get(symbol, ""),
            chips=_context_chips(meta.get("ai_context")),
            flags=[str(flag) for flag in meta.get("ai_flags") or []],
            news=_saved_news(meta.get("ai_context")),
            research=meta.get("ai_research") or {},
            fundamentals=_fundamentals_line(meta.get("ai_context")),
            analysts=_analyst_lines(meta.get("ai_context")),
            review=meta.get("ai_review") or {},
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


def _bar_date(bar: Mapping[str, Any]) -> datetime.date:
    return datetime.datetime.fromtimestamp(int(bar["time"]), tz=datetime.timezone.utc).date()


def plan_start_index(run_timestamp: str | None,
                     bars: Sequence[Mapping[str, Any]]) -> int | None:
    """Index of the first daily bar after the run's last completed session (SRD-GUI-022.011).

    A session is completed once the market closes at 16:00 New York time, so a
    Sunday run starts on Monday and a pre-market run starts on the same day.
    Returns None when the run time is unknown or no such bar exists yet.
    """
    when = _run_time(run_timestamp, ET)
    if when is None or when.tzinfo is None:
        return None
    last_done = when.date() if when.time() >= _SESSION_CLOSE else when.date() - _ONE_DAY
    return next((i for i, bar in enumerate(bars) if _bar_date(bar) > last_done), None)


def plan_outcome(bars: Sequence[Mapping[str, Any]], start: int, entry: float, stop: float,
                 target: float) -> tuple[str, datetime.date | None]:
    """What a long plan did from ``bars[start]`` on (SRD-GUI-022.011).

    The plan is entered when a bar reaches ``entry`` from the side of the last
    close before ``start``, a gap past it included. After entry the first bar
    reaching ``stop`` or ``target`` decides; a bar reaching both counts as stop.

    Returns:
        ``("not_entered" | "open", None)`` or ``("stop" | "target", bar date)``.
    """
    ref = float(bars[start - 1]["close"] if start > 0 else bars[start]["open"])
    entered = False
    for bar in bars[start:]:
        low, high = float(bar["low"]), float(bar["high"])
        if not entered:
            entered = low <= entry if ref >= entry else high >= entry
            if not entered:
                continue
        if low <= stop:
            return "stop", _bar_date(bar)
        if high >= target:
            return "target", _bar_date(bar)
    return ("open" if entered else "not_entered"), None


def outcome_text(outcome: tuple[str, datetime.date | None]) -> str:
    """Tag text, e.g. ``Target hit 30 Oct``."""
    status, day = outcome
    if day is not None:
        return f"{'Target' if status == 'target' else 'Stop'} hit {day.day} {day:%b}"
    return "Open" if status == "open" else "Not entered"


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


_LEVEL_TIERS = {"green": "Strong", "yellow": "Watch", "red": "Weak"}


def _context_chip(chip: ContextChip) -> QLabel:
    """Tag styled like the Strong / Watch / Weak tier tag; neutral levels use a grey tag."""
    _T: Any = active_palette()
    tier = _LEVEL_TIERS.get(chip.level)
    fg, bg = _tier_colours(tier) if tier else (_T.SUBTEXT, _T.OVERLAY)
    label = QLabel(chip.text)
    label.setAccessibleName(chip.text)
    label.setStyleSheet(
        f"color: {fg}; background: {bg}; border-radius: 3px; padding: 1px 7px;"
        " font-size: 8pt; font-weight: bold;"
    )
    return label


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


class _FlowLayout(QLayout):
    """Left-to-right layout that wraps its widgets onto more lines when space runs out."""

    def __init__(self, spacing: int = 6) -> None:
        super().__init__()
        self._items: list[QLayoutItem] = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: QLayoutItem | None) -> None:  # noqa: N802 — Qt override
        if item is not None:
            self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 — Qt override
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 — Qt override
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802 — Qt override
        return Qt.Orientation.Horizontal

    def hasHeightForWidth(self) -> bool:  # noqa: N802 — Qt override
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 — Qt override
        return self._arrange(QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 — Qt override
        super().setGeometry(rect)
        self._arrange(rect, move=True)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 — Qt override
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _arrange(self, outer: QRect, move: bool) -> int:
        m = self.contentsMargins()
        rect = outer.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = rect.x(), rect.y(), 0
        gap = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and line_h > 0:
                x, y, line_h = rect.x(), y + line_h + gap, 0
            if move:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + gap
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + m.top() + m.bottom()


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


# ── Run stepper and drawer (SRD-GUI-022.009 / .010) ──────────────────────────

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

    @property
    def candles(self) -> list[dict[str, Any]]: ...

    def set_plan(self, plan: tuple[float, float, float] | None,
                 start: int | None = None) -> None: ...


def _detail_settings() -> QSettings:
    """Settings store for the stock detail tabs height (SRD-GUI-043.012)."""
    return QSettings("USSwing", "ScreenerDetail")


class _DragBar(QFrame):
    """Thin bar the user drags up or down; reports the move since the press."""

    moved = pyqtSignal(int)
    released = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("drag_bar")
        self.setFixedHeight(6)
        self.setCursor(Qt.CursorShape.SplitVCursor)
        self.setToolTip("Drag to resize")
        self._press_y: float | None = None

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        _T: Any = active_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_T.OVERLAY2))
        painter.drawRoundedRect((self.width() - 40) // 2, (self.height() - 3) // 2, 40, 3, 1.5, 1.5)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._press_y = event.globalPosition().y()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and self._press_y is not None:
            self.moved.emit(round(event.globalPosition().y() - self._press_y))

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if self._press_y is not None:
            self._press_y = None
            self.released.emit()


class _ScoreBar(QWidget):
    """Thin bar filled to the score, in the tier colour (SRD-GUI-044.004)."""

    def __init__(self, score: float, colour: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fill = max(0.0, min(1.0, score))
        self._colour = QColor(colour)
        self.setFixedSize(46, 4)

    def paintEvent(self, event: QPaintEvent | None) -> None:
        _T: Any = active_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_T.OVERLAY))
        painter.drawRoundedRect(self.rect(), 2, 2)
        if self._fill > 0:
            painter.setBrush(self._colour)
            painter.drawRoundedRect(0, 0, max(4, round(self.width() * self._fill)),
                                    self.height(), 2, 2)
        painter.end()


class _ListRow(QWidget):
    """One-line stock row: symbol, company, score bar and red flags (SRD-GUI-044.004)."""

    def __init__(self, row: ResultRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("result_row")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        _T: Any = active_palette()
        tier_fg, _ = _tier_colours(row.tier)
        line = QHBoxLayout(self)
        line.setContentsMargins(8, 0, 6, 0)
        line.setSpacing(8)
        self.symbol_lbl = QLabel(row.symbol)
        self.symbol_lbl.setObjectName("row_symbol")
        self.symbol_lbl.setFixedWidth(44)
        line.addWidget(self.symbol_lbl)
        company = _key_label(row.name)
        company.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        line.addWidget(company, 1)
        self.score_bar = _ScoreBar(row.score, tier_fg)
        line.addWidget(self.score_bar)
        self.flag_lbl = _value_label(row.flag_text, _T.RED, "8pt", bold=True)
        self.flag_lbl.setFixedWidth(22)
        self.flag_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        line.addWidget(self.flag_lbl)


def _tab_page(parts: Sequence[QWidget | QLayout]) -> QScrollArea:
    """Frameless scroll page holding ``parts`` from the top down."""
    page = QWidget()
    page.setObjectName("result_detail")
    box = QVBoxLayout(page)
    box.setContentsMargins(0, 0, 8, 0)
    box.setSpacing(6)
    for part in parts:
        if isinstance(part, QLayout):
            box.addLayout(part)
        else:
            box.addWidget(part)
    box.addStretch(1)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(page)
    return scroll


class ListDetailView(QWidget):
    """Ranked stock list and the detail of the selected stock.

    The panel moves the list into its left pane (``detach_list``); the detail is a
    header, plan strip, chart and tabs (SRD-GUI-043.007–.010).
    """

    chart_requested = pyqtSignal(str)
    watchlist_requested = pyqtSignal(str)
    selection_changed = pyqtSignal(str)

    def __init__(self, chart_factory: Callable[[], QWidget] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[ResultRow] = []
        self._timeframe = "1d"
        self._run_timestamp: str | None = None
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
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.currentRowChanged.connect(self._show_row)
        layout.addWidget(self.list)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        detail = QWidget()
        detail.setObjectName("result_detail")
        self._body = QVBoxLayout(detail)
        self._body.setContentsMargins(24, 18, 24, 18)
        self._body.setSpacing(14)
        self._body.addLayout(self._build_header())
        self._body.addWidget(self._build_plan())

        self.chart_slot = QFrame()
        self.chart_slot.setObjectName("chart_slot")
        self.chart_slot.setMinimumHeight(260)
        self._chart_layout = QVBoxLayout(self.chart_slot)
        self._chart_layout.setContentsMargins(1, 1, 1, 1)
        if chart_factory is None:
            self.chart_slot.hide()
        self._body.addWidget(self.chart_slot, 1)
        self.tabs_bar = _DragBar()
        self.tabs_bar.moved.connect(self._drag_tabs)
        self.tabs_bar.released.connect(self._save_tabs_height)
        self._body.addWidget(self.tabs_bar)
        self._body.addWidget(self._build_tabs())
        self._hide_company_sections()

        scroll.setWidget(detail)
        layout.addWidget(scroll, 1)

    def _build_header(self) -> QVBoxLayout:
        """Symbol, tier and context chips, previous / next, actions, meta line."""
        top = QHBoxLayout()
        top.setSpacing(10)
        self.symbol_lbl = QLabel()
        self.symbol_lbl.setObjectName("detail_symbol")
        top.addWidget(self.symbol_lbl, 0, Qt.AlignmentFlag.AlignTop)
        self._tier_slot = QHBoxLayout()
        self._tier_slot.setContentsMargins(0, 7, 0, 0)
        top.addLayout(self._tier_slot)
        self._chips_box = _FlowLayout(spacing=6)
        self._chips_box.setContentsMargins(0, 7, 0, 0)
        top.addLayout(self._chips_box, 1)
        self.prev_btn = icon_button("chevron-up", "neutral", "Previous stock")
        self.prev_btn.setFixedWidth(C.BTN_H)
        self.prev_btn.clicked.connect(lambda: self._step(-1))
        top.addWidget(self.prev_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.next_btn = icon_button("chevron-down", "neutral", "Next stock")
        self.next_btn.setFixedWidth(C.BTN_H)
        self.next_btn.clicked.connect(lambda: self._step(1))
        top.addWidget(self.next_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.chart_btn = _action_button("Open in Charts", "chart-candlestick", "info")
        self.chart_btn.clicked.connect(lambda: self._emit_selected(self.chart_requested))
        top.addWidget(self.chart_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.watch_btn = _action_button("Add to watchlist", "plus", "add")
        self.watch_btn.clicked.connect(lambda: self._emit_selected(self.watchlist_requested))
        top.addWidget(self.watch_btn, 0, Qt.AlignmentFlag.AlignTop)

        head = QVBoxLayout()
        head.setSpacing(2)
        head.addLayout(top)
        self.meta_lbl = _key_label("")
        head.addWidget(self.meta_lbl)
        return head

    def _build_plan(self) -> QFrame:
        """Stop, Entry, Target and Reward : risk strip with the risk bar (SRD-GUI-043.008)."""
        plan = QFrame()
        plan.setObjectName("detail_plan")
        plan_box = QVBoxLayout(plan)
        plan_box.setContentsMargins(16, 10, 16, 10)
        plan_box.setSpacing(8)
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
        self.outcome_lbl = QLabel()
        self.outcome_lbl.setObjectName("plan_outcome")
        self.outcome_lbl.setVisible(False)
        amounts.addWidget(self.outcome_lbl)
        amounts.addStretch(1)
        self.reward_lbl = _key_label("")
        amounts.addWidget(self.reward_lbl)
        plan_box.addLayout(amounts)
        return plan

    def _build_tabs(self) -> QWidget:
        """Tabs that show one long detail section at a time (SRD-GUI-043.010)."""
        self.tabs = QTabBar()
        self.tabs.setObjectName("detail_tabs")
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self._pages = QStackedWidget()
        self.tabs.currentChanged.connect(self._pages.setCurrentIndex)

        self.reasoning_lbl = QLabel()
        self.reasoning_lbl.setWordWrap(True)
        self.reasoning_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.rules_head = QLabel("RULES")
        self.rules_head.setObjectName("view_head")
        self._rules_box = QVBoxLayout()
        self._rules_box.setSpacing(4)
        self.flags_head = QLabel("RED FLAGS")
        self.flags_head.setObjectName("view_head")
        self.flags_head.hide()
        self._flags_box = QVBoxLayout()
        self._flags_box.setSpacing(4)

        self.news_head = QLabel("NEWS, LAST 5 DAYS")
        self.news_head.setObjectName("view_head")
        self.news_head.hide()
        self._news_box = QVBoxLayout()
        self._news_box.setSpacing(4)
        self.research_box = QFrame()
        self.research_box.setObjectName("detail_plan")
        research_vl = QVBoxLayout(self.research_box)
        research_vl.setContentsMargins(16, 12, 16, 12)
        research_vl.setSpacing(6)
        research_head = QLabel("WEB RESEARCH")
        research_head.setObjectName("view_head")
        research_vl.addWidget(research_head)
        self.research_lbl = QLabel()
        self.research_lbl.setWordWrap(True)
        self.research_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        research_vl.addWidget(self.research_lbl)
        self.research_links = QLabel()
        self.research_links.setTextFormat(Qt.TextFormat.RichText)
        self.research_links.setOpenExternalLinks(True)
        research_vl.addWidget(self.research_links)
        self.research_box.hide()

        self.fundamentals_head = QLabel("FUNDAMENTALS")
        self.fundamentals_head.setObjectName("view_head")
        self.fundamentals_lbl = QLabel()
        self.fundamentals_lbl.setWordWrap(True)
        self.analysts_head = QLabel("ANALYST CHANGES, LAST 30 DAYS")
        self.analysts_head.setObjectName("view_head")
        self._analysts_box = QVBoxLayout()
        self._analysts_box.setSpacing(4)

        self.review_box = QFrame()
        review_vl = QVBoxLayout(self.review_box)
        review_vl.setContentsMargins(0, 0, 0, 0)
        review_vl.setSpacing(6)
        self.review_bull_lbl = QLabel()
        self.review_bear_lbl = QLabel()
        self.review_verdict_lbl = QLabel()
        for label in (self.review_bull_lbl, self.review_bear_lbl):
            label.setTextFormat(Qt.TextFormat.RichText)
        for label in (self.review_bull_lbl, self.review_bear_lbl, self.review_verdict_lbl):
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            review_vl.addWidget(label)
        self.review_box.hide()

        sections: list[tuple[str, list[QWidget | QLayout]]] = [
            ("AI reasoning", [self.reasoning_lbl]),
            ("Rules", [self.rules_head, self._rules_box, self.flags_head, self._flags_box]),
            ("News", [self.news_head, self._news_box, self.research_box]),
            ("Fundamentals", [self.fundamentals_head, self.fundamentals_lbl,
                              self.analysts_head, self._analysts_box]),
            ("Bull vs bear", [self.review_box]),
        ]
        for title, parts in sections:
            self.tabs.addTab(title)
            self._pages.addWidget(_tab_page(parts))

        box = QWidget()
        saved = _detail_settings().value("tabs_height", _TABS_H, type=int)
        box.setFixedHeight(max(_TABS_MIN_H, int(saved or _TABS_H)))
        self._tabs_box = box
        self._drag_start_h = box.height()
        vl = QVBoxLayout(box)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(8)
        vl.addWidget(self.tabs)
        vl.addWidget(self._pages, 1)
        return box

    def _drag_tabs(self, dy: int) -> None:
        """Dragging the bar up makes the tabs taller (SRD-GUI-043.012)."""
        detail = self._tabs_box.parentWidget()
        top = int(detail.height() * 0.7) if detail is not None else _TABS_MIN_H
        self._tabs_box.setFixedHeight(
            max(_TABS_MIN_H, min(max(top, _TABS_MIN_H), self._drag_start_h - dy)))

    def _save_tabs_height(self) -> None:
        self._drag_start_h = self._tabs_box.height()
        _detail_settings().setValue("tabs_height", self._drag_start_h)

    def _step(self, delta: int) -> None:
        row = self.list.currentRow() + delta
        if 0 <= row < len(self._rows):
            self.list.setCurrentRow(row)

    def _refresh_nav(self) -> None:
        row = self.list.currentRow()
        self.prev_btn.setEnabled(row > 0)
        self.next_btn.setEnabled(0 <= row < len(self._rows) - 1)

    def _refresh_tabs(self, row: ResultRow | None) -> None:
        """Rules count on its tab; tabs with nothing to show are greyed (SRD-GUI-043.010)."""
        if row is not None and row.rule_count:
            self.tabs.setTabText(_TAB_RULES, f"Rules {row.passed_count}/{row.rule_count}")
        else:
            self.tabs.setTabText(_TAB_RULES, "Details" if row is not None else "Rules")
        has = {
            _TAB_NEWS: not (self.news_head.isHidden() and self.research_box.isHidden()),
            _TAB_FUNDAMENTALS: not (self.fundamentals_lbl.isHidden()
                                    and self.analysts_head.isHidden()),
            _TAB_REVIEW: not self.review_box.isHidden(),
        }
        if not has.get(self.tabs.currentIndex(), True):
            self.tabs.setCurrentIndex(0)
        for index, enabled in has.items():
            self.tabs.setTabEnabled(index, enabled)

    def load(self, rows: list[ResultRow], timeframe: str = "1d",
             run_timestamp: str | None = None) -> None:
        """Show ``rows`` of the run made at ``run_timestamp`` and select the first one."""
        self._rows = rows
        self._timeframe = timeframe
        self._run_timestamp = run_timestamp
        self.list.blockSignals(True)
        self.list.clear()
        for row in rows:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, STOCK_ROW_H))
            self.list.addItem(item)
            self.list.setItemWidget(item, _ListRow(row))
        self.list.blockSignals(False)
        if rows:
            self.list.setCurrentRow(0)
        else:
            self._show_row(-1)

    def detach_list(self) -> QListWidget:
        """Take the stock list out of this view so the caller can place it elsewhere.

        The view keeps loading, selecting and restyling the list (SRD-GUI-043.003).
        """
        layout = self.layout()
        if layout is not None:
            layout.removeWidget(self.list)
        self.list.setMinimumWidth(0)
        self.list.setMaximumWidth(16777215)
        return self.list

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
            self._show_plan(self._rows[index])
            self.selection_changed.emit(symbol)

    def _fill_detail(self, index: int) -> bool:
        """Fill the detail panel for row ``index``; False when there is no such row."""
        _T: Any = active_palette()
        _clear_layout(self._tier_slot)
        _clear_layout(self._rules_box)
        _clear_layout(self._chips_box)
        _clear_layout(self._flags_box)
        _clear_layout(self._news_box)
        _clear_layout(self._analysts_box)
        self.flags_head.hide()
        self.news_head.hide()
        self.research_box.hide()
        self._hide_company_sections()
        self._refresh_nav()
        if not 0 <= index < len(self._rows):
            self._refresh_tabs(None)
            self.symbol_lbl.setText("")
            self.meta_lbl.setText("")
            self.reasoning_lbl.setText("")
            self.rules_head.setText("RULES")
            for value in self.tiles.values():
                value.setText(_DASH)
            self.rr_bar.setVisible(False)
            self.outcome_lbl.setVisible(False)
            self.risk_lbl.setText("")
            self.reward_lbl.setText("")
            return False
        row = self._rows[index]
        self.symbol_lbl.setText(row.symbol)
        self._tier_slot.addWidget(_tier_chip(row.tier), 0, Qt.AlignmentFlag.AlignTop)
        parts = [part for part in (row.name, row.sector) if part]
        parts += [f"rank {row.rank} of {len(self._rows)}", f"AI score {row.score:.2f}"]
        self.meta_lbl.setText(" · ".join(parts))
        self._fill_plan(row, _T)
        self.rules_head.setText(
            f"RULES · {row.passed_count} OF {row.rule_count}" if row.rule_count else "DETAILS")
        for rule in row.rules:
            self._rules_box.addWidget(self._rule_line(rule, _T))
        self._fill_context(row, _T)
        self._fill_news_research(row, _T)
        self._fill_company_review(row, _T)
        self.reasoning_lbl.setText(row.reasoning or "No AI reasoning for this run.")
        self._refresh_tabs(row)
        return True

    def _fill_news_research(self, row: ResultRow, palette: Any) -> None:
        """News list and Web research box (SRD-GUI-022.019)."""
        for item in row.news:
            label = QLabel(_news_html(item, palette.BLUE))
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setOpenExternalLinks(True)
            label.setWordWrap(True)
            self._news_box.addWidget(label)
        self.news_head.setVisible(bool(row.news))
        summary = str(row.research.get("summary", ""))
        if summary:
            self.research_lbl.setText(summary)
            self.research_links.setText(_source_links(row.research.get("sources") or [],
                                                      palette.BLUE))
            self.research_box.show()

    def _hide_company_sections(self) -> None:
        for widget in (self.fundamentals_head, self.fundamentals_lbl, self.analysts_head,
                       self.review_box):
            widget.hide()

    def _fill_company_review(self, row: ResultRow, palette: Any) -> None:
        """Fundamentals line, Analyst changes list and Bull vs bear box (SRD-GUI-022.021)."""
        if row.fundamentals:
            self.fundamentals_lbl.setText(row.fundamentals)
            self.fundamentals_head.show()
            self.fundamentals_lbl.show()
        for line in row.analysts:
            self._analysts_box.addWidget(QLabel(line))
        self.analysts_head.setVisible(bool(row.analysts))
        verdict = str(row.review.get("verdict", ""))
        if not verdict:
            return
        for label, key, mark, colour in ((self.review_bull_lbl, "bull", "▲", palette.GREEN),
                                         (self.review_bear_lbl, "bear", "▼", palette.RED)):
            points = [html.escape(str(p)) for p in row.review.get(key) or []]
            label.setText("<br>".join(
                f'<span style="color:{colour};">{mark}</span> {point}' for point in points))
            label.setVisible(bool(points))
        text = f"Verdict: {verdict} ({row.review.get('confidence', '')})"
        if row.review.get("summary"):
            text += f" — {row.review['summary']}"
        if verdict in ("Wait", "Avoid"):
            text += f"  ·  differs from the ranking (#{row.rank})"
        self.review_verdict_lbl.setText(text)
        self.review_box.show()

    def _fill_context(self, row: ResultRow, palette: Any) -> None:
        """Context chips under the name and the Red flags list (SRD-GUI-022.017)."""
        for chip in row.chips:
            self._chips_box.addWidget(_context_chip(chip))
        if not row.chips:
            return
        self.flags_head.show()
        for flag in row.flags or ["None for this stock"]:
            label = QLabel(flag)
            label.setStyleSheet(f"color: {palette.RED if row.flags else palette.MUTED};")
            self._flags_box.addWidget(label)

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
        label.setToolTip(rule.tip)
        label.setMinimumWidth(_RULE_NAME_W)
        box.addWidget(label)
        if rule.passed is None:
            box.addWidget(QLabel(rule.value))
        box.addStretch(1)
        return line

    def _show_chart(self, symbol: str) -> None:
        if self._chart_factory is None:
            return
        if self._chart is None:
            self._chart = self._chart_factory()
            self._chart_layout.addWidget(self._chart)
        chart: _ChartLike = self._chart  # type: ignore[assignment]
        chart.show_symbol(symbol, self._timeframe)

    def _show_plan(self, row: ResultRow) -> None:
        """Draw the AI plan from the next candle after the run and tag what it did."""
        self.outcome_lbl.setVisible(False)
        if self._chart is None:
            return
        chart: _ChartLike = self._chart  # type: ignore[assignment]
        entry, stop, target = row.entry, row.stop, row.target
        if (self._timeframe != "1d" or row.rr is None
                or entry is None or stop is None or target is None):
            chart.set_plan(None)
            return
        bars = chart.candles
        start = plan_start_index(self._run_timestamp, bars)
        chart.set_plan((entry, stop, target), None if start is None else int(bars[start]["time"]))
        if start is None:
            return
        outcome = plan_outcome(bars, start, entry, stop, target)
        palette: Any = active_palette()
        colour = {"target": palette.GREEN, "stop": palette.RED,
                  "open": palette.YELLOW}.get(outcome[0], palette.MUTED)
        self.outcome_lbl.setText(outcome_text(outcome))
        self.outcome_lbl.setStyleSheet(f"color: {colour}; font-weight: bold;")
        self.outcome_lbl.setVisible(True)

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
        index = self.list.currentRow()
        if self._fill_detail(index):
            self._show_plan(self._rows[index])
