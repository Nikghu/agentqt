"""
Module: MD-GUI-035.001.M01 — AI Desk Team at work section
Parent SRD: SRD-GUI-035.001
Also: SRD-GUI-035.002–.005 (run bar, Live tab, pipeline, timeline), SRD-GUI-035.009 (refresh)

One section that shows how the AI employee team works: a run bar, the Live tab (pipeline or
timeline), the Event log tab, the Team scorecard tab and a side pane with the team wheel and
the picked employee's profile. Reads desk.db only through ``core.desk_team``.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QHideEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QShowEvent,
)
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_contract import desk_home
from us_swing.core.desk_overview import run_name
from us_swing.core.desk_team import (
    Call,
    Member,
    MemberState,
    Run,
    RunView,
    day_events,
    history,
    last_brief,
    levels,
    month_cost,
    run_view,
    runs,
    scorecard,
    team,
)
from us_swing.gui.ai_desk_sections import muted, scroll_of, section_frame
from us_swing.gui.ai_desk_team_log import EventLogView
from us_swing.gui.ai_desk_team_pane import (
    ProfilePane,
    ScoreTable,
    TeamWheel,
    WheelItem,
    arrow_button,
    checked_style,
    skill_text,
    tone,
    wheel_buttons,
)
from us_swing.gui.theme import C

NY = ZoneInfo("America/New_York")
IST = ZoneInfo("Asia/Kolkata")
NAME = "Team at work"
TICK_MS = 3000
IDLE_TICKS = 5
_ASLEEP = MemberState("asleep", "Asleep")


def _dur(seconds: float) -> str:
    secs = max(0, int(seconds))
    return f"{secs // 60}m {secs % 60:02d}s"


def _toggle_row(names: Sequence[str], group: QButtonGroup) -> tuple[QHBoxLayout,
                                                                   list[QPushButton]]:
    row = QHBoxLayout()
    row.setSpacing(4)
    buttons = []
    for i, name in enumerate(names):
        btn = QPushButton(name)
        btn.setCheckable(True)
        btn.setChecked(i == 0)
        btn.setStyleSheet(checked_style())
        group.addButton(btn, i)
        row.addWidget(btn)
        buttons.append(btn)
    return row, buttons


class StageCard(QFrame):
    """One pipeline card: name, state, skill and a short fact line."""

    clicked = pyqtSignal(str)

    def __init__(self, key: str, name: str, skill: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.state_key = "asleep"
        self.selected = False
        self.setObjectName("team_card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(140)
        lines = QVBoxLayout(self)
        lines.setContentsMargins(10, 8, 10, 8)
        lines.setSpacing(3)
        top = QHBoxLayout()
        title = QLabel(name)
        title.setStyleSheet("font-weight: bold; background: transparent; border: none;")
        self.state_label = QLabel()
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.state_label)
        lines.addLayout(top)
        sub = QLabel(skill)
        sub.setStyleSheet(f"color: {C.MUTED}; background: transparent; border: none;")
        lines.addWidget(sub)
        self.meta = QLabel()
        self.meta.setWordWrap(True)
        self.meta.setStyleSheet(f"color: {C.SUBTEXT}; background: transparent; border: none;")
        lines.addWidget(self.meta)
        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.setMaximumHeight(4)
        self.busy.hide()
        lines.addWidget(self.busy)
        self.paint_border(C.OVERLAY)

    def set_state(self, key: str, label: str, meta: str) -> None:
        """Show state ``key`` with ``label`` and the fact line ``meta``."""
        self.state_key = key
        colour = tone(key)
        self.state_label.setText(label)
        self.state_label.setStyleSheet(
            f"color: {colour}; border: 1px solid {colour}; border-radius: 8px;"
            " padding: 0 6px; background: transparent;")
        self.meta.setText(meta)
        self.busy.setVisible(key == "working")
        if key != "working":
            self.paint_border(C.BLUE if self.selected else C.OVERLAY)

    def paint_border(self, colour: str) -> None:
        """Draw the card border in ``colour``."""
        self.setStyleSheet(f"QFrame#team_card {{ background: {C.SURFACE};"
                           f" border: 1px solid {colour}; border-radius: 8px; }}")

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Tell listeners this card was clicked."""
        self.clicked.emit(self.key)
        super().mousePressEvent(event)


