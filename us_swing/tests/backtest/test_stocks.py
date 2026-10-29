"""Tests for MD-BKT-002.010.M07 — backtest/steps/stocks.py."""
from __future__ import annotations

import pickle
import types
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from us_swing.backtest.cache import StepCache
from us_swing.backtest.spec import Period
from us_swing.backtest.steps import stocks
from us_swing.backtest.store import BacktestStore
from us_swing.screener.executor import PresetExecutor
from us_swing.screener.preset import Preset
from tests.backtest.conftest import LATE, daily_bars, plan_for, rsi_preset

_NAMES = ("AAPL", "MSFT", "NVDA")
_START, _END = date(2025, 3, 3), date(2025, 3, 7)


def _run(store: BacktestStore, cache: StepCache, end: date = _END,
         preset: dict[str, Any] | None = None, **kw: Any) -> tuple[str, list[date]]:
    plan = plan_for(_START, end, _NAMES)
    return stocks.run_stocks(plan, preset or rsi_preset(0, 100), list(_NAMES), store, cache,
                             {}, workers=0, **kw)


def test_days_from_spy(store: BacktestStore) -> None:
    """UT-BKT-002.010.M07.T01: Days are SPY's dates inside the period."""
    store.save("SPY", "1d", daily_bars("2025-03-04", 3, 9), LATE)

    days = stocks.trading_days(store, Period(_START, _END), list(_NAMES))

    assert days == [date(2025, 3, 4), date(2025, 3, 5), date(2025, 3, 6)]


def test_days_without_spy(store: BacktestStore) -> None:
    """UT-BKT-002.010.M07.T02: Without SPY the days are the stocks' dates."""
    days = stocks.trading_days(store, Period(_START, _END), ["AAPL", "MSFT"])

    assert days == [date(2025, 3, d) for d in range(3, 8)]


