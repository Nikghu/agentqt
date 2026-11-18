"""
Module: MD-SCR-018.004.M35 — core/stock_context/_sector.py
Parent SRD: SRD-SCR-018.004, SRD-GUI-025.022

Sector ETF list, sector moves against the equal-weight S&P 500 (RSP), and the
GICS sector → ETF map. Moved from gui/sector_rotation.py so the screener can use it.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

SECTOR_BENCHMARK = "RSP"
SECTOR_ETFS: tuple[tuple[str, str], ...] = (
    ("XLK", "Technology"),
    ("XLF", "Financials"),
    ("XLE", "Energy"),
    ("XLV", "Health Care"),
    ("XLY", "Consumer Discretionary"),
    ("XLP", "Consumer Staples"),
    ("XLI", "Industrials"),
    ("XLB", "Materials"),
    ("XLU", "Utilities"),
    ("XLRE", "Real Estate"),
    ("XLC", "Communication"),
)
SECTOR_SYMBOLS: tuple[str, ...] = (SECTOR_BENCHMARK, *(sym for sym, _name in SECTOR_ETFS))
RANGE_DAYS: dict[str, int] = {"1W": 5, "1M": 21, "3M": 63}
GICS_TO_ETF: dict[str, str] = {
    "Information Technology": "XLK",
    "Financials": "XLF",
    "Energy": "XLE",
    "Health Care": "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}



@dataclass(frozen=True, slots=True)
class SectorMove:
    """One sector's move over the range, minus the RSP move, in percent."""

    symbol: str
    name: str
    relative_pct: float


def sector_moves(
    closes: Mapping[str, Mapping[str, float]], days: int
) -> tuple[list[SectorMove], str]:
    """Sector moves against RSP over the last ``days`` RSP trading days, strongest first.

    Args:
        closes: Daily closes per symbol, keyed by ISO date (``YYYY-MM-DD``).
        days: Number of trading days back from RSP's last close.

    Returns:
        The ranked moves and RSP's last close date; ``([], "")`` when RSP has too few
        closes. A sector without a close on both the start and end day is left out.
    """
    bench = closes.get(SECTOR_BENCHMARK, {})
    dates = sorted(bench)
    if len(dates) <= days:
        return [], ""
    start, end = dates[-1 - days], dates[-1]
    bench_move = bench[end] / bench[start] - 1
    moves = []
    for symbol, name in SECTOR_ETFS:
        sector = closes.get(symbol, {})
        if sector.get(start) and end in sector:
            relative = (sector[end] / sector[start] - 1 - bench_move) * 100
            moves.append(SectorMove(symbol, name, relative))
    moves.sort(key=lambda move: move.relative_pct, reverse=True)
    return moves, end