def _call_meta(calls: Sequence[Call]) -> str:
    if not calls:
        return ""
    last = calls[-1]
    secs = sum(c.seconds for c in calls)
    return f"{calls[0].started:%H:%M:%S} · {secs:.1f} s · {last.source}"


def _mix(a: str, b: str, t: float) -> str:
    ca, cb = QColor(a), QColor(b)
    return QColor(round(ca.red() + (cb.red() - ca.red()) * t),
                  round(ca.green() + (cb.green() - ca.green()) * t),
                  round(ca.blue() + (cb.blue() - ca.blue()) * t)).name()


class PipelineView(QWidget):
    """Trigger, data steps, one column per skill need level and an on-demand row."""

    picked = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._shape: tuple[tuple[str, ...], ...] = ()
        self._cards: dict[str, StageCard] = {}
        self._arrows: list[tuple[QLabel, list[str]]] = []
        self._phase = 0
        self._lines = QVBoxLayout(self)
        self._lines.setContentsMargins(0, 0, 0, 0)
        self._pulse = QTimer(self)
        self._pulse.setInterval(90)
        # pulse timer → timeout → pipeline → _on_pulse
        self._pulse.timeout.connect(self._on_pulse)

    def _clear(self) -> None:
        while self._lines.count():
            item = self._lines.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()
        self._arrows.clear()

    def _build(self, members: Sequence[Member]) -> None:
        self._clear()
        cols: list[tuple[str, list[StageCard]]] = [
            ("Trigger", [StageCard("trigger", "Evening run", "US weekdays, 16:25 ET")]),
            ("Data steps", [StageCard("data", "Market data", "Regime, sectors, ideas, news")]),
        ]
        for n, group in enumerate(levels(members), start=1):
            title = "Start" if n == 1 else ("Then" if n < len(levels(members)) else "Last")
            cards = [StageCard(m.id, m.name, skill_text(m.skill)) for m in group]
            cols.append((f"{n} · {title}", cards))
        row = QWidget()
        flow = QHBoxLayout(row)
        flow.setContentsMargins(0, 0, 0, 0)
        flow.setSpacing(6)
        for i, (title, cards) in enumerate(cols):
            if i:
                arrow = QLabel("→")
                arrow.setStyleSheet(f"color: {C.OVERLAY2}; font-size: 18px;")
                flow.addWidget(arrow)
                self._arrows.append((arrow, [c.key for c in cards]))
            col = QVBoxLayout()
            col.setSpacing(6)
            head = QLabel(title.upper())
            head.setStyleSheet(f"color: {C.MUTED}; font-size: 10px; letter-spacing: 1px;")
            col.addWidget(head)
            for card in cards:
                self._add(card)
                col.addWidget(card)
            col.addStretch(1)
            flow.addLayout(col, 1)
        self._lines.addWidget(row)
        demand = [m for m in members if m.on_demand]
        if demand:
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet(f"color: {C.OVERLAY};")
            self._lines.addWidget(line)
            box = QWidget()
            drow = QHBoxLayout(box)
            drow.setContentsMargins(0, 0, 0, 0)
            drow.addWidget(muted("ON DEMAND · wake when you ask"))
            for m in demand:
                card = StageCard(m.id, m.name, skill_text(m.skill))
                self._add(card)
                drow.addWidget(card, 1)
            self._lines.addWidget(box)
        self._lines.addStretch(1)

    def _add(self, card: StageCard) -> None:
        self._cards[card.key] = card
        # card → clicked → pipeline → picked (stage cards are not employees)
        card.clicked.connect(lambda key: self.picked.emit(key) if key not in (
            "trigger", "data") else None)

    def show_view(self, members: Sequence[Member], view: RunView | None, selected: str) -> None:
        """Show each card's state for ``view`` (all asleep without a run)."""
        shape = tuple(tuple(m.id for m in col) for col in levels(members)) + (
            tuple(m.id for m in members if m.on_demand),)
        if shape != self._shape:
            self._shape = shape
            self._build(members)
        self._show_stages(view)
        for m in members:
            state = view.states.get(m.id, _ASLEEP) if view else _ASLEEP
            card = self._cards.get(m.id)
            if card is None:
                continue
            card.selected = m.id == selected
            meta = _call_meta(state.calls) or (
                "Waits for " + str(len(m.needs)) + " before" if state.key == "waiting" and m.needs
                else "Plan: " + (m.primary or "—"))
            card.set_state(state.key, state.label, meta)
        for arrow, keys in self._arrows:
            states = [self._cards[k].state_key for k in keys if k in self._cards]
            colour = C.BLUE if "working" in states else (
                C.GREEN if states and all(s == "done" for s in states) else C.OVERLAY2)
            arrow.setStyleSheet(f"color: {colour}; font-size: 18px;")
        working = any(c.state_key == "working" for c in self._cards.values())
        if working and not self._pulse.isActive():
            self._pulse.start()
        elif not working:
            self._pulse.stop()

    def _show_stages(self, view: RunView | None) -> None:
        trigger, data = self._cards.get("trigger"), self._cards.get("data")
        if trigger is None or data is None:
            return
        if view is None:
            trigger.set_state("asleep", "Upcoming", "Next: 16:25 ET · 02:55 IST")
            data.set_state("asleep", "Asleep", "No AI, no cost")
            return
        run = view.run
        trigger.set_state("done", "Fired", f"{run_name(run.kind)} · {run.started:%H:%M:%S} ET")
        if run.ended is None and view.ai_started is None:
            data.set_state("working", "Working", "Saving market data · no AI")
            return
        end = view.ai_started or run.ended or run.started
        data.set_state("done", "Done", f"{_dur((end - run.started).total_seconds())} · no AI")

    def stop_motion(self) -> None:
        """Stop the working pulse while the view is hidden."""
        self._pulse.stop()

    def _on_pulse(self) -> None:
        self._phase = (self._phase + 1) % 20
        t = abs(10 - self._phase) / 10
        colour = _mix(C.OVERLAY, C.BLUE, 1 - t)
        for card in self._cards.values():
            if card.state_key == "working":
                card.paint_border(colour)


