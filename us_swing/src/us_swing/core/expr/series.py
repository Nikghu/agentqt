"""
Module: MD-BKT-002.021.M10 — core/expr/series.py
Parent SRD: SRD-BKT-002.021

Backtest evaluator: a strategy condition as one value per 3m bar.

``function_series`` gives, for each bar *i* of one timeframe, the value the live
evaluator returns on that frame's bars up to *i*. ``evaluate`` reads every
series as of each 3m bar close, so a timeframe is seen only as far as live could
see it then (SRD-BKT-002.022).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import numpy.typing as npt
import pandas as pd
import talib

from us_swing.core.expr import EvaluatorError, parse

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
IntArray = npt.NDArray[np.int64]

ET = ZoneInfo("America/New_York")
INTRADAY_MINUTES = {"3m": 3, "15m": 15}
_NS_PER_MIN = 60_000_000_000
_ARITY = {"Number": 1, "PNL": 1, "VWAP": 2, "Price": 4, "RSI": 3, "ADX": 3, "EMA": 3,
          "SUPERTREND": 5, "SWING": 6, "MACD": 5}
_COMPARE: dict[str, Callable[[FloatArray, FloatArray], BoolArray]] = {
    ">": np.greater, "<": np.less, ">=": np.greater_equal, "<=": np.less_equal,
    "==": np.equal, "!=": np.not_equal,
}


@dataclass(frozen=True)
class Evaluation:
    """Result on the 3m timeline: fired per bar, each function's values, PNL use."""

    fired: BoolArray
    values: dict[str, FloatArray]
    uses_pnl: bool


def _col(frame: pd.DataFrame, name: str) -> FloatArray:
    if name not in frame.columns:
        raise EvaluatorError(f"Unknown price type {name!r}")
    return frame[name].to_numpy(dtype=np.float64)


def _ns(stamps: pd.DatetimeIndex) -> IntArray:
    naive = stamps.tz_convert("UTC").tz_localize(None)
    return np.asarray(naive.to_numpy(dtype="datetime64[ns]").view(np.int64), dtype=np.int64)


def _utc_ns(frame: pd.DataFrame) -> IntArray:
    stamps = pd.DatetimeIndex(frame["ts"])
    return _ns(stamps if stamps.tz is not None else stamps.tz_localize("UTC"))


def available_ns(frame: pd.DataFrame, tf: str) -> IntArray:
    """When each bar becomes visible: intraday at its close, 1d next day, 1w next week."""
    if tf in INTRADAY_MINUTES:
        return _utc_ns(frame) + INTRADAY_MINUTES[tf] * _NS_PER_MIN
    days = 1 if tf == "1d" else 7
    local = pd.DatetimeIndex(frame["ts"]).normalize().tz_localize(ET) + pd.Timedelta(days=days)
    return _ns(local)


def _as_of(values: FloatArray, avail: IntArray, at: IntArray, back: int = 0) -> FloatArray:
    idx = np.searchsorted(avail, at, side="right") - 1 - back
    out = np.full(at.shape, np.nan)
    ok = idx >= 0
    out[ok] = values[idx[ok]]
    return out


def _vwap(frame: pd.DataFrame, tf: str) -> FloatArray:
    typical = (_col(frame, "high") + _col(frame, "low") + _col(frame, "close")) / 3.0
    volume = _col(frame, "volume")
    session = (pd.DatetimeIndex(frame["ts"]).tz_convert(ET).date if tf in INTRADAY_MINUTES
               else np.zeros(len(frame)))
    cum_v = pd.Series(volume).groupby(session).cumsum().to_numpy(dtype=np.float64)
    cum_pv = pd.Series(typical * volume).groupby(session).cumsum().to_numpy(dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cum_v == 0, np.nan, cum_pv / cum_v)


