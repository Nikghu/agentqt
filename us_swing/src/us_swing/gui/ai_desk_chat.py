"""
Module: MD-GUI-034.039.M26 — gui/ai_desk_chat.py
Parent SRD: SRD-GUI-034.039
Also: SRD-GUI-034.040 (Ask box), SRD-GUI-034.041 (waiting check)
Also: MD-GUI-034.061.M35 — chat bubbles (SRD-GUI-034.061)
Also: SRD-GUI-034.074 (session list), SRD-GUI-034.075 (New discussion), SRD-GUI-034.076
(updates and the team note), SRD-GUI-034.079 (a table reply shown as a table)
Also: SRD-GUI-034.086 (clean conversation look: lead cards, Not answered notice, composer)
Also: SRD-GUI-034.088 (+ and menu buttons, discussions grouped by day in a tree)

The real lead chat in AI Desk → Command. Questions go to ``desk.db`` through
``core.desk_chat``; the desk process answers. This panel only shows the turns and asks.
"""
from __future__ import annotations

import html
from collections.abc import Callable
from datetime import date, datetime, timedelta
from itertools import groupby
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QShowEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_chat import (
    CELL_GAP,
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
from us_swing.gui.ai_desk_console import primary
from us_swing.gui.ai_desk_sections import heading, muted, scroll_of
from us_swing.gui.floor_charts import mix
from us_swing.gui.icons import icon_button
from us_swing.gui.theme import C

NY = ZoneInfo("America/New_York")
NO_TURNS = "Ask the lead about today's views, ideas and picks"
NEW_TALK = "New discussion: ask the lead a question"
LIST_W = 190
NOT_ANSWERED = "Not answered"
SANS = '"IBM Plex Sans", "Segoe UI", Arial, sans-serif'
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
    """One session row under its day: title and open or closed."""
    state = "open" if session.state == "open" else "closed"
    return f"{session.title} · {state}"


def _opened_day(session: ChatSession) -> date | None:
    try:
        return datetime.fromisoformat(session.opened).astimezone(NY).date()
    except ValueError:
        return None


def day_label(day: date | None, today: date) -> str:
    """A day group name: Today, Yesterday or e.g. ``Fri 13 Nov``."""
    if day is None:
        return "Earlier"
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    return f"{day:%a} {day.day} {day:%b}"


def table_html(text: str) -> str:
    """Chat text as HTML; each run of lines whose cells are joined by `` | `` becomes a table
    with the first line as its header (SRD-GUI-034.079). Other lines keep their line breaks."""
    out: list[str] = []
    for is_table, group in groupby(text.split("\n"), key=lambda line: CELL_GAP in line):
        lines = list(group)
        if not is_table:
            plain = "<br>".join(html.escape(line) for line in lines)
            out.append(plain if plain or not out else "<br>")
            continue
        rows = []
        for number, line in enumerate(lines):
            tag = "td" if number else "th"
            cells = "".join(f"<{tag} align='left'>{html.escape(cell)}</{tag}>"
                            for cell in line.split(CELL_GAP))
            rows.append(f"<tr>{cells}</tr>")
        out.append(f"<table cellspacing='0' cellpadding='3'>{''.join(rows)}</table>")
    return "".join(out)


def _bubble(mine: bool, who: str, text: str, created: str, failed: bool) -> QWidget:
    """One chat turn: the Master in a green bubble on the right; the lead as a plain card on
    the left with a coloured edge (red and "Not answered" when the desk had no answer)."""
    accent = C.RED if failed else (C.GREEN if mine else C.BLUE)
    flag = f" · {NOT_ANSWERED}" if failed else ""
    label = QLabel(f"<div style='margin-bottom:4px'><b style='color:{accent}'>"
                   f"{html.escape(who)}</b><span style='color:{C.MUTED}'> · "
                   f"{_et_time(created)}</span><b style='color:{accent}'>{flag}</b></div>"
                   f"<div style='line-height:140%; color:{C.TEXT}'>{table_html(text)}</div>")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    bubble = QFrame()
    bubble.setObjectName("chat_bubble")
    bubble.setProperty("mine", mine)
    if mine:
        look = f"background: {mix(C.SURFACE, C.GREEN, 0.14).name()}; border-radius: 10px;"
    else:
        look = (f"background: {mix(C.SURFACE, C.TEXT, 0.04).name()}; border-radius: 6px;"
                f" border-left: 3px solid {accent};")
    bubble.setStyleSheet(f"QFrame#chat_bubble {{ {look} }} QLabel {{ background: transparent;"
                         " border: none; }")
    inner = QVBoxLayout(bubble)
    inner.setContentsMargins(14, 10, 14, 10)
    inner.addWidget(label)
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    if mine:
        row.addStretch(2)
        row.addWidget(bubble, 3)
    else:
        row.addWidget(bubble, 6)
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
        self._side_open = True
        lines = QVBoxLayout(self)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(8)
        head = QHBoxLayout()
        self.menu_btn = icon_button("menu", "neutral", "Show or hide discussions")
        self.new_btn = icon_button("plus", "add", "New discussion")
        for button in (self.menu_btn, self.new_btn):
            button.setFixedWidth(C.BTN_H + 6)
            head.addWidget(button)
        head.addWidget(heading("Lead chat"))
        head.addStretch(1)
        lines.addLayout(head)
        body = QHBoxLayout()
        body.setSpacing(10)
        self.side = QWidget()
        self.side.setFixedWidth(LIST_W)
        side = QVBoxLayout(self.side)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(4)
        side.addWidget(muted("Discussions"))
        self.session_tree = QTreeWidget()
        self.session_tree.setHeaderHidden(True)
        self.session_tree.setIndentation(12)
        self.session_tree.setWordWrap(True)
        self.session_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.session_tree.setStyleSheet(
            "QTreeWidget { border: none; background: transparent; outline: none;"
            f" font-family: {SANS}; }}"
            " QTreeWidget::item { padding: 4px 4px; border-radius: 6px; }"
            f" QTreeWidget::item:selected {{ background: {C.OVERLAY}; color: {C.TEXT}; }}"
            " QTreeWidget::branch:selected { background: transparent; }")
        side.addWidget(self.session_tree, 1)
        body.addWidget(self.side)
        self._feed = QWidget()
        self._msgs = QVBoxLayout(self._feed)
        self._msgs.setContentsMargins(0, 0, 10, 0)
        self._msgs.setSpacing(10)
        self._scroll = scroll_of(self._feed)
        body.addWidget(self._scroll, 1)
        lines.addLayout(body, 1)
        self.note = muted("")
        self.note.setStyleSheet(f"color: {C.YELLOW}; background: transparent;")
        lines.addWidget(self.note)
        composer = QFrame()
        composer.setObjectName("chat_composer")
        composer.setStyleSheet(f"QFrame#chat_composer {{ background: {C.INPUT};"
                               f" border: 1px solid {C.OVERLAY2}; border-radius: 8px; }}")
        row = QHBoxLayout(composer)
        row.setContentsMargins(6, 4, 4, 4)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Message the lead")
        self.entry.setToolTip("Press Enter to send")
        self.entry.setMaxLength(MAX_QUESTION)
        self.entry.setStyleSheet("QLineEdit { border: none; background: transparent;"
                                 " outline: none; } QLineEdit:focus { border: none;"
                                 " outline: none; }")
        self.ask_btn = primary(QPushButton("Ask"))
        self.ask_btn.setFixedWidth(90)
        row.addWidget(self.entry, 1)
        row.addWidget(self.ask_btn)
        lines.addWidget(composer)
        self._timer = QTimer(self)
        self._timer.setInterval(CHECK_MS)
        # timer → timeout → panel → _tick
        self._timer.timeout.connect(self._tick)
        # entry → textChanged → panel → _update_button; Ask / Return → ask
        self.entry.textChanged.connect(self._on_text)
        self.ask_btn.clicked.connect(self.ask)
        self.entry.returnPressed.connect(self.ask)
        # session tree → itemClicked → panel → _pick; + → _new_talk; menu → _toggle_side
        self.session_tree.itemClicked.connect(self._pick)
        self.new_btn.clicked.connect(self._new_talk)
        self.menu_btn.clicked.connect(self._toggle_side)
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

    def _toggle_side(self) -> None:
        """Open or close the discussions list."""
        self._side_open = not self._side_open
        self.side.setVisible(self._side_open and self._sessions_on())

    def _pick(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        """Show a chosen session (the next question goes into it); a day row opens or closes."""
        sid = item.data(0, Qt.ItemDataRole.UserRole)
        if sid is None:
            item.setExpanded(not item.isExpanded())
            return
        self._chosen = self._session = int(sid)
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
        """Group sessions under their New York day; Today and Yesterday start open."""
        self.session_tree.clear()
        today = self._clock().astimezone(NY).date()
        groups: dict[str, QTreeWidgetItem] = {}
        for session in rows:
            day = _opened_day(session)
            name = day_label(day, today)
            group = groups.get(name)
            if group is None:
                group = QTreeWidgetItem(self.session_tree, [name])
                group.setFlags(Qt.ItemFlag.ItemIsEnabled)
                group.setForeground(0, QColor(C.SUBTEXT))
                bold = group.font(0)
                bold.setBold(True)
                group.setFont(0, bold)
                group.setExpanded(day is not None and day >= today - timedelta(days=1))
                groups[name] = group
            item = QTreeWidgetItem(group, [session_label(session)])
            item.setData(0, Qt.ItemDataRole.UserRole, session.id)
            item.setToolTip(0, session.title)
            if session.id == self._session:
                group.setExpanded(True)
                item.setSelected(True)

    def _current(self, on: bool, rows: list[ChatSession]) -> list[ChatTurn]:
        if not on:
            return chat_turns(self._home)
        if self._session is None and not self._new and rows:
            self._session = rows[0].id
        return session_turns(self._home, self._session) if self._session is not None else []

    def _show_turns(self) -> None:
        on = self._sessions_on()
        self.side.setVisible(on and self._side_open)
        self.new_btn.setVisible(on)
        self.menu_btn.setVisible(on)
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
