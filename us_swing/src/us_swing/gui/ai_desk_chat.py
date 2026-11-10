"""
Module: MD-GUI-034.039.M26 — gui/ai_desk_chat.py
Parent SRD: SRD-GUI-034.039
Also: SRD-GUI-034.040 (Ask box), SRD-GUI-034.041 (waiting check)
Also: MD-GUI-034.061.M35 — chat bubbles (SRD-GUI-034.061)

The real lead chat in AI Desk → Command. Questions go to ``desk.db`` through
``core.desk_chat``; the desk process answers. This panel only shows the turns and asks.
"""
from __future__ import annotations

import html
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_chat import (
    EXPIRED,
    WAITING,
    MAX_QUESTION,
    ask_question,
    chat_turns,
    question_note,
)
from us_swing.core.desk_contract import DeskState, desk_home
from us_swing.core.desk_hiring import employees
from us_swing.gui.ai_desk_sections import heading, muted, scroll_of
from us_swing.gui.floor_charts import mix
from us_swing.gui.theme import C

NY = ZoneInfo("America/New_York")
NO_TURNS = "Ask the lead about today's views, ideas and picks"
CHECK_MS = 2000
_UP = (DeskState.RUNNING, DeskState.SLEEPING)


def chat_name(home: Path) -> str:
    """Current name of the active chat employee, or "Lead" when there is none."""
    return next((e.name for e in employees(home) if e.skill == "lead_chat"
                 and e.status == "active"), "Lead")


def _et_time(created: str) -> str:
    try:
        return datetime.fromisoformat(created).astimezone(NY).strftime("%H:%M ET")
    except ValueError:
        return ""


def _bubble(mine: bool, who: str, text: str, created: str, failed: bool) -> QWidget:
    """One chat turn as a bubble: the Master on the right in green, the lead on the left."""
    colour = C.GREEN if mine else C.BLUE
    body = html.escape(text).replace("\n", "<br>")
    if failed:
        body = f"<span style='color:{C.MUTED}'>{body}</span>"
    label = QLabel(f"<b style='color:{colour}'>{html.escape(who)}</b>"
                   f"<span style='color:{C.MUTED}'> · {_et_time(created)}</span><br>{body}")
    label.setWordWrap(True)
    bubble = QFrame()
    bubble.setObjectName("chat_bubble")
    bubble.setProperty("mine", mine)
    tint = mix(C.SURFACE, colour, 0.15 if mine else 0.12).name()
    bubble.setStyleSheet(f"QFrame#chat_bubble {{ background: {tint}; border-radius: 6px; }}"
                         " QLabel { background: transparent; }")
    inner = QVBoxLayout(bubble)
    inner.setContentsMargins(10, 6, 10, 6)
    inner.addWidget(label)
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    if mine:
        row.addStretch(1)
    row.addWidget(bubble, 4)
    if not mine:
        row.addStretch(1)
    return holder


class ChatPanel(QWidget):
    """Chat turns, an Ask box, and a 2-second check while a question waits."""

    def __init__(self, home: Path | None, desk_state: Callable[[], DeskState],
                 clock: Callable[[], datetime] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._home = home or desk_home()
        self._desk_state = desk_state
        self._clock = clock or (lambda: datetime.now(NY))
        self._waiting: int | None = None
        self._shown: tuple[int, int, str] | None = None
        lines = QVBoxLayout(self)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.addWidget(heading("Lead chat"))
        self._feed = QWidget()
        self._msgs = QVBoxLayout(self._feed)
        self._msgs.setSpacing(6)
        self._scroll = scroll_of(self._feed)
        lines.addWidget(self._scroll, 1)
        self.note = muted("")
        lines.addWidget(self.note)
        row = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Message the lead")
        self.entry.setMaxLength(MAX_QUESTION)
        self.ask_btn = QPushButton("Ask")
        self.ask_btn.setFixedWidth(80)
        row.addWidget(self.entry, 1)
        row.addWidget(self.ask_btn)
        lines.addLayout(row)
        self._timer = QTimer(self)
        self._timer.setInterval(CHECK_MS)
        # timer → timeout → panel → _tick
        self._timer.timeout.connect(self._tick)
        # entry → textChanged → panel → _update_button; Ask / Return → ask
        self.entry.textChanged.connect(self._on_text)
        self.ask_btn.clicked.connect(self.ask)
        self.entry.returnPressed.connect(self.ask)
        self._resume()
        self._show_turns()
        self._update_button()

    def _resume(self) -> None:
        """Keep waiting for a question asked before this panel was built."""
        turns = chat_turns(self._home)
        replied = {t.reply_to for t in turns if t.role == "lead"}
        open_q = [t for t in turns if t.role == "master" and t.id not in replied]
        if open_q and question_note(self._home, open_q[-1].id, self._clock(), True) == WAITING:
            self._waiting = open_q[-1].id
            self._tick()
            if self._waiting is not None:
                self._timer.start()

    def _on_text(self) -> None:
        if self._waiting is None:
            self.note.setText("")
        self._update_button()

    def _show_turns(self) -> None:
        turns = chat_turns(self._home)
        key = (len(turns), turns[-1].id if turns else 0, turns[-1].state if turns else "")
        if key == self._shown:
            return
        self._shown = key
        while self._msgs.count():
            item = self._msgs.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()  # type: ignore[union-attr]
        if not turns:
            self._msgs.addWidget(muted(NO_TURNS))
        lead = chat_name(self._home)
        for t in turns:
            mine = t.role == "master"
            self._msgs.addWidget(_bubble(mine, "Master" if mine else lead, t.text, t.created,
                                         t.state == "failed"))
        self._msgs.addStretch(1)
        # after the layout settles → scroll to the newest turn
        QTimer.singleShot(0, self._to_bottom)

    def _to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.maximum())

    def _update_button(self) -> None:
        self.ask_btn.setEnabled(bool(self.entry.text().strip()) and self._waiting is None)

    def ask(self) -> None:
        """Send the typed question to the desk."""
        if not self.ask_btn.isEnabled():
            return
        try:
            self._waiting = ask_question(self._home, self.entry.text(), self._clock())
        except ValueError as exc:
            self.note.setText(str(exc))
            return
        self.entry.clear()
        self._tick()
        if self._waiting is not None:
            self._timer.start()

    def _tick(self) -> None:
        if self._waiting is None:
            self._timer.stop()
            return
        note = question_note(self._home, self._waiting, self._clock(),
                             self._desk_state() in _UP)
        self.note.setText(note)
        if not note or note == EXPIRED:
            self._waiting = None
            self._timer.stop()
        self._show_turns()
        self._update_button()
