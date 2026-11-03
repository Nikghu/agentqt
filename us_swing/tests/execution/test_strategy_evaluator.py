"""
Module: MD-EXE-011.001.M03 — tests
Parent SRD: SRD-EXE-011.006
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest
import talib

from us_swing.execution.strategy_engine._evaluator import (
    ConditionEvaluator,
    EvaluatorError,
    _Parser,
    _tokenize,
)


def _declining_candles(n: int = 50) -> dict[str, pd.DataFrame]:
    closes = np.linspace(100.0, 85.0, n)
    df = pd.DataFrame({
        "open": closes + 0.5,
        "high": closes + 1.0,
        "low": closes - 0.5,
        "close": closes,
        "volume": np.full(n, 1_000_000),
    })
    return {"3m": df}


def _rising_candles(n: int = 50) -> dict[str, pd.DataFrame]:
    closes = np.linspace(85.0, 105.0, n)
    df = pd.DataFrame({
        "open": closes - 0.5,
        "high": closes + 1.0,
        "low": closes - 1.0,
        "close": closes,
        "volume": np.full(n, 1_000_000),
    })
    return {"3m": df}


def test_tokenize_rsi_expr_correct_kinds() -> None:
    """UT-EXE-011.001.M03.T01: Tokenize 'RSI('Spot', 14, '3m') < 30' → correct token kinds."""
    tokens = _tokenize("RSI('Spot', 14, '3m') < 30")
    kinds = [t[0] for t in tokens]
    assert kinds == ["IDENT", "LPAREN", "STRING", "COMMA", "NUMBER", "COMMA", "STRING", "RPAREN", "OP", "NUMBER"]
    assert tokens[0][1] == "RSI"
    assert tokens[4][1] == 14
    assert tokens[8][1] == "<"
    assert tokens[9][1] == 30


def test_parse_and_or_produces_correct_tree() -> None:
    """UT-EXE-011.001.M03.T02: Parse 'Price > 100 AND RSI < 30 OR Number == 0' → top-level OR, left=AND."""
    expr = "Price('Spot', 'Current', 'close', '3m') > 100 AND RSI('Spot', 14, '3m') < 30 OR Number(1) == Number(0)"
    tokens = _tokenize(expr)
    ast = _Parser(tokens).parse()
    assert ast["type"] == "BIN_OP"
    assert ast["op"] == "OR"
    assert ast["left"]["op"] == "AND"


def test_tokenize_invalid_token_raises_evaluator_error() -> None:
    """UT-EXE-011.001.M03.T03: Tokenize 'RSI(14) ~~ 30' → EvaluatorError on unexpected token."""
    with pytest.raises(EvaluatorError, match="Unexpected token"):
        _tokenize("RSI(14) ~~ 30")


def test_rsi_value_for_declining_series() -> None:
    """UT-EXE-011.001.M03.T04: RSI returns ~27 for monotonically declining close series."""
    candles = _declining_candles(50)
    closes = candles["3m"]["close"].to_numpy(dtype=np.float64)
    rsi_arr = talib.RSI(closes, timeperiod=14)
    rsi_last = float(rsi_arr[-1])
    assert rsi_last < 35.0, f"Expected RSI < 35, got {rsi_last:.2f}"


def test_evaluate_rsi_lt_30_with_low_rsi_candles_returns_true() -> None:
    """UT-EXE-011.001.M03.T05: evaluate('RSI ... < 30') with low RSI candles → True."""
    evaluator = ConditionEvaluator()
    candles = _declining_candles(50)
    result = evaluator.evaluate("RSI('Spot', 14, '3m') < 30", candles, "AAPL")
    assert result is True


def test_evaluate_rsi_lt_30_with_high_rsi_candles_returns_false() -> None:
    """UT-EXE-011.001.M03.T06: evaluate('RSI ... < 30') with rising candles → False."""
    evaluator = ConditionEvaluator()
    candles = _rising_candles(50)
    result = evaluator.evaluate("RSI('Spot', 14, '3m') < 30", candles, "AAPL")
    assert result is False


def test_evaluate_rsi_wrong_arity_raises_evaluator_error() -> None:
    """UT-EXE-011.001.M03.T07: evaluate('RSI(14)') → EvaluatorError about arity."""
    evaluator = ConditionEvaluator()
    candles = _declining_candles(50)
    with pytest.raises(EvaluatorError, match="expects 3 arg"):
        evaluator.evaluate("RSI(14) < 30", candles, "AAPL")


def test_function_map_has_exactly_11_keys() -> None:
    """UT-EXE-011.001.M03.T08: FUNCTION_MAP keys == exactly the 11 implemented names.

    The four BOSS/BOS entries were stubs and were removed in d6c4f4db; BOSS_ST
    is real (SRD-EXE-011.027). The Strategy Builder offers the same 11, so no
    strategy can reference a missing indicator.
    """
    expected = {
        "Number", "PNL", "VWAP", "Price", "RSI", "ADX", "EMA",
        "SUPERTREND", "SWING", "MACD", "BOSS_ST",
    }
    assert set(ConditionEvaluator.FUNCTION_MAP.keys()) == expected


def test_parse_grouped_or_and_produces_top_level_and() -> None:
    """UT-EXE-011.001.M03.T09: '(A OR B) AND C' parse → top-level AND with left=OR-node."""
    expr = "(Number(1) == Number(1) OR Number(0) == Number(1)) AND Number(1) == Number(1)"
    tokens = _tokenize(expr)
    ast = _Parser(tokens).parse()
    assert ast["type"] == "BIN_OP"
    assert ast["op"] == "AND"
    assert ast["left"]["op"] == "OR"


def _short_candles(n: int = 5) -> dict[str, pd.DataFrame]:
    closes = np.linspace(100.0, 98.0, n)
    df = pd.DataFrame({
        "open": closes,
        "high": closes + 0.5,
        "low": closes - 0.5,
        "close": closes,
        "volume": np.full(n, 1_000_000),
    })
    return {"3m": df}


def test_supertrend_insufficient_bars_raises() -> None:
    """UT-EXE-011.001.M03.T10: short SUPERTREND raises EvaluatorError, not NaN→False."""
    evaluator = ConditionEvaluator()
    expr = "Price('Stock', 'current', 'close', '3m') < SUPERTREND('Stock', 10, 3, 0, '3m')"
    with pytest.raises(EvaluatorError):
        evaluator.evaluate(expr, _short_candles(5), "AAA")


def test_short_rsi_surfaced_not_false() -> None:
    """UT-EXE-011.001.M03.T11: a NaN RSI surfaces as EvaluatorError, not a silent False."""
    evaluator = ConditionEvaluator()
    with pytest.raises(EvaluatorError):
        evaluator.evaluate("RSI('Stock', 14, '3m') < 30", _short_candles(5), "AAA")


def test_finite_indicator_passes_guard() -> None:
    """UT-EXE-011.001.M03.T12: a finite indicator result passes the guard unchanged."""
    evaluator = ConditionEvaluator()
    assert evaluator.evaluate(
        "RSI('Stock', 14, '3m') < 30", _declining_candles(50), "AAA"
    ) is True


def test_short_ema_raises_generic_guard() -> None:
    """UT-EXE-011.001.M03.T13: the guard is generic — a short EMA raises rather than NaN."""
    evaluator = ConditionEvaluator()
    with pytest.raises(EvaluatorError):
        evaluator.evaluate("EMA('Stock', 50, '3m') > 0", _short_candles(3), "AAA")


def _swing_candles() -> dict[str, pd.DataFrame]:
    highs = [10.0, 12.0, 11.0, 15.0]
    lows = [8.0, 9.0, 7.0, 13.0]
    df = pd.DataFrame({
        "open": [9.0, 10.0, 10.0, 13.5],
        "high": highs,
        "low": lows,
        "close": [9.5, 11.0, 8.0, 14.0],
        "volume": np.full(4, 1_000_000),
    })
    return {"1d": df}


def _swing(args: list[Any], candles: dict[str, pd.DataFrame]) -> float:
    return ConditionEvaluator.FUNCTION_MAP["SWING"](args, candles, "AAA")


def test_swing_previous_window_fires_breakout() -> None:
    """UT-EXE-011.026.M03.T01: Previous window gives a real breakout."""
    expr = "Price('Spot', 'current', 'close', '1d') > SWING('Spot', 2, 'High', 'Previous', '1d')"

    assert ConditionEvaluator().evaluate(expr, _swing_candles(), "AAA") is True


def test_swing_current_window_never_broken_by_close() -> None:
    """UT-EXE-011.026.M03.T02: Current window can never be broken by the close."""
    expr = "Price('Spot', 'current', 'close', '1d') > SWING('Spot', 2, 'High', 'Current', '1d')"

    assert ConditionEvaluator().evaluate(expr, _swing_candles(), "AAA") is False


@pytest.mark.parametrize(("kind", "window", "expected"), [
    ("High", "Current", 15.0), ("High", "Previous", 12.0),
    ("Low", "Current", 7.0), ("Low", "Previous", 7.0),
    ("Range", "Current", 8.0), ("Range", "Previous", 5.0),
])
def test_swing_values_for_both_windows(kind: str, window: str, expected: float) -> None:
    """UT-EXE-011.026.M03.T03: High, Low and Range for both windows."""
    assert _swing(["Spot", 2, kind, window, "1d"], _swing_candles()) == expected


@pytest.mark.parametrize("args", [
    ["Spot", 0, "High", "Previous", "1d"],
    ["Spot", -5, "High", "Current", "1d"],
    ["Spot", 2, "High", "Sideways", "1d"],
])
def test_swing_bad_candles_or_window_raises(args: list[Any]) -> None:
    """UT-EXE-011.026.M03.T04: Candles below 1 or a bad Window raise."""
    with pytest.raises(EvaluatorError):
        _swing(args, _swing_candles())


def test_swing_legacy_six_args_read_as_current() -> None:
    """UT-EXE-011.026.M03.T05: Legacy 6-arg form reads as Current."""
    legacy = _swing(["Spot", 2, 5, "High", "Day", "1d"], _swing_candles())

    assert legacy == _swing(["Spot", 2, "High", "Current", "1d"], _swing_candles())


def _boss_candles(cut: int | None = None) -> dict[str, pd.DataFrame]:
    from tests.core.test_market_structure import boss_frames

    ltf, htf = boss_frames(col="datetime")
    if cut is not None:
        ltf = ltf.iloc[:cut]
        last_close = ltf["datetime"].iloc[-1] + pd.Timedelta(minutes=15)
        htf = htf[htf["datetime"] + pd.Timedelta(minutes=30) <= last_close]
    return {"15m": ltf, "30m": htf}


def _boss(signal: str, candles: dict[str, pd.DataFrame]) -> float:
    return ConditionEvaluator.FUNCTION_MAP["BOSS_ST"](
        ["Spot", 2, 0.0, "30m", "15m", signal], candles, "AAPL"
    )


def test_boss_st_live_value_is_last_series_value() -> None:
    """UT-EXE-011.027.M03.T01: Live value is the last series value."""
    from us_swing.core.market_structure import BossStParams, bars_from_frame, boss_st

    full = _boss_candles()
    result = boss_st(bars_from_frame(full["15m"], 15), bars_from_frame(full["30m"], 30),
                     BossStParams(2, 0.0))
    turn = int(np.flatnonzero(np.nan_to_num(result.fresh))[-1])
    candles = _boss_candles(cut=turn + 1)
    ev = ConditionEvaluator()
    fresh = int(result.fresh[turn])

    assert _boss("State", candles) == result.state[turn]
    assert ev.evaluate(f"BOSS_ST('Spot', 2, 0.0, '30m', '15m', 'Fresh') == Number({fresh})",
                       candles, "AAPL")
    assert not ev.evaluate("BOSS_ST('Spot', 2, 0.0, '30m', '15m', 'Fresh') == Number(0)",
                           candles, "AAPL")
    assert _boss("Fresh", _boss_candles(cut=turn + 2)) in (0.0, -fresh)


@pytest.mark.parametrize("args", [
    ["Spot", 0, 0.0, "30m", "15m", "Fresh"],
    ["Spot", 21, 0.0, "30m", "15m", "Fresh"],
    ["Spot", 2, 6.0, "30m", "15m", "Fresh"],
    ["Spot", 2, 0.0, "15m", "15m", "Fresh"],
    ["Spot", 2, 0.0, "1d", "15m", "Fresh"],
    ["Spot", 2, 0.0, "30m", "15m", "Maybe"],
    ["Spot", 2, 0.0, "30m", "15m"],
])
def test_boss_st_bad_args_raise(args: list[Any]) -> None:
    """UT-EXE-011.027.M03.T02: Bad arguments raise."""
    with pytest.raises(EvaluatorError):
        ConditionEvaluator.FUNCTION_MAP["BOSS_ST"](args, _boss_candles(), "AAPL")


def test_boss_st_too_little_history_raises() -> None:
    """UT-EXE-011.027.M03.T03: Too little history raises, never 0."""
    with pytest.raises(EvaluatorError):
        ConditionEvaluator().evaluate(
            "BOSS_ST('Spot', 2, 0.0, '30m', '15m', 'State') == Number(0)",
            _boss_candles(cut=50), "AAPL",
        )
