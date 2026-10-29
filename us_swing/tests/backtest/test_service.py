"""Tests for MD-BKT-002.008.M05 — backtest/service.py and MD-BKT-002.009.M06 — cli.py."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from us_swing.backtest import cli
from us_swing.backtest.cache import StepCache
from us_swing.backtest.results import ResultsStore
from us_swing.backtest.service import BacktestService
from us_swing.backtest.steps.stocks import StepCancelled
from us_swing.backtest.store import BacktestStore
from tests.backtest.conftest import LATE, Record, daily_bars, plan_for, rsi_preset

_NAMES = ("AAPL", "MSFT", "NVDA")
_RECORDS = [Record(s, "Information Technology", 1e9) for s in _NAMES]


def _service(store: BacktestStore, tmp_path: Path) -> tuple[BacktestService, ResultsStore]:
    results = ResultsStore(tmp_path / "results.db")

    def presets(_preset_id: str, _user: str) -> dict[str, Any]:
        return rsi_preset(0, 100)

    svc = BacktestService(store, StepCache(tmp_path / "cache"), results,
                          lambda: _RECORDS, presets)
    return svc, results


def test_estimate_on_fake_store(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.008.M05.T01: Estimate counts stocks, missing 3m, SPY and days."""
    store.save("SPY", "1d", daily_bars("2025-01-01", 60, 7), LATE)
    store.save("AAPL", "3m", daily_bars("2025-03-03", 5, 1).assign(
        ts=lambda f: f["ts"] + pd.Timedelta(hours=15)), LATE)
    svc, _ = _service(store, tmp_path)

    est = svc.estimate(plan_for(date(2025, 3, 3), date(2025, 3, 7), _NAMES), "1",
                       today=date(2026, 1, 1))

    assert est.symbols == list(_NAMES)
    assert est.missing_1d == []
    assert est.missing_3m == ["MSFT", "NVDA"]
    assert est.benchmark_ok
    assert (est.days_total, est.days_cached, est.errors) == (5, 0, [])


def test_estimate_with_errors(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.008.M05.T02: A bad plan lists errors and counts no days."""
    svc, _ = _service(store, tmp_path)

    est = svc.estimate(plan_for(date(2025, 3, 7), date(2025, 3, 3), _NAMES), "1")

    assert est.errors == ["Start date is after the end date"]
    assert (est.days_total, est.days_cached) == (0, 0)


def test_service_run_recorded(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.017.M05.T01: A run returns the daily list and is saved as done."""
    svc, results = _service(store, tmp_path)

    out = svc.run_stocks(plan_for(date(2025, 3, 3), date(2025, 3, 7), _NAMES), "1", workers=0)

    assert len(out.days) == 5
    assert set(out.frame["date"]) <= set(out.days)
    assert [r.status for r in results.list_runs()] == ["done"]


def test_service_cancel_recorded(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.017.M05.T02: A cancelled run is saved as cancelled."""
    svc, results = _service(store, tmp_path)

    with pytest.raises(StepCancelled):
        svc.run_stocks(plan_for(date(2025, 3, 3), date(2025, 3, 7), _NAMES), "1",
                       workers=0, cancel=lambda: True)

    assert [r.status for r in results.list_runs()] == ["cancelled"]


def test_cli_estimate(store: BacktestStore, tmp_path: Path,
                      capsys: pytest.CaptureFixture[str]) -> None:
    """UT-BKT-002.009.M06.T01: The CLI prints the estimate and exits 0."""
    svc, _ = _service(store, tmp_path)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(plan_for(date(2025, 3, 3), date(2025, 3, 7), _NAMES).to_json(),
                         encoding="utf-8")

    code = cli.main(["estimate", str(plan_file)], service=svc)

    assert code == 0
    assert "3 stocks" in capsys.readouterr().out


def test_estimate_lists_rs_refusal(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.018.M05.T01: The data check shows the RS-rule message and counts no days."""
    from tests.backtest.test_stocks import _rs_preset

    svc = BacktestService(store, StepCache(tmp_path / "cache"),
                          ResultsStore(tmp_path / "results.db"), lambda: _RECORDS,
                          lambda _p, _u: _rs_preset())

    est = svc.estimate(plan_for(date(2025, 3, 3), date(2025, 3, 7), _NAMES), "1")

    assert len(est.errors) == 1 and est.errors[0].startswith("This screener uses the RS rule")
    assert est.days_total == 0
