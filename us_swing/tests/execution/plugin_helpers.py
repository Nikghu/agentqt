"""Shared helpers for the FO-EXE-022 indicator plugin tests."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PLUGIN_FILES = Path(__file__).parent / "plugin_files"
SWING_PLUS = PLUGIN_FILES / "swing_plus.py"

_MINUTES = {"3m": 3, "15m": 15, "30m": 30}


def frame(n: int, tf: str = "3m", seed: int = 1, start: str = "2026-11-02 14:30") -> pd.DataFrame:
    """``n`` made-up closed candles in the engine's frame shape (``ts`` + OHLCV)."""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    step = pd.Timedelta(days=1) if tf == "1d" else pd.Timedelta(minutes=_MINUTES[tf])
    ts = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=n, freq=step)
    return pd.DataFrame({"ts": ts, "open": close, "high": high, "low": low, "close": close,
                         "volume": rng.integers(1_000, 5_000, n).astype(float)})


def frames(n: int = 120, seed: int = 1) -> dict[str, pd.DataFrame]:
    """3m, 15m, 30m and 1d frames for one stock."""
    return {tf: frame(n, tf, seed) for tf in ("3m", "15m", "30m", "1d")}


def write_plugin(folder: Path, name: str, body: str) -> Path:
    """Write an indicator file built from the SWING_PLUS example with ``body`` changes."""
    path = folder / name
    path.write_text(body, encoding="utf-8")
    return path


def swing_plus_source(*swaps: tuple[str, str]) -> str:
    """The SWING_PLUS example text with each ``(old, new)`` swap applied."""
    text = SWING_PLUS.read_text(encoding="utf-8")
    for old, new in swaps:
        assert old in text, old
        text = text.replace(old, new)
    return text
