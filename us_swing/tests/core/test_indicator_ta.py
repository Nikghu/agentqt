"""Unit tests: MD-SCR-015.008.M25 — core/indicator_rules/_ta.py
Refs: UT-SCR-015.008.M25.T01–T04
"""
from __future__ import annotations

import math

import numpy as np
import pytest
import talib

from us_swing.core.indicator_rules import _ta

from .conftest import seeded_arrays


def test_rsi_matches_talib() -> None:
    """UT-SCR-015.008.M25.T01: RSI equals TA-Lib Wilder RSI."""
    a = seeded_arrays(60)
    assert _ta.rsi(a.close, 14)[-1] == pytest.approx(talib.RSI(a.close, timeperiod=14)[-1])


def test_atr_pct_is_wilder_atr_over_close() -> None:
    """UT-SCR-015.008.M25.T02: ATR % equals Wilder ATR ÷ close × 100."""
    a = seeded_arrays(60)
    expected = talib.ATR(a.high, a.low, a.close, timeperiod=14)[-1] / a.close[-1] * 100
    assert _ta.atr_pct(a.high, a.low, a.close, 14)[-1] == pytest.approx(expected)


def test_ppo_signal_and_histogram() -> None:
    """UT-SCR-015.008.M25.T03: hist == ppo − EMA(ppo, 9)."""
    a = seeded_arrays(80)
    line, sig, hist = _ta.ppo(a.close, 12, 26, 9)
    assert sig[-1] == pytest.approx(talib.EMA(line, timeperiod=9)[-1])
    assert hist[-1] == pytest.approx(line[-1] - sig[-1])
    fast, slow = talib.EMA(a.close, 12)[-1], talib.EMA(a.close, 26)[-1]
    assert line[-1] == pytest.approx((fast - slow) / slow * 100)


def test_too_few_bars_gives_nan() -> None:
    """UT-SCR-015.008.M25.T04: 5 closes with RSI 14 → NaN."""
    close = np.asarray([10.0, 11.0, 12.0, 11.0, 10.0])
    assert math.isnan(_ta.rsi(close, 14)[-1])
