"""Fixtures for market (MKT) tests: small hand-made candle files."""
from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

START = "2025-01-01"


def bdays(n: int, start: str = START) -> pd.DatetimeIndex:
    """Return ``n`` business days from ``start``."""
    return pd.bdate_range(start, periods=n)


def write_candles(
    path: Path, series: dict[str, Sequence[float]], start: str = START, volume: float = 1000.0
) -> None:
    """Write ``price_1d`` rows (high = close + 1%, low = close - 1%) for each symbol."""
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS price_1d (symbol TEXT, datetime TEXT, open REAL, "
        "high REAL, low REAL, close REAL, volume REAL)"
    )
    for sym, closes in series.items():
        days = bdays(len(closes), start)
        con.executemany(
            "INSERT INTO price_1d VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(sym, d.isoformat(), c, c * 1.01, c * 0.99, c, volume)
             for d, c in zip(days, closes, strict=True)],
        )
    con.commit()
    con.close()


@pytest.fixture
def candle_file(tmp_path: Path) -> Callable[[dict[str, Sequence[float]]], Path]:
    """Return a maker that writes a candles.db in tmp_path."""

    def make(series: dict[str, Sequence[float]]) -> Path:
        path = tmp_path / "candles.db"
        write_candles(path, series)
        return path

    return make


@pytest.fixture(scope="session")
def p5b_market(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A desk.db filled by the real P1-P3 steps on synthetic candles (read-only, shared)."""
    from datetime import UTC, datetime

    from tests.market.test_idea_step import N, _Earnings, _make, _steps
    from us_swing.core.desk_contract import StepContext

    root = tmp_path_factory.mktemp("p5b_market")
    candles, home = root / "candles.db", root / "desk"
    _make(candles)
    for step in _steps(candles, N, _Earnings()):
        step(StepContext(1, "manual", datetime.now(UTC), home))
    return candles, home


@pytest.fixture
def p5b(p5b_market: tuple[Path, Path], tmp_path: Path) -> Any:
    """A private copy of the shared P5b market data for one test."""
    from tests.market.p5b_support import copy_env

    return copy_env(p5b_market, tmp_path)
