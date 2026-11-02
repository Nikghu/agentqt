"""
Module: MD-GUI-013.001.M01 — tests
Parent SRD: SRD-GUI-013.022
"""
from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QLineEdit

from us_swing.gui.strategy_builder_dialog import _INDICATOR_DATA, _ConditionSelectorDialog


def _swing_dialog(qtbot) -> _ConditionSelectorDialog:  # type: ignore[no-untyped-def]
    dlg = _ConditionSelectorDialog("Condition 1")
    qtbot.addWidget(dlg)
    dlg._ind_combo.setCurrentText("SWING")
    return dlg


def test_swing_form_has_window_and_no_lookback(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-013.022.M01.T01: SWING form has the new fields."""
    dlg = _swing_dialog(qtbot)
    built: list[str] = []
    dlg.condition_built.connect(built.append)

    window = dlg._inputs["Window"]
    assert list(dlg._inputs) == ["Symbol Type", "Candles", "Price Swing", "Window", "Timeframe"]
    assert isinstance(window, QComboBox)
    assert [window.itemText(i) for i in range(window.count())] == ["Previous", "Current"]

    candles = dlg._inputs["Candles"]
    assert isinstance(candles, QLineEdit)
    candles.setText("20")
    dlg._on_add()
    assert built == ["SWING('Spot', 20, 'High', 'Previous', '3m')"]


def test_swing_candles_zero_refused(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-013.022.M01.T02: Candles 0 is refused."""
    dlg = _swing_dialog(qtbot)
    built: list[str] = []
    dlg.condition_built.connect(built.append)
    candles = dlg._inputs["Candles"]
    assert isinstance(candles, QLineEdit)

    candles.setText("0")
    dlg._on_add()

    assert not candles.hasAcceptableInput()
    assert built == []


def test_timeframe_dropdowns_offer_30m() -> None:
    """UT-GUI-013.023.M01.T01: every Timeframe dropdown lists 3m, 15m, 30m, 1d, 1w."""
    lists = [p["Datatype"] for ind in _INDICATOR_DATA for p in ind["parameters"]
             if p["name"] == "Timeframe"]

    assert len(lists) == 9
    assert all(lst == ["3m", "15m", "30m", "1d", "1w"] for lst in lists)
