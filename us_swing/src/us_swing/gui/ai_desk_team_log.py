"""
Module: MD-GUI-035.006.M03 — AI Desk Team at work: Event log
Parent SRD: SRD-GUI-035.006
Also: SRD-GUI-035.015 (message rows)

A day of desk events: a clickable day strip, filters and a tree whose event rows open to
the LLM calls each event caused.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_team import DeskEvent, Member
from us_swing.gui.ai_desk_sections import muted
from us_swing.gui.ai_desk_team_pane import arrow_button, checked_style
from us_swing.gui.theme import C

HEADERS = ("Time ET", "Event · employee", "Why · model", "Urgency", "Woke · tokens",
           "Result · answer", "Took", "Cost")
FILTERS = ("All", "Urgent", "With AI work", "Problems")
_URGENCY = {0: "Urgent", 1: "Normal", 2: "Low"}
_DAY_START, _DAY_HOURS = 8, 12
_ROLE = Qt.ItemDataRole.UserRole


def result_of(event: DeskEvent) -> tuple[str, str]:
    """Plain result text and theme colour name of an event."""
    if event.note == "nobody listens":
        return "Nobody listens", "MUTED"
    if event.state == "waiting":
        return "Waiting", "BLUE"
    if event.state == "expired":
        return "Expired", "MUTED"
    if event.note == "failed" or (event.calls and not any(c.valid for c in event.calls)):
        return "Failed", "RED"
    if event.state == "late":
        return "Late", "YELLOW"
    return "Done", "GREEN"


def is_problem(event: DeskEvent) -> bool:
    """True for late, expired or failed events and events with a bad answer."""
    return result_of(event)[0] in ("Late", "Expired", "Failed") or any(
        not c.valid for c in event.calls)


def woke_text(event: DeskEvent, members: Sequence[Member]) -> str:
    """Who an event wakes, in plain words; a message wakes only its receiver."""
    if event.kind == "message":
        return next((m.name for m in members if m.id == event.target), event.target or "nobody")
    names = [m.name for m in members if event.kind in m.triggers]
    if not names:
        return "nobody"
    return names[0] if len(names) == 1 else f"{len(names)} employees"


def _took(event: DeskEvent) -> str:
    if event.handled is None:
        return "—"
    secs = max(0, int((event.handled - event.created).total_seconds()))
    return f"{secs // 60}m {secs % 60:02d}s" if secs >= 60 else f"{secs} s"


def keep(event: DeskEvent, which: str) -> bool:
    """True when ``event`` passes the filter ``which``."""
    if which == "Urgent":
        return event.priority == 0
    if which == "With AI work":
        return bool(event.calls)
    if which == "Problems":
        return is_problem(event)
    return True


class DayStrip(QWidget):
    """08:00 to 20:00 ET line with one dot per event; a click picks the event."""

    picked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._events: list[DeskEvent] = []
        self._chosen = -1
        self.setMinimumHeight(64)
        self.setMouseTracking(True)

    def set_events(self, events: Sequence[DeskEvent], chosen: int) -> None:
        """Show ``events``; ``chosen`` is the id drawn bigger."""
        self._events = list(events)
        self._chosen = chosen
        self.update()

    def _x(self, moment: datetime) -> float:
        hours = moment.hour + moment.minute / 60 - _DAY_START
        share = min(max(hours / _DAY_HOURS, 0.0), 1.0)
        return 16 + share * (self.width() - 32)

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw the hour line, market hours band and event dots."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        line_y = 30.0
        p.setPen(QPen(QColor(C.OVERLAY2), 2))
        p.drawLine(QPointF(16, line_y), QPointF(self.width() - 16, line_y))
        open_x = self._x(datetime(2000, 1, 1, 9, 30))
        close_x = self._x(datetime(2000, 1, 1, 16, 0))
        p.fillRect(QRectF(open_x, line_y - 4, close_x - open_x, 8), QColor(C.OVERLAY))
        p.setPen(QColor(C.MUTED))
        for hour in range(_DAY_START, _DAY_START + _DAY_HOURS + 1, 2):
            x = self._x(datetime(2000, 1, 1, hour % 24, 0)) if hour < 24 else self.width() - 16
            p.drawText(QRectF(x - 20, line_y + 10, 40, 16), Qt.AlignmentFlag.AlignCenter,
                       f"{hour:02d}:00")
        for ev in self._events:
            colour = QColor(getattr(C, result_of(ev)[1]))
            radius = 7.0 if ev.id == self._chosen else 5.0
            p.setPen(QPen(QColor(C.SURFACE), 2))
            p.setBrush(colour)
            p.drawEllipse(QPointF(self._x(ev.created), line_y), radius, radius)
        p.end()

    def _hit(self, x: float) -> DeskEvent | None:
        near = [(abs(self._x(ev.created) - x), ev) for ev in self._events]
        best = min(near, key=lambda pair: pair[0], default=None)
        return best[1] if best is not None and best[0] <= 8 else None

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Show the event under the mouse as a tooltip."""
        if event is None:
            return
        hit = self._hit(event.position().x())
        self.setToolTip(f"{hit.created:%H:%M} · {hit.name} · {result_of(hit)[0]}" if hit else "")

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Pick the clicked event."""
        if event is None:
            return
        hit = self._hit(event.position().x())
        if hit is not None:
            self.picked.emit(hit.id)


class EventLogView(QWidget):
    """The Event log tab."""

    day_changed = pyqtSignal(object)
    member_picked = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day = date.today()
        self._events: list[DeskEvent] = []
        self._members: list[Member] = []
        self._open: set[int] = set()
        self._chosen = -1
        self._shape: object = None
        lines = QVBoxLayout(self)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(8)
        bar = QHBoxLayout()
        self.prev_btn = arrow_button("Left", "Day before")
        self.next_btn = arrow_button("Right", "Day after")
        self.day_label = QLabel()
        self.day_label.setStyleSheet("font-weight: bold;")
        bar.addWidget(self.prev_btn)
        bar.addWidget(self.day_label)
        bar.addWidget(self.next_btn)
        bar.addSpacing(16)
        self._group = QButtonGroup(self)
        self._filter_btns: dict[str, QPushButton] = {}
        for name in FILTERS:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(name == "All")
            btn.setStyleSheet(checked_style())
            self._group.addButton(btn)
            self._filter_btns[name] = btn
            bar.addWidget(btn)
        bar.addStretch(1)
        lines.addLayout(bar)
        self.strip = DayStrip()
        lines.addWidget(self.strip)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(list(HEADERS))
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setStyleSheet("QTreeWidget { outline: none; }")
        head = self.tree.header()
        if head is not None:
            head.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            head.setStretchLastSection(True)
        lines.addWidget(self.tree, 1)
        self.empty = muted("No desk events on this day")
        lines.addWidget(self.empty)
        # day buttons → clicked → log → _move_day
        self.prev_btn.clicked.connect(lambda: self._move_day(-1))
        self.next_btn.clicked.connect(lambda: self._move_day(1))
        # filter group → buttonClicked → log → _fill
        self._group.buttonClicked.connect(lambda _b: self._fill())
        # strip → picked → log → open_event
        self.strip.picked.connect(self.open_event)
        # tree → itemExpanded/itemCollapsed → log → remember open rows
        self.tree.itemExpanded.connect(lambda it: self._open.add(int(it.data(0, _ROLE) or -1)))
        self.tree.itemCollapsed.connect(
            lambda it: self._open.discard(int(it.data(0, _ROLE) or -1)))
        # tree → itemClicked → log → _on_click
        self.tree.itemClicked.connect(self._on_click)

    @property
    def day(self) -> date:
        """The day on show."""
        return self._day

    def filter_name(self) -> str:
        """The chosen filter."""
        return next((n for n, b in self._filter_btns.items() if b.isChecked()), "All")

    def set_filter(self, name: str) -> None:
        """Choose the filter ``name``."""
        self._filter_btns[name].setChecked(True)
        self._fill()

    def set_events(self, day: date, events: Sequence[DeskEvent],
                   members: Sequence[Member], today: date) -> None:
        """Show ``events`` of ``day``; open rows stay open; no paging past ``today``."""
        shape = (day, [(e.id, e.state, e.handled, len(e.calls)) for e in events],
                 [m.id for m in members])
        if shape == self._shape:
            return
        self._shape = shape
        self._day = day
        self._events = list(events)
        self._members = list(members)
        self.day_label.setText(f"{day:%a %d %b %Y} · New York time")
        self.next_btn.setEnabled(day < today)
        self._fill()

    def open_event(self, event_id: int) -> None:
        """Open and show the event row ``event_id``."""
        self._chosen = event_id
        self._open.add(event_id)
        if not any(e.id == event_id and keep(e, self.filter_name()) for e in self._events):
            self._filter_btns["All"].setChecked(True)
        self._fill()
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if item is not None and item.data(0, _ROLE) == event_id:
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)

    def _move_day(self, delta: int) -> None:
        self._open.clear()
        self.day_changed.emit(self._day + timedelta(days=delta))

    def _fill(self) -> None:
        shown = [e for e in self._events if keep(e, self.filter_name())]
        self.strip.set_events(self._events, self._chosen)
        bar = self.tree.verticalScrollBar()
        scroll = bar.value() if bar is not None else 0
        self.tree.clear()
        for ev in shown:
            text, tone = result_of(ev)
            cost = sum(c.cost_usd for c in ev.calls)
            item = QTreeWidgetItem([
                f"{ev.created:%H:%M:%S}", ev.name, ev.detail or ev.why,
                _URGENCY.get(ev.priority, "Low"),
                woke_text(ev, self._members), text, _took(ev),
                f"${cost:.3f}" if ev.calls else "—"])
            item.setData(0, _ROLE, ev.id)
            if ev.target:
                item.setToolTip(2, f"Message event {ev.id} to {ev.target}")
            item.setForeground(5, QColor(getattr(C, tone)))
            font = item.font(1)
            font.setBold(True)
            item.setFont(1, font)
            for call in ev.calls:
                child = QTreeWidgetItem([
                    f"{call.started:%H:%M:%S}", call.employee_name,
                    f"{call.source} · {call.model} · try {call.attempt}", "",
                    f"{call.tokens_in:,} / {call.tokens_out:,}",
                    "Valid" if call.valid else (call.error[:80] or "Bad answer"),
                    f"{call.seconds:.1f} s", f"${call.cost_usd:.4f}"])
                child.setData(0, _ROLE, -1)
                child.setData(1, _ROLE, call.employee)
                child.setForeground(5, QColor(C.GREEN if call.valid else C.RED))
                if call.error:
                    child.setToolTip(5, call.error)
                item.addChild(child)
            self.tree.addTopLevelItem(item)
            item.setExpanded(ev.id in self._open)
        self.tree.setVisible(bool(shown))
        self.empty.setVisible(not shown)
        if bar is not None:
            bar.setValue(scroll)

    def _on_click(self, item: QTreeWidgetItem, _col: int) -> None:
        member_id = item.data(1, _ROLE)
        if member_id:
            self.member_picked.emit(str(member_id))
        elif item.childCount():
            item.setExpanded(not item.isExpanded())