class TimelineView(QWidget):
    """One row per employee and one bar per LLM call across the run."""

    picked = pyqtSignal(str)
    LABEL_W = 170
    ROW_H = 28

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._members: list[Member] = []
        self._view: RunView | None = None
        self._now: datetime | None = None
        self.setMouseTracking(True)

    def show_view(self, members: Sequence[Member], view: RunView | None, now: datetime) -> None:
        """Draw ``view``; the now line shows while the run runs."""
        self._members = [m for m in members if not m.on_demand]
        self._view = view
        self._now = now
        self.setMinimumHeight(40 + self.ROW_H * (len(self._members) + 1))
        self.update()

    def _span(self) -> tuple[datetime, float] | None:
        if self._view is None or self._now is None:
            return None
        run = self._view.run
        end = run.ended or self._now
        last = max((c.ended for c in self._view.calls), default=end)
        return run.started, max(60.0, (max(end, last) - run.started).total_seconds())

    def _x(self, moment: datetime, start: datetime, span: float) -> float:
        width = self.width() - self.LABEL_W - 16
        return self.LABEL_W + (moment - start).total_seconds() / span * width

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw time ticks, the data steps bar and one bar per call."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        span = self._span()
        if span is None or self._view is None:
            p.setPen(QColor(C.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No desk run yet")
            p.end()
            return
        start, secs = span
        step = next((s for s in (30, 60, 120, 300, 600, 1800, 3600) if secs / s <= 8), 3600)
        p.setPen(QColor(C.MUTED))
        tick = 0.0
        while tick <= secs:
            x = self._x(start + timedelta(seconds=tick), start, secs)
            p.setPen(QPen(QColor(C.OVERLAY), 1))
            p.drawLine(QPointF(x, 22), QPointF(x, self.height()))
            p.setPen(QColor(C.MUTED))
            p.drawText(QRectF(x - 30, 2, 60, 16), Qt.AlignmentFlag.AlignCenter,
                       f"{start + timedelta(seconds=tick):%H:%M:%S}")
            tick += step
        view = self._view
        rows: list[tuple[str, list[tuple[datetime, datetime, str]]]] = []
        data_end = view.ai_started or view.run.ended or self._now or start
        rows.append(("Data steps", [(start, data_end, C.OVERLAY2)]))
        for m in self._members:
            main = m.primary.split(" / ")[0]
            bars = [(c.started, c.ended, C.RED if not c.valid else (
                C.YELLOW if c.source != main else C.BLUE))
                for c in view.calls if c.employee == m.id]
            rows.append((m.name, bars))
        for i, (label, bars) in enumerate(rows):
            y = 26 + i * self.ROW_H
            p.setPen(QColor(C.TEXT))
            p.drawText(QRectF(4, y, self.LABEL_W - 8, self.ROW_H),
                       Qt.AlignmentFlag.AlignVCenter, label)
            for b_start, b_end, colour in bars:
                x0 = self._x(b_start, start, secs)
                x1 = max(x0 + 3, self._x(b_end, start, secs))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(colour))
                p.drawRoundedRect(QRectF(x0, y + 5, x1 - x0, self.ROW_H - 10), 3, 3)
        if view.run.ended is None and self._now is not None:
            x = self._x(self._now, start, secs)
            p.setPen(QPen(QColor(C.BLUE), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, 20), QPointF(x, self.height()))
        p.end()

    def _row_member(self, y: float) -> Member | None:
        row = int((y - 26) // self.ROW_H) - 1
        return self._members[row] if 0 <= row < len(self._members) else None

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Show the call under the mouse as a tooltip."""
        span = self._span()
        if event is None or span is None or self._view is None:
            return
        member = self._row_member(event.position().y())
        x = event.position().x()
        tip = ""
        if member is not None:
            for c in self._view.calls:
                if c.employee == member.id and self._x(c.started, *span) - 2 <= x <= max(
                        self._x(c.started, *span) + 3, self._x(c.ended, *span)) + 2:
                    tip = (f"{member.name} · try {c.attempt} · {c.source} {c.model}\n"
                           f"{c.started:%H:%M:%S} · {c.seconds:.1f} s · "
                           f"{c.tokens_in:,} in / {c.tokens_out:,} out · ${c.cost_usd:.4f}\n"
                           + ("valid answer" if c.valid else (c.error[:120] or "bad answer")))
        self.setToolTip(tip)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Pick the employee of the clicked row."""
        if event is not None and (member := self._row_member(event.position().y())):
            self.picked.emit(member.id)


class TeamAtWork(QWidget):
    """AI Desk → Team at work."""

    def __init__(self, home: Path | None = None,
                 clock: Callable[[], datetime] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._home = home
        self._clock = clock or (lambda: datetime.now(NY))
        self._members: list[Member] = []
        self._runs: list[Run] = []
        self._run_id: int | None = None
        self._view: RunView | None = None
        self._selected = ""
        self._log_day: date | None = None
        self._ticks = 0
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame, body = section_frame(NAME, sample=False)
        outer.addWidget(frame)
        main = QHBoxLayout()
        main.setSpacing(14)
        body.addLayout(main, 1)
        left = QVBoxLayout()
        left.setSpacing(10)
        main.addLayout(left, 1)
        left.addLayout(self._run_bar())
        self._tabs = QButtonGroup(self)
        tab_row, _ = _toggle_row(("Live", "Event log", "Team"), self._tabs)
        tab_row.addStretch(1)
        left.addLayout(tab_row)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._live_page())
        self.log = EventLogView()
        self.pages.addWidget(self.log)
        team_page = QWidget()
        team_lines = QVBoxLayout(team_page)
        team_lines.setContentsMargins(0, 0, 0, 0)
        team_lines.addWidget(muted("Last 30 days · shadow and replay calls left out · "
                                   "click a row to open the profile"))
        self.scores = ScoreTable()
        team_lines.addWidget(self.scores, 1)
        self.pages.addWidget(team_page)
        left.addWidget(self.pages, 1)
        main.addWidget(self._side_pane())
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        # timer → timeout → section → _on_tick
        self._timer.timeout.connect(self._on_tick)
        # tabs → idClicked → section → _on_tab
        self._tabs.idClicked.connect(self._on_tab)
        # log → day_changed / member_picked → section
        self.log.day_changed.connect(self._on_day)
        self.log.member_picked.connect(self.select_member)
        # scorecard → picked → section → select_member
        self.scores.picked.connect(self.select_member)

    def _folder(self) -> Path:
        return self._home or desk_home()

    def _run_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.prev_run = arrow_button("Left", "Older run")
        self.next_run = arrow_button("Right", "Newer run")
        self.run_label = QLabel("No desk run yet")
        self.run_label.setStyleSheet("font-weight: bold;")
        row.addWidget(self.prev_run)
        row.addWidget(self.run_label)
        row.addWidget(self.next_run)
        row.addSpacing(12)
        self.chips: dict[str, QLabel] = {}
        for key in ("time", "done", "calls", "tokens", "cost"):
            chip = QLabel()
            chip.setStyleSheet(f"color: {C.SUBTEXT}; border: 1px solid {C.OVERLAY};"
                               " border-radius: 9px; padding: 1px 8px;")
            self.chips[key] = chip
            row.addWidget(chip)
        row.addStretch(1)
        # run buttons → clicked → section → _move_run
        self.prev_run.clicked.connect(lambda: self._move_run(1))
        self.next_run.clicked.connect(lambda: self._move_run(-1))
        return row

    def _live_page(self) -> QWidget:
        page = QWidget()
        lines = QVBoxLayout(page)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(8)
        now_row = QHBoxLayout()
        head = QLabel("Right now")
        head.setStyleSheet("font-weight: bold;")
        self.now_label = QLabel()
        self.now_label.setWordWrap(True)
        self.now_label.setStyleSheet(f"color: {C.SUBTEXT};")
        now_row.addWidget(head)
        now_row.addWidget(self.now_label, 1)
        self._views = QButtonGroup(self)
        view_row, _ = _toggle_row(("Pipeline", "Timeline"), self._views)
        now_row.addLayout(view_row)
        lines.addLayout(now_row)
        self.live = QStackedWidget()
        self.pipeline = PipelineView()
        self.timeline = TimelineView()
        self.live.addWidget(scroll_of(self.pipeline))
        self.live.addWidget(scroll_of(self.timeline))
        lines.addWidget(self.live, 1)
        # view switch → idClicked → live stack → setCurrentIndex
        self._views.idClicked.connect(self.live.setCurrentIndex)
        # pipeline/timeline → picked → section → select_member
        self.pipeline.picked.connect(self.select_member)
        self.timeline.picked.connect(self.select_member)
        return page

    def _side_pane(self) -> QWidget:
        pane = QWidget()
        pane.setFixedWidth(340)
        lines = QVBoxLayout(pane)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(6)
        head = QHBoxLayout()
        self.team_label = QLabel("Team")
        self.team_label.setStyleSheet("font-weight: bold;")
        self.follow_btn = QPushButton("Follow live")
        self.follow_btn.setCheckable(True)
        self.follow_btn.setChecked(True)
        self.follow_btn.setStyleSheet(checked_style())
        self.follow_btn.setToolTip("Roll to whoever is working now")
        self.wheel = TeamWheel()
        up, down = wheel_buttons(self.wheel)
        head.addWidget(self.team_label)
        head.addStretch(1)
        head.addWidget(self.follow_btn)
        head.addWidget(up)
        head.addWidget(down)
        lines.addLayout(head)
        lines.addWidget(self.wheel)
        self.profile = ProfilePane()
        lines.addWidget(scroll_of(self.profile), 1)
        # wheel → picked → section → _on_wheel
        self.wheel.picked.connect(self._on_wheel)
        # follow → toggled → section → _show_live
        self.follow_btn.toggled.connect(lambda _on: self._show_live())
        return pane

    # ── refresh ───────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Read the team, runs and the open tab's data again and show them."""
        home = self._folder()
        self._members = team(home)
        self._runs = runs(home)
        ids = [r.id for r in self._runs]
        if self._run_id not in ids:
            self._run_id = ids[0] if ids else None
        run = next((r for r in self._runs if r.id == self._run_id), None)
        self._view = run_view(home, run, self._members) if run else None
        self._show_run_bar()
        self._show_live()
        self._refresh_tab()

    def _refresh_tab(self) -> None:
        home, now = self._folder(), self._clock()
        if self.pages.currentIndex() == 1:
            run_day = self._view.run.started.date() if self._view else None
            day = self._log_day or run_day or now.astimezone(NY).date()
            self.log.set_events(day, day_events(home, day, self._members, now), self._members,
                                now.astimezone(NY).date())
        elif self.pages.currentIndex() == 2:
            self.scores.fill(scorecard(home, self._members, now), self._members)

    def _show_run_bar(self) -> None:
        view, now = self._view, self._clock()
        index = next((i for i, r in enumerate(self._runs) if r.id == self._run_id), 0)
        self.prev_run.setEnabled(index < len(self._runs) - 1)
        self.next_run.setEnabled(index > 0)
        for chip in self.chips.values():
            chip.setVisible(view is not None)
        if view is None:
            self.run_label.setText("No desk run yet")
            return
        run = view.run
        self.run_label.setText(f"{run_name(run.kind)} #{run.id} · {run.started:%a %d %b · %H:%M}"
                               f" ET ({run.started.astimezone(IST):%H:%M} IST)")
        taken = ((run.ended or now) - run.started).total_seconds()
        woken = [s for m, s in ((m, view.states.get(m.id)) for m in self._members)
                 if s is not None and not m.on_demand and m.status == "active"]
        done = sum(1 for s in woken if s.key == "done")
        self.chips["time"].setText(("Running " if run.ended is None else "Took ") + _dur(taken))
        self.chips["done"].setText(f"Done {done} of {len(woken)}")
        self.chips["calls"].setText(f"LLM calls {len(view.calls)}")
        tokens = sum(c.tokens_in + c.tokens_out for c in view.calls)
        self.chips["tokens"].setText(f"Tokens {tokens / 1000:.1f}k")
        self.chips["cost"].setText(f"Cost ${sum(c.cost_usd for c in view.calls):.3f}")

    def _working(self) -> Member | None:
        if self._view is None:
            return None
        return next((m for m in self._members
                     if self._view.states.get(m.id, _ASLEEP).key == "working"), None)

    def _show_live(self) -> None:
        working = self._working()
        if self.follow_btn.isChecked() and working is not None:
            self._selected = working.id
        if not self._selected and self._members:
            self._selected = self._members[0].id
        self.now_label.setText(self._now_text(working))
        self.pipeline.show_view(self._members, self._view, self._selected)
        self.timeline.show_view(self._members, self._view, self._clock())
        self.wheel.set_items([
            WheelItem(m.id, m.name, skill_text(m.skill), s.label, s.key)
            for m in self._members
            for s in [self._view.states.get(m.id, _ASLEEP) if self._view else _ASLEEP]])
        self.wheel.set_current(self._selected)
        self._show_profile()

    def _now_text(self, working: Member | None) -> str:
        view = self._view
        if view is None:
            return "The desk has not run yet. The evening run starts at 16:25 ET (02:55 IST)."
        run = view.run
        if run.ended is None and view.ai_started is None:
            return "Data steps are saving market data. No AI and no cost yet."
        if working is not None:
            label = view.states[working.id].label
            waiting = [m.name for m in self._members
                       if view.states.get(m.id, _ASLEEP).key == "waiting"]
            nxt = f" Next: {waiting[0]}." if waiting else ""
            return f"{working.name} is working on {skill_text(working.skill)} ({label}).{nxt}"
        if run.ended is None:
            return "Handing over to the next employee."
        failed = [m.name for m in self._members if view.states.get(m.id, _ASLEEP).key == "failed"]
        text = f"Run finished in {_dur((run.ended - run.started).total_seconds())}."
        if failed:
            text += (f" {len(failed)} employee(s) gave no valid answer. Open Event log or pick "
                     "one to see why.")
        return text

    def _show_profile(self) -> None:
        member = next((m for m in self._members if m.id == self._selected), None)
        names = {m.id: m.name for m in self._members}
        pos = [m.id for m in self._members].index(member.id) + 1 if member else 0
        self.team_label.setText(f"Team · {pos} of {len(self._members)}")
        if member is None:
            return
        home = self._folder()
        state = self._view.states.get(member.id, _ASLEEP) if self._view else _ASLEEP
        self.profile.show_member(member, state, names, last_brief(home, member.id),
                                 history(home, member.id), month_cost(home, member.id,
                                                                      self._clock()))

    # ── user actions ──────────────────────────────────────────────────────

    def select_member(self, member_id: str) -> None:
        """Pick ``member_id`` everywhere; Follow live turns off."""
        if member_id not in {m.id for m in self._members}:
            return
        self.follow_btn.blockSignals(True)
        self.follow_btn.setChecked(False)
        self.follow_btn.blockSignals(False)
        self._selected = member_id
        self.wheel.set_current(member_id)
        self.pipeline.show_view(self._members, self._view, member_id)
        self._show_profile()

    def _on_wheel(self, member_id: str) -> None:
        self.select_member(member_id)

    def _move_run(self, delta: int) -> None:
        index = next((i for i, r in enumerate(self._runs) if r.id == self._run_id), 0)
        index = min(max(index + delta, 0), len(self._runs) - 1)
        if self._runs:
            self._run_id = self._runs[index].id
            self.refresh()

    def _on_tab(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self._refresh_tab()

    def _on_day(self, day: object) -> None:
        if isinstance(day, date):
            self._log_day = day
            self._refresh_tab()

    def _on_tick(self) -> None:
        self._ticks += 1
        running = any(r.ended is None for r in self._runs[:1])
        if running or self._ticks % IDLE_TICKS == 0:
            newest = self._runs[0].id if self._runs else None
            if self._run_id == newest:
                self._run_id = None
            self.refresh()

    def showEvent(self, event: QShowEvent | None) -> None:  # noqa: N802
        """Read the desk and start the timer each time the section is shown."""
        super().showEvent(event)
        self.refresh()
        self._timer.start()

    def hideEvent(self, event: QHideEvent | None) -> None:  # noqa: N802
        """Stop reading the desk while the section is hidden."""
        super().hideEvent(event)
        self._timer.stop()
        self.pipeline.stop_motion()
        self.wheel.stop_motion()
