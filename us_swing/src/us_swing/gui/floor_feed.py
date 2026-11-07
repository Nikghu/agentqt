"""
Module: MD-GUI-034.004.M04 — Floor AI feed column
Parent SRD: SRD-GUI-034.004
Also: MD-GUI-034.015.M14 — real briefs from the desk (SRD-GUI-034.015)
Also: MD-GUI-034.062.M36 — quantity on pick cards (SRD-GUI-034.034)
Also: MD-GUI-034.053.M31 — typed cards, filter tabs, live dot, footer, actions
(SRD-GUI-034.053, .055–.057)
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_feed import FeedCard, approve_pick, reject_pick
from us_swing.core.desk_trades import DeskTradeSink
from us_swing.gui.floor_sample import SAMPLE_TAG, sample_feed_cards
from us_swing.gui.icons import icon_button, set_icon
from us_swing.gui.theme import C

_OPEN_WIDTH = 300
_FOLDED_WIDTH = 40
CUT_CHARS = 220
NY = ZoneInfo("America/New_York")
IST = ZoneInfo("Asia/Kolkata")
FILTERS: dict[str, tuple[str, ...]] = {
    "All": ("result", "ask", "answer", "desk"), "Ideas": ("result",), "Asks": ("ask",),
    "Alerts": ("desk",),
}
_KIND_TEXT = {"result": "Result", "ask": "Ask", "answer": "Answer", "desk": "Desk"}
_KIND_COLOUR = {"result": "ORANGE", "ask": "YELLOW", "answer": "TEAL", "desk": "RED"}
_BORDER = {"ask": "YELLOW", "desk": "RED"}


def _flat(button: QPushButton) -> QPushButton:
    button.setCheckable(True)
    button.setStyleSheet(
        f"QPushButton {{ background: transparent; border: 1px solid {C.OVERLAY};"
        f" color: {C.SUBTEXT}; padding: 0 8px; outline: none; }}"
        f"QPushButton:checked {{ background: {C.OVERLAY}; color: {C.TEXT}; outline: none; }}"
        "QPushButton:focus { outline: none; }"
    )
    return button


def time_text(when: datetime | None, now: datetime) -> tuple[str, str]:
    """Return ``(ET text, IST tooltip)``; the date shows when the card is not from today."""
    if when is None:
        return "", ""
    et = when.astimezone(NY)
    day = "" if et.date() == now.astimezone(NY).date() else f"{et:%m-%d} "
    return f"{day}{et:%H:%M} ET", f"{when.astimezone(IST):%m-%d %H:%M} IST"


class FeedContext:
    """What a card needs to decide a trade pick: the desk folder, the sink and a clock."""

    def __init__(self, home: Path | None, sink: DeskTradeSink | None,
                 clock: Callable[[], datetime]) -> None:
        self.home, self.sink, self.clock = home, sink, clock


class FeedCardWidget(QFrame):
    """One feed card: type label, sender, time, cut text with More, and its buttons."""

    chart_requested = pyqtSignal(str)
    section_requested = pyqtSignal(str)
    decided = pyqtSignal()

    def __init__(self, card: FeedCard, context: FeedContext,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.card, self._context = card, context
        self._open = False
        self.setObjectName("feed_card")
        border = getattr(C, _BORDER.get(card.kind, "OVERLAY"))
        self.setStyleSheet(
            f"QFrame#feed_card {{ background: {C.SURFACE}; border: 1px solid {border};"
            " border-radius: 6px; } QLabel { background: transparent; border: none; }"
        )
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(4)
        box.addLayout(self._head())
        self.text = QLabel()
        self.text.setTextFormat(Qt.TextFormat.PlainText)
        self.text.setWordWrap(True)
        box.addWidget(self.text)
        if card.pick is not None:
            sink = context.sink
            qty = sink.desk_pick_qty(card.pick) if sink is not None else None
            self.qty = QLabel(f"Qty {qty}" if qty else "Qty —")
            self.qty.setObjectName("feed_qty")
            self.qty.setStyleSheet(f"color: {C.SUBTEXT};")
            box.addWidget(self.qty)
        self.note = QLabel("")
        self.note.setStyleSheet(f"color: {C.MUTED};")
        self.note.setWordWrap(True)
        self.note.hide()
        box.addWidget(self.note)
        self.more_btn = QPushButton("More")
        # more button → clicked → card → _toggle_text
        self.more_btn.clicked.connect(self._toggle_text)
        self.more_btn.setVisible(len(card.text) > CUT_CHARS)
        self._buttons = QHBoxLayout()
        self._buttons.setSpacing(6)
        self._add_buttons()
        self._buttons.addStretch(1)
        self._buttons.addWidget(self.more_btn)
        box.addLayout(self._buttons)
        self._show_text()

    def _head(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        kind = QLabel(_KIND_TEXT[self.card.kind].upper())
        kind.setObjectName("feed_kind")
        colour = getattr(C, _KIND_COLOUR[self.card.kind])
        kind.setStyleSheet(f"color: {colour}; font-weight: 600;")
        who = QLabel(f"{self.card.sender} · {self.card.subject}")
        who.setTextFormat(Qt.TextFormat.PlainText)
        who.setStyleSheet(f"color: {C.MUTED};")
        who.setMinimumWidth(0)
        who.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        et, ist = time_text(self.card.when, self._context.clock())
        when = QLabel(et)
        when.setObjectName("feed_time")
        when.setToolTip(ist)
        when.setStyleSheet(f"color: {C.MUTED};")
        row.addWidget(kind)
        row.addWidget(who, 1)
        row.addWidget(when)
        return row

    def _button(self, text: str, slot: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(slot)  # card button → clicked → card → its action
        self._buttons.addWidget(button)
        return button

    def _add_buttons(self) -> None:
        card = self.card
        self.approve_btn: QPushButton | None = None
        self.reject_btn: QPushButton | None = None
        if card.ref == "pick":
            self.approve_btn = self._button("Approve", self._approve)
            self.reject_btn = self._button("Reject", self._reject)
            set_icon(self.approve_btn, "check", "add")
            set_icon(self.reject_btn, "x", "danger")
            can_decide = card.pick is not None and self._context.home is not None
            self.approve_btn.setEnabled(can_decide and self._context.sink is not None)
            self.reject_btn.setEnabled(can_decide)
        if card.symbol:
            self._button("Open in Charts", lambda: self.chart_requested.emit(card.symbol))
        if card.ref == "hire":
            self._button("Open Hiring", lambda: self.section_requested.emit("Hiring"))
        if card.ref == "chat":
            self._button("Open chat", lambda: self.section_requested.emit("Command"))

    def _show_text(self) -> None:
        text = self.card.text
        if not self._open and len(text) > CUT_CHARS:
            text = text[:CUT_CHARS].rstrip() + "…"
        self.text.setText(text)
        self.more_btn.setText("Less" if self._open else "More")

    def _toggle_text(self) -> None:
        self._open = not self._open
        self._show_text()

    def _result(self, result: tuple[str, bool]) -> None:
        note, closed = result
        if not note and closed:
            self.decided.emit()
            return
        self.note.setText(note)
        self.note.show()
        if closed:
            for button in (self.approve_btn, self.reject_btn):
                if button is not None:
                    button.setEnabled(False)

    def _approve(self) -> None:
        ctx, pick = self._context, self.card.pick
        if ctx.home is not None and ctx.sink is not None and pick is not None:
            self._result(approve_pick(ctx.home, pick, ctx.sink, ctx.clock()))

    def _reject(self) -> None:
        ctx, pick = self._context, self.card.pick
        if ctx.home is not None and pick is not None:
            self._result(reject_pick(ctx.home, pick, ctx.clock()))


class AiFeedColumn(QWidget):
    """Foldable AI feed: filter tabs, typed cards and a footer that opens the lead chat."""

    folded_changed = pyqtSignal(bool)
    chart_requested = pyqtSignal(str)
    section_requested = pyqtSignal(str)
    decided = pyqtSignal()

    def __init__(self, folded: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folded = folded
        self._cards: list[FeedCard] = []
        self._sample = True
        self._built = False
        self._filter = "All"
        self.context = FeedContext(None, None, lambda: datetime.now(NY))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        outer.addLayout(self._build_head())
        self._tabs_box = QWidget()
        tabs = QHBoxLayout(self._tabs_box)
        tabs.setContentsMargins(0, 0, 0, 0)
        tabs.setSpacing(0)
        self._group = QButtonGroup(self)
        self.filter_btns: dict[str, QPushButton] = {}
        for name in FILTERS:
            button = _flat(QPushButton(name))
            self._group.addButton(button)
            self.filter_btns[name] = button
            tabs.addWidget(button)
            # filter button → clicked → column → set_filter
            button.clicked.connect(lambda _c=False, n=name: self.set_filter(n))
        tabs.addStretch(1)
        self.filter_btns["All"].setChecked(True)
        outer.addWidget(self._tabs_box)
        self._body = QScrollArea()
        self._body.setWidgetResizable(True)
        self._body.setFrameShape(QFrame.Shape.NoFrame)
        self._body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self._body, 1)
        self.talk_btn = QPushButton("Talk to lead in AI Desk")
        # talk button → clicked → column → section_requested("Command")
        self.talk_btn.clicked.connect(lambda: self.section_requested.emit("Command"))
        outer.addWidget(self.talk_btn)
        self.set_cards(None)
        self.set_folded(folded)

    def _build_head(self) -> QHBoxLayout:
        head = QHBoxLayout()
        head.setSpacing(6)
        self._title = QLabel("AI feed · from desk")
        self._title.setObjectName("view_head")
        self._tag = QLabel(SAMPLE_TAG)
        self._tag.setStyleSheet(f"color: {C.MUTED};")
        self.live_dot = QLabel("●")
        self.live_dot.setObjectName("feed_live")
        self.set_live(False)
        self._fold_btn = icon_button("panel-left-open", "neutral", "Fold the AI feed")
        self._fold_btn.clicked.connect(self._toggle)  # button → clicked → column → _toggle
        head.addWidget(self._title)
        head.addWidget(self._tag)
        head.addStretch(1)
        head.addWidget(self.live_dot)
        head.addWidget(self._fold_btn)
        return head

    def set_live(self, live: bool) -> None:
        """Colour the live dot green while the desk is live, grey otherwise."""
        self.live_dot.setStyleSheet(f"color: {C.GREEN if live else C.MUTED};")
        self.live_dot.setToolTip("Desk is on" if live else "Desk is off")
        self.live_dot.setProperty("live", live)

    def set_cards(self, cards: list[FeedCard] | None) -> None:
        """Show ``cards`` (newest first); ``None`` shows sample cards with the Sample tag."""
        new = sample_feed_cards() if cards is None else list(cards)
        if self._built and new == self._cards and self._sample == (cards is None):
            return
        self._built = True
        self._sample = cards is None
        self._cards = new
        asks = sum(1 for c in self._cards if c.kind == "ask")
        self.filter_btns["Asks"].setText(f"Asks {asks}" if asks else "Asks")
        self._tag.setVisible(self._sample and not self._folded)
        self._rebuild()

    def set_filter(self, name: str) -> None:
        """Show only the cards of filter ``name`` (All, Ideas, Asks or Alerts)."""
        self._filter = name
        self.filter_btns[name].setChecked(True)
        self._rebuild()

    def shown_cards(self) -> list[FeedCardWidget]:
        """Return the card widgets on show, top first."""
        widget = self._body.widget()
        return widget.findChildren(FeedCardWidget) if widget is not None else []

    def _rebuild(self) -> None:
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(6)
        kinds = FILTERS[self._filter]
        shown = [c for c in self._cards if c.kind in kinds]
        for card in shown:
            widget = FeedCardWidget(card, self.context)
            widget.chart_requested.connect(self.chart_requested)  # card → column → page
            widget.section_requested.connect(self.section_requested)
            widget.decided.connect(self.decided)
            layout.addWidget(widget)
        if not shown:
            empty = QLabel("Nothing here yet")
            empty.setStyleSheet(f"color: {C.MUTED};")
            layout.addWidget(empty)
        layout.addStretch(1)
        old = self._body.takeWidget()
        self._body.setWidget(holder)
        if old is not None:
            old.deleteLater()  # a card may still be inside its own click handler

    def is_folded(self) -> bool:
        """Return True when only the unfold button shows."""
        return self._folded

    def set_folded(self, folded: bool) -> None:
        """Fold or unfold the column; emits ``folded_changed`` when the state changes."""
        changed = folded != self._folded
        self._folded = folded
        for widget in (self._title, self._body, self._tabs_box, self.talk_btn, self.live_dot):
            widget.setVisible(not folded)
        self._tag.setVisible(self._sample and not folded)
        set_icon(self._fold_btn, "panel-left-open" if folded else "panel-left-close")
        tip = "Show the AI feed" if folded else "Fold the AI feed"
        self._fold_btn.setToolTip(tip)
        self._fold_btn.setAccessibleName(tip)
        self.setFixedWidth(_FOLDED_WIDTH if folded else _OPEN_WIDTH)
        if changed:
            self.folded_changed.emit(folded)

    def _toggle(self) -> None:
        self.set_folded(not self._folded)
