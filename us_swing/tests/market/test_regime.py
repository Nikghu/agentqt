"""Tests for MD-MKT-001.002.M02 — market/regime.py."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.market.conftest import bdays
from us_swing.market.regime import breadth_frame, fear_reading, regime_series, volatility_series


def _series(values: np.ndarray) -> pd.Series:
    return pd.Series(values, index=bdays(len(values)))


def test_uptrend() -> None:
    """UT-MKT-001.002.M02.T01: Uptrend."""
    assert regime_series(_series(np.linspace(100, 200, 260))).iloc[-1] == "Uptrend"


def test_downtrend() -> None:
    """UT-MKT-001.002.M02.T02: Downtrend."""
    assert regime_series(_series(np.linspace(200, 100, 260))).iloc[-1] == "Downtrend"


def test_choppy_and_too_short() -> None:
    """UT-MKT-001.002.M02.T03: Choppy and too short."""
    zigzag = _series(np.array([100.0 + (i % 2) * 2 for i in range(260)]))
    assert regime_series(zigzag).iloc[-1] == "Choppy"
    short = regime_series(_series(np.linspace(100, 200, 150)))
    assert short.isna().all()


def _noise(n: int, scale: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(0, scale, n)))


def test_high_volatility() -> None:
    """UT-MKT-001.003.M02.T01: High volatility."""
    calm = _noise(300, 0.002, 1)
    wild = calm[-1] * np.exp(np.cumsum(np.random.default_rng(2).normal(0, 0.04, 20)))
    out = volatility_series(_series(np.concatenate([calm, wild])))
    assert out["volatility"].iloc[-1] == "High"
    assert out["vol_pct"].iloc[-1] > 70


def test_calm_volatility() -> None:
    """UT-MKT-001.003.M02.T02: Calm volatility."""
    wild = _noise(300, 0.03, 3)
    calm = wild[-1] * np.exp(np.cumsum(np.random.default_rng(4).normal(0, 0.001, 20)))
    out = volatility_series(_series(np.concatenate([wild, calm])))
    assert out["volatility"].iloc[-1] == "Calm"


def _wide(cols: dict[str, np.ndarray]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = max(len(v) for v in cols.values())
    idx = bdays(n)
    closes = pd.DataFrame(
        {k: pd.Series(v, index=idx[n - len(v):]) for k, v in cols.items()}, index=idx
    )
    return closes, closes * 1.01, closes * 0.99


def test_breadth_counts() -> None:
    """UT-MKT-001.004.M02.T01: Breadth counts."""
    closes, highs, lows = _wide({"UP": np.linspace(100, 200, 260),
                                 "DOWN": np.linspace(200, 100, 260)})
    last = breadth_frame(closes, highs, lows).iloc[-1]
    assert last["members"] == 2
    assert last["pct_above_20"] == last["pct_above_50"] == last["pct_above_200"] == 50
    assert (last["new_highs"], last["new_lows"]) == (1, 1)
    assert (last["advancers"], last["decliners"]) == (1, 1)


def test_short_history_member() -> None:
    """UT-MKT-001.004.M02.T02: Short history member."""
    closes, highs, lows = _wide({"UP": np.linspace(100, 200, 260),
                                 "DOWN": np.linspace(200, 100, 260),
                                 "NEW": np.linspace(50, 60, 30)})
    last = breadth_frame(closes, highs, lows).iloc[-1]
    assert last["pct_above_20"] == pytest.approx(200 / 3)
    assert last["pct_above_50"] == 50


def test_fear_points() -> None:
    """UT-MKT-001.006.M02.T01: Fear points."""
    fear = fear_reading(32.0, 25.0, "High", 35.0)
    assert (fear.score, fear.label, fear.note) == (6, "Fearful", "")


def test_fear_without_vix() -> None:
    """UT-MKT-001.006.M02.T02: No VIX."""
    fear = fear_reading(None, None, "Normal", 60.0)
    assert (fear.score, fear.label, fear.note) == (0, "Calm", "no VIX")
