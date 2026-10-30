"""Shared fixtures for backtest engine tests (FO-BKT-002)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from us_swing.backtest.spec import Period, RunPlan, ScreenerSpec, UniverseSpec
from us_swing.backtest.store import BacktestStore

LATE = datetime(2030, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Record:
    symbol: str
    sector: str
    market_cap: float | None = None


def daily_bars(start: str, days: int, seed: int, base: float = 50.0) -> pd.DataFrame:
    """Random-walk 1d bars on business days; price above $5, volume 2 M."""
    rng = np.random.default_rng(seed)
    close = base + np.cumsum(rng.normal(0, 1, days))
    close = np.maximum(close, 10.0)
    return pd.DataFrame({
        "ts": pd.bdate_range(start, periods=days),
        "open": close, "high": close + 1, "low": close - 1, "close": close,
        "volume": [2_000_000.0] * days,
    })


def intraday_bars(days: list[str], seed: int, base: float = 50.0) -> pd.DataFrame:
    """130 random-walk 3m bars per session, 09:30–15:57 US/Eastern, as UTC."""
    rng = np.random.default_rng(seed)
    stamps = pd.DatetimeIndex([
        ts for day in days
        for ts in pd.date_range(f"{day} 09:30", periods=130, freq="3min", tz="America/New_York")
    ]).tz_convert("UTC")
    close = np.maximum(base + np.cumsum(rng.normal(0, 0.2, len(stamps))), 10.0)
    return pd.DataFrame({
        "ts": stamps, "open": close - 0.1, "high": close + 0.3, "low": close - 0.3,
        "close": close, "volume": rng.integers(1_000, 5_000, len(stamps)).astype(float),
    })


def rsi_preset(low: float = 50.0, high: float = 100.0, timeframe: str = "1d") -> dict[str, Any]:
    """Weighted preset with one RSI rule; passes when RSI(14) is within [low, high]."""
    return {
        "id": "p1", "name": "RSI", "preset_type": "weighted", "groups": [],
        "screeners": [{
            "screener_id": "indicator_composite", "enabled": True, "weight": 1.0,
            "config": {"schema": 2, "rules": [
                {"indicator_id": "rsi", "condition": "between", "value": low, "to": high},
            ]},
        }],
        "threshold": 1.0, "timeframe": timeframe, "enable_llm_ranking": False, "top_n": 0,
    }


def plan_for(start: date, end: date, names: tuple[str, ...], **screener: Any) -> RunPlan:
    return RunPlan(
        name="t", period=Period(start, end),
        universe=UniverseSpec(mode="names", names=names),
        screener=ScreenerSpec(preset_id="p1", **screener),
    )


@pytest.fixture()
def store(tmp_path: Path) -> BacktestStore:
    """Store with AAPL, MSFT, NVDA 1d bars from 2025-01-01 (60 business days)."""
    st = BacktestStore(tmp_path / "store")
    for seed, sym in enumerate(("AAPL", "MSFT", "NVDA")):
        st.save(sym, "1d", daily_bars("2025-01-01", 60, seed), LATE)
    return st
