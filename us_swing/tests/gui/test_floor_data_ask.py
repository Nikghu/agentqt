"""Tests for MD-GUI-034.042.M37 (Ask box in the Add panel catalog) and MD-GUI-034.043.M38
(asked panel cards and failed requests in Approvals waiting)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from tests.market.test_data_recipe import GOOD, _market
from us_swing.core import desk_data_asks as da
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_floor import DeskFloorData
from us_swing.core.desk_recipes import DataRecipe
from us_swing.data.market_calendar import ET
from us_swing.gui.ai_desk_hiring import WaitingBox, approvals_box
from us_swing.gui.floor_dialogs import ASK_SENT, CatalogDialog
from us_swing.gui.floor_feed import FeedCardWidget
from us_swing.gui.floor_sample import SampleFloorData

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=ET)


def _box(qtbot: QtBot, home: Path, now: datetime = NOW) -> WaitingBox:
    box = approvals_box(home, lambda: None, None, lambda: now)
    qtbot.addWidget(box)
    return box


def _proposed(home: Path, limit: int = 20) -> int:
    rid = da.ask_data(home, "Tech longs", NOW)
    recipe = DataRecipe.model_validate({**GOOD, "filters": [], "limit": limit})
    return da.add_asked(home, rid, recipe, "", NOW)


def _data_cards(box: WaitingBox) -> list[FeedCardWidget]:
    return [c for c in box.cards() if c.card.ref == "data"]


def _click(card: FeedCardWidget, text: str) -> None:
    next(b for b in card.findChildren(QPushButton) if b.text() == text).click()


def test_ask_box_sends(qtbot: QtBot) -> None:
    """UT-GUI-034.042.M37.T01: Ask sends the text, shows the sent note and clears the box."""
    sent: list[str] = []
    dialog = CatalogDialog([], ask=lambda text: sent.append(text) or "")
    qtbot.addWidget(dialog)
    dialog.ask_box.setText("  long scores above 80  ")
    assert dialog.ask_button.isEnabled() and dialog.ask_button.isDefault()
    dialog.ask_button.click()
    assert sent == ["long scores above 80"]
    assert dialog.ask_note.text() == ASK_SENT and dialog.ask_box.text() == ""
    assert dialog.add_button.isDefault()


def test_ask_box_guards(qtbot: QtBot) -> None:
    """UT-GUI-034.042.M37.T02: empty box disables Ask; no ask hides it; errors keep the text."""
    dialog = CatalogDialog([], ask=lambda _text: "Could not save the request")
    qtbot.addWidget(dialog)
    assert not dialog.ask_button.isEnabled()
    dialog.ask_box.setText("   ")
    assert not dialog.ask_button.isEnabled()
    dialog.ask_box.setText("Tech longs")
    dialog.ask_button.click()
    assert dialog.ask_note.text() == "Could not save the request"
    assert dialog.ask_box.text() == "Tech longs"
    plain = CatalogDialog([])
    qtbot.addWidget(plain)
    assert plain.ask_box.isHidden() and plain.ask_button.isHidden()


def test_product_card(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.043.M38.T01: one Ask card with title, recipe words and 5 preview rows."""
    _market(tmp_path)
    con = sqlite3.connect(tmp_path / DB_NAME)
    with con:
        for i in range(4):
            con.execute("INSERT INTO stock_score (date, symbol, side, score) VALUES "
                        "('2026-11-09', ?, 'long', 50)", (f"X{i}",))
    con.close()
    _proposed(tmp_path)
    box = _box(qtbot, tmp_path)
    [card] = _data_cards(box)
    assert box.count == 1
    assert card.card.subject == "New panel · Tech longs"
    lines = card.card.text.split("\n")
    assert lines[0].startswith("Scores · symbol, score, sector")
    assert len(lines) == 6
    heads = [w.text() for w in box.findChildren(QLabel) if w.objectName() == "view_head"]
    assert heads == ["Approvals waiting · 1"]


def test_approve_and_reject(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.043.M38.T02: decisions are saved, cards leave, only the approved one lists."""
    _market(tmp_path)
    keep, drop = _proposed(tmp_path), _proposed(tmp_path)
    box = _box(qtbot, tmp_path)
    cards = {c.card.item: c for c in _data_cards(box)}
    _click(cards[keep], "Approve")
    _click(cards[drop], "Reject")
    qtbot.waitUntil(lambda: _data_cards(box) == [])
    con = sqlite3.connect(tmp_path / DB_NAME)
    rows = con.execute("SELECT subject, decision FROM approvals ORDER BY id").fetchall()
    con.close()
    assert rows == [(str(keep), "approve"), (str(drop), "reject")]
    asked = [p.id for p in DeskFloorData(SampleFloorData(), tmp_path).products()
             if p.id.startswith("asked.")]
    assert asked == [f"asked.{keep}"]


def test_already_decided(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.043.M38.T03: a product decided elsewhere shows a note and turns buttons off."""
    pid = _proposed(tmp_path)
    box = _box(qtbot, tmp_path)
    [card] = _data_cards(box)
    da.decide_product(tmp_path, pid, "approve", NOW)
    _click(card, "Approve")
    assert card.note.text() == "already decided"
    assert card.approve_btn is not None and not card.approve_btn.isEnabled()
    assert card.reject_btn is not None and not card.reject_btn.isEnabled()


def _failed(home: Path, when: datetime) -> None:
    rid = da.ask_data(home, "Volume spikes", when)
    da.add_asked(home, rid, None, "No volume data in the menu", when)


def test_failed_note(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.044.M38.T01: a recent failure shows its reason, no buttons, not counted."""
    _failed(tmp_path, NOW - timedelta(hours=2))
    box = _box(qtbot, tmp_path)
    [card] = [c for c in box.cards() if c.card.kind == "desk"]
    assert card.card.text == "Volume spikes — No volume data in the menu"
    assert card.approve_btn is None and card.reject_btn is None
    assert box.count == 0


def test_old_failure_hidden(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.044.M38.T02: a failure older than one day is not shown."""
    _failed(tmp_path, NOW - timedelta(hours=25))
    assert _box(qtbot, tmp_path).cards() == []
