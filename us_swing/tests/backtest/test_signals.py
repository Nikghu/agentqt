"""Tests for MD-BKT-002.026.M11 — backtest/steps/signals.py and Step 2 in service.py."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from us_swing.backtest.cache import StepCache
from us_swing.backtest.results import ResultsStore
from us_swing.backtest.service import BacktestService, DailyList
from us_swing.backtest.spec import Period, StrategySpec
from us_swing.backtest.steps import signals
from us_swing.backtest.store import BacktestStore
from us_swing.core.expr.series import ET, Evaluation
from tests.backtest.conftest import LATE, daily_bars, intraday_bars, plan_for, rsi_preset

_DAYS = ["2025-03-20", "2025-03-21", "2025-03-24"]
_PERIOD = Period(date(2025, 3, 21), date(2025, 3, 24))
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def _strategy(name: str = "ST_A", **kw: Any) -> dict[str, Any]:
    return {
        "name": name, "start_time": "09:30", "end_time": "16:00", "days": _WEEKDAYS,
        "entry_condition": "RSI('Spot', 14, '3m') > 55",
        "exit_condition": "RSI('Spot', 14, '3m') < 45",
        "symbol_mode": "all", "symbols_include": [], "symbols_exclude": [],
        "capital_max": 50, "per_trade_pct": 100, **kw,
    }


def _daily(*ranked: str) -> pd.DataFrame:
    return pd.DataFrame({"date": [date(2025, 3, 20)] * len(ranked), "symbol": list(ranked),
                         "score": [1.0] * len(ranked), "rank": list(range(1, len(ranked) + 1))})


@pytest.fixture()
def store(tmp_path: Path) -> BacktestStore:
    st = BacktestStore(tmp_path / "store")
    for seed, sym in enumerate(("AAPL", "MSFT")):
        st.save(sym, "1d", daily_bars("2025-01-01", 60, seed), LATE)
        st.save(sym, "3m", intraday_bars(_DAYS, seed + 10), LATE)
    return st


def test_periods_from_runs() -> None:
    """UT-BKT-002.026.M11.T01: Each run of true bars is one period."""
    fired = np.array([False, True, True, False, True])
    closes = pd.date_range("2025-03-24 13:33", periods=5, freq="3min", tz="UTC")
    ev = Evaluation(fired, {"RSI(14, 3m)": np.arange(5, dtype=float)}, False)

    out = signals.periods(fired, closes, np.array([1.0, 2, 3, 4, 5]), ev, "entry")

    assert list(zip(out["start"], out["end"])) == [(closes[1], closes[2]), (closes[4], closes[4])]
    assert list(out["close_at_start"]) == [2.0, 5.0]
    assert out["values"].iloc[0] == '{"RSI(14, 3m)": 1.0}'


def test_hours_and_days() -> None:
    """UT-BKT-002.026.M11.T02: Only bars closing inside hours on trading days are kept."""
    closes = pd.DatetimeIndex([f"{d} {t}" for d in ("2025-03-24", "2025-03-22")
                               for t in ("09:36", "10:00", "15:30")]).tz_localize(ET)
    strategy = _strategy(start_time="09:40", end_time="15:30")

    mask = signals.schedule_mask(closes, strategy)

    assert list(mask) == [False, True, False, False, False, False]


def test_cache_reuse(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.028.M11.T01: A second run computes nothing and returns the same rows."""
    cache = StepCache(tmp_path / "cache")
    first = signals.run_signals(_PERIOD, [_strategy()], _daily("AAPL", "MSFT"), 0, store,
                                cache, workers=0)
    calls: list[tuple[int, int]] = []

    again = signals.run_signals(_PERIOD, [_strategy()], _daily("AAPL", "MSFT"), 0, store,
                                cache, workers=0, progress=lambda d, t: calls.append((d, t)))

    assert calls == [(0, 0)]
    assert len(first) > 0
    pd.testing.assert_frame_equal(first, again)
    assert set(first["kind"]) == {"entry", "exit"}
    starts_et = pd.DatetimeIndex(first["start"]).tz_convert(ET)
    assert (starts_et.date >= _PERIOD.start).all()


def test_stocks_follow_top_n_and_include(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.028.M11.T02: Only top-N stocks the strategy accepts are computed."""
    include_msft = _strategy(symbol_mode="include", symbols_include=["MSFT"])
    include_aapl = _strategy(symbol_mode="include", symbols_include=["AAPL"])

    assert signals.stocks_for(include_aapl, _daily("AAPL", "MSFT"), 1) == ["AAPL"]
    assert signals.stocks_for(include_msft, _daily("AAPL", "MSFT"), 1) == []
    out = signals.run_signals(_PERIOD, [include_aapl], _daily("AAPL", "MSFT"), 1, store,
                              StepCache(tmp_path / "c"), workers=0)
    assert set(out["symbol"]) == {"AAPL"}


def test_process_pool_equals_in_process(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.028.M11.T03: Worker processes give the same periods."""
    serial = signals.run_signals(_PERIOD, [_strategy()], _daily("AAPL", "MSFT"), 0, store,
                                 StepCache(tmp_path / "a"), workers=0)
    pooled = signals.run_signals(_PERIOD, [_strategy()], _daily("AAPL", "MSFT"), 0, store,
                                 StepCache(tmp_path / "b"), workers=2)

    pd.testing.assert_frame_equal(serial, pooled)


def _service(store: BacktestStore, tmp_path: Path) -> tuple[BacktestService, ResultsStore]:
    results = ResultsStore(tmp_path / "results.db")
    svc = BacktestService(store, StepCache(tmp_path / "cache"), results, lambda: [],
                          lambda _p, _u: rsi_preset(0, 100), lambda: [_strategy()])
    return svc, results


def test_missing_strategy_name(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.029.M05.T01: A plan naming an unknown strategy is a plain error."""
    svc, _ = _service(store, tmp_path)
    plan = plan_for(_PERIOD.start, _PERIOD.end, ("AAPL",))
    plan = replace(plan, strategies=(StrategySpec("X"),))

    with pytest.raises(ValueError, match="Strategy X is not in the strategy list"):
        svc.run_signals(plan, DailyList("k", [], _daily("AAPL")), workers=0)


def test_service_runs_step_2(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.029.M05.T02: Step 2 through the service returns periods and a done row."""
    svc, results = _service(store, tmp_path)
    plan = plan_for(_PERIOD.start, _PERIOD.end, ("AAPL", "MSFT"))
    plan = replace(plan, strategies=(StrategySpec("ST_A"),))

    out = svc.run_signals(plan, DailyList("k", [], _daily("AAPL", "MSFT")), workers=0)

    assert set(out["strategy"]) == {"ST_A"}
    assert [r.status for r in results.list_runs()] == ["done"]
