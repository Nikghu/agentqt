"""Tests for SRD-BKT-002.060 — saved runs in MD-BKT-002.007.M04 (results) and .008.M05 (service)."""
from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from us_swing.backtest.results import ResultsStore
from us_swing.backtest.store import BacktestStore
from tests.backtest.conftest import plan_for
from tests.backtest.test_report import _DAYS, _VARIANT, _log, _money, _trades
from tests.backtest.test_service import _NAMES
from tests.backtest.test_service import _service as _rsi_service

_NOW = pd.Timestamp("2026-10-30 12:00", tz="UTC")


def _saved_run(results: ResultsStore, name: str = "Backtest") -> str:
    plan = replace(plan_for(_DAYS[0], _DAYS[-1], ("AAPL", "MSFT", "NVDA")), name=name)
    run_id = results.start_run(plan, _NOW)
    results.save_variant(run_id, 0, _VARIANT, _trades(), _log(), _money())
    results.finish_run(run_id, "done", _NOW)
    return run_id


def test_rename_and_note(tmp_path: Path) -> None:
    """UT-BKT-002.060.M04.T01: Rename and note are saved; an old file gets the note column."""
    path = tmp_path / "results.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, name TEXT NOT NULL, "
                     "plan_json TEXT NOT NULL, status TEXT NOT NULL, started TEXT NOT NULL, "
                     "finished TEXT, message TEXT NOT NULL DEFAULT '')")
    results = ResultsStore(path)
    run_id = _saved_run(results)

    results.rename_run(run_id, "IT · Jan")
    results.set_note(run_id, "after the closed-candle change")

    row = results.get_run(run_id)
    assert row is not None
    assert (row.name, row.note) == ("IT · Jan", "after the closed-candle change")


def test_delete_removes_all_rows(tmp_path: Path) -> None:
    """UT-BKT-002.060.M04.T02: Delete removes the run and its variant rows; others stay."""
    results = ResultsStore(tmp_path / "results.db")
    gone, kept = _saved_run(results), _saved_run(results)

    results.delete_run(gone)

    assert results.get_run(gone) is None
    assert results.list_variants(gone) == []
    assert results.read_table("trades", f"{gone}-0").empty
    assert len(results.read_table("money_daily", f"{kept}-0")) == 4
    ResultsStore(tmp_path / "empty.db").delete_run("nope")  # no tables yet: no error


def test_saved_reports_list(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.060.M05.T01: Only runs with Step 3 rows are listed, with their numbers."""
    svc, results = _rsi_service(store, tmp_path)
    run_id = _saved_run(results, "Mine")
    results.start_run(plan_for(_DAYS[0], _DAYS[-1], _NAMES), _NOW)  # a Step 1 row only

    (saved,) = svc.saved_reports()

    assert (saved.run.run_id, saved.run.name, saved.trades) == (run_id, "Mine", 4)
    assert saved.net_pnl == pytest.approx(0.0)
    assert saved.max_dd_pct == pytest.approx(990 / 1010 - 1)


def test_open_run_reads_back(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.060.M05.T02: Opening reads Step 3 rows back and records no new run."""
    svc, results = _rsi_service(store, tmp_path)
    plan = plan_for(date(2025, 3, 3), date(2025, 3, 7), _NAMES)
    run_id = results.start_run(plan, _NOW)
    results.save_variant(run_id, 0, _VARIANT, _trades(), _log(), _money())

    opened = svc.open_run(run_id, "1", workers=0)

    assert len(opened.daily.days) == 5
    assert opened.signals is None
    assert len(opened.results[0].trades) == 4
    assert len(opened.reports) == 1
    assert len(results.list_runs()) == 1
    with pytest.raises(ValueError, match="No saved run"):
        svc.open_run("nope", "1", workers=0)
