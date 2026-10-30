"""Tests for MD-BKT-002.040.M13 — backtest/steps/report.py and the Step 4 service calls."""
from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from us_swing.backtest.cache import StepCache
from us_swing.backtest.results import ResultsStore
from us_swing.backtest.service import BacktestService, variant_label
from us_swing.backtest.spec import Variant
from us_swing.backtest.steps import report
from us_swing.backtest.steps.portfolio import VariantResult
from us_swing.backtest.store import BacktestStore
from tests.backtest.conftest import Record, plan_for

_DAYS = [date(2025, 3, d) for d in (3, 4, 5, 6)]
_SECTORS = {"AAPL": "Information Technology", "MSFT": "Information Technology"}
_VARIANT = Variant(1000.0, (("S1", 100.0, 50.0),))


def _ts(day: date, hhmm: str) -> pd.Timestamp:
    return pd.Timestamp(f"{day} {hhmm}", tz="America/New_York").tz_convert("UTC")


def _trades() -> pd.DataFrame:
    rows = [("S1", "AAPL", 10.0, "strategy"), ("S1", "MSFT", -20.0, "end_time"),
            ("S2", "AAPL", 30.0, "strategy"), ("S1", "NVDA", -20.0, "end_time")]
    return pd.DataFrame([
        {"strategy": s, "symbol": sym, "direction": "LONG", "entry_ts": _ts(d, "10:00"),
         "entry_px": 100.0, "qty": 1, "exit_ts": _ts(d, "15:00"), "exit_px": 100.0,
         "exit_reason": why, "costs": 0.0, "net_pnl": pnl, "mae": 0.0, "mfe": 0.0,
         "score": 1.0, "rank": 1}
        for d, (s, sym, pnl, why) in zip(_DAYS, rows)
    ])


def _money() -> pd.DataFrame:
    return pd.DataFrame({"date": _DAYS, "start_capital": 1000.0, "deployed": 0.0,
                         "margin_min": 1000.0, "margin_close": 1000.0, "open_value": 0.0,
                         "equity": [1010.0, 990.0, 1020.0, 1000.0]})


def _log() -> pd.DataFrame:
    return pd.DataFrame({"ts": [_ts(_DAYS[0], "10:00")] * 6, "symbol": "AAPL", "strategy": "S1",
                         "decision": ["entered"] * 4 + ["no_margin"] * 2,
                         "margin_available": 0.0, "strategy_deployed": 0.0})


@pytest.fixture()
def rep() -> report.Report:
    return report.build_report("v", 1000.0, _trades(), _money(), _log(), _SECTORS)


def test_returns_on_known_days(rep: report.Report) -> None:
    """UT-BKT-002.041.M13.T01: Net P&L, return, CAGR, time invested and month P&L."""
    assert rep.stat("Net P&L") == pytest.approx(0.0)
    assert rep.stat("Return") == pytest.approx(0.0)
    assert rep.stat("CAGR") == pytest.approx(0.0)
    assert rep.stat("Time invested") == pytest.approx(1.0)
    assert rep.monthly.to_dict("records") == [{"year": 2025, "month": 3, "pnl": 0.0}]


def test_returns_without_trades() -> None:
    """UT-BKT-002.041.M13.T02: No trades and flat equity give zero P&L and no time invested."""
    flat = _money().assign(equity=1000.0)
    empty = _trades().iloc[0:0]

    out = report.build_report("v", 1000.0, empty, flat, _log().iloc[0:0], {})

    assert out.stat("Net P&L") == 0.0
    assert out.stat("Time invested") == 0.0
    assert math.isnan(out.stat("Win rate"))


def test_risk_on_known_days(rep: report.Report) -> None:
    """UT-BKT-002.042.M13.T01: Drawdown, worst day and trade, Sharpe from daily returns."""
    rets = np.array([1010 / 1000, 990 / 1010, 1020 / 990, 1000 / 1020]) - 1

    assert rep.stat("Max drawdown") == pytest.approx(990 / 1010 - 1)
    assert rep.stat("Max drawdown $") == pytest.approx(-20.0)
    assert rep.stat("Longest drawdown") == 1
    assert rep.stat("Worst day") == pytest.approx(-20.0)
    assert rep.stat("Worst trade") == pytest.approx(-20.0)
    assert rep.stat("Sharpe") == pytest.approx(rets.mean() / rets.std(ddof=1) * math.sqrt(252))
    assert list(rep.daily["drawdown"]) == pytest.approx([0, 990 / 1010 - 1, 0, 1000 / 1020 - 1])


def test_risk_without_losses() -> None:
    """UT-BKT-002.042.M13.T02: Equity that only rises has no drawdown and no Sortino."""
    up = _money().assign(equity=[1001.0, 1002.0, 1003.0, 1004.0])

    out = report.build_report("v", 1000.0, _trades(), up, _log(), {})

    assert out.stat("Max drawdown") == 0.0
    assert out.stat("Longest drawdown") == 0
    assert math.isnan(out.stat("Sortino"))
    assert math.isnan(out.stat("Calmar"))


