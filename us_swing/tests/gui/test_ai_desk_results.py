"""Tests for MD-GUI-034.037.M25 (AI Desk Results section)."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QLabel, QTableWidget, QWidget
from pytestqt.qtbot import QtBot

from tests.market.test_desk_results import FRI, SAT, _four, _results, _snap
from tests.market.test_desk_trades import _seed
from us_swing.core.desk_results import record_pick_trade
from us_swing.core.desk_trades import (
    TradePick,
    pick_expiry,
    record_trade_decision,
    record_trade_outcome,
)
from us_swing.gui.ai_desk_results import NO_PICKS, results_frame

_ALIVE: list[QWidget] = []


def _frame(qtbot: QtBot, home: Path) -> QWidget:
    frame = results_frame("Results", home, lambda: SAT)
    qtbot.addWidget(frame)
    _ALIVE.append(frame)
    return frame


def _labels(w: QWidget) -> list[str]:
    return [x.text() for x in w.findChildren(QLabel)]


def _cells(table: QTableWidget) -> list[list[str]]:
    return [[table.item(r, c).text() if table.item(r, c) else ""  # type: ignore[union-attr]
             for c in range(table.columnCount())] for r in range(table.rowCount())]


def test_totals_and_breakdowns(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.037.M25.T01: the top line has paper and real totals; three breakdown tables."""
    _four(tmp_path)
    pick = TradePick(FRI, "long", "TGT", 1, "", 100.0, 95.0, 110.0, pick_expiry(FRI))
    record_trade_decision(tmp_path, pick, "approve", 10, SAT)
    record_trade_outcome(tmp_path, pick.subject, "executed", SAT)
    record_pick_trade(tmp_path, _snap("TGT"), SAT)
    frame = _frame(qtbot, tmp_path)
    assert any(t.startswith("Paper: 4 picks, 3 filled, hit rate 50%") and "Real: 1 trades, 1 wins"
               in t for t in _labels(frame))
    assert {"Decision", "Setup grade", "News tone", "Picks"} <= set(_labels(frame))
    assert len(frame.findChildren(QTableWidget)) == 4


def test_no_picks(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.037.M25.T02: an empty desk shows the empty note."""
    assert NO_PICKS in _labels(_frame(qtbot, tmp_path))


def test_pick_table(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.038.M25.T01: newest day first; real P&L only on the traded pick."""
    _seed(tmp_path, "2026-11-05", [("long", "OLD", 100.0, 95.0, "pass")])
    _results(tmp_path, "2026-11-05", [("OLD", "stop", "2026-11-06", -1.0)])
    _four(tmp_path)
    pick = TradePick(FRI, "long", "TGT", 1, "", 100.0, 95.0, 110.0, pick_expiry(FRI))
    record_trade_decision(tmp_path, pick, "approve", 10, SAT)
    record_trade_outcome(tmp_path, pick.subject, "executed", SAT)
    record_pick_trade(tmp_path, _snap("TGT"), SAT)
    table = _frame(qtbot, tmp_path).findChild(QTableWidget, "results_picks")
    assert table is not None
    rows = _cells(table)
    assert rows[0][0] == FRI and rows[-1][:3] == ["2026-11-05", "long", "OLD"]
    assert [r[6] for r in rows if r[2] == "TGT"] == ["100.00"]
    assert all(r[6] == "" for r in rows if r[2] != "TGT")


def test_section_is_live(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.038.M25.T02: Results is a live section, rebuilt on each show."""
    from us_swing.gui.ai_desk import _LIVE_SECTIONS, SECTIONS, AiDeskWorkspace
    from us_swing.gui.desk_control import DeskPoller as Poller

    assert "Results" in SECTIONS and "Results" in _LIVE_SECTIONS
    page = AiDeskWorkspace(Poller(tmp_path))
    qtbot.addWidget(page)
    page.select_section("Results")
    assert NO_PICKS in _labels(page)
    _four(tmp_path)
    page.select_section("Command")
    page.select_section("Results")
    assert any(t.startswith("Paper: 4 picks") for t in _labels(page))


def test_not_worked_out_yet(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.038.M25.T03: picks without paper rows show a blank paper status."""
    _seed(tmp_path, FRI, [("long", "NEW", 100.0, 95.0, "pass")])
    table = _frame(qtbot, tmp_path).findChild(QTableWidget, "results_picks")
    assert table is not None
    assert _cells(table)[0][2:5] == ["NEW", "waiting", "—"]
