"""
Module: MD-GUI-034.078.M40 — gui/ai_desk_day.py
Parent SRD: SRD-GUI-034.078
Also: MD-GUI-035.018.M06 — SRD-GUI-035.018 (day strip in Team at work)

Company day views (AI Desk v3 M5): the Day call and Handover tiles in the Command header
and the day strip of phases in Team at work. Read-only; data from ``core/desk_day.py``.
Both hide themselves while the company day is off.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_day import DayView, day_phases, day_view, plan_day, skill_names
from us_swing.gui.ai_desk_console import stat_tile
from us_swing.gui.theme import C

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


def handover_text(view: DayView) -> str:
    """Rich text for the Handover tile."""
    if not view.handover:
        return "No handover note yet"
    lines = "<br>".join(escape(line) for line in view.handover)
    return (f"<span style='font-size: 12px; font-weight: normal;'>{lines}</span><br>"
            f"<span style='font-size: 11px; font-weight: normal; color: {C.SUBTEXT};'>"
            f"plan of {view.handover_day}</span>")


class DayTiles(QWidget):
    """The Day call and Handover tiles for the Command header (SRD-GUI-034.078)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build both tiles; they stay hidden until ``refresh`` finds the company day on."""
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        call_tile, _head, self.call_label = stat_tile("Day call")
        hand_tile, _head, self.handover_label = stat_tile("Handover")
        for label in (self.call_label, self.handover_label):
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
        row.addWidget(call_tile, 1)
        row.addWidget(hand_tile, 2)
        self.hide()

    def refresh(self, home: Path) -> None:
        """Read the latest day call and handover again; hide while the company day is off."""
        if not load_settings(home).company_day_on:
            self.hide()
            return
        view = day_view(home)
        self.call_label.setText(call_text(view, skill_names(home)))
        self.handover_label.setText(handover_text(view))
        self.show()


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
