"""Tests for MD-MKT-012.007.M04 (market/view_check.py): views checked against daily closes."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from us_swing.core import desk_memory
from us_swing.core.desk_ai_settings import SETTINGS_FILE
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_msg import Remember
from us_swing.desk.recorder import NY
from us_swing.market import view_check
from us_swing.market.view_check import ViewCheckStep

MADE = "2026-11-02"
RUN = datetime(2026, 11, 17, 5, 0, tzinfo=NY)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "desk"
    path.mkdir()
    (path / SETTINGS_FILE).write_text(json.dumps({"memory_v2_on": True}), encoding="utf-8")
    return path


def _candles(tmp_path: Path, symbol: str, closes: list[float]) -> Path:
    path = tmp_path / "candles.db"
    con = sqlite3.connect(path)
    with con:
        con.execute("CREATE TABLE IF NOT EXISTS price_1d (symbol TEXT, datetime TEXT, open REAL, "
                    "high REAL, low REAL, close REAL, volume REAL)")
        days = pd.bdate_range(MADE, periods=len(closes))
        con.executemany("INSERT INTO price_1d VALUES (?, ?, ?, ?, ?, ?, 1000)",
                        [(symbol, d.strftime("%Y-%m-%d"), c, c, c, c)
                         for d, c in zip(days, closes, strict=True)])
    con.close()
    return path


def _view(home: Path, symbol: str, direction: str) -> None:
    desk_memory.write(home, "emp-v", [Remember(kind="view", text="call", symbol=symbol,
                                               direction=direction)],  # type: ignore[arg-type]
                      MADE, RUN)


def _views(home: Path) -> list[Any]:
    con = desk_memory.connect(home)
    try:
        return con.execute("SELECT symbol, status, result FROM memories WHERE kind = 'view'"
                           ).fetchall()
    finally:
        con.close()


def _run(home: Path, candles: Path, when: datetime = RUN) -> None:
    ViewCheckStep(candles)(StepContext(1, "morning", when, home))


def test_up_view_right(home: Path, tmp_path: Path) -> None:
    """UT-MKT-012.007.M04.T01: An up view whose 10th close is +1.5% is right."""
    _view(home, "NVDA", "up")
    _run(home, _candles(tmp_path, "NVDA", [100.0] * 10 + [101.5]))
    assert _views(home) == [("NVDA", "right", 1.5)]


def test_down_view_wrong(home: Path, tmp_path: Path) -> None:
    """UT-MKT-012.007.M04.T02: A down view whose stock rose 2% is wrong."""
    _view(home, "TSLA", "down")
    _run(home, _candles(tmp_path, "TSLA", [100.0] * 10 + [102.0]))
    assert _views(home) == [("TSLA", "wrong", 2.0)]


def test_not_due(home: Path, tmp_path: Path) -> None:
    """UT-MKT-012.007.M04.T03: A view not due yet stays open."""
    _view(home, "NVDA", "up")
    _run(home, _candles(tmp_path, "NVDA", [100.0] * 11), datetime(2026, 11, 10, 5, 0, tzinfo=NY))
    assert _views(home) == [("NVDA", "open", None)]


def test_off(home: Path, tmp_path: Path) -> None:
    """UT-MKT-012.007.M04.T04: With Memory v2 off nothing changes."""
    _view(home, "NVDA", "up")
    (home / SETTINGS_FILE).write_text("{}", encoding="utf-8")
    _run(home, _candles(tmp_path, "NVDA", [100.0] * 10 + [105.0]))
    assert _views(home) == [("NVDA", "open", None)]


def test_no_close(home: Path, tmp_path: Path) -> None:
    """UT-MKT-012.007.M04.T05: A stock with no closes stays open and the run goes on."""
    _view(home, "ZZZ", "up")
    _view(home, "NVDA", "up")
    _run(home, _candles(tmp_path, "NVDA", [100.0] * 10 + [99.0]))
    assert sorted(_views(home)) == [("NVDA", "wrong", -1.0), ("ZZZ", "open", None)]


def test_scores_and_review(home: Path, tmp_path: Path) -> None:
    """UT-MKT-012.008.M04.T01: A right view scores the note shown that day."""
    desk_memory.write(home, "emp-v", [Remember(kind="note", text="Semis lead", symbol="NVDA")],
                      MADE, RUN)
    desk_memory.recall(home, "emp-v", "NVDA", MADE)
    _view(home, "NVDA", "up")
    _run(home, _candles(tmp_path, "NVDA", [100.0] * 10 + [103.0]))
    con = desk_memory.connect(home)
    right = con.execute("SELECT right FROM memories WHERE kind = 'note'").fetchone()[0]
    con.close()
    assert right == 1


def test_error_does_not_stop(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                             caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-012.008.M04.T02: A store error is logged and the step returns."""
    def boom(*_a: Any) -> list[Any]:
        raise sqlite3.OperationalError("locked")

    monkeypatch.setattr(view_check, "open_views_due", boom)
    with caplog.at_level(logging.ERROR):
        _run(home, _candles(tmp_path, "NVDA", [100.0]))
    assert "[Memory] Could not check the views" in caplog.text