def test_replay_equals_live_screener(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.011.M07.T01: One day's list equals the live rule stages on the same bars."""
    cache = StepCache(tmp_path / "cache")
    preset = rsi_preset(50, 100)
    key, _ = _run(store, cache, preset=preset)
    day = date(2025, 3, 5)
    bars = {
        sym: [types.SimpleNamespace(datetime=r.ts, open=r.open, high=r.high, low=r.low,
                                    close=r.close, volume=r.volume)
              for r in store.read(sym, "1d", None, day).itertuples()]
        for sym in _NAMES
    }

    live = PresetExecutor().screen(Preset.from_dict(preset), list(_NAMES), bars, {})

    expected = sorted((s, d["score"]) for s, d in live.items() if d["passed"])
    saved = cache.read(stocks.STEP, key, day.isoformat())
    assert saved is not None
    assert list(zip(saved["symbol"], saved["score"])) == expected


def test_no_look_ahead(tmp_path: Path) -> None:
    """UT-BKT-002.011.M07.T02: A jump after day D does not change D's result."""
    flat = daily_bars("2025-01-01", 60, 1)
    jumped = flat.copy()
    jumped.loc[jumped.index[-1], ["open", "high", "low", "close"]] = 500.0
    results = []
    for i, frame in enumerate((flat, jumped)):
        st = BacktestStore(tmp_path / f"s{i}")
        st.save("AAPL", "1d", frame, LATE)
        history = stocks.load_bars(st.root, ["AAPL"], date(2024, 1, 1), date(2025, 12, 31))
        day = frame["ts"].iloc[-2].date()
        results.append(stocks.compute_day(history, rsi_preset(0, 100), ["AAPL"], day, {}))

    pd.testing.assert_frame_equal(results[0], results[1])


def test_one_file_per_day(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.012.M07.T01: A 5-day run saves 5 day files under one key."""
    cache = StepCache(tmp_path / "cache")

    key, days = _run(store, cache)

    assert len(days) == 5
    assert cache.names(stocks.STEP, key) == {d.isoformat() for d in days}


def test_rules_change_gives_new_key() -> None:
    """UT-BKT-002.012.M07.T02: Changed rules give a new key; name and top N do not."""
    base = rsi_preset(50, 100)
    renamed = {**base, "name": "Other", "top_n": 3, "enable_llm_ranking": True}

    assert stocks.rules_key(base, ["AAPL"]) == stocks.rules_key(renamed, ["AAPL"])
    assert stocks.rules_key(base, ["AAPL"]) != stocks.rules_key(rsi_preset(60, 100), ["AAPL"])
    assert stocks.rules_key(base, ["AAPL"]) != stocks.rules_key(base, ["AAPL", "MSFT"])


def test_second_run_computes_nothing(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.013.M07.T01: A second run (other top N) has nothing to compute."""
    cache = StepCache(tmp_path / "cache")
    _run(store, cache)
    calls: list[tuple[int, int]] = []

    stocks.run_stocks(plan_for(_START, _END, _NAMES, top_n=2), rsi_preset(0, 100),
                      list(_NAMES), store, cache, {}, workers=0,
                      progress=lambda d, t: calls.append((d, t)))

    assert calls == [(0, 0)]


def test_longer_period_only_new_days(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.013.M07.T02: Extending the period computes only the new days."""
    cache = StepCache(tmp_path / "cache")
    _run(store, cache)
    calls: list[tuple[int, int]] = []

    _run(store, cache, end=date(2025, 3, 11), progress=lambda d, t: calls.append((d, t)))

    assert calls[-1] == (2, 2)


def test_rank_and_top_n(tmp_path: Path) -> None:
    """UT-BKT-002.014.M07.T01: Rank by score, ties by symbol; top 1 keeps one row."""
    cache = StepCache(tmp_path)
    day = date(2025, 3, 3)
    cache.write(stocks.STEP, "k", day.isoformat(), pd.DataFrame(
        {"symbol": ["NVDA", "MSFT", "AAPL"], "passed": True, "score": [0.9, 0.5, 0.9]}))

    frame = stocks.daily_list(cache, "k", [day, date(2025, 3, 4)])

    assert list(zip(frame["symbol"], frame["rank"])) == [("AAPL", 1), ("NVDA", 2),
                                                         ("MSFT", 3)]
    assert list(stocks.top_n(frame, 1)["symbol"]) == ["AAPL"]


def test_top_n_zero_keeps_all(tmp_path: Path) -> None:
    """UT-BKT-002.014.M07.T02: Top N 0 keeps every row."""
    frame = pd.DataFrame({"date": [date(2025, 3, 3)] * 2, "symbol": ["A", "B"],
                          "score": [1.0, 0.5], "rank": [1, 2]})

    assert len(stocks.top_n(frame, 0)) == 2


def test_process_pool_run(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.015.M07.T01: The process pool gives the same frames as in-process."""
    serial, pooled = StepCache(tmp_path / "a"), StepCache(tmp_path / "b")
    key, days = _run(store, serial)
    calls: list[tuple[int, int]] = []

    stocks.run_stocks(plan_for(_START, date(2025, 3, 6), _NAMES), rsi_preset(0, 100),
                      list(_NAMES), store, pooled, {}, workers=2,
                      progress=lambda d, t: calls.append((d, t)))

    assert calls[-1] == (4, 4)
    for day in days[:4]:
        pd.testing.assert_frame_equal(
            serial.read(stocks.STEP, key, day.isoformat()),
            pooled.read(stocks.STEP, key, day.isoformat()),
        )


def test_cancel_keeps_finished_days(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.015.M07.T02: Cancel raises and the finished day stays cached."""
    cache = StepCache(tmp_path / "cache")

    with pytest.raises(stocks.StepCancelled):
        _run(store, cache, cancel=lambda: True)

    key = stocks.rules_key(rsi_preset(0, 100), list(_NAMES))
    assert cache.names(stocks.STEP, key) == {_START.isoformat()}


def test_weekly_preset_refused(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.016.M07.T01: A weekly preset is refused with a plain message."""
    with pytest.raises(stocks.StepRefused, match="Weekly screener presets"):
        _run(store, StepCache(tmp_path), preset=rsi_preset(timeframe="1w"))


def test_ai_tick_refused(store: BacktestStore, tmp_path: Path,
                         monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-BKT-002.016.M07.T02: The AI tick is refused before any screening."""
    calls: list[str] = []
    monkeypatch.setattr(stocks, "screen_day", lambda *a: calls.append("x") or {})
    plan = plan_for(_START, _END, _NAMES, ai_ranking=True)

    with pytest.raises(stocks.StepRefused, match="AI ranking"):
        stocks.run_stocks(plan, rsi_preset(), list(_NAMES), store, StepCache(tmp_path), {},
                          workers=0)
    assert calls == []


def _rs_preset(rs_enabled: bool = True) -> dict[str, Any]:
    preset = rsi_preset(0, 100)
    rules = preset["screeners"][0]["config"]["rules"]
    rules.append({"indicator_id": "rs_index", "condition": "at_least", "value": 70,
                  "enabled": rs_enabled})
    return {**preset, "preset_type": "composite", "screeners": [],
            "groups": [{"group_id": "g1", "logic": "AND", "screeners": [preset["screeners"][0]]}]}


def test_rs_rule_detected() -> None:
    """UT-BKT-002.018.M07.T01: An enabled RS rule inside a group needs the benchmark."""
    assert stocks.needs_benchmark(_rs_preset())
    assert not stocks.needs_benchmark(_rs_preset(rs_enabled=False))
    assert not stocks.needs_benchmark(rsi_preset())


def test_rs_rule_refused_without_spy(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.018.M07.T02: RS rule and no SPY stops Step 1 with one plain sentence."""
    with pytest.raises(stocks.StepRefused) as err:
        _run(store, StepCache(tmp_path), preset=_rs_preset())

    message = str(err.value)
    assert message.startswith("This screener uses the RS rule")
    assert message.count("SPY") == 1


def test_worker_error_is_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-BKT-002.019.M07.T01: A worker error comes back once, as plain text with the day."""
    class Doubling(Exception):
        def __init__(self, symbol: str) -> None:
            super().__init__(f"Data for '{symbol}' is missing")

    def boom(*_a: Any) -> dict[str, tuple[bool, float]]:
        raise Doubling("SPY")

    monkeypatch.setattr(stocks, "screen_day", boom)
    monkeypatch.setattr(stocks, "_history", {})

    with pytest.raises(RuntimeError) as err:
        stocks._run_day({}, ["AAPL"], date(2025, 3, 3), {})

    assert str(err.value) == "2025-03-03: Data for 'SPY' is missing"
    assert pickle.loads(pickle.dumps(err.value)).args == err.value.args
