"""
Module: MD-GUI-035.007.M04 — AI Desk Team at work: wheel, profile and scorecard
Parent SRD: SRD-GUI-035.008
Also: SRD-GUI-035.007 (30-day scorecard table)

The rolling team picker, the picked employee's profile and the Team tab scorecard.
"""
from __future__ import annotations

import html
from collections.abc import Sequence
from dataclasses import dataclass

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_team import Call, Member, MemberState, Score
from us_swing.gui.ai_desk_sections import heading, muted, read_only_text
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C

ROW = 52
SHOWN = 2
STATE_TONES = {"asleep": "MUTED", "waiting": "YELLOW", "working": "BLUE", "done": "GREEN",
               "failed": "RED", "skipped": "SUBTEXT"}


def tone(key: str) -> str:
    """Theme colour for a member state key."""
    return str(getattr(C, STATE_TONES.get(key, "SUBTEXT")))


def skill_text(skill: str) -> str:
    """A skill key in plain words: ``regime_view`` → ``Regime view``."""
    return skill.replace("_", " ").capitalize()


def checked_style() -> str:
    """Stylesheet that marks a checked toggle button with the accent colour."""
    return (f"QPushButton {{ outline: none; }}"
            f" QPushButton:checked {{ color: {C.BLUE}; border: 1px solid {C.BLUE};"
            f" background: {C.OVERLAY}; outline: none; }}")


def tab_style() -> str:
    """Underline tab look for checkable buttons (SRD-GUI-035.012)."""
    return (f"QPushButton {{ background: transparent; border: none; outline: none;"
            f" border-bottom: 2px solid transparent; border-radius: 0; color: {C.SUBTEXT};"
            f" font-weight: bold; padding: 0 6px; }}"
            f" QPushButton:hover {{ color: {C.TEXT}; }}"
            f" QPushButton:checked {{ color: {C.TEXT}; border-bottom: 2px solid {C.BLUE};"
            f" outline: none; }}")


def bar_style(colour: str) -> str:
    """Plain label with a thin ``colour`` bar on its left edge."""
    return (f"background: transparent; border: none; border-left: 3px solid {colour};"
            " border-radius: 0; padding-left: 8px;")


def lift_fill() -> str:
    """Background for a selected card or row: a step lighter than the panel."""
    base, top = QColor(C.SURFACE), QColor(C.OVERLAY)
    return QColor((base.red() + top.red()) // 2, (base.green() + top.green()) // 2,
                  (base.blue() + top.blue()) // 2).name()


def chip_style(key: str) -> str:
    """Pill for a state chip; a left bar in the state colour carries the status."""
    return (f"color: {C.TEXT}; background: {C.OVERLAY}; border: none;"
            f" border-left: 3px solid {tone(key)}; border-radius: 3px; padding: 1px 8px;")


def chip_text(label: str) -> str:
    """Escaped text for a state chip."""
    return html.escape(label)


def bar_rows(rows: Sequence[tuple[str, str]]) -> str:
    """Rich text lines, each with a thin bar in its colour on the left."""
    cells = "".join(f"<tr><td width='3' bgcolor='{colour}'></td><td>&nbsp;{text}</td></tr>"
                    for colour, text in rows)
    return f"<table cellspacing='3' cellpadding='0'>{cells}</table>"


def panel(child: QWidget | None = None, name: str = "team_panel") -> QFrame:
    """A bordered panel on the page colour; holds ``child`` when given."""
    frame = QFrame()
    frame.setObjectName(name)
    frame.setStyleSheet(f"QFrame#{name} {{ background: {C.BG}; border: 1px solid {C.OVERLAY};"
                        " border-radius: 10px; }")
    if child is not None:
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 10, 12, 10)
        box.addWidget(child)
    return frame


def arrow_button(kind: str, tip: str) -> QPushButton:
    """A small button with the chevron icon ``kind`` (Up, Down, Left, Right)."""
    btn = QPushButton()
    set_icon(btn, f"chevron-{kind.lower()}", "neutral", 16)
    btn.setToolTip(tip)
    btn.setAccessibleName(tip)
    btn.setFixedWidth(36)
    return btn


def initials(name: str) -> str:
    """Up to two initials from a name (one word gives its first two letters)."""
    words = [w for w in name.split() if w]
    if len(words) >= 2:
        return (words[0][0] + words[-1][0]).upper()
    return name[:2].upper() if name else "?"


@dataclass(frozen=True)
class WheelItem:
    """One row of the team wheel."""

    id: str
    name: str
    skill: str
    label: str
    key: str