def _supertrend(frame: pd.DataFrame, length: int, factor: float) -> FloatArray:
    high, low, close = _col(frame, "high"), _col(frame, "low"), _col(frame, "close")
    atr = talib.ATR(high, low, close, timeperiod=length)
    hl2 = (high + low) / 2.0
    final_upper = hl2 + factor * atr
    final_lower = hl2 - factor * atr
    basic_upper, basic_lower = final_upper.copy(), final_lower.copy()
    out = np.full(len(frame), np.nan)
    direction = 1
    if len(frame):
        out[0] = final_lower[0]
    for i in range(1, len(frame)):
        if not np.isnan(atr[i - 1]):
            final_lower[i] = (max(basic_lower[i], final_lower[i - 1])
                              if close[i - 1] > final_lower[i - 1] else basic_lower[i])
            final_upper[i] = (min(basic_upper[i], final_upper[i - 1])
                              if close[i - 1] < final_upper[i - 1] else basic_upper[i])
            if direction == -1 and close[i] > final_upper[i - 1]:
                direction = 1
            elif direction == 1 and close[i] < final_lower[i - 1]:
                direction = -1
        out[i] = final_lower[i] if direction == 1 else final_upper[i]
    return out


def _swing(frame: pd.DataFrame, bars: int, kind: str) -> FloatArray:
    if bars < 1:
        return np.full(len(frame), np.nan)
    high = pd.Series(_col(frame, "high")).rolling(bars, min_periods=1)
    low = pd.Series(_col(frame, "low")).rolling(bars, min_periods=1)
    if kind == "high":
        return high.max().to_numpy()
    if kind == "low":
        return low.min().to_numpy()
    if kind == "range":
        return (high.max() - low.min()).to_numpy()
    raise EvaluatorError(f"SWING: unknown Price Swing {kind!r}")


def function_series(name: str, args: list[Any], frame: pd.DataFrame, tf: str) -> FloatArray:
    """Value per bar equal to the live function on ``frame`` up to that bar.

    Raises:
        EvaluatorError: unknown function or bad argument.
    """
    close = _col(frame, "close")
    if name == "VWAP":
        return _vwap(frame, tf)
    if name == "RSI":
        return np.asarray(talib.RSI(close, timeperiod=int(args[1])), dtype=np.float64)
    if name == "EMA":
        return np.asarray(talib.EMA(close, timeperiod=int(args[1])), dtype=np.float64)
    if name == "ADX":
        return np.asarray(talib.ADX(_col(frame, "high"), _col(frame, "low"), close,
                                    timeperiod=int(args[1])), dtype=np.float64)
    if name == "MACD":
        _line, _signal, hist = talib.MACD(close, fastperiod=int(args[1]),
                                          slowperiod=int(args[2]), signalperiod=int(args[3]))
        return np.asarray(hist, dtype=np.float64)
    if name == "SUPERTREND":
        return _supertrend(frame, int(args[1]), float(args[2]))
    if name == "SWING":
        return _swing(frame, int(args[1]), str(args[3]).lower())
    if name == "Price":
        values = _col(frame, str(args[2]).lower())
        if str(args[1]).lower() == "current":
            return values
        return np.concatenate(([np.nan], values[:-1]))
    raise EvaluatorError(f"Unknown indicator {name!r}")


