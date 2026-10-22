"""Shared helpers for core/indicator_rules tests."""
from __future__ import annotations

import random

import numpy as np

from us_swing.core.indicator_rules import BarArrays


def seeded_arrays(n: int = 120, seed: int = 7, trend: float = 0.0) -> BarArrays:
    """Deterministic random-walk OHLCV arrays (2% daily volatility)."""
    rng = random.Random(seed)
    closes = [100.0]
    for _ in range(n - 1):
        closes.append(max(closes[-1] * (1 + rng.gauss(trend, 0.02)), 1.0))
    close = np.asarray(closes, dtype=np.float64)
    volume = np.asarray([rng.uniform(1.4e6, 2.6e6) for _ in range(n)], dtype=np.float64)
    return BarArrays(close, close * 1.01, close * 0.99, close, volume)


def arrays_from_close(close: list[float]) -> BarArrays:
    """Arrays whose high/low/open equal the given closes; constant volume."""
    c = np.asarray(close, dtype=np.float64)
    return BarArrays(c, c, c, c, np.full(len(c), 1e6))
