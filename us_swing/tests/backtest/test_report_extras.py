"""Tests for MD-BKT-002.040.M13 Phase 4b — exit / hold stats, groups, robustness, heat map."""
from __future__ import annotations

import math
from dataclasses import replace

import pandas as pd
import pytest

from us_swing.backtest.steps import report
from tests.backtest.test_report import _SECTORS, _log, _money, _trades


def _rep(trades: pd.DataFrame | None = None) -> report.Report:
    return report.build_report("v", 1000.0, _trades() if trades is None else trades, _money(),
                               _log(), _SECTORS)


def _with_excursions() -> pd.DataFrame:
    return _trades().assign(mae=[5.0, 25.0, 0.0, 30.0], mfe=[20.0, 0.0, 40.0, 4.0])


def test_exit_and_hold_stats() -> None:
    """UT-BKT-002.070.M13.T01: Average MAE, MFE, profit given back and hold times."""
    rep = _rep(_with_excursions())

    assert rep.stat("Average MAE") == pytest.approx(15.0)
    assert rep.stat("Average MFE") == pytest.approx(16.0)
    assert rep.stat("Profit given back") == pytest.approx((10 + 20 + 10 + 24) / 4)
    assert rep.stat("Median hold") == pytest.approx(5.0)
    assert rep.stat("Longest hold") == pytest.approx(5.0)


def test_exit_stats_without_trades() -> None:
    """UT-BKT-002.070.M13.T02: No trades gives dashes (NaN), not an error."""
    assert math.isnan(_rep(_trades().iloc[0:0]).stat("Median hold"))


def test_new_groups() -> None:
    """UT-BKT-002.071.M13.T01: Breakdown by hold time, score bucket and rank."""
    trades = _trades().assign(rank=[1, 2, 1, 3])
    rep = _rep(trades)

    assert list(report.breakdown(rep.trades, "hold")["group"]) == ["3 h–1 day"]
    assert list(report.breakdown(rep.trades, "score_bucket")["group"]) == ["1.00"]
    by_rank = report.breakdown(rep.trades, "rank")
    assert dict(zip(by_rank["group"], by_rank["trades"], strict=True)) == {"1": 2, "2": 1, "3": 1}


def test_score_quartiles() -> None:
    """UT-BKT-002.071.M13.T02: Four or more scores are split into quartile ranges."""
    buckets = report._score_buckets(pd.Series([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]))

    assert len(set(buckets)) == 4
    assert buckets[0].startswith("0.10–")


def test_robustness_is_repeatable() -> None:
    """UT-BKT-002.072.M13.T01: Monte Carlo repeats exactly; halves add up; top 5 removed."""
    one, two = _rep(), _rep()
    names = ("Monte Carlo drawdown, bad 5%", "Monte Carlo drawdown, median",
             "Monte Carlo drawdown, good 5%")

    assert [one.stat(n) for n in names] == [two.stat(n) for n in names]
    bad, mid, good = (one.stat(n) for n in names)
    assert bad <= mid <= good <= 0.0
    assert one.stat("First half P&L") + one.stat("Second half P&L") == pytest.approx(0.0)
    assert one.stat("First half P&L") == pytest.approx(-10.0)
    assert one.stat("P&L without top 5 trades") == pytest.approx(0.0)


def test_robustness_without_trades() -> None:
    """UT-BKT-002.072.M13.T02: No trades gives NaN drawdowns and zero P&L."""
    rep = _rep(_trades().iloc[0:0])

    assert math.isnan(rep.stat("Monte Carlo drawdown, median"))
    assert rep.stat("P&L without top 5 trades") == 0.0


def test_heat_map_grid() -> None:
    """UT-BKT-002.073.M13.T01: Two capitals × two per-trade % give a 2 × 2 return grid."""
    base = _rep()
    reps = [replace(base, capital=c, per_trade_pct=p) for c in (1000.0, 2000.0)
            for p in (50.0, 100.0)]

    grid = report.heat_map(reps)

    assert grid.shape == (2, 2)
    assert list(grid.columns) == [50.0, 100.0]


def test_heat_map_needs_both() -> None:
    """UT-BKT-002.073.M13.T02: One capital only gives no grid."""
    base = _rep()

    assert report.heat_map([replace(base, per_trade_pct=p) for p in (50.0, 100.0)]).empty