class _Walker:
    """Evaluates one AST on the 3m timeline of ``frames``."""

    def __init__(self, frames: Mapping[str, pd.DataFrame]) -> None:
        self.frames = frames
        self.base = self._frame("3m")
        self.close_ns = _utc_ns(self.base) + 3 * _NS_PER_MIN
        self.values: dict[str, FloatArray] = {}
        self.uses_pnl = False

    def _frame(self, tf: str) -> pd.DataFrame:
        frame = self.frames.get(tf)
        if frame is None or frame.empty:
            raise EvaluatorError(f"No candle data for timeframe {tf!r}")
        return frame

    def _full(self, value: float) -> FloatArray:
        return np.full(len(self.base), value)

    def number(self, node: dict[str, Any]) -> FloatArray | BoolArray:
        kind = node["type"]
        if kind == "NUMBER":
            return self._full(float(node["value"]))
        if kind == "FUNC":
            return self._function(node)
        if kind == "BIN_OP":
            return self._bin_op(node)
        raise EvaluatorError(f"{kind.title()} is not allowed here")

    def _function(self, node: dict[str, Any]) -> FloatArray:
        name = node["name"]
        if name not in _ARITY:
            raise EvaluatorError(f"Unknown indicator {name!r}")
        args = [self._constant(a) for a in node["args"]]
        if len(args) != _ARITY[name]:
            raise EvaluatorError(f"Indicator {name!r} expects {_ARITY[name]} arg(s), "
                                 f"got {len(args)}")
        if name == "Number":
            return self._full(float(args[0]))
        if name == "PNL":
            self.uses_pnl = True
            return self._full(np.nan)
        tf = str(args[-1])
        if name == "Price":
            out = self._price(args, tf)
        else:
            frame = self._frame(tf)
            series = function_series(name, args, frame, tf)
            out = _as_of(series, available_ns(frame, tf), self.close_ns)
        label = f"{name}({', '.join(str(a) for a in args[1:])})"
        self.values[label] = out
        return out

    @staticmethod
    def _constant(node: dict[str, Any]) -> Any:
        if node["type"] in ("NUMBER", "STRING"):
            return node["value"]
        raise EvaluatorError("Only numbers and text are allowed inside a function")

    def _price(self, args: list[Any], tf: str) -> FloatArray:
        """SRD-BKT-002.023 — current / previous candle as live reads them."""
        column = str(args[2]).lower()
        current = str(args[1]).lower() == "current"
        if tf == "3m":
            values = _col(self.base, column)
            return values if current else np.concatenate(([np.nan], values[:-1]))
        frame = self._frame(tf)
        avail = available_ns(frame, tf)
        if tf not in INTRADAY_MINUTES:
            return _as_of(_col(frame, column), avail, self.close_ns, back=0 if current else 1)
        bucket = pd.DatetimeIndex(self.base["ts"]).floor(f"{INTRADAY_MINUTES[tf]}min")
        if not current:
            start_ns = _ns(bucket)
            return _as_of(_col(frame, column), avail, start_ns)
        grouped = pd.Series(_col(self.base, column)).groupby(np.asarray(bucket))
        forming = {"open": grouped.transform("first"), "high": grouped.cummax(),
                   "low": grouped.cummin(), "volume": grouped.cumsum()}
        if column == "close":
            return _col(self.base, "close")
        if column not in forming:
            raise EvaluatorError(f"Unknown price type {column!r}")
        return forming[column].to_numpy(dtype=np.float64)

    def _bin_op(self, node: dict[str, Any]) -> BoolArray:
        op = node["op"]
        left, right = self.number(node["left"]), self.number(node["right"])
        if op == "AND":
            return truth(left) & truth(right)
        if op == "OR":
            return truth(left) | truth(right)
        if op not in _COMPARE:
            raise EvaluatorError(f"Unknown operator {op!r}")
        lhs, rhs = left.astype(np.float64), right.astype(np.float64)
        valid = ~np.isnan(lhs) & ~np.isnan(rhs)
        with np.errstate(invalid="ignore"):
            return np.asarray(_COMPARE[op](lhs, rhs) & valid, dtype=np.bool_)


def truth(values: FloatArray | BoolArray) -> BoolArray:
    """True where a value is a true comparison or a non-zero, known number."""
    if values.dtype == np.bool_:
        return np.asarray(values, dtype=np.bool_)
    return np.asarray(~np.isnan(values) & (values != 0), dtype=np.bool_)


def evaluate(expr: str, frames: Mapping[str, pd.DataFrame]) -> Evaluation:
    """Evaluate ``expr`` on every bar of ``frames["3m"]`` (SRD-BKT-002.021–.025, .027).

    Raises:
        EvaluatorError: bad condition text or a timeframe with no candles.
    """
    walker = _Walker(frames)
    result = walker.number(parse(expr))
    return Evaluation(truth(result), walker.values, walker.uses_pnl)
