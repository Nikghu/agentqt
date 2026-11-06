"""Tests for MD-MKT-003.011.M07 — market/idea_step.py."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tests.market.conftest import bdays, write_candles
from us_swing.core.desk_contract import CommandKind, StepContext, send_command
from us_swing.core.desk_steps import STEP_PATHS, load_steps
from us_swing.desk.process import DeskProcess
from us_swing.market.idea_step import IdeaStep
from us_swing.market.sector_step import SectorStep
from us_swing.market.step import RegimeStep

N = 300
SECTORS = {f"M{i}": ("Tech", "Energy", "Health Care")[i % 3] for i in range(9)}


def _closes(n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n))))


def _make(path: Path, n: int = N) -> None:
    series: dict[str, Sequence[float]] = {"SPY": _closes(n, 0)}
    for i, sym in enumerate(SECTORS):
        series[sym] = _closes(n, i + 1)
    if path.exists():
        path.unlink()
    write_candles(path, series, volume=1e6)


class _Earnings:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, symbols: Iterable[str]) -> dict[str, date | None]:
        names = list(symbols)
        self.calls.append(names)
        return dict.fromkeys(names)


def _vix(_start: date) -> pd.DataFrame:
    return pd.DataFrame({"vix": 15.0, "vix3m": 17.0}, index=bdays(N + 5))


def _steps(candles: Path, n: int, earnings: _Earnings) -> list[Any]:
    last = bdays(n)[-1].date()
    triples = [(s, s, sec) for s, sec in SECTORS.items()]
    return [
        RegimeStep(candles, _vix, lambda: [(s, s) for s in SECTORS], lambda: last),
        SectorStep(candles, lambda: triples),
        IdeaStep(candles, lambda: triples, earnings),
    ]


def _run(steps: list[Any], home: Path) -> None:
    for step in steps:
        step(StepContext(1, "manual", datetime.now(UTC), home))


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_first_run_fills_history(tmp_path: Path) -> None:
    """UT-MKT-003.011.M07.T01: The first run scores every day that has regime and sector rows."""
    candles, home, earnings = tmp_path / "candles.db", tmp_path / "desk", _Earnings()
    _make(candles)
    _run(_steps(candles, N, earnings), home)
    regime_days = _rows(home, "SELECT COUNT(*), MIN(date) FROM regime_snapshot")[0]
    score_days = _rows(home, "SELECT COUNT(DISTINCT date), MIN(date), MAX(date) "
                             "FROM stock_score")[0]
    assert score_days == (regime_days[0], regime_days[1], bdays(N)[-1].date().isoformat())
    sides = _rows(home, "SELECT DISTINCT side FROM stock_score ORDER BY side")
    assert sides == [("long",), ("short",)]
    assert len(earnings.calls) == 1
    assert 0 < len(earnings.calls[0]) <= 18


def test_later_run_adds_new_day(tmp_path: Path) -> None:
    """UT-MKT-003.011.M07.T02: One more bar adds one new day; earnings are checked for it."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    _run(_steps(candles, N, _Earnings()), home)
    before = _rows(home, "SELECT COUNT(DISTINCT date) FROM stock_score")[0][0]
    _make(candles, N + 1)
    earnings = _Earnings()
    _run(_steps(candles, N + 1, earnings), home)
    days, last = _rows(home, "SELECT COUNT(DISTINCT date), MAX(date) FROM stock_score")[0]
    assert (days, last) == (before + 1, bdays(N + 1)[-1].date().isoformat())
    assert len(earnings.calls) == 1


def test_no_sector_rows_yet(tmp_path: Path) -> None:
    """UT-MKT-003.011.M07.T03: Without sector rows the step adds nothing and does not fail."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    steps = _steps(candles, N, _Earnings())
    _run([steps[0], steps[2]], home)
    assert _rows(home, "SELECT COUNT(*) FROM regime_snapshot")[0][0] > 0
    assert _rows(home, "SELECT COUNT(*) FROM stock_score")[0][0] == 0


def test_no_candle_file(tmp_path: Path) -> None:
    """UT-MKT-003.011.M07.T04: With no candles.db the step adds nothing and does not fail."""
    home = tmp_path / "desk"
    _run([IdeaStep(tmp_path / "missing.db", lambda: [], _Earnings())], home)
    assert _rows(home, "SELECT COUNT(*) FROM stock_score")[0][0] == 0


def test_runs_third_in_desk_run(tmp_path: Path) -> None:
    """UT-MKT-003.011.M07.T05: Regime, Sectors and Ideas all run ok; score rows are written."""
    assert [s.name for s in load_steps(STEP_PATHS)] == ["Market regime", "Sectors", "Ideas"]
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    desk = DeskProcess(home, _steps(candles, N, _Earnings()), sleep=lambda _s: None)
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT result FROM runs") == [("ok",)]
    assert _rows(home, "SELECT COUNT(*) FROM stock_score")[0][0] > 0
