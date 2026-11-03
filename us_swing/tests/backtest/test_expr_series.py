"""Tests for MD-BKT-002.020.M09 — core/expr and MD-BKT-002.021.M10 — core/expr/series.py."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from us_swing.backtest.store import BacktestStore
from us_swing.core.expr import ConditionEvaluator, EvaluatorError, parse
from us_swing.core.expr.series import ET, evaluate, function_series
from us_swing.execution.strategy_engine._evaluator import _Parser, _tokenize
from tests.backtest.conftest import LATE, daily_bars, intraday_bars

_DAYS = ["2025-03-20", "2025-03-21", "2025-03-24"]
_CASES: list[tuple[str, list[Any]]] = [
    ("RSI", ["Spot", 14]), ("EMA", ["Spot", 9]), ("ADX", ["Spot", 14]),
    ("MACD", ["Spot", 12, 26, 9]), ("SUPERTREND", ["Spot", 10, 3, "No"]),
    ("SWING", ["Spot", 20, 5, "high", "Recent"]), ("SWING", ["Spot", 20, 5, "range", "Old"]),
    ("Price", ["Spot", "current", "close"]), ("Price", ["Spot", "Last", "high"]),
]


@pytest.fixture()
def frames(tmp_path: Path) -> dict[str, pd.DataFrame]:
    store = BacktestStore(tmp_path)
    store.save("AAPL", "1d", daily_bars("2025-01-01", 60, 3), LATE)
    store.save("AAPL", "3m", intraday_bars(_DAYS, 4), LATE)
    return {tf: store.read("AAPL", tf) for tf in ("3m", "15m", "30m", "1d", "1w")}


def _live(name: str, args: list[Any], frame: pd.DataFrame, tf: str) -> float:
    try:
        return ConditionEvaluator.FUNCTION_MAP[name](args, {tf: frame}, "AAPL")
    except EvaluatorError:
        return float("nan")


def _on_day(frames: dict[str, pd.DataFrame], day: str) -> np.ndarray:
    et = pd.DatetimeIndex(frames["3m"]["ts"]).tz_convert(ET)
    return np.asarray(et.strftime("%Y-%m-%d") == day)


def test_parser_is_live_parser() -> None:
    """UT-BKT-002.020.M09.T01: The shared parser gives the live AST."""
    text = "RSI('Spot', 14, '3m') > 50 AND Price('Spot', 'current', 'close', '15m') > 1"

    assert parse(text) == _Parser(_tokenize(text)).parse()


def test_bad_text_raises() -> None:
    """UT-BKT-002.020.M09.T02: Bad condition text raises EvaluatorError."""
    with pytest.raises(EvaluatorError):
        parse("RSI((")


def test_parity_every_function_and_timeframe(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.021.M10.T01: Series value at bar i equals live on bars up to i."""
    cases = [*_CASES, ("VWAP", ["Spot"])]
    for tf, frame in frames.items():
        for name, args in cases:
            if name == "VWAP" and tf in ("3m", "15m", "30m"):
                continue  # resets per session by design (UT-BKT-002.024.M10.T01)
            full = [*args, tf]
            series = function_series(name, full, frame, tf)
            live = [_live(name, full, frame.iloc[:i + 1], tf) for i in range(len(frame))]
            np.testing.assert_allclose(series, live, rtol=1e-9, equal_nan=True,
                                       err_msg=f"{name} {tf}")


