"""
Module: MD-GUI-040.001.M01 — gui/ai_desk_cards.py
Parent SRD: SRD-GUI-040.001
Also: SRD-GUI-040.002–.004 (card detail, Test button, test log)

The AI Desk "Cards" section: the strategy cards the desk made from books and the latest test
of each. It reads through ``core.desk_cards``; the Test button only raises an approved test
ticket through ``core.desk_research``.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from us_swing.core.desk_cards import CardRow, CardTest, cards, latest_tests, open_test_cards
from us_swing.core.desk_contract import desk_home
from us_swing.core.desk_research import raise_owner_test
from us_swing.gui.ai_desk_sections import muted, section_frame
from us_swing.gui.theme import C

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
COLUMNS = ("Card", "Name", "Book", "Made", "Test", "Trades", "Avg R")
NO_CARDS = "No strategy cards yet. Book tickets make them"
TESTING = "Testing"
_RESULT_LABELS = {"pass": "Pass", "fail": "Fail", "cant_test": "Can't test"}


def result_label(card_id: int, latest: dict[int, CardTest], open_ids: set[int]) -> str:
    """Testing, Pass, Fail, Can't test or Not tested for one card."""
    if card_id in open_ids:
        return TESTING
    test = latest.get(card_id)
    if test is None:
        return "Not tested"
    return _RESULT_LABELS.get(test.result, "Not tested")


def card_detail(card: CardRow | None, test: CardTest | None) -> str:
    """The card rules and quotes, then the latest test line and verdict."""
    if card is None:
        return ""
    lines = [f"Idea: {card.idea}", f"Market: {card.market}", f"Entry: {card.entry}",
             f"Exit: {card.exit}", f"Stop: {card.stop}"]
    lines.extend(f"Quote: {q}" for q in card.quotes)
    if test is not None and test.result == "cant_test":
        lines.append(f"Last test: can't test — {test.reason}")
    elif test is not None and test.result in ("pass", "fail"):
        lines.append(
            f"Last test: {test.trades} trades, win rate {test.win_rate:.0%}, "
            f"average R {test.avg_r:+.2f}, worst losing run {test.worst_run}, "
            f"baseline {test.base_r:+.2f}R")
        lines.append(f"Verdict: {test.verdict}")
    return "\n".join(lines)


def _cells(card: CardRow, label: str, test: CardTest | None) -> list[str]:
    scored = test is not None and test.result in ("pass", "fail")
    return [f"SC-{card.id}", card.name, f"{card.source} ch {card.chapter}", card.made[:10],
            label, str(test.trades) if scored and test else "",
            f"{test.avg_r:+.2f}" if scored and test else ""]


def _table() -> QTableWidget:
    table = QTableWidget(0, len(COLUMNS))
    table.setHorizontalHeaderLabels(list(COLUMNS))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    side, head = table.verticalHeader(), table.horizontalHeader()
    if side is not None:
        side.setVisible(False)
    if head is not None:
        head.setStretchLastSection(True)
    return table


class CardsView(QWidget):
    """Card table, detail of the chosen card and the Test button."""

    def __init__(self, name: str, home: Path,
                 clock: Callable[[], datetime] | None = None) -> None:
        """Build the section for the desk folder ``home``."""
        super().__init__()
        self._home = home
        self._clock = clock or (lambda: datetime.now(NY))
        self._cards: list[CardRow] = []
        self._latest: dict[int, CardTest] = {}
        self._labels: dict[int, str] = {}
        frame, body = section_frame(name, sample=False)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        self.empty = muted(NO_CARDS)
        body.addWidget(self.empty)
        self.table = _table()
        body.addWidget(self.table, 3)
        buttons = QHBoxLayout()
        self.test_button = QPushButton("Test")
        self.test_button.clicked.connect(lambda _=False: self._test())
        buttons.addWidget(self.test_button)
        buttons.addStretch(1)
        body.addLayout(buttons)
        self.note = muted("")
        body.addWidget(self.note)
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        body.addWidget(self.detail, 2)
        # table selection → Test button and detail
        self.table.itemSelectionChanged.connect(self._on_pick)
        self.refresh()

    def refresh(self) -> None:
        """Read the cards, their latest tests and the open test tickets again."""
        try:
            rows = cards(self._home)
            latest = latest_tests(self._home)
            open_ids = open_test_cards(self._home)
        except sqlite3.Error:
            log.warning("[Research] Could not read the strategy cards; try again in a moment")
            self.note.setText("Could not read the strategy cards; try again in a moment")
            return
        self._cards, self._latest = rows, latest
        self._labels = {c.id: result_label(c.id, latest, open_ids) for c in rows}
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            label = self._labels[row.id]
            for c, text in enumerate(_cells(row, label, latest.get(row.id))):
                item = QTableWidgetItem(text)
                if c == 4 and label == TESTING:
                    item.setForeground(QColor(C.YELLOW))
                self.table.setItem(r, c, item)
        self.empty.setVisible(not rows)
        self.table.setVisible(bool(rows))
        self._on_pick()

    def _chosen(self) -> CardRow | None:
        model = self.table.selectionModel()
        rows = model.selectedRows() if model is not None else []
        return self._cards[rows[0].row()] if rows else None

    def _on_pick(self) -> None:
        card = self._chosen()
        self.test_button.setEnabled(card is not None and self._labels[card.id] != TESTING)
        self.detail.setText(card_detail(card, self._latest.get(card.id) if card else None))

    def _test(self) -> None:
        card = self._chosen()
        if card is None or self._labels[card.id] == TESTING:
            return
        try:
            answer = raise_owner_test(self._home, card.id, self._clock())
        except sqlite3.Error:
            log.warning("[Research] Could not start the card test; try again in a moment")
            self.note.setText("Test not started: could not write to the desk database")
            return
        if answer.startswith("ticket "):
            number = answer.split()[1]
            log.info("[Research] Test of card SC-%d started from the app as ticket %s",
                     card.id, number)
            self.note.setText(f"Test started as ticket {number}")
        else:
            why = answer.removeprefix("refused: ")
            log.info("[Research] Test of card SC-%d not started: %s", card.id, why)
            self.note.setText(f"Test not started: {why}")
        row = self._cards.index(card)
        self.refresh()
        if row < self.table.rowCount():
            self.table.selectRow(row)


def cards_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the Cards section for the desk folder ``home`` (the default folder when None)."""
    return CardsView(name, home or desk_home())
