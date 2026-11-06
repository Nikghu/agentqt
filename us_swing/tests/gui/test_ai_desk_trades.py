"""Tests for MD-GUI-034.034.M24 (trade pick rows in Command → Approvals waiting).
Employee names here are made up."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import QLabel, QListWidget, QWidget
from pytestqt.qtbot import QtBot

from tests.gui.test_ai_desk_hiring import _ready
from tests.market.test_desk_trades import _seed
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_trades import TradePick, record_trade_decision, trade_picks
from us_swing.data.market_calendar import ET
from us_swing.gui.ai_desk_hiring import NO_APPROVALS, TradePickRow, approvals_box

FRI = "2026-11-06"
SAT = datetime(2026, 11, 7, 12, 0, tzinfo=ET)
MON_10 = datetime(2026, 11, 9, 10, 0, tzinfo=ET)


class _Sink:
    def __init__(self, qty: int = 45, why: str = "") -> None:
        self.qty, self.why = qty, why
        self.sent: list[str] = []
        self.dismissed: list[str] = []

    def desk_pick_qty(self, pick: TradePick) -> int:
        return self.qty

    def send_desk_pick(self, pick: TradePick) -> tuple[int, str]:
        self.sent.append(pick.symbol)
        return (0, self.why) if self.why else (self.qty, "")

    def dismiss_desk_pick(self, pick: TradePick) -> None:
        self.dismissed.append(pick.symbol)


def _two(home: Path) -> None:
    _seed(home, FRI, [("long", "AAA", 100.0, 95.0, "pass"), ("short", "BBB", 50.0, 52.0, "pass")])


_ALIVE: list[QWidget] = []


def _box(qtbot: QtBot, home: Path, sink: _Sink | None, clock: list[datetime]) -> QWidget:
    box = approvals_box(home, lambda: None, sink, lambda: clock[0])
    qtbot.addWidget(box)
    _ALIVE.append(box)  # an unparented box is freed with its last Python reference
    return box


def _rows(box: QWidget) -> list[TradePickRow]:
    return box.findChildren(TradePickRow)


def _decisions(home: Path) -> list[tuple[str, str, int]]:
    con = sqlite3.connect(home / DB_NAME)
    try:
        rows = con.execute("SELECT subject, decision, detail FROM approvals "
                           "WHERE kind = 'trade'").fetchall()
    except sqlite3.OperationalError:
        rows = []  # no approvals table yet: nothing was saved
    finally:
        con.close()
    return [(s, d, json.loads(x)["qty"]) for s, d, x in rows]


def test_pick_rows(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.034.M24.T01: hires stay listed and each waiting pick gets a row with buttons."""
    _ready(tmp_path)
    _two(tmp_path)
    box = _box(qtbot, tmp_path, _Sink(), [SAT])
    assert box.findChild(QListWidget, "approvals_list") is not None
    rows = _rows(box)
    assert [r.text.text() for r in rows] == [
        "LONG  AAA  entry 100.00  stop 95.00  target 110.00  qty 45",
        "SHORT  BBB  entry 50.00  stop 52.00  target 46.00  qty 45"]
    assert all(r.approve_btn.isEnabled() and r.reject_btn.isEnabled() for r in rows)


def test_no_picks_or_no_sink(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.034.M24.T02: the empty note with nothing waiting; no sink disables the buttons."""
    box = _box(qtbot, tmp_path, _Sink(), [SAT])
    assert NO_APPROVALS in [w.text() for w in box.findChildren(QLabel)]
    _two(tmp_path)
    rows = _rows(_box(qtbot, tmp_path, None, [SAT]))
    assert rows[0].text.text().endswith("qty —")
    assert not rows[0].approve_btn.isEnabled() and not rows[0].reject_btn.isEnabled()


def test_no_desk_data(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.034.M24.T03: with no lead picks the hire line still shows and no row is made."""
    _ready(tmp_path)
    box = _box(qtbot, tmp_path, _Sink(), [SAT])
    assert box.findChild(QListWidget, "approvals_list") is not None
    assert _rows(box) == []


def test_approve(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.035.M24.T01: Approve sends once, saves the approve row and hides the row."""
    _two(tmp_path)
    sink = _Sink()
    row = _rows(_box(qtbot, tmp_path, sink, [SAT]))[0]
    row.approve_btn.click()
    assert sink.sent == ["AAA"]
    assert _decisions(tmp_path) == [(f"{FRI}:long:AAA", "approve", 45)]
    assert row.isHidden()


def test_reject(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.035.M24.T02: Reject saves the reject row and sends nothing."""
    _two(tmp_path)
    sink = _Sink()
    row = _rows(_box(qtbot, tmp_path, sink, [SAT]))[1]
    row.reject_btn.click()
    assert sink.sent == []
    assert _decisions(tmp_path) == [(f"{FRI}:short:BBB", "reject", 0)]
    assert row.isHidden()


def test_send_refused(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.035.M24.T03: a refused send saves nothing and shows why."""
    _two(tmp_path)
    row = _rows(_box(qtbot, tmp_path, _Sink(why="quantity is 0"), [SAT]))[0]
    row.approve_btn.click()
    assert _decisions(tmp_path) == []
    assert row.note.text() == "quantity is 0"
    assert row.approve_btn.isEnabled() and not row.isHidden()


def test_expired_at_click(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.035.M24.T04: a pick that expired after the box was shown is not sent."""
    _two(tmp_path)
    clock = [SAT]
    sink = _Sink()
    row = _rows(_box(qtbot, tmp_path, sink, clock))[0]
    clock[0] = MON_10
    row.approve_btn.click()
    assert sink.sent == [] and _decisions(tmp_path) == []
    assert row.note.text() == "expired at the market open"


def test_decided_and_expired_drop_off(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.036.M24.T01: only waiting picks are listed when the box is built again."""
    _seed(tmp_path, FRI, [("long", "AAA", 100.0, 95.0, "pass"), ("long", "BBB", 10.0, 9.0, "pass"),
                          ("long", "CCC", 20.0, 19.0, "pass")])
    picks = {p.symbol: p for p in trade_picks(tmp_path, SAT, 2.0)}
    record_trade_decision(tmp_path, picks["AAA"], "approve", 1, SAT)
    record_trade_decision(tmp_path, picks["BBB"], "reject", 0, SAT)
    assert [r.text.text().split()[1] for r in _rows(_box(qtbot, tmp_path, _Sink(), [SAT]))] == [
        "CCC"]
    assert _rows(_box(qtbot, tmp_path, _Sink(), [MON_10])) == []
