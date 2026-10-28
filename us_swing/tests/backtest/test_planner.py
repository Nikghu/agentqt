"""Tests for MD-BKT-001.005.M03 — backtest/planner.py."""
from __future__ import annotations

from datetime import date

from us_swing.backtest.planner import Job, plan
from us_swing.backtest.settings import BacktestDataSettings
from us_swing.backtest.store import Timeframe

Coverage = dict[tuple[str, Timeframe], tuple[date, date]]
_RANGE_2025 = BacktestDataSettings(start_date=date(2025, 1, 1), end_date=date(2025, 12, 31))
_LATEST = BacktestDataSettings(start_date=date(2025, 1, 1))


def _plan(
    settings: BacktestDataSettings,
    cov: Coverage,
    *,
    symbols: tuple[str, ...] = ("AAPL", "MSFT"),
    floors: dict[str, date] | None = None,
    last_session: date = date(2025, 12, 31),
    delta_only: bool = False,
) -> list[Job]:
    return plan(
        list(symbols), settings, lambda s, tf: cov.get((s, tf)), floors or {},
        last_session, delta_only,
    )


def test_empty_store_plan() -> None:
    """UT-BKT-001.005.M03.T01: Empty store gives 1d jobs first, then 3m newest end first."""
    jobs = _plan(_RANGE_2025, {})

    assert [(j.symbol, j.tf) for j in jobs[:2]] == [("AAPL", "1d"), ("MSFT", "1d")]
    assert all(j.duration == "1 Y" for j in jobs[:2])
    m3 = jobs[2:]
    assert all(j.tf == "3m" and j.duration == "3 M" for j in m3)
    assert [j.end for j in m3] == sorted((j.end for j in m3), reverse=True)
    assert [j.symbol for j in m3[:2]] == ["AAPL", "MSFT"]
    assert m3[0].end == date(2025, 12, 31)
    assert len(m3) == 8
    assert min(j.end for j in m3) >= date(2025, 1, 1)


def test_fully_saved_store_has_no_jobs() -> None:
    """UT-BKT-001.005.M03.T02: A store that already covers the range plans nothing."""
    full = (date(2025, 1, 2), date(2025, 12, 31))
    cov: Coverage = {(s, tf): full for s in ("AAPL", "MSFT") for tf in ("1d", "3m")}

    assert _plan(_RANGE_2025, cov) == []


def test_earlier_start_backfills_only_older_windows() -> None:
    """UT-BKT-001.005.M03.T03: Moving start earlier plans only older windows and one 1d job."""
    saved = (date(2024, 1, 2), date(2025, 12, 31))
    cov: Coverage = {("AAPL", "1d"): saved, ("AAPL", "3m"): saved}
    settings = BacktestDataSettings(start_date=date(2023, 1, 1), end_date=date(2025, 12, 31))

    jobs = _plan(settings, cov, symbols=("AAPL",))

    jobs_1d = [j for j in jobs if j.tf == "1d"]
    jobs_3m = [j for j in jobs if j.tf == "3m"]
    assert len(jobs_1d) == 1
    assert jobs_1d[0].end < date(2024, 1, 2)
    assert jobs_3m
    assert all(date(2023, 1, 1) <= j.end < date(2024, 1, 2) for j in jobs_3m)


def test_floor_skips_windows_before_first_data() -> None:
    """UT-BKT-001.005.M03.T04: No 3m job ends before the stock's floor."""
    jobs = _plan(_RANGE_2025, {}, symbols=("AAPL",), floors={"AAPL": date(2025, 6, 1)})

    jobs_3m = [j for j in jobs if j.tf == "3m"]
    assert jobs_3m
    assert all(j.end > date(2025, 6, 1) for j in jobs_3m)


def test_delta_asks_days_since_last_bar() -> None:
    """UT-BKT-001.008.M03.T01: Delta asks for trading days since the last bar plus one."""
    saved = (date(2025, 1, 2), date(2025, 12, 26))
    cov: Coverage = {(s, tf): saved for s in ("AAPL", "MSFT") for tf in ("1d", "3m")}

    jobs = _plan(_LATEST, cov, delta_only=True)

    assert len(jobs) == 4
    assert {(j.symbol, j.tf) for j in jobs} == {
        ("AAPL", "1d"), ("MSFT", "1d"), ("AAPL", "3m"), ("MSFT", "3m"),
    }
    assert all(j.duration == "4 D" and j.end == date(2025, 12, 31) for j in jobs)


def test_delta_minimum_two_days() -> None:
    """UT-BKT-001.008.M03.T02: Delta asks at least 2 days even when up to date."""
    saved = (date(2025, 1, 2), date(2025, 12, 31))
    cov: Coverage = {("AAPL", "1d"): saved, ("AAPL", "3m"): saved}

    jobs = _plan(_LATEST, cov, symbols=("AAPL",), delta_only=True)

    assert [j.duration for j in jobs] == ["2 D", "2 D"]


def test_no_delta_with_fixed_end_date() -> None:
    """UT-BKT-001.008.M03.T03: Delta plans nothing when the end date is fixed."""
    saved = (date(2025, 1, 2), date(2025, 12, 26))
    cov: Coverage = {("AAPL", "1d"): saved, ("AAPL", "3m"): saved}

    assert _plan(_RANGE_2025, cov, symbols=("AAPL",), delta_only=True) == []
