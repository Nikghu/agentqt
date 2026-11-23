"""Tests for MD-EXE-022.001.M01 — the public ``usswing`` library."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from tests.execution.plugin_helpers import SWING_PLUS, frame
from usswing import Input, Number, USSwingIndicator
from usswing._indicator import OutputError, compute
from usswing._parameters import ParameterError


def _load_swing_plus() -> type[USSwingIndicator]:
    spec = importlib.util.spec_from_file_location("swing_plus_example", SWING_PLUS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SwingPlus  # type: ignore[no-any-return]


def _source(candles: pd.DataFrame) -> Any:
    return lambda _symbol_type, _timeframe: candles


class _Signal(USSwingIndicator):
    indicator_name = "UP_CANDLE"
    description = "1 when the candle closed above its open"
    version = "1.0"
    output_type = "signal"
    parameters = [Input("Timeframe", options=["3m"], default="3m")]

    def calculate(self) -> Any:
        candles = self.candles("Spot", self.parameter("Timeframe"))
        return candles["close"] > candles["open"]


def test_public_names_import() -> None:
    """UT-EXE-022.001.M01.T01: The three public names import; the library uses no tool internals."""
    import usswing

    assert {"USSwingIndicator", "Number", "Input"} <= set(usswing.__all__)
    package = Path(usswing.__file__).parent
    for file in package.glob("*.py"):
        assert "us_swing" not in file.read_text(encoding="utf-8"), file.name


def test_old_and_internal_names_not_offered() -> None:
    """UT-EXE-022.001.M01.T02: Old or internal names are not offered by the package."""
    with pytest.raises(ImportError):
        from usswing import Choice  # type: ignore[attr-defined]  # noqa: F401
    with pytest.raises(ImportError):
        from usswing import compute as _compute  # type: ignore[attr-defined]  # noqa: F401


def test_number_keeps_fields_and_converts() -> None:
    """UT-EXE-022.002.M01.T01: Number keeps its fields and converts to an int."""
    candles = Number("Candles", default=20, minimum=1, maximum=500, whole_number=True)

    assert (candles.label, candles.default, candles.minimum, candles.maximum) == (
        "Candles", 20, 1, 500)
    value = candles.convert("35")
    assert value == 35 and isinstance(value, int)


def test_number_default_outside_limits() -> None:
    """UT-EXE-022.002.M01.T02: A default outside its limits is refused, naming the label."""
    with pytest.raises(ParameterError, match="^Candles"):
        Number("Candles", default=600, minimum=1, maximum=500)


def test_input_default_not_in_options() -> None:
    """UT-EXE-022.002.M01.T03: An Input default that is not an option is refused."""
    with pytest.raises(ParameterError, match="^Price Swing"):
        Input("Price Swing", options=["High", "Low"], default="Mid")


def test_convert_out_of_range() -> None:
    """UT-EXE-022.002.M01.T04: Converting a value outside the limits gives a plain message."""
    candles = Number("Candles", default=20, minimum=1, maximum=500, whole_number=True)

    with pytest.raises(ParameterError, match="^Candles must be 1 to 500, got 0$"):
        candles.convert(0)
    with pytest.raises(ParameterError, match="one of High, Low, Range, got 'Mid'"):
        Input("Price Swing", options=["High", "Low", "Range"], default="High").convert("Mid")


def test_swing_example_one_value_per_candle() -> None:
    """UT-EXE-022.003.M01.T01: SWING_PLUS gives one value per candle; Range = max high − min low."""
    candles = frame(30)
    swing = _load_swing_plus()(_source(candles), {"Candles": 5, "Price Swing": "Range",
                                                  "Window": "Current"})

    result = compute(swing)

    assert len(result.values) == 30 and result.main_timeframe == "3m"
    window = candles.iloc[6:11]
    assert result.values.iloc[10] == pytest.approx(window["high"].max() - window["low"].min())
    assert result.values.iloc[:4].isna().all()


def test_signal_becomes_one_and_zero() -> None:
    """UT-EXE-022.003.M01.T02: A True/False result becomes 1.0 and 0.0."""
    candles = frame(10)

    values = compute(_Signal(_source(candles))).values

    assert set(values.unique()) <= {0.0, 1.0}
    assert values.tolist() == (candles["close"] > candles["open"]).astype(float).tolist()


def test_wrong_length_or_infinite_value() -> None:
    """UT-EXE-022.003.M01.T03: Wrong length and infinite values are refused with plain text."""
    candles = frame(390)

    class Short(_Signal):
        def calculate(self) -> Any:
            self.candles("Spot", "3m")
            return np.zeros(120)

    class Infinite(_Signal):
        def calculate(self) -> Any:
            values = self.candles("Spot", "3m")["close"].copy()
            values.iloc[5] = np.inf
            return values

    with pytest.raises(OutputError, match="120 values, but there are 390 candles"):
        compute(Short(_source(candles)))
    with pytest.raises(OutputError, match="infinite"):
        compute(Infinite(_source(candles)))


def test_candles_are_a_copy_and_debug_kept() -> None:
    """UT-EXE-022.004.M01.T01: Changing the candles does not change the source; debug kept."""
    candles = frame(10)
    before = candles.copy()

    class Changer(_Signal):
        def calculate(self) -> Any:
            mine = self.candles("Spot", "3m")
            mine["close"] = 0.0
            self.debug_value("High", mine["high"])
            return mine["close"]

    result = compute(Changer(_source(candles)))

    pd.testing.assert_frame_equal(candles, before)
    assert list(result.debug) == ["High"]
    assert result.table().columns.tolist() == ["value", "High"]


def test_unknown_parameter_label() -> None:
    """UT-EXE-022.004.M01.T02: Asking for a label that is not declared raises a plain error."""
    indicator = _Signal(_source(frame(5)))

    with pytest.raises(ParameterError, match="Unknown parameter 'Lookback'"):
        indicator.parameter("Lookback")
