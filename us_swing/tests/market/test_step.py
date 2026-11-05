"""Tests for MD-MKT-001.011.M05 — market/step.py, and MD-DSK-001.021.M07 step loading."""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from tests.market.conftest import bdays, write_candles
from us_swing.core.desk_contract import CommandKind, StepContext, send_command
from us_swing.core.desk_steps import load_steps
from us_swing.desk.process import DeskProcess
from us_swing.market.step import RegimeStep

N = 300
FIRST_READY = 271
MEMBERS = [f"M{i}" for i in range(10)]


def _closes(n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n))))


def _make(path: Path, n: int = N, drop_last: Sequence[str] = ()) -> None:
    series: dict[str, Sequence[float]] = {"SPY": _closes(n, 0)}
    for i, sym in enumerate(MEMBERS):
        series[sym] = _closes(n - 1 if sym in drop_last else n, i + 1)
    if path.exists():
        path.unlink()
    write_candles(path, series)


def _vix(_start: date) -> pd.DataFrame:
    idx = bdays(N + 5)
    return pd.DataFrame({"vix": 15.0, "vix3m": 17.0}, index=idx)


def _step(candles: Path, today: date, vix: Callable[[date], pd.DataFrame] = _vix) -> RegimeStep:
    return RegimeStep(candles, vix, lambda: [(m, m) for m in MEMBERS], lambda: today)


def _run(step: RegimeStep, home: Path) -> None:
    step(StepContext(1, "manual", datetime.now(UTC), home))


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _last_day(n: int = N) -> date:
    return bdays(n)[-1].date()


def test_first_run_fills_history(tmp_path: Path) -> None:
    """UT-MKT-001.008.M05.T01: First run fills history."""
    candles = tmp_path / "candles.db"
    _make(candles)
    _run(_step(candles, _last_day()), tmp_path / "desk")
    count, first, last = _rows(tmp_path / "desk",
                               "SELECT COUNT(*), MIN(date), MAX(date) FROM regime_snapshot")[0]
    assert count == N - FIRST_READY
    assert first == bdays(N)[FIRST_READY].date().isoformat()
    assert last == _last_day().isoformat()


def test_later_run_adds_only_new_days(tmp_path: Path) -> None:
    """UT-MKT-001.008.M05.T02: Later run adds only new days."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    _run(_step(candles, _last_day()), home)
    _make(candles, N + 1)
    _run(_step(candles, _last_day(N + 1)), home)
    assert _rows(home, "SELECT COUNT(*) FROM regime_snapshot")[0][0] == N + 1 - FIRST_READY


def test_no_new_candles(tmp_path: Path) -> None:
    """UT-MKT-001.008.M05.T03: No new candles."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    _run(_step(candles, _last_day()), home)
    _run(_step(candles, _last_day()), home)
    assert _rows(home, "SELECT COUNT(*) FROM regime_snapshot")[0][0] == N - FIRST_READY


def test_low_coverage_day_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-001.009.M05.T01: Low coverage day skipped."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles, drop_last=MEMBERS[:3])
    with caplog.at_level(logging.INFO):
        _run(_step(candles, _last_day()), home)
    days = [r[0] for r in _rows(home, "SELECT date FROM regime_snapshot")]
    assert _last_day().isoformat() not in days
    assert "skipped" in caplog.text


def test_full_coverage_day_stored(tmp_path: Path) -> None:
    """UT-MKT-001.009.M05.T02: Full coverage day stored."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    _run(_step(candles, _last_day()), home)
    members = _rows(home, f"SELECT members FROM breadth_daily WHERE date = '{_last_day()}'")
    assert members == [(10,)]


def test_stale_candles_noted(tmp_path: Path) -> None:
    """UT-MKT-001.010.M05.T01: Stale candles noted."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    _run(_step(candles, _last_day() + timedelta(days=7)), home)
    note = _rows(home, f"SELECT note FROM regime_snapshot WHERE date = '{_last_day()}'")[0][0]
    assert "candles stale" in note


def test_fresh_candles_not_flagged(tmp_path: Path) -> None:
    """UT-MKT-001.010.M05.T02: Fresh candles not flagged."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    _run(_step(candles, _last_day()), home)
    note = _rows(home, f"SELECT note FROM regime_snapshot WHERE date = '{_last_day()}'")[0][0]
    assert "stale" not in note


def test_step_runs_in_desk_run(tmp_path: Path) -> None:
    """UT-MKT-001.011.M05.T01: Step runs in a desk run."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    desk = DeskProcess(home, [_step(candles, _last_day())], sleep=lambda _s: None)
    desk.start()
    send_command(CommandKind.RUN_NOW, home)
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT result FROM runs") == [("ok",)]
    assert _rows(home, "SELECT COUNT(*) FROM regime_snapshot")[0][0] == N - FIRST_READY


def test_vix_down_step_still_ok(tmp_path: Path) -> None:
    """UT-MKT-001.011.M05.T02: VIX down, step still ok."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    _run(_step(candles, _last_day(), lambda _s: pd.DataFrame(columns=["vix", "vix3m"])), home)
    notes = {r[0] for r in _rows(home, "SELECT note FROM regime_snapshot")}
    assert notes == {"no VIX"}


def test_steps_load_from_list() -> None:
    """UT-DSK-001.021.M07.T01: Steps load from the list."""
    steps = load_steps(["us_swing.market.step:RegimeStep"])
    assert [s.name for s in steps] == ["Market regime"]


def test_bad_step_path_left_out(caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-001.021.M07.T02: Bad path is left out."""
    with caplog.at_level(logging.WARNING):
        assert load_steps(["us_swing.nowhere:Ghost"]) == []
    assert "Could not load desk step" in caplog.text


def test_partial_day_corrected_next_run(tmp_path: Path) -> None:
    """UT-MKT-001.008.M05.T04: A day stored from a partial download is redone next run."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles, drop_last=MEMBERS[:1])
    _run(_step(candles, _last_day()), home)
    day = _last_day().isoformat()
    assert _rows(home, f"SELECT members FROM breadth_daily WHERE date = '{day}'") == [(9,)]
    _make(candles)
    _run(_step(candles, _last_day()), home)
    assert _rows(home, f"SELECT members FROM breadth_daily WHERE date = '{day}'") == [(10,)]


def test_stray_date_does_not_spoil_breadth(tmp_path: Path) -> None:
    """UT-MKT-001.004.M02.T03: A stray non-trading-day row for one stock is ignored."""
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    _make(candles)
    con = sqlite3.connect(candles)
    con.execute("INSERT INTO price_1d VALUES ('M0', '2025-06-07T00:00:00', 1, 1, 1, 1, 1)")
    con.commit()
    con.close()
    _run(_step(candles, _last_day()), home)
    pct = _rows(home, f"SELECT pct_above_200 FROM breadth_daily WHERE date = '{_last_day()}'")
    count = _rows(home, f"SELECT members FROM breadth_daily WHERE date = '{_last_day()}'")
    assert count == [(10,)] and pct[0][0] is not None


def test_missing_candles_does_not_fail(tmp_path: Path) -> None:
    """UT-MKT-001.011.M05.T03: No candle file yet: the step adds nothing and does not fail."""
    _run(_step(tmp_path / "none.db", _last_day()), tmp_path / "desk")
    assert _rows(tmp_path / "desk", "SELECT COUNT(*) FROM regime_snapshot") == [(0,)]