def test_trade_quality(rep: report.Report) -> None:
    """UT-BKT-002.043.M13.T01: Win rate, averages, payoff, profit factor, streaks."""
    assert rep.stat("Trades") == 4
    assert rep.stat("Win rate") == pytest.approx(0.5)
    assert (rep.stat("Average win"), rep.stat("Average loss")) == (20.0, -20.0)
    assert rep.stat("Payoff") == pytest.approx(1.0)
    assert rep.stat("Profit factor") == pytest.approx(1.0)
    assert rep.stat("Expectancy") == pytest.approx(0.0)
    assert (rep.stat("Longest win streak"), rep.stat("Longest loss streak")) == (1, 1)


def test_profit_factor_without_losses() -> None:
    """UT-BKT-002.043.M13.T02: Only winning trades give no payoff or profit factor."""
    wins = _trades().assign(net_pnl=5.0)

    out = report.build_report("v", 1000.0, wins, _money(), _log(), {})

    assert math.isnan(out.stat("Profit factor"))
    assert math.isnan(out.stat("Payoff"))
    assert out.stat("Longest win streak") == 4


def test_breakdown_by_strategy_and_sector(rep: report.Report) -> None:
    """UT-BKT-002.044.M13.T01: Groups sum P&L, best first; unknown sector is named."""
    by_strategy = report.breakdown(rep.trades, "strategy")
    by_sector = report.breakdown(rep.trades, "sector")

    assert list(by_strategy["group"]) == ["S2", "S1"]
    assert list(by_strategy["net_pnl"]) == [30.0, -30.0]
    assert by_strategy["win_rate"].iloc[1] == pytest.approx(1 / 3)
    assert set(by_sector["group"]) == {"Information Technology", "Unknown"}
    assert set(report.breakdown(rep.trades, "weekday")["group"]) == {
        "Monday", "Tuesday", "Wednesday", "Thursday"}
    assert list(report.breakdown(rep.trades, "hour")["group"]) == ["10:00"]


def test_breakdown_unknown_group(rep: report.Report) -> None:
    """UT-BKT-002.044.M13.T02: An unknown group name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown group"):
        report.breakdown(rep.trades, "colour")


def test_skip_counts(rep: report.Report) -> None:
    """UT-BKT-002.045.M13.T01: Entries taken and each skip reason are counted."""
    assert dict(zip(rep.skips["decision"], rep.skips["count"])) == {"entered": 4, "no_margin": 2}


def test_equal_weight_benchmark() -> None:
    """UT-BKT-002.046.M13.T01: Capital grows by the average daily return of the stocks."""
    closes = {
        "A": pd.Series([100.0, 110.0, 99.0], index=[date(2025, 2, 28), *_DAYS[:2]]),
        "B": pd.Series([50.0, 50.0, 55.0], index=[date(2025, 2, 28), *_DAYS[:2]]),
    }

    bench = report.equal_weight_benchmark(closes, _DAYS[:2], 1000.0)

    assert list(bench) == pytest.approx([1050.0, 1050.0])


def test_benchmark_without_stocks() -> None:
    """UT-BKT-002.046.M13.T02: No stock closes give an empty (NaN) benchmark line."""
    assert report.equal_weight_benchmark({}, _DAYS, 1000.0).isna().all()


def test_compare_rows(rep: report.Report) -> None:
    """UT-BKT-002.047.M13.T01: One row of key stats per variant."""
    other = report.build_report("w", 2000.0, _trades(), _money().assign(equity=2100.0), _log(),
                                {})

    table = report.compare([rep, other])

    assert list(table["variant"]) == ["v", "w"]
    assert list(table["Net P&L"]) == pytest.approx([0.0, 100.0])
    assert set(report.COMPARE_STATS) <= set(table.columns)


def _service(store: BacktestStore, tmp_path: Path) -> tuple[BacktestService, ResultsStore]:
    results = ResultsStore(tmp_path / "results.db")
    records = [Record(s, "Information Technology", 1e9) for s in ("AAPL", "MSFT", "NVDA")]
    return BacktestService(store, StepCache(tmp_path / "cache"), results, lambda: records,
                           lambda _p, _u: {}), results


def test_report_from_saved_run(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.040.M13.T01: A saved run gives the same report as the in-memory rows."""
    svc, results = _service(store, tmp_path)
    plan = plan_for(_DAYS[0], _DAYS[-1], ("AAPL", "MSFT", "NVDA"))
    res = VariantResult(_VARIANT, _trades(), _log(), _money())
    run_id = results.start_run(plan, pd.Timestamp.now(tz="UTC"))
    results.save_variant(run_id, 0, res.variant, res.trades, res.day_log, res.money)

    (saved,) = svc.report_for_run(run_id)
    (live,) = svc.build_reports(plan, [res])

    assert saved.label == variant_label(_VARIANT) == "$1,000 · S1 100%/50%"
    assert [s.value for s in saved.stats] == pytest.approx([s.value for s in live.stats],
                                                           nan_ok=True)
    assert saved.daily["benchmark"].notna().all()


def test_report_unknown_run(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.040.M13.T02: An unknown run id raises ValueError."""
    svc, _ = _service(store, tmp_path)

    with pytest.raises(ValueError, match="No saved run"):
        svc.report_for_run("nope")
