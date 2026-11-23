"""
Module: MD-EXE-022.001.M01 — usswing indicator base class
Parent SRD: SRD-EXE-022.003
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np
import pandas as pd

from usswing._parameters import Parameter, ParameterError, resolve_values

CandleSource = Callable[[str, str], pd.DataFrame]


class OutputError(ValueError):
    """``calculate()`` gave something that is not one number per candle."""


class USSwingIndicator:
    """Base class for a custom indicator.

    Set the five details below, list every popup row in ``parameters`` and write
    ``calculate()``. Nothing is added for you: the popup shows exactly ``parameters``.
    """

    indicator_name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    version: ClassVar[str] = ""
    output_type: ClassVar[str] = "value"
    parameters: ClassVar[list[Parameter]] = []

    def __init__(self, candle_source: CandleSource,
                 values: Mapping[str, Any] | None = None) -> None:
        self._candle_source = candle_source
        self._values = resolve_values(type(self).parameters, dict(values or {}))
        self._debug: dict[str, Any] = {}
        self._main_timeframe: str | None = None
        self._main_candles: pd.DataFrame | None = None

    def candles(self, symbol_type: str, timeframe: str) -> pd.DataFrame:
        """Candles of the stock for ``timeframe``, oldest first (a copy you may change).

        The first timeframe you ask for is the one ``calculate()`` must give values for.
        """
        frame = self._candle_source(symbol_type, timeframe)
        if self._main_candles is None:
            self._main_timeframe = timeframe
            self._main_candles = frame
        return frame.copy()

    def parameter(self, label: str) -> Any:
        """The value the user chose for the parameter with this label."""
        if label not in self._values:
            raise ParameterError(f"Unknown parameter {label!r}")
        return self._values[label]

    def debug_value(self, name: str, series: Any) -> None:
        """Keep a series for the test table and the chart preview; no effect on trading."""
        self._debug[str(name)] = series

    def calculate(self) -> Any:
        """Return one value per candle of the first timeframe you read."""
        raise NotImplementedError("calculate() is not written")


@dataclass(frozen=True)
class Result:
    """What one ``calculate()`` run gave, lined up with the main candles."""

    values: pd.Series
    main_timeframe: str
    debug: dict[str, pd.Series] = field(default_factory=dict)
    times: pd.Series | None = None

    def table(self) -> pd.DataFrame:
        """Time (when the candles have one), value and debug series, one row per candle."""
        columns: dict[str, pd.Series] = {"value": self.values, **self.debug}
        if self.times is not None:
            columns = {"time": self.times, **columns}
        return pd.DataFrame(columns)


def compute(indicator: USSwingIndicator) -> Result:
    """Run ``calculate()`` and check its output.

    Raises:
        OutputError: no candles read, wrong length, not numbers, or infinite values.
    """
    raw = indicator.calculate()
    main = indicator._main_candles
    if main is None or indicator._main_timeframe is None:
        raise OutputError("calculate() did not read any candles")
    values = _as_series(raw, main.index, "calculate()")
    debug = {name: _as_series(series, main.index, f"debug value {name!r}")
             for name, series in indicator._debug.items()}
    return Result(values=values, main_timeframe=indicator._main_timeframe, debug=debug,
                  times=_times(main))


def _times(candles: pd.DataFrame) -> pd.Series | None:
    """The candles' time column (``datetime`` in the tool, ``ts`` in replay), if any."""
    for column in ("datetime", "ts"):
        if column in candles:
            return candles[column]
    return None


def _as_series(raw: Any, index: pd.Index, what: str) -> pd.Series:
    if isinstance(raw, pd.DataFrame):
        raise OutputError(f"{what} must give one value per candle, not a table")
    array = raw.to_numpy() if isinstance(raw, pd.Series) else np.asarray(raw)
    if array.ndim != 1:
        raise OutputError(f"{what} must give one value per candle")
    if len(array) != len(index):
        raise OutputError(f"{what} returned {len(array)} values, but there are "
                          f"{len(index)} candles")
    try:
        series = pd.Series(array, index=index, dtype="float64")
    except (TypeError, ValueError):
        raise OutputError(f"{what} must give numbers or True/False") from None
    if np.isinf(series.to_numpy()).any():
        raise OutputError(f"{what} gave an infinite value")
    return series
