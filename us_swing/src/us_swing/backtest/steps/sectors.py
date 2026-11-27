"""
Module: MD-BKT-002.093.M16 — backtest/steps/sectors.py
Parent SRD: SRD-BKT-002.093

Leading sectors for Step 3: each session ranks the 11 sector ETFs against RSP
over the chosen range on closes up to the previous trading day (same formula
as core/stock_context sector_moves). Longs may enter the top N sectors, shorts
the bottom N; with "must beat RSP" only sectors above (longs) or below
(shorts) RSP count.
"""
from __future__ import annotations

from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd

from us_swing.backtest.spec import SectorFilterSpec
from us_swing.core.stock_context import (
    GICS_TO_ETF,
    RANGE_DAYS,
    SECTOR_BENCHMARK,
    SECTOR_ETFS,
    SECTOR_SYMBOLS,
)

ETF_TO_GICS = {etf: gics for gics, etf in GICS_TO_ETF.items()}


@dataclass(frozen=True, slots=True)
class SectorGate:
    """GICS sectors open for long and short entries on one session."""

    longs: frozenset[str]
    shorts: frozenset[str]


def missing_symbols(has_data: Mapping[str, bool]) -> list[str]:
    """RSP and sector ETFs with no saved daily data (SRD-BKT-002.095)."""
    return [sym for sym in SECTOR_SYMBOLS if not has_data.get(sym, False)]


def sector_gates(closes: Mapping[str, pd.Series], days: Sequence[date],
                 spec: SectorFilterSpec) -> dict[date, SectorGate]:
    """Open sectors per session; a session with no ranking is left out (all allowed).

    Args:
        closes: Daily closes per symbol, indexed by date, for RSP and the sector ETFs.
        days: Sessions of the run.
        spec: Top N, range and the RSP rule.
    """
    bench = closes.get(SECTOR_BENCHMARK)
    if bench is None or bench.empty:
        return {}
    span = RANGE_DAYS[spec.range]
    frame = pd.DataFrame({sym: closes[sym] for sym, _name in SECTOR_ETFS if sym in closes})
    frame = frame.reindex(bench.index)
    bench_dates = list(bench.index)
    gates: dict[date, SectorGate] = {}
    for day in days:
        end_i = bisect_left(bench_dates, day) - 1
        if end_i < span:
            continue
        start, end = bench_dates[end_i - span], bench_dates[end_i]
        bench_move = bench[end] / bench[start] - 1
        moves = ((frame.loc[end] / frame.loc[start] - 1 - bench_move) * 100).dropna()
        if moves.empty:
            continue
        ranked = moves.sort_values(ascending=False, kind="stable")
        top = ranked[ranked > 0] if spec.beat_benchmark else ranked
        bottom = ranked[ranked < 0] if spec.beat_benchmark else ranked
        gates[day] = SectorGate(
            frozenset(ETF_TO_GICS[s] for s in top.index[:spec.top_n]),
            frozenset(ETF_TO_GICS[s] for s in bottom.index[::-1][:spec.top_n]),
        )
    return gates

