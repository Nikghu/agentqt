"""
Module: MD-EXE-011.001.M03 — ConditionEvaluator
Parent SRD: SRD-EXE-011.006
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, ClassVar, cast

import numpy as np
import pandas as pd
import talib


class EvaluatorError(RuntimeError):
    """Raised on tokenizer / parser / arity / evaluation failures."""


_IndicatorFn = Callable[[list[Any], dict[str, pd.DataFrame], str], float]


_TOKEN_SPEC: tuple[tuple[str, str], ...] = (
    ("NUMBER", r"-?\d+(\.\d+)?"),
    ("IDENT", r"[A-Za-z_]\w*"),
    ("STRING", r"'(?:\\'|[^'])*'"),
    ("OP", r">=|<=|==|!=|>|<"),
    ("COMMA", r","),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("SKIP", r"[ \t]+"),
    ("MISMATCH", r"."),
)
_TOKEN_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in _TOKEN_SPEC))


# ── Tokenizer ─────────────────────────────────────────────────────────────────

def _tokenize(expr: str) -> list[tuple[str, Any]]:
    tokens: list[tuple[str, Any]] = []
    for mo in _TOKEN_RE.finditer(expr):
        kind = mo.lastgroup
        val = mo.group()
        if kind == "NUMBER":
            tokens.append(("NUMBER", float(val) if "." in val else int(val)))
        elif kind == "STRING":
            tokens.append(("STRING", val[1:-1].replace("\\'", "'")))
        elif kind == "IDENT":
            upper = val.upper()
            if upper in ("AND", "OR"):
                tokens.append((upper, upper))
            else:
                tokens.append(("IDENT", val))
        elif kind in ("OP", "COMMA", "LPAREN", "RPAREN"):
            tokens.append((kind, val))
        elif kind == "SKIP":
            continue
        elif kind == "MISMATCH":
            raise EvaluatorError(f"Unexpected token {val!r} at position {mo.start()}")
    return tokens


# ── Parser (recursive descent → AST as plain dicts) ───────────────────────────

class _Parser:
    def __init__(self, tokens: list[tuple[str, Any]]) -> None:
        self._tokens = tokens
        self._pos = 0

    def parse(self) -> dict[str, Any]:
        node = self._or_expr()
        if self._pos != len(self._tokens):
            raise EvaluatorError(f"Trailing tokens at position {self._pos}")
        return node

    def _current(self) -> tuple[str, Any] | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _eat(self, kind: str | None = None) -> tuple[str, Any]:
        tok = self._current()
        if tok is None:
            raise EvaluatorError("Unexpected end of expression")
        if kind is not None and tok[0] != kind:
            raise EvaluatorError(f"Expected {kind} but got {tok[0]}")
        self._pos += 1
        return tok

    def _or_expr(self) -> dict[str, Any]:
        node = self._and_expr()
        while (cur := self._current()) is not None and cur[0] == "OR":
            self._eat("OR")
            right = self._and_expr()
            node = {"type": "BIN_OP", "op": "OR", "left": node, "right": right}
        return node

    def _and_expr(self) -> dict[str, Any]:
        node = self._comparison()
        while (cur := self._current()) is not None and cur[0] == "AND":
            self._eat("AND")
            right = self._comparison()
            node = {"type": "BIN_OP", "op": "AND", "left": node, "right": right}
        return node

    def _comparison(self) -> dict[str, Any]:
        node = self._term()
        cur = self._current()
        if cur is not None and cur[0] == "OP":
            op = self._eat("OP")[1]
            right = self._term()
            node = {"type": "BIN_OP", "op": op, "left": node, "right": right}
        return node

    def _term(self) -> dict[str, Any]:
        tok = self._current()
        if tok is None:
            raise EvaluatorError("Unexpected end of expression in term")
        kind, value = tok

        if kind == "NUMBER":
            self._eat("NUMBER")
            return {"type": "NUMBER", "value": value}
        if kind == "STRING":
            self._eat("STRING")
            return {"type": "STRING", "value": value}
        if kind == "IDENT":
            ident = self._eat("IDENT")[1]
            if (nxt := self._current()) is not None and nxt[0] == "LPAREN":
                self._eat("LPAREN")
                args = self._arg_list()
                self._eat("RPAREN")
                return {"type": "FUNC", "name": ident, "args": args}
            return {"type": "IDENT", "value": ident}
        if kind == "LPAREN":
            self._eat("LPAREN")
            node = self._or_expr()
            self._eat("RPAREN")
            return node
        raise EvaluatorError(f"Unexpected token {kind!r}")

    def _arg_list(self) -> list[dict[str, Any]]:
        args: list[dict[str, Any]] = []
        if (cur := self._current()) is not None and cur[0] == "RPAREN":
            return args
        args.append(self._term())
        while (cur := self._current()) is not None and cur[0] == "COMMA":
            self._eat("COMMA")
            args.append(self._term())
        return args


# ── Indicator helpers ─────────────────────────────────────────────────────────

def _require_args(name: str, args: list[Any], expected: int) -> None:
    if len(args) != expected:
        raise EvaluatorError(
            f"Indicator {name!r} expects {expected} arg(s), got {len(args)}"
        )


def _frame_for_tf(candles: dict[str, pd.DataFrame], tf: str) -> pd.DataFrame:
    df = candles.get(tf)
    if df is None or df.empty:
        raise EvaluatorError(f"No candle data for timeframe {tf!r}")
    return df


def _last(series: pd.Series) -> float:
    val = series.iloc[-1]
    if pd.isna(val):
        return float("nan")
    return float(val)


def _to_f64(series: pd.Series) -> np.ndarray:
    return series.to_numpy(dtype=np.float64)


def _last_arr(arr: np.ndarray) -> float:
    if arr.size == 0:
        return float("nan")
    val = arr[-1]
    return float("nan") if np.isnan(val) else float(val)


# ── Indicator implementations ─────────────────────────────────────────────────

def _fn_number(args: list[Any], _c: dict[str, pd.DataFrame], _s: str) -> float:
    _require_args("Number", args, 1)
    return float(args[0])


def _fn_pnl(args: list[Any], _c: dict[str, pd.DataFrame], _s: str) -> float:
    _require_args("PNL", args, 1)
    return 0.0  # Position-context indicator; supplied by router at call time.


def _fn_price(args: list[Any], c: dict[str, pd.DataFrame], _s: str) -> float:
    _require_args("Price", args, 4)
    _symbol_type, candle, price_type, tf = args
    df = _frame_for_tf(c, str(tf))
    idx = -1 if str(candle).lower() == "current" else -2
    if abs(idx) > len(df):
        raise EvaluatorError(f"Insufficient bars for Price({candle!r})")
    return float(df[str(price_type).lower()].iloc[idx])


def _fn_vwap(args: list[Any], c: dict[str, pd.DataFrame], _s: str) -> float:
    _require_args("VWAP", args, 2)
    _symbol_type, tf = args
    df = _frame_for_tf(c, str(tf))
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_v = df["volume"].cumsum()
    cum_pv = (typical * df["volume"]).cumsum()
    vwap = cum_pv / cum_v.replace(0, np.nan)
    return _last(vwap)


def _fn_rsi(args: list[Any], c: dict[str, pd.DataFrame], _s: str) -> float:
    _require_args("RSI", args, 3)
    _symbol_type, length, tf = args
    df = _frame_for_tf(c, str(tf))
    return _last_arr(talib.RSI(_to_f64(df["close"]), timeperiod=int(length)))


def _fn_adx(args: list[Any], c: dict[str, pd.DataFrame], _s: str) -> float:
    _require_args("ADX", args, 3)
    _symbol_type, length, tf = args
    df = _frame_for_tf(c, str(tf))
    return _last_arr(
        talib.ADX(
            _to_f64(df["high"]),
            _to_f64(df["low"]),
            _to_f64(df["close"]),
            timeperiod=int(length),
        )
    )


def _fn_ema(args: list[Any], c: dict[str, pd.DataFrame], _s: str) -> float:
    _require_args("EMA", args, 3)
    _symbol_type, period, tf = args
    df = _frame_for_tf(c, str(tf))
    return _last_arr(talib.EMA(_to_f64(df["close"]), timeperiod=int(period)))


def _supertrend_direction(df: pd.DataFrame, length: int, factor: float) -> float:
    """Supertrend direction (+1 uptrend, -1 downtrend) for the last bar.

    Built on top of `talib.ATR` since TA-Lib does not ship a Supertrend primitive.
    """
    high = _to_f64(df["high"])
    low = _to_f64(df["low"])
    close = _to_f64(df["close"])
    atr = talib.ATR(high, low, close, timeperiod=length)
    hl2 = (high + low) / 2.0
    upper = hl2 + factor * atr
    lower = hl2 - factor * atr

    direction = 1
    for i in range(1, len(df)):
        if np.isnan(upper[i - 1]) or np.isnan(lower[i - 1]):
            continue
        if close[i] > upper[i - 1]:
            direction = 1
        elif close[i] < lower[i - 1]:
            direction = -1
    return float(direction)


def _fn_supertrend(args: list[Any], c: dict[str, pd.DataFrame], _s: str) -> float:
    _require_args("SUPERTREND", args, 5)
    _symbol_type, atr_length, factor, _abs_dev, tf = args
    df = _frame_for_tf(c, str(tf))
    return _supertrend_direction(df, int(atr_length), float(factor))


def _fn_swing(args: list[Any], c: dict[str, pd.DataFrame], _s: str) -> float:
    _require_args("SWING", args, 6)
    _symbol_type, lookback_bars, _lookback_days, price_swing, swing_type, tf = args
    df = _frame_for_tf(c, str(tf))
    n = min(int(lookback_bars), len(df))
    window = df.tail(n)
    kind = str(price_swing).lower()
    if kind == "high":
        return float(window["high"].max())
    if kind == "low":
        return float(window["low"].min())
    if kind == "range":
        return float(window["high"].max() - window["low"].min())
    raise EvaluatorError(f"SWING: unknown Price Swing {price_swing!r}")
    # `swing_type` ('Day' / 'Recent' / 'Old') is currently informational; logic is window-based.
    _ = swing_type  # keep arity check honest


def _fn_macd(args: list[Any], c: dict[str, pd.DataFrame], _s: str) -> float:
    _require_args("MACD", args, 5)
    _symbol_type, fast, slow, signal, tf = args
    df = _frame_for_tf(c, str(tf))
    _macd, _sig, hist = talib.MACD(
        _to_f64(df["close"]),
        fastperiod=int(fast),
        slowperiod=int(slow),
        signalperiod=int(signal),
    )
    return _last_arr(hist)



# ── Public class ──────────────────────────────────────────────────────────────

class ConditionEvaluator:
    """Parses and evaluates an FO-GUI-013 trigger expression against candles."""

    FUNCTION_MAP: ClassVar[dict[str, _IndicatorFn]] = {
        "Number": _fn_number,
        "PNL": _fn_pnl,
        "VWAP": _fn_vwap,
        "Price": _fn_price,
        "RSI": _fn_rsi,
        "ADX": _fn_adx,
        "EMA": _fn_ema,
        "SUPERTREND": _fn_supertrend,
        "SWING": _fn_swing,
        "MACD": _fn_macd,
    }

    def evaluate(
        self,
        expr: str,
        candles: dict[str, pd.DataFrame],
        symbol: str,
    ) -> bool:
        ast = _Parser(_tokenize(expr)).parse()
        return bool(self._eval(ast, candles, symbol))

    # ── AST eval ──────────────────────────────────────────────────────────────

    def _eval(
        self,
        node: dict[str, Any],
        candles: dict[str, pd.DataFrame],
        symbol: str,
    ) -> float | bool:
        kind = node["type"]

        if kind == "NUMBER":
            return float(node["value"])
        if kind == "STRING":
            return cast(float, node["value"])
        if kind == "FUNC":
            fn = self.FUNCTION_MAP.get(node["name"])
            if fn is None:
                raise EvaluatorError(f"Unknown indicator {node['name']!r}")
            resolved_args = [self._eval(a, candles, symbol) for a in node["args"]]
            return fn(resolved_args, candles, symbol)
        if kind == "BIN_OP":
            op = node["op"]
            left = self._eval(node["left"], candles, symbol)
            right = self._eval(node["right"], candles, symbol)
            return self._apply_op(op, left, right)
        if kind == "IDENT":
            raise EvaluatorError(f"Bare identifier {node['value']!r} not allowed")
        raise EvaluatorError(f"Unknown AST node kind {kind!r}")

    @staticmethod
    def _apply_op(
        op: str,
        left: float | bool,
        right: float | bool,
    ) -> float | bool:
        if op == "AND":
            return bool(left) and bool(right)
        if op == "OR":
            return bool(left) or bool(right)
        l_num = float(left) if not isinstance(left, bool) else float(int(left))
        r_num = float(right) if not isinstance(right, bool) else float(int(right))
        if op == ">":
            return l_num > r_num
        if op == "<":
            return l_num < r_num
        if op == ">=":
            return l_num >= r_num
        if op == "<=":
            return l_num <= r_num
        if op == "==":
            return l_num == r_num
        if op == "!=":
            return l_num != r_num
        raise EvaluatorError(f"Unknown operator {op!r}")
