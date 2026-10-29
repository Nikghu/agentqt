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
    return {tf: store.read("AAPL", tf) for tf in ("3m", "15m", "1d", "1w")}


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
            if name == "VWAP" and tf in ("3m", "15m"):
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
