"""
Module: MD-GUI-034.078.M40 — gui/ai_desk_day.py
Parent SRD: SRD-GUI-034.078
Also: MD-GUI-034.092.M41 — Today block moved to the AI feed (SRD-GUI-034.092)
Also: MD-GUI-035.018.M06 — SRD-GUI-035.018 (day strip in Team at work)

Company day views (AI Desk v3 M5): the Today block (Day call and Handover) at the top of
the AI feed (SRD-GUI-034.092) and the day strip of phases in Team at work. Read-only; data from ``core/desk_day.py``.
Both hide themselves while the company day is off.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_day import DayView, day_phases, day_view, plan_day, skill_names
from us_swing.gui.theme import C

_PLAIN = "background: transparent; border: none;"
_RESULT_TONE = {"right": C.GREEN, "wrong": C.RED, "neutral": C.SUBTEXT}


def call_text(view: DayView, names: dict[str, str]) -> str:
    """Rich text for the Day call tile."""
    call = view.call
    if call is None:
        return "No day call yet"
    head = escape(f"{call.market} · {', '.join(call.favour)}")
    agreed = [escape(names.get(v.skill, v.skill)) for v in view.votes if v.stance == "agreed"]
    disagreed = [escape(names.get(v.skill, v.skill)) for v in view.votes
                 if v.stance == "disagreed"]
    parts = [f"Agreed: {', '.join(agreed) or 'none'}",
             f"Disagreed: {', '.join(disagreed) or 'none'}"]
    if call.huddle:
        parts.append("Huddle")
    if call.market_result:
        tone = _RESULT_TONE.get(call.market_result, C.SUBTEXT)
        parts.append(f"<span style='color: {tone};'>{escape(call.market_result)}</span>")
    small = " · ".join(parts)
    return f"{head}<br><span style='font-size: 11px; font-weight: normal;'>{small}</span>"


def handover_text(view: DayView, limit: int | None = None) -> str:
    """Rich text for the Handover; ``limit`` keeps only the first lines, with an ellipsis."""
    if not view.handover:
        return "No handover note yet"
    lines = list(view.handover)
    if limit is not None and len(lines) > limit:
        lines = lines[:limit]
        lines[-1] += " …"
    body = "<br>".join(escape(line) for line in lines)
    return (f"<span style='font-size: 12px; font-weight: normal;'>{body}</span><br>"
            f"<span style='font-size: 11px; font-weight: normal; color: {C.SUBTEXT};'>"
            f"plan of {view.handover_day}</span>")


class DayTiles(QFrame):
    """The Today block at the top of the AI feed: Day call and Handover (SRD-GUI-034.092)."""

    FOLDED_LINES = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the block; it stays hidden until ``refresh`` finds the company day on."""
        super().__init__(parent)
        self.setObjectName("day_block")
        self.setStyleSheet(f"QFrame#day_block {{ background: {C.SURFACE};"
                           f" border: 1px solid {C.OVERLAY2}; border-radius: 8px; }}")
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(4)
        self._view: DayView | None = None
        self._open = False
        self.call_label = self._section(box, "Day call")
        head = self._section_head("Handover")
        self.more_btn = QPushButton("More")
        self.more_btn.setFlat(True)
        self.more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_btn.setStyleSheet(f"QPushButton {{ color: {C.BLUE}; {_PLAIN}"
                                    " padding: 0 4px; outline: none; }"
                                    f"QPushButton:hover {{ color: {C.TEXT}; }}")
        # more button → clicked → block → toggle the full handover
        self.more_btn.clicked.connect(self._toggle)
        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 0)
        row.addWidget(head)
        row.addStretch(1)
        row.addWidget(self.more_btn)
        box.addLayout(row)
        self.handover_label = self._value()
        box.addWidget(self.handover_label)
        self.hide()

    @staticmethod
    def _section_head(title: str) -> QLabel:
        head = QLabel(title)
        head.setStyleSheet(f"color: {C.MUTED}; font-size: 11px; {_PLAIN}")
        return head

    @staticmethod
    def _value() -> QLabel:
        label = QLabel("")
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setStyleSheet(f"font-size: 13px; font-weight: bold; {_PLAIN}")
        return label

    def _section(self, box: QVBoxLayout, title: str) -> QLabel:
        box.addWidget(self._section_head(title))
        label = self._value()
        box.addWidget(label)
        return label

    def refresh(self, home: Path) -> None:
        """Read the latest day call and handover again; hide while the company day is off."""
        if not load_settings(home).company_day_on:
            self.hide()
            return
        self._view = day_view(home)
        self.call_label.setText(call_text(self._view, skill_names(home)))
        self._show_handover()
        self.show()

    def _toggle(self) -> None:
        self._open = not self._open
        self._show_handover()

    def _show_handover(self) -> None:
        if self._view is None:
            return
        long = len(self._view.handover) > self.FOLDED_LINES
        self.more_btn.setVisible(long)
        self.more_btn.setText("Less" if self._open else "More")
        limit = None if self._open else self.FOLDED_LINES
        self.handover_label.setText(handover_text(self._view, limit))


class DayStrip(QFrame):
    """One line of the company day phases for Team at work (SRD-GUI-035.018)."""

    PHASES = ("Stand-up", "Huddle", "Plan", "Market hours", "Day-end")

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build one label per phase; hidden until ``refresh`` finds the company day on."""
        super().__init__(parent)
        self.setObjectName("day_strip")
        self.setStyleSheet(f"QFrame#day_strip {{ background: {C.SURFACE};"
                           f" border: 1px solid {C.OVERLAY2}; border-radius: 8px; }}")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 12, 6)
        row.setSpacing(18)
        self.day_label = QLabel("")
        self.day_label.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 11px;")
        row.addWidget(self.day_label)
        self.labels: dict[str, QLabel] = {}
        for name in self.PHASES:
            label = QLabel(name)
            label.setStyleSheet("font-size: 12px;")
            label.setTextFormat(Qt.TextFormat.RichText)
            self.labels[name] = label
            row.addWidget(label)
        row.addStretch(1)
        self.hide()

    def refresh(self, home: Path, now: datetime) -> None:
        """Show the phases of the latest plan; hide while the company day is off."""
        if not load_settings(home).company_day_on:
            self.hide()
            return
        day = plan_day(home, "9999-12-31")
        if not day:
            self.hide()
            return
        self.day_label.setText(f"Plan of {day}")
        for name, state in day_phases(home, day, now):
            tone = C.SUBTEXT if state in ("waiting", "skipped") else C.TEXT
            self.labels[name].setText(f"{name}: <span style='color: {tone};'>{state}</span>")
        self.show()
