"""Tests for MD-BKT-002.007.M04 — backtest/results.py."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from us_swing.backtest.results import ResultsStore
from us_swing.backtest.spec import Period, RunPlan


def test_run_row_life(tmp_path: Path) -> None:
    """UT-BKT-002.007.M04.T01: A run row keeps plan, final status and both times."""
    results = ResultsStore(tmp_path / "results.db")
    plan = RunPlan(name="My run", period=Period(date(2026, 1, 2), date(2026, 3, 1)))
    t0 = datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 29, 10, 5, tzinfo=timezone.utc)

    run_id = results.start_run(plan, t0)
    results.finish_run(run_id, "done", t1)

    row = results.get_run(run_id)
    assert row is not None
    assert (row.name, row.status, row.started, row.finished) == ("My run", "done", t0, t1)
    assert RunPlan.from_json(row.plan_json) == plan
    assert [r.run_id for r in results.list_runs()] == [run_id]


def test_unknown_run(tmp_path: Path) -> None:
    """UT-BKT-002.007.M04.T02: An unknown run id returns None."""
    assert ResultsStore(tmp_path / "results.db").get_run("x") is None