def test_too_few_bars_is_nan(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.021.M10.T02: Short history gives NaN where live raises."""
    short = frames["3m"].iloc[:5]

    assert np.isnan(function_series("RSI", ["Spot", 14, "3m"], short, "3m")).all()
    with pytest.raises(EvaluatorError):
        ConditionEvaluator().evaluate("RSI('Spot', 14, '3m') > 0", {"3m": short}, "AAPL")


def test_daily_and_15m_alignment(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.022.M10.T01: 1d is yesterday's value; 15m changes only at bucket closes."""
    ev = evaluate("EMA('Spot', 3, '1d') > 0 AND EMA('Spot', 3, '15m') > 0", frames)

    daily = function_series("EMA", ["Spot", 3, "1d"], frames["1d"], "1d")
    day1_row = int(np.flatnonzero(frames["1d"]["ts"] == pd.Timestamp("2025-03-20"))[0])
    on_day2 = _on_day(frames, "2025-03-21")
    assert np.allclose(ev.values["EMA(3, 1d)"][on_day2], daily[day1_row])

    closes = pd.DatetimeIndex(frames["3m"]["ts"]) + pd.Timedelta(minutes=3)
    values = ev.values["EMA(3, 15m)"]
    same = (values[1:] == values[:-1]) | (np.isnan(values[1:]) & np.isnan(values[:-1]))
    changed = np.flatnonzero(~same) + 1
    assert len(changed) > 0
    assert all(closes[i].minute % 15 == 0 for i in changed)


def test_no_look_ahead(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.022.M10.T02: Changing day 2's daily bar leaves day 2's 3m results alone."""
    text = "EMA('Spot', 3, '1d') > 0"
    before = evaluate(text, frames).values["EMA(3, 1d)"]
    changed = dict(frames)
    changed["1d"] = frames["1d"].copy()
    changed["1d"].loc[changed["1d"]["ts"] == pd.Timestamp("2025-03-21"), "close"] *= 2

    after = evaluate(text, changed).values["EMA(3, 1d)"]

    on_day2 = _on_day(frames, "2025-03-21")
    np.testing.assert_array_equal(before[on_day2], after[on_day2])


def test_price_reads_closed_15m_bars(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.050.M10.T01: 15m current is the last closed bar; Last is the one before."""
    ev = evaluate("Price('Spot', 'current', 'close', '15m') > 0 AND "
                  "Price('Spot', 'current', 'high', '15m') > 0 AND "
                  "Price('Spot', 'Last', 'close', '15m') > 0", frames)
    bars = frames["3m"]
    i = 131  # day 2, second 3m bar (09:33–09:36) of the 09:30 bucket
    closed = frames["15m"][frames["15m"]["ts"] < bars["ts"].iloc[130]]

    assert ev.values["Price(current, close, 15m)"][i] == closed["close"].iloc[-1]
    assert ev.values["Price(current, high, 15m)"][i] == closed["high"].iloc[-1]
    assert ev.values["Price(Last, close, 15m)"][i] == closed["close"].iloc[-2]


def test_price_15m_changes_only_at_bucket_close(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.050.M10.T02: 15m current price never moves inside a forming bar."""
    ev = evaluate("Price('Spot', 'current', 'close', '15m') > 0", frames)
    closes = pd.DatetimeIndex(frames["3m"]["ts"]) + pd.Timedelta(minutes=3)
    values = ev.values["Price(current, close, 15m)"]
    same = (values[1:] == values[:-1]) | (np.isnan(values[1:]) & np.isnan(values[:-1]))

    assert all(closes[i].minute % 15 == 0 for i in np.flatnonzero(~same) + 1)


def test_vwap_resets_each_session(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.024.M10.T01: The first bar of a session has VWAP = its typical price."""
    ev = evaluate("VWAP('Spot', '3m') > 0", frames)
    bar = frames["3m"].iloc[130]

    assert ev.values["VWAP(3m)"][130] == pytest.approx((bar.high + bar.low + bar.close) / 3)


def test_nan_comparison_is_false(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.025.M10.T01: Bars without enough history do not fire, even with !=."""
    ev = evaluate("RSI('Spot', 14, '3m') != 0", frames)

    assert not ev.fired[:14].any()
    assert ev.fired[14:].all()


def test_pnl_is_flagged(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.027.M10.T01: PNL is flagged and counts as unknown."""
    ev = evaluate("PNL('Spot') > 1 OR RSI('Spot', 14, '3m') > 0", frames)
    rsi = function_series("RSI", ["Spot", 14, "3m"], frames["3m"], "3m")

    assert ev.uses_pnl
    np.testing.assert_array_equal(ev.fired, ~np.isnan(rsi) & (np.nan_to_num(rsi) > 0))


def test_swing_window_parity(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.082.M10.T01: SWING Previous and Current series equal live on bars up to i."""
    for tf, frame in frames.items():
        for kind in ("High", "Low", "Range"):
            for window in ("Previous", "Current"):
                args = ["Spot", 5, kind, window, tf]
                series = function_series("SWING", args, frame, tf)
                live = [_live("SWING", args, frame.iloc[:i + 1], tf) for i in range(len(frame))]
                np.testing.assert_allclose(series, live, rtol=1e-9, equal_nan=True,
                                           err_msg=f"SWING {kind} {window} {tf}")


def test_swing_bad_candles_and_legacy_args(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.082.M10.T02: Candles 0 raises; legacy 6 args give the Current series."""
    with pytest.raises(EvaluatorError):
        evaluate("SWING('Spot', 0, 'High', 'Previous', '3m') > 0", frames)

    legacy = evaluate("SWING('Spot', 5, 3, 'High', 'Day', '3m') > 0", frames)
    current = evaluate("SWING('Spot', 5, 'High', 'Current', '3m') > 0", frames)
    np.testing.assert_array_equal(list(legacy.values.values())[0],
                                  list(current.values.values())[0])


def test_price_30m_changes_only_at_bucket_close(frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.085.M10.T01: 30m current price moves only at :00 and :30 closes."""
    ev = evaluate("Price('Spot', 'current', 'close', '30m') > 0", frames)
    closes = pd.DatetimeIndex(frames["3m"]["ts"]) + pd.Timedelta(minutes=3)
    values = ev.values["Price(current, close, 30m)"]
    same = (values[1:] == values[:-1]) | (np.isnan(values[1:]) & np.isnan(values[:-1]))
    changed = np.flatnonzero(~same) + 1

    assert len(changed) > 0
    assert all(closes[i].minute % 30 == 0 for i in changed)


_BOSS = "BOSS_ST('Spot', 2, 0.0, '30m', '15m', '{}') > -9"


@pytest.fixture(scope="module")
def boss_frames(tmp_path_factory: pytest.TempPathFactory) -> dict[str, pd.DataFrame]:
    store = BacktestStore(tmp_path_factory.mktemp("boss"))
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-03-03", periods=14)]
    store.save("AAPL", "3m", intraday_bars(days, 11), LATE)
    return {tf: store.read("AAPL", tf) for tf in ("3m", "15m", "30m")}


def _cut(frames: dict[str, pd.DataFrame], at: pd.Timestamp) -> dict[str, pd.DataFrame]:
    minutes = {"15m": 15, "30m": 30}
    return {tf: f[f["ts"] + pd.Timedelta(minutes=minutes[tf]) <= at]
            for tf, f in frames.items() if tf in minutes}


def test_boss_st_parity(boss_frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.087.M10.T01: BOSS_ST value at each 3m close equals live on frames cut then."""
    closes = pd.DatetimeIndex(boss_frames["3m"]["ts"]) + pd.Timedelta(minutes=3)
    for signal in ("State", "Fresh"):
        values = list(evaluate(_BOSS.format(signal), boss_frames).values.values())[0]
        changed = np.flatnonzero(np.nan_to_num(np.diff(values), nan=1.0)) + 1
        picks = sorted(set(range(0, len(values), 23)) | set(changed.tolist()))
        live = [_live_boss(signal, _cut(boss_frames, closes[i])) for i in picks]
        np.testing.assert_array_equal(values[picks], live, err_msg=signal)
        assert np.nanmax(np.abs(values)) == 1.0


def _live_boss(signal: str, frames: dict[str, pd.DataFrame]) -> float:
    try:
        return ConditionEvaluator.FUNCTION_MAP["BOSS_ST"](
            ["Spot", 2, 0.0, "30m", "15m", signal], frames, "AAPL")
    except EvaluatorError:
        return float("nan")


def test_boss_st_bad_args_raise(boss_frames: dict[str, pd.DataFrame]) -> None:
    """UT-BKT-002.087.M10.T02: Bad BOSS_ST args raise."""
    with pytest.raises(EvaluatorError):
        evaluate("BOSS_ST('Spot', 2, 0.0, '15m', '15m', 'State') > 0", boss_frames)
    with pytest.raises(EvaluatorError):
        evaluate("BOSS_ST('Spot', 2, 0.0, '30m', '15m', 'Maybe') > 0", boss_frames)
