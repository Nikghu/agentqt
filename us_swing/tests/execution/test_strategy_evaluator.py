"""
Module: MD-EXE-011.001.M03 — tests
Parent SRD: SRD-EXE-011.006
"""
from __future__ import annotations

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


def test_function_map_has_exactly_14_keys() -> None:
    """UT-EXE-011.001.M03.T08: FUNCTION_MAP keys == exactly the 14 documented names."""
    expected = {
        "Number", "PNL", "VWAP", "Price", "RSI", "ADX", "EMA",
        "SUPERTREND", "SWING", "MACD", "BOS_Engulfing",
        "BOSS_EMA", "BOSS_ADX", "BOSS_SMT",
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