class TeamWheel(QWidget):
    """A rolling picker: the picked employee in the middle, two above and two below."""

    picked = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[WheelItem] = []
        self._pos = 0.0
        self._index = 0
        self._spin = 0
        self.setMinimumHeight(ROW * (2 * SHOWN + 1))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(380)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # anim → valueChanged → wheel → _on_anim
        self._anim.valueChanged.connect(self._on_anim)
        self._ring = QTimer(self)
        self._ring.setInterval(60)
        # ring timer → timeout → wheel → _turn
        self._ring.timeout.connect(self._turn)

    def set_items(self, items: Sequence[WheelItem]) -> None:
        """Show ``items``; the picked id stays picked when it is still there."""
        current = self.current()
        self._items = list(items)
        ids = [i.id for i in self._items]
        self._index = ids.index(current) if current in ids else 0
        if self._anim.state() != QVariantAnimation.State.Running:
            self._pos = float(self._index)
        working = any(i.key == "working" for i in self._items)
        if working and not self._ring.isActive():
            self._ring.start()
        elif not working:
            self._ring.stop()
        self.update()

    def stop_motion(self) -> None:
        """Stop the working ring while the wheel is hidden."""
        self._ring.stop()

    def current(self) -> str:
        """Id of the employee in the middle, or an empty string."""
        return self._items[self._index].id if self._items else ""

    def set_current(self, member_id: str) -> None:
        """Roll to ``member_id`` without telling listeners."""
        ids = [i.id for i in self._items]
        if member_id in ids and ids.index(member_id) != self._index:
            self._roll_to(ids.index(member_id))

    def step(self, delta: int) -> None:
        """Roll ``delta`` rows and tell listeners who is in the middle."""
        if self._items:
            self._roll_to((self._index + delta) % len(self._items))
            self.picked.emit(self.current())

    def _roll_to(self, index: int) -> None:
        n = len(self._items)
        if not n:
            return
        self._anim.stop()
        start = self._pos
        gap = (index - start) % n
        self._anim.setStartValue(start)
        self._anim.setEndValue(start + (gap - n if gap > n / 2 else gap))
        self._index = index
        self._anim.start()

    def _on_anim(self, value: object) -> None:
        self._pos = float(value) if isinstance(value, float | int) else self._pos
        self.update()

    def _turn(self) -> None:
        self._spin = (self._spin + 24) % 360
        self.update()

    def _offset(self, i: int) -> float:
        n = len(self._items)
        d = (i - self._pos) % n
        return d - n if d > n / 2 else d

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw the band and the rows around the middle."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        mid = self.height() / 2
        p.setPen(QPen(QColor(C.MUTED), 1))
        p.setBrush(QColor(lift_fill()))
        p.drawRoundedRect(QRectF(4, mid - ROW / 2 + 2, self.width() - 8, ROW - 4), 8, 8)
        for i, item in enumerate(self._items):
            d = self._offset(i)
            if abs(d) > SHOWN + 0.6:
                continue
            p.setOpacity(max(0.0, 1.0 - 0.3 * abs(d)))
            self._draw_row(p, item, mid + d * ROW, abs(d) < 0.5)
        p.setOpacity(1.0)
        p.end()

    def _draw_row(self, p: QPainter, item: WheelItem, y: float, centre: bool) -> None:
        size = 34.0 if centre else 28.0
        centre_pt = QPointF(14 + size / 2, y)
        colour = QColor(tone(item.key))
        p.setPen(QPen(colour, 2))
        p.setBrush(QColor(C.OVERLAY))
        p.drawRoundedRect(QRectF(centre_pt.x() - size / 2, y - size / 2, size, size), 9, 9)
        if item.key == "working":
            p.setPen(QPen(QColor(C.BLUE), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            ring = QRectF(centre_pt.x() - size / 2 - 4, y - size / 2 - 4, size + 8, size + 8)
            p.drawArc(ring, -self._spin * 16, 100 * 16)
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() - (0 if centre else 1))
        p.setFont(font)
        p.setPen(QColor(C.TEXT))
        p.drawText(QRectF(14, y - size / 2, size, size), Qt.AlignmentFlag.AlignCenter,
                   initials(item.name))
        left = 14 + size + 12
        right = self.width() - left - 10
        font.setPointSizeF(font.pointSizeF() + (2 if centre else 0))
        font.setBold(centre)
        p.setFont(font)
        p.drawText(QRectF(left, y - 18, right, 20), Qt.AlignmentFlag.AlignLeft, item.name)
        small = QFont(self.font())
        small.setPointSizeF(small.pointSizeF() - 1.5)
        p.setFont(small)
        p.setPen(QColor(C.MUTED))
        p.drawText(QRectF(left, y + 2, right, 18), Qt.AlignmentFlag.AlignLeft, item.skill)
        p.setPen(colour)
        p.drawText(QRectF(left, y + 2, right, 18), Qt.AlignmentFlag.AlignRight, item.label)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Roll the clicked row to the middle."""
        if event is None or not self._items:
            return
        rows = round((event.position().y() - self.height() / 2) / ROW)
        if rows:
            self.step(rows)

    def wheelEvent(self, event: QWheelEvent | None) -> None:  # noqa: N802
        """Roll one row per wheel notch."""
        if event is None:
            return
        notch = event.angleDelta().y()
        if notch:
            self.step(-1 if notch > 0 else 1)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:  # noqa: N802
        """Up and Down roll the wheel."""
        if event is not None and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.step(-1 if event.key() == Qt.Key.Key_Up else 1)
        else:
            super().keyPressEvent(event)


class ProfilePane(QWidget):
    """The picked employee: role, model, this run's calls, last answer and spend."""

    edit_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lines = QVBoxLayout(self)
        lines.setContentsMargins(0, 6, 0, 0)
        lines.setSpacing(8)
        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.sub_label = muted("")
        self.state_label = QLabel()
        lines.addWidget(self.name_label)
        lines.addWidget(self.sub_label)
        lines.addWidget(self.state_label, 0, Qt.AlignmentFlag.AlignLeft)
        model_row = QHBoxLayout()
        model_key = QLabel("Model")
        model_key.setStyleSheet(f"color: {C.MUTED};")
        self.model_label = QLabel()
        self.model_label.setWordWrap(True)
        model_row.addWidget(model_key, 0, Qt.AlignmentFlag.AlignTop)
        model_row.addWidget(self.model_label, 1)
        lines.addLayout(model_row)
        lines.addWidget(heading("This run"))
        self.calls_label = QLabel()
        self.calls_label.setWordWrap(True)
        self.calls_label.setTextFormat(Qt.TextFormat.RichText)
        lines.addWidget(self.calls_label)
        self.brief_label = QLabel()
        self.brief_label.setWordWrap(True)
        self.brief_label.setTextFormat(Qt.TextFormat.PlainText)
        self.brief_label.setStyleSheet(
            f"color: {C.SUBTEXT}; background: {C.SURFACE}; border: 1px solid {C.OVERLAY2};"
            " border-radius: 8px; padding: 8px;")
        lines.addWidget(self.brief_label)
        buttons = QHBoxLayout()
        self.prompt_btn = QPushButton("Prompt")
        self.answer_btn = QPushButton("Answer")
        for btn in (self.prompt_btn, self.answer_btn):
            btn.setCheckable(True)
            btn.setStyleSheet(checked_style())
            buttons.addWidget(btn)
        buttons.addStretch(1)
        lines.addLayout(buttons)
        self.peek = read_only_text("")
        self.peek.setMaximumHeight(160)
        self.peek.hide()
        lines.addWidget(self.peek)
        # prompt/answer buttons → toggled → pane → _on_peek
        self.prompt_btn.toggled.connect(lambda on: self._on_peek("prompt", on))
        self.answer_btn.toggled.connect(lambda on: self._on_peek("answer", on))
        month = QHBoxLayout()
        month.addWidget(QLabel("Month"))
        self.month_bar = QProgressBar()
        self.month_bar.setRange(0, 100)
        self.month_bar.setTextVisible(False)
        self.month_bar.setMaximumHeight(6)
        self.month_label = QLabel()
        month.addWidget(self.month_bar, 1)
        month.addWidget(self.month_label)
        lines.addLayout(month)
        self.edit_btn = QPushButton("Edit in Team setup")
        self.edit_btn.setEnabled(False)
        lines.addWidget(self.edit_btn, 0, Qt.AlignmentFlag.AlignLeft)
        lines.addStretch(1)
        self._call: Call | None = None
        self._member_id = ""
        # edit button → clicked → pane → edit_requested(member id)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._member_id))

    def show_member(self, member: Member, state: MemberState, names: dict[str, str],
                    brief: str, month_usd: float) -> None:
        """Fill the pane for ``member`` in its ``state``."""
        self._member_id = member.id
        self.edit_btn.setEnabled(True)
        self.name_label.setText(member.name)
        boss = names.get(member.reports_to, "nobody")
        self.sub_label.setText(f"{member.title or member.level} · {skill_text(member.skill)} · "
                               f"reports to {boss}")
        self.state_label.setText(chip_text(state.label))
        self.state_label.setStyleSheet(chip_style(state.key))
        self.model_label.setText(f"{member.primary or '—'} · backup {member.backup or 'none'}")
        self.calls_label.setText(_calls_html(state.calls, member.on_demand))
        self._call = state.calls[-1] if state.calls else None
        self.brief_label.setText(f"“{brief}”" if brief else "No answer saved yet")
        share = min(100, round(month_usd / member.month_cap_usd * 100)) if \
            member.month_cap_usd > 0 else 0
        self.month_bar.setValue(share)
        self.month_label.setText(f"${month_usd:.2f} / ${member.month_cap_usd:.2f}")
        self._refresh_peek()

    def _on_peek(self, which: str, on: bool) -> None:
        other = self.answer_btn if which == "prompt" else self.prompt_btn
        if on and other.isChecked():
            other.blockSignals(True)
            other.setChecked(False)
            other.blockSignals(False)
        self._refresh_peek()

    def _refresh_peek(self) -> None:
        which = "prompt" if self.prompt_btn.isChecked() else (
            "answer" if self.answer_btn.isChecked() else "")
        self.peek.setVisible(bool(which))
        if not which:
            return
        if self._call is None:
            self.peek.setPlainText("No call in this run")
        else:
            text = self._call.prompt if which == "prompt" else (
                self._call.answer or self._call.error)
            self.peek.setPlainText(text or "(empty)")


def _calls_html(calls: Sequence[Call], on_demand: bool) -> str:
    if not calls:
        return (f"<span style='color:{C.MUTED}'>"
                + ("Not part of the morning run; wakes when you ask" if on_demand
                   else "No calls in this run") + "</span>")
    rows = []
    for c in calls:
        colour = C.GREEN if c.valid else C.RED
        answer = "valid" if c.valid else html.escape(c.error[:60] or "bad answer")
        rows.append((colour, f"{c.started:%H:%M:%S} · try "
                    f"{c.attempt} · {html.escape(c.source)} · {c.seconds:.1f} s · "
                    f"{c.tokens_in + c.tokens_out:,} tok · {answer}"))
    return bar_rows(rows)


SCORE_HEADERS = ("Employee", "Skill", "Runs", "Calls", "Valid", "Retries", "Backup",
                 "Avg time", "Slowest", "Avg tokens in / out", "Cost 30 d", "Per answer",
                 "Last problem")


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "—"


def score_cells(score: Score, name: str, skill: str) -> list[str]:
    """Text cells of one scorecard row."""
    per = score.cost_per_answer
    return [
        name, skill, str(score.runs), str(score.calls),
        f"{score.valid_share:.0%}" if score.valid_share is not None else "—",
        str(score.retries), _pct(score.backup_calls, score.calls),
        f"{score.avg_seconds:.1f} s" if score.calls else "—",
        f"{score.max_seconds:.1f} s" if score.calls else "—",
        f"{score.avg_tokens_in:,.0f} / {score.avg_tokens_out:,.0f}" if score.calls else "—",
        f"${score.cost_usd:.3f}", f"${per:.4f}" if per is not None else "—",
        f"{score.last_problem:%d %b %H:%M}" if score.last_problem else "none",
    ]


class ScoreTable(QTableWidget):
    """30-day scorecard: one row per employee and a team total row."""

    picked = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, len(SCORE_HEADERS), parent)
        self.setHorizontalHeaderLabels(list(SCORE_HEADERS))
        self.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setStyleSheet("QTableWidget { outline: none; }")
        head = self.horizontalHeader()
        if head is not None:
            head.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            head.setStretchLastSection(True)
        # table → cellClicked → scorecard → _on_click
        self.cellClicked.connect(self._on_click)

    def fill(self, scores: Sequence[Score], members: Sequence[Member]) -> None:
        """Show one row per member (same order as ``scores``) and the total row last."""
        self.setRowCount(len(scores))
        for row, score in enumerate(scores):
            member = members[row] if row < len(members) else None
            cells = score_cells(score, member.name if member else "Team total",
                                skill_text(member.skill) if member else "")
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, member.id if member else "")
                if member is None:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if col == 4 and score.valid_share is not None:
                    item.setForeground(QColor(_valid_tone(score.valid_share)))
                if col == 12 and score.last_error:
                    item.setToolTip(score.last_error)
                    item.setForeground(QColor(C.RED))
                self.setItem(row, col, item)

    def _on_click(self, row: int, _col: int) -> None:
        item = self.item(row, 0)
        member_id = str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""
        if member_id:
            self.picked.emit(member_id)


def _valid_tone(share: float) -> str:
    if share >= 0.9:
        return str(C.GREEN)
    return str(C.YELLOW if share >= 0.6 else C.RED)


def wheel_buttons(wheel: TeamWheel) -> tuple[QPushButton, QPushButton]:
    """Up and down buttons that roll ``wheel``."""
    up = arrow_button("Up", "Previous employee")
    down = arrow_button("Down", "Next employee")
    # buttons → clicked → wheel → step
    up.clicked.connect(lambda: wheel.step(-1))
    down.clicked.connect(lambda: wheel.step(1))
    return up, down
