"""
Module: MD-GUI-034.039.M26 — gui/ai_desk_chat.py
Parent SRD: SRD-GUI-034.039
Also: SRD-GUI-034.040 (Ask box), SRD-GUI-034.041 (waiting check)
Also: MD-GUI-034.061.M35 — chat bubbles (SRD-GUI-034.061)
Also: SRD-GUI-034.074 (session list), SRD-GUI-034.075 (New discussion), SRD-GUI-034.076
(updates and the team note)

The real lead chat in AI Desk → Command. Questions go to ``desk.db`` through
``core.desk_chat``; the desk process answers. This panel only shows the turns and asks.
"""
from __future__ import annotations

import html
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_chat import (
    EXPIRED,
    MAX_QUESTION,
    TEAM,
    WAITING,
    ChatSession,
    ChatTurn,
    ask_question,
    chat_turns,
    close_session,
    question_note,
    session_for,
    session_turns,
    sessions,
)
from us_swing.core.desk_contract import DeskState, desk_home
from us_swing.core.desk_hiring import employees
from us_swing.gui.ai_desk_sections import heading, muted, scroll_of
from us_swing.gui.floor_charts import mix
from us_swing.gui.theme import C

NY = ZoneInfo("America/New_York")
NO_TURNS = "Ask the lead about today's views, ideas and picks"
NEW_TALK = "New discussion: ask the lead a question"
LIST_W = 220
GRACE_TICKS = 3
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


def session_label(session: ChatSession) -> str:
    """One session row: title, New York date and open or closed."""
    try:
        day = datetime.fromisoformat(session.opened).astimezone(NY).strftime("%m-%d")
    except ValueError:
        day = ""
    state = "open" if session.state == "open" else "closed"
    return f"{session.title} · {day} · {state}"


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
        self._shown: tuple[object, ...] | None = None
        self._chosen: int | None = None
        self._new = False
        self._session: int | None = None
        self._grace = 0
        lines = QVBoxLayout(self)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.addWidget(heading("Lead chat"))
        body = QHBoxLayout()
        self.side = QWidget()
        self.side.setFixedWidth(LIST_W)
        side = QVBoxLayout(self.side)
        side.setContentsMargins(0, 0, 0, 0)
        self.new_btn = QPushButton("New discussion")
        self.session_list = QListWidget()
        side.addWidget(self.new_btn)
        side.addWidget(self.session_list, 1)
        body.addWidget(self.side)
        self._feed = QWidget()
        self._msgs = QVBoxLayout(self._feed)
        self._msgs.setSpacing(6)
        self._scroll = scroll_of(self._feed)
        body.addWidget(self._scroll, 1)
        lines.addLayout(body, 1)
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
        # session list → itemClicked → panel → _pick; New discussion → _new_talk
        self.session_list.itemClicked.connect(self._pick)
        self.new_btn.clicked.connect(self._new_talk)
        self._resume()
        self._show_turns()
        self._update_button()

    def showEvent(self, event: QShowEvent | None) -> None:  # noqa: N802 — Qt override
        """Read the turns and the Chat sessions switch again each time the chat is shown."""
        super().showEvent(event)
        self._show_turns()

    def _sessions_on(self) -> bool:
        return load_settings(self._home).sessions_on

    def _resume(self) -> None:
        """Keep waiting for a question asked before this panel was built."""
        asked = [t for t in chat_turns(self._home) if t.role == "master"]
        if asked and question_note(self._home, asked[-1].id, self._clock(),
                                   True) in (WAITING, TEAM):
            self._waiting = asked[-1].id
            self._tick()
            if self._waiting is not None:
                self._timer.start()

    def _on_text(self) -> None:
        if self._waiting is None:
            self.note.setText("")
        self._update_button()

    def _pick(self, item: QListWidgetItem) -> None:
        """Show a chosen session; the next question goes into it."""
        self._chosen = self._session = int(item.data(Qt.ItemDataRole.UserRole))
        self._new = False
        self._show_turns()

    def _new_talk(self) -> None:
        """Close the shown session; the next question starts a new one."""
        if self._session is not None:
            close_session(self._home, self._session)
        self._chosen = self._session = None
        self._new = True
        self._show_turns()

    def _fill_list(self, rows: list[ChatSession]) -> None:
        self.session_list.clear()
        for session in rows:
            item = QListWidgetItem(session_label(session))
            item.setData(Qt.ItemDataRole.UserRole, session.id)
            self.session_list.addItem(item)
            if session.id == self._session:
                item.setSelected(True)

    def _current(self, on: bool, rows: list[ChatSession]) -> list[ChatTurn]:
        if not on:
            return chat_turns(self._home)
        if self._session is None and not self._new and rows:
            self._session = rows[0].id
        return session_turns(self._home, self._session) if self._session is not None else []

    def _show_turns(self) -> None:
        on = self._sessions_on()
        self.side.setVisible(on)
        rows = sessions(self._home) if on else []
        turns = self._current(on, rows)
        key = (on, self._session, tuple((r.id, r.state) for r in rows), len(turns),
               turns[-1].id if turns else 0, turns[-1].state if turns else "")
        if key == self._shown:
            return
        if on:
            self._fill_list(rows)
        self._shown = key
        while self._msgs.count():
            item = self._msgs.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()  # type: ignore[union-attr]
        if not turns:
            self._msgs.addWidget(muted(NEW_TALK if self._new else NO_TURNS))
        lead = chat_name(self._home)
        for t in turns:
            mine = t.role == "master"
            who = "Master" if mine else (f"{lead} · Update" if t.role == "update" else lead)
            self._msgs.addWidget(_bubble(mine, who, t.text, t.created, t.state == "failed"))
        self._msgs.addStretch(1)
        # after the layout settles → scroll to the newest turn
        QTimer.singleShot(0, self._to_bottom)

    def _to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.maximum())

    def _update_button(self) -> None:
        free = self._waiting is None or self.note.text() == TEAM
        self.ask_btn.setEnabled(bool(self.entry.text().strip()) and free)

    def ask(self) -> None:
        """Send the typed question to the desk."""
        if not self.ask_btn.isEnabled():
            return
        text, now = self.entry.text(), self._clock()
        try:
            session = None
            if self._sessions_on():
                session = session_for(self._home, now, self._chosen, text, self._new)
                self._session, self._new = session, False
            self._waiting = ask_question(self._home, text, now, session=session)
            self._grace = 0
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
        if not note and self._sessions_on() and self._grace < GRACE_TICKS:
            self._grace += 1  # the desk stores a team ask just after the answer
        elif not note or note == EXPIRED:
            self._waiting = None
            self._timer.stop()
        self._show_turns()
        self._update_button()
