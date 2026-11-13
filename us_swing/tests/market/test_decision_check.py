"""Tests for MD-MKT-020.014.M06 — market/decision_check.py (day call check, AI Desk v3 M5)."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from us_swing.core.desk_ai_settings import SETTINGS_FILE
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_day import connect, save_call
from us_swing.desk.recorder import NY
from us_swing.market import decision_check
from us_swing.market.decision_check import (
    DecisionCheckStep,
    market_result,
    sector_result,
    vote_result,
)
from us_swing.market.store import MarketStore, RegimeViewRow, SectorViewRow

DAY = "2026-11-02"
DUE = "2026-11-09"
RUN = datetime(2026, 11, 12, 5, 0, tzinfo=NY)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "desk"
    path.mkdir()
    (path / SETTINGS_FILE).write_text(json.dumps({"company_day_on": True}), encoding="utf-8")
    return path


def _candles(tmp_path: Path, closes: list[float]) -> Path:
    path = tmp_path / "candles.db"
    con = sqlite3.connect(path)
    with con:
        con.execute("CREATE TABLE IF NOT EXISTS price_1d (symbol TEXT, datetime TEXT, open REAL, "
                    "high REAL, low REAL, close REAL, volume REAL)")
        days = pd.bdate_range(DAY, periods=len(closes))
        con.executemany("INSERT INTO price_1d VALUES ('SPY', ?, ?, ?, ?, ?, 1000)",
                        [(d.strftime("%Y-%m-%d"), c, c, c, c)
                         for d, c in zip(days, closes, strict=True)])
    con.close()
    return path


def _call(home: Path, market: str = "Uptrend", favour: tuple[str, ...] = ("Energy",),
          regime: str = "Uptrend", sector_favour: tuple[str, ...] = ("Energy",)) -> None:
    store = MarketStore(home)
    try:
        store.write_regime_view(RegimeViewRow(DAY, regime, 0.6, "[]", "b", regime, True))
        store.replace_day("sector_view", DAY, [SectorViewRow(
            DAY, json.dumps(list(sector_favour)), "[]", "r", "b")])
        end = pd.bdate_range(DAY, periods=6)[-1].strftime("%Y-%m-%d")
        con = sqlite3.connect(home / "desk.db")
        with con:
            for sector, start_line, end_line in (("Energy", 100.0, 104.0),
                                                 ("Utilities", 100.0, 100.0)):
                con.execute("INSERT INTO sector_daily (date, sector, line) VALUES (?, ?, ?)",
                            (DAY, sector, start_line))
                con.execute("INSERT INTO sector_daily (date, sector, line) VALUES (?, ?, ?)",
                            (end, sector, end_line))
        con.close()
    finally:
        store.close()
    save_call(home, DAY, market, list(favour), "", DUE, RUN)


def _decision(home: Path) -> Any:
    con = connect(home)
    try:
        return con.execute("SELECT status, market_result, sector_result, spy_move, sector_move "
                           "FROM decisions").fetchone()
    finally:
        con.close()


def _votes(home: Path) -> list[Any]:
    con = connect(home)
    try:
        return con.execute("SELECT skill, result FROM decision_votes ORDER BY skill").fetchall()
    finally:
        con.close()


def _run(home: Path, candles: Path) -> None:
    DecisionCheckStep(candles)(StepContext(1, "morning", RUN, home))


def test_trend_calls_right() -> None:
    """UT-MKT-020.015.M06.T01: Up +1.5, Down -1.2 and Choppy +0.4 are right."""
    assert market_result("Uptrend", 1.5) == "right"
    assert market_result("Downtrend", -1.2) == "right"
    assert market_result("Choppy", 0.4) == "right"


def test_trend_calls_wrong_or_neutral() -> None:
    """UT-MKT-020.015.M06.T02: Wrong at 1% the other way or Choppy at 2%; else neutral."""
    assert market_result("Uptrend", -1.0) == "wrong"
    assert market_result("Choppy", -2.5) == "wrong"
    assert market_result("Uptrend", 0.5) == "neutral"
    assert market_result("Choppy", 1.5) == "neutral"


def test_sector_part() -> None:
    """UT-MKT-020.016.M06.T01: Gap +0.6 right, -0.7 wrong, +0.2 neutral, none neutral."""
    assert [sector_result(g) for g in (0.6, -0.7, 0.2, None)] == [
        "right", "wrong", "neutral", "neutral"]


def test_sector_with_no_line(home: Path, tmp_path: Path) -> None:
    """UT-MKT-020.016.M06.T02: A favoured sector with no line makes the sector part neutral."""
    _call(home, "Uptrend", ("Materials",))
    _run(home, _candles(tmp_path, [100.0] * 5 + [102.0]))
    status, market, sector, _spy, sector_move = _decision(home)
    assert (status, market, sector, sector_move) == ("checked", "right", "neutral", None)


def test_vote_results() -> None:
    """UT-MKT-020.017.M06.T01: Agreeing takes the result; disagreeing takes the opposite."""
    assert vote_result("agreed", "right") == "right"
    assert vote_result("disagreed", "right") == "wrong"
    assert vote_result("disagreed", "wrong") == "right"
    assert vote_result("disagreed", "neutral") == "neutral"


def test_neutral_part(home: Path, tmp_path: Path) -> None:
    """UT-MKT-020.017.M06.T02: Neutral parts leave every vote neutral."""
    _call(home, "Uptrend", ("Utilities",), regime="Choppy", sector_favour=("Utilities",))
    _run(home, _candles(tmp_path, [100.0] * 5 + [100.2]))
    assert _decision(home)[1:3] == ("neutral", "neutral")
    assert _votes(home) == [("regime_view", "neutral"), ("sector_flow_view", "neutral")]


def test_step_checks_due_call(home: Path, tmp_path: Path,
                              caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-020.014.M06.T01: A due call gets its results, moves and votes."""
    _call(home, "Uptrend", ("Energy",), regime="Downtrend")
    with caplog.at_level(logging.INFO):
        _run(home, _candles(tmp_path, [100.0] * 5 + [102.0]))
    assert _decision(home) == ("checked", "right", "right", 2.0, 4.0)
    assert _votes(home) == [("regime_view", "wrong"), ("sector_flow_view", "right")]
    assert any("[Company day] Checked 1 day call(s): 1 right, 0 wrong" in r.getMessage()
               for r in caplog.records)


def test_not_due_or_off(home: Path, tmp_path: Path) -> None:
    """UT-MKT-020.014.M06.T02: Too few closes keep it open; off reads nothing."""
    _call(home)
    candles = _candles(tmp_path, [100.0, 100.0, 101.0, 102.0])
    _run(home, candles)
    assert _decision(home)[0] == "open"
    (home / SETTINGS_FILE).write_text(json.dumps({"company_day_on": False}), encoding="utf-8")
    _run(home, tmp_path / "missing.db")
    assert _decision(home)[0] == "open"


def test_error_never_stops(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                           caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-020.014.M06.T03: An error is logged and the step returns."""
    _call(home)

    def boom(*_a: Any) -> Any:
        raise RuntimeError("broken table")

    monkeypatch.setattr(decision_check, "due_calls", boom)
    with caplog.at_level(logging.ERROR):
        _run(home, _candles(tmp_path, [100.0] * 6))
    assert any("Could not check the day calls" in r.getMessage() for r in caplog.records)
