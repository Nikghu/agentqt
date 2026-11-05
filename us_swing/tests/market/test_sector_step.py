"""Tests for MD-MKT-002.009.M05 — market/sector_step.py."""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tests.market.conftest import bdays, write_candles
from us_swing.core.desk_contract import CommandKind, StepContext, send_command
from us_swing.core.desk_steps import STEP_PATHS, load_steps
from us_swing.desk.process import DeskProcess
from us_swing.market.sector_step import SectorStep
from us_swing.market.step import RegimeStep

N = 300
FIRST_READY = 252
SECTORS = {f"M{i}": ("Tech", "Energy", "Health Care")[i % 3] for i in range(9)}


def _closes(n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n))))


def _make(path: Path, n: int = N, drop_last: Sequence[str] = ()) -> None:
    series: dict[str, Sequence[float]] = {"SPY": _closes(n, 0)}
    for i, sym in enumerate(SECTORS):
        series[sym] = _closes(n - 1 if sym in drop_last else n, i + 1)
    if path.exists():
        path.unlink()
    write_candles(path, series)


def _universe() -> list[tuple[str, str, str]]:
    return [(s, s, sec) for s, sec in SECTORS.items()]


def _run(candles: Path, home: Path) -> None:
    SectorStep(candles, _universe)(StepContext(1, "manual", datetime.now(UTC), home))


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _day(i: int, n: int = N) -> str:
    return bdays(n)[i].date().isoformat()


def test_first_run_fills_history(tmp_path: Path) -> None:
    """UT-MKT-002.009.M05.T01: The first run writes rows from the first ready day."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    _run(candles, home)
    days, first, last = _rows(home, "SELECT COUNT(DISTINCT date), MIN(date), MAX(date) "
                                    "FROM sector_daily")[0]
    assert (days, first, last) == (N - FIRST_READY, _day(FIRST_READY), _day(-1))
    assert _rows(home, "SELECT COUNT(*) FROM sector_daily")[0][0] == 3 * (N - FIRST_READY)
    assert _rows(home, "SELECT COUNT(*) FROM stock_rs")[0][0] == 9 * (N - FIRST_READY)
    ranks = _rows(home, f"SELECT rank FROM sector_daily WHERE date = '{_day(-1)}' ORDER BY rank")
    assert [r[0] for r in ranks] == [1, 2, 3]
    quads = _rows(home, "SELECT DISTINCT quadrant FROM sector_daily")
    assert {q[0] for q in quads} <= {"Leading", "Weakening", "Lagging", "Improving"}


def test_later_run_adds_new_day(tmp_path: Path) -> None:
    """UT-MKT-002.009.M05.T02: One more bar adds one new day of rows."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    _run(candles, home)
    _make(candles, N + 1)
    _run(candles, home)
    days, last = _rows(home, "SELECT COUNT(DISTINCT date), MAX(date) FROM sector_daily")[0]
    assert (days, last) == (N + 1 - FIRST_READY, _day(-1, N + 1))
    assert _rows(home, f"SELECT COUNT(*) FROM stock_rs WHERE date = '{last}'")[0][0] == 9


def test_low_coverage_day_skipped(tmp_path: Path) -> None:
    """UT-MKT-002.009.M05.T03: A last day missing a third of the stocks gets no rows."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles, drop_last=["M0", "M1", "M2"])
    _run(candles, home)
    assert _rows(home, "SELECT MAX(date) FROM sector_daily")[0][0] == _day(-2)
    assert _rows(home, f"SELECT COUNT(*) FROM stock_rs WHERE date = '{_day(-1)}'")[0][0] == 0


def test_no_candle_file(tmp_path: Path) -> None:
    """UT-MKT-002.009.M05.T04: With no candles.db the step adds nothing and does not fail."""
    home = tmp_path / "desk"
    _run(tmp_path / "missing.db", home)
    assert _rows(home, "SELECT COUNT(*) FROM sector_daily")[0][0] == 0


def test_runs_after_regime_in_desk_run(tmp_path: Path) -> None:
    """UT-MKT-002.009.M05.T05: Sectors runs after Market regime; both ok, sector rows written."""
    assert [s.name for s in load_steps(STEP_PATHS)] == ["Market regime", "Sectors"]
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    last = bdays(N)[-1].date()

    def vix(_start: date) -> pd.DataFrame:
        return pd.DataFrame({"vix": 15.0, "vix3m": 17.0}, index=bdays(N))

    regime = RegimeStep(candles, vix, lambda: [(s, s) for s in SECTORS], lambda: last)
    desk = DeskProcess(home, [regime, SectorStep(candles, _universe)], sleep=lambda _s: None)
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT result FROM runs") == [("ok",)]
    assert _rows(home, "SELECT COUNT(*) FROM regime_snapshot")[0][0] > 0
    assert _rows(home, "SELECT COUNT(DISTINCT date) FROM sector_daily")[0][0] == N - FIRST_READY
