"""
Module: MD-MKT-002.009.M05 — market/sector_step.py
Parent SRD: SRD-MKT-002.009

Desk step "Sectors": adds every new day of sector strength, rotation and stock RS.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.market.candles import BENCHMARK, CANDLE_DB, CandleReader, member_sectors
from us_swing.market.rs import rs_scores, rs_table
from us_swing.market.sectors import sector_lines, sector_table
from us_swing.market.step import MIN_COVERAGE, RECOMPUTE_DAYS
from us_swing.market.store import MarketStore, SectorRow, StockRsRow

log = logging.getLogger(__name__)

_READY_COLUMNS = ["rs_ratio", "rs_momentum", "rel_6m"]


def _num(value: object) -> float | None:
    out = float(value)  # type: ignore[arg-type]
    return None if math.isnan(out) else out


def _int(value: object) -> int | None:
    out = _num(value)
    return None if out is None else int(out)


def _per_day(values: pd.Series) -> dict[Any, int]:
    return {k: int(v) for k, v in zip(values.index, values.to_numpy(), strict=True)}


class SectorStep:
    """Computes and stores sector strength, rotation and stock RS for every new candle day."""

    name = "Sectors"

    def __init__(
        self,
        candles: Path = CANDLE_DB,
        universe: Callable[[], list[tuple[str, str, str]]] | None = None,
    ) -> None:
        """Set the data sources; both are injectable for tests."""
        self._candles = candles
        self._universe = universe

    def __call__(self, ctx: StepContext) -> None:
        """Run the step inside a desk run."""
        store = MarketStore(ctx.home or desk_home())
        try:
            added = self._add_days(store)
        finally:
            store.close()
        log.info("[Sectors] %d day(s) added", added)

    def _add_days(self, store: MarketStore) -> int:
        try:
            reader = CandleReader(self._candles)
        except FileNotFoundError:
            log.warning("[Sectors] No candle file yet; open the app to download candles")
            return 0
        members = member_sectors(reader.symbols(), self._universe)
        if not members.sectors:
            log.warning("[Sectors] No S&P 500 stocks with a sector and candles; nothing computed")
            return 0
        bars = reader.read([*members.sectors, BENCHMARK])
        if BENCHMARK not in bars.closes.columns:
            log.warning("[Sectors] SPY has no daily candles; nothing computed")
            return 0
        spy = bars.closes[BENCHMARK].dropna()
        cols = [s for s in members.sectors if s in bars.closes.columns]
        closes = bars.closes[cols].reindex(spy.index)
        sector_of = {s: members.sectors[s] for s in cols}
        lines, counts = sector_lines(closes, sector_of)
        sectors = sector_table(lines, spy)
        stocks = rs_table(rs_scores(closes), sector_of)
        days = self._days_to_write(store, sectors, stocks)
        if not days:
            return 0
        coverage = _per_day(closes.notna().sum(axis=1))
        return self._write(store, days, sectors, counts, stocks, coverage, members.listed)

    @staticmethod
    def _days_to_write(
        store: MarketStore, sectors: pd.DataFrame, stocks: pd.DataFrame
    ) -> list[pd.Timestamp]:
        ready = set(sectors.dropna(subset=_READY_COLUMNS).index.get_level_values("date"))
        ready &= set(stocks.index.get_level_values("date"))
        stored = store.stored_sector_dates()
        redo_from = (date.fromisoformat(max(stored)) - timedelta(days=RECOMPUTE_DAYS)
                     if stored else None)
        return sorted(
            ts for ts in ready
            if redo_from is None or ts.date().isoformat() not in stored or ts.date() > redo_from
        )

    def _write(
        self, store: MarketStore, days: list[pd.Timestamp], sectors: pd.DataFrame,
        counts: pd.DataFrame, stocks: pd.DataFrame, coverage: dict[pd.Timestamp, int],
        listed: int,
    ) -> int:
        written: list[pd.Timestamp] = []
        for ts in days:
            if coverage[ts] < MIN_COVERAGE * listed:
                log.info("[Sectors] %s skipped: data for %d of %d stocks",
                         ts.date().isoformat(), coverage[ts], listed)
                continue
            written.append(ts)
        stacked = pd.Series(counts.stack(), dtype=int)
        members: dict[Any, int] = dict(zip(stacked.index, stacked.tolist(), strict=True))
        sec = sectors[sectors.index.get_level_values("date").isin(written)].reset_index()
        sec = sec[["date", "sector", "line", "rel_1m", "rel_3m", "rel_6m", "rank", "rs_ratio",
                   "rs_momentum", "quadrant"]]
        sector_rows = [
            SectorRow(ts.date().isoformat(), str(sector), float(line), _num(r1), _num(r3),
                      _num(r6), _int(rank), _num(ratio), _num(mom), quad,
                      members.get((ts, sector), 0))
            for ts, sector, line, r1, r3, r6, rank, ratio, mom, quad
            in sec.itertuples(index=False, name=None)
        ]
        stk = stocks[stocks.index.get_level_values("date").isin(written)].reset_index()
        stk = stk[["date", "symbol", "sector", "score", "rs_rating", "sector_rank",
                   "sector_size"]]
        stock_rows = [
            StockRsRow(ts.date().isoformat(), str(sym), str(sector), float(score), int(rating),
                       int(rank), int(size))
            for ts, sym, sector, score, rating, rank, size
            in stk.itertuples(index=False, name=None)
        ]
        store.write_sector_days(sector_rows, stock_rows)
        if written:
            _log_latest(sectors, written[-1])
        return len(written)


def _log_latest(sectors: pd.DataFrame, last: pd.Timestamp) -> None:
    today = pd.DataFrame(sectors.xs(last, level="date"))
    top = today.dropna(subset=["rank"]).sort_values("rank").index[:3]
    log.info("[Sectors] Latest %s: top sectors %s", last.date().isoformat(), ", ".join(top))
    dates = sectors.index.get_level_values("date").unique().sort_values()
    before = dates[dates < last]
    if before.empty:
        return
    prev = sectors.xs(before[-1], level="date")["quadrant"]
    for sector, quad in today["quadrant"].items():
        old = prev.get(sector)
        if quad and old and quad != old:
            log.info("[Sectors] %s moved from %s to %s", sector, old, quad)
