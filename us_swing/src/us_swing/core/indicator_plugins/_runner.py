"""
Module: MD-EXE-022.010.M04 — running a custom indicator
Parent SRD: SRD-EXE-022.010

Turns expression arguments into parameter values and runs ``calculate()`` on the
engine's frames. Live and replay both use this, so they get the same values
(SRD-EXE-022.010–.011).
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from usswing._indicator import Result, compute
from usswing._parameters import ParameterError

from us_swing.core.indicator_plugins._check import PluginSpec
from us_swing.core.indicator_plugins._guard import PluginGuard


class PluginArgError(ValueError):
    """Wrong number or value of arguments for a custom indicator."""


class NoCandleData(LookupError):
    """The indicator asked for a timeframe the engine has no candles for."""


def values_from_args(spec: PluginSpec, args: Sequence[Any]) -> dict[str, Any]:
    """Map expression arguments to labels, in ``parameters`` order, with checks."""
    if len(args) != len(spec.parameters):
        raise PluginArgError(f"{spec.name} expects {len(spec.parameters)} arg(s), "
                             f"got {len(args)}")
    values: dict[str, Any] = {}
    for parameter, raw in zip(spec.parameters, args, strict=True):
        try:
            values[parameter.label] = parameter.convert(raw)
        except ParameterError as exc:
            raise PluginArgError(f"{spec.name}: {exc}") from None
    return values


def run_plugin(spec: PluginSpec, values: Mapping[str, Any], frames: Mapping[str, pd.DataFrame],
               *, symbol: str = "", guard: PluginGuard | None = None) -> Result:
    """Run the indicator on ``frames``; through ``guard`` when given (live), else directly.

    Raises:
        NoCandleData: a timeframe it reads has no candles (never counted as a failure).
        PluginCallError: the guarded call failed.
    """
    def source(_symbol_type: str, timeframe: str) -> pd.DataFrame:
        frame = frames.get(timeframe)
        if frame is None or frame.empty:
            raise NoCandleData(f"No candle data for timeframe {timeframe!r}")
        return frame

    def call() -> Result:
        return compute(spec.indicator_class(source, values))

    if guard is None:
        return call()
    return guard.run(spec.name, call, symbol=symbol, candle=_candle_key(frames),
                     passthrough=(NoCandleData,))


def last_value(result: Result) -> float:
    """The newest value, or NaN when there is none."""
    if result.values.empty:
        return math.nan
    return float(result.values.iloc[-1])


def _candle_key(frames: Mapping[str, pd.DataFrame]) -> str:
    frame = frames.get("3m")
    if frame is None or frame.empty or "ts" not in frame:
        return ""
    return str(frame["ts"].iloc[-1])
