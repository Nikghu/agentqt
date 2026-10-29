"""Tests for MD-BKT-002.004.M02 — backtest/universe.py."""
from __future__ import annotations

from us_swing.backtest.spec import UniverseSpec
from us_swing.backtest.universe import resolve
from tests.backtest.conftest import Record

_RECORDS = [
    Record("AAPL", "Information Technology"),
    Record("MSFT", "Information Technology"),
    Record("XOM", "Energy"),
    Record("CVX", "Energy"),
]


def test_each_mode_resolves() -> None:
    """UT-BKT-002.004.M02.T01: S&P 500, sector and names modes each resolve."""
    assert resolve(UniverseSpec(mode="sp500"), _RECORDS) == ["AAPL", "CVX", "MSFT", "XOM"]
    assert resolve(UniverseSpec(mode="sector", sectors=("Energy",)), _RECORDS) == [
        "CVX", "XOM",
    ]
    assert resolve(UniverseSpec(mode="names", names=("nvda", " amd ")), _RECORDS) == [
        "AMD", "NVDA",
    ]


def test_add_and_remove() -> None:
    """UT-BKT-002.004.M02.T02: Add joins, remove takes out, result sorted and unique."""
    spec = UniverseSpec(
        mode="sector", sectors=("Information Technology",),
        add=("PLTR", "pltr", "AAPL"), remove=("MSFT",),
    )

    assert resolve(spec, _RECORDS) == ["AAPL", "PLTR"]
