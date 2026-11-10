"""
Module: MD-MKT-001.011.M05 — market/step.py
Parent SRD: SRD-MKT-001.011

Also: SRD-DSK-003.005 (posts ``regime_change`` when the latest regime differs)

Desk step "Market regime": adds every new day of regime, volatility, breadth and fear.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.core.desk_events import post_event
from us_swing.market.candles import BENCHMARK, CANDLE_DB, CandleReader, member_symbols
from us_swing.market.regime import (
    averages,
    breadth_frame,
    fear_reading,
    regime_series,
    volatility_series,
)
from us_swing.market.store import BreadthRow, MarketStore, RegimeRow
from us_swing.market.vix import fetch_vix

log = logging.getLogger(__name__)

MIN_COVERAGE = 0.8
RECOMPUTE_DAYS = 7
VIX_FIRST_DAY = date(2023, 1, 1)
_ET_OFFSET = timedelta(hours=-5)
NY = ZoneInfo("America/New_York")


def _weekdays_after(first: date, last: date) -> int:
    """Count weekdays in (first, last]."""
    return int(np.busday_count(first + timedelta(days=1), last + timedelta(days=1)))


def _num(value: object) -> float | None:
    if value is None:
        return None
    out = float(value)  # type: ignore[arg-type]
    return None if math.isnan(out) else out


def _regime_change(store: MarketStore) -> tuple[str, str] | None:
    """``(day, "Choppy to Uptrend")`` when the latest regime differs from the day before."""
    rows = store.read_frame("SELECT date, regime FROM regime_snapshot ORDER BY date DESC "
                            "LIMIT 2")
    if len(rows) < 2 or rows["regime"].iloc[0] == rows["regime"].iloc[1]:
        return None
    return str(rows["date"].iloc[0]), f"{rows['regime'].iloc[1]} to {rows['regime'].iloc[0]}"


class RegimeStep:
    """Computes and stores market regime, breadth and fear for every new candle day."""

    name = "Market regime"

    def __init__(
        self,
        candles: Path = CANDLE_DB,
        vix_fetch: Callable[[date], pd.DataFrame] = fetch_vix,
        universe: Callable[[], list[tuple[str, str]]] | None = None,
        today: Callable[[], date] | None = None,
    ) -> None:
        """Set the data sources; all are injectable for tests."""
        self._candles = candles
        self._vix_fetch = vix_fetch
        self._universe = universe
        self._today = today or (lambda: (datetime.now(UTC) + _ET_OFFSET).date())

    def __call__(self, ctx: StepContext) -> None:
        """Run the step inside a desk run."""
        home = ctx.home or desk_home()
        store = MarketStore(home)
        try:
            self._update_vix(store)
            added = self._add_days(store)
            change = _regime_change(store)
        finally:
            store.close()
        log.info("[Regime] %d day(s) added", added)
        if change and post_event(home, "regime_change", change[0], datetime.now(NY)):
            log.info("[Regime] Regime changed on %s: %s", change[0], change[1])

    def _update_vix(self, store: MarketStore) -> None:
        last = store.last_date("vix_daily")
        start = last - timedelta(days=RECOMPUTE_DAYS) if last else VIX_FIRST_DAY
        if start > self._today():
            return
        frame = self._vix_fetch(start)
        if not frame.empty:
            store.write_vix(frame)

    def _add_days(self, store: MarketStore) -> int:
        try:
            reader = CandleReader(self._candles, store.home)
        except FileNotFoundError:
            log.warning("[Regime] No candle file yet; open the app to download candles")
            return 0
        members = member_symbols(reader.symbols(), self._universe)
        bars = reader.read([*members.symbols, BENCHMARK])
        if BENCHMARK not in bars.closes.columns:
            log.warning("[Regime] SPY has no daily candles; nothing computed")
            return 0
        spy = bars.closes[BENCHMARK].dropna()
        table = pd.concat(
            [regime_series(spy).rename("regime"), volatility_series(spy), averages(spy),
             spy.rename("spy_close")],
            axis=1,
        )
        cols = [m for m in members.symbols if m in bars.closes.columns]
        days = spy.index
        breadth = breadth_frame(bars.closes[cols].reindex(days), bars.highs[cols].reindex(days),
                                bars.lows[cols].reindex(days))
        ready = table.dropna(subset=["regime", "volatility", "sma200"])
        stored = store.stored_dates()
        if stored:
            redo_from = date.fromisoformat(max(stored)) - timedelta(days=RECOMPUTE_DAYS)
            ready = ready[[ts.date().isoformat() not in stored or ts.date() > redo_from
                           for ts in pd.DatetimeIndex(ready.index)]]
        if ready.empty:
            return 0
        data_day = pd.Timestamp(spy.index[-1]).date()
        return self._write(store, ready, breadth, members.listed, data_day, members.note)

    def _write(
        self, store: MarketStore, ready: pd.DataFrame, breadth: pd.DataFrame,
        member_count: int, data_day: date, members_note: str,
    ) -> int:
        vix = store.vix_by_date()
        stale = _weekdays_after(data_day, self._today()) > 1
        stamp = datetime.now(UTC).isoformat()
        regimes: list[RegimeRow] = []
        breadths: list[BreadthRow] = []
        for ts in pd.DatetimeIndex(ready.index):
            day = ts.date().isoformat()
            r = ready.loc[ts]
            b = breadth.loc[ts]
            if b["members"] < MIN_COVERAGE * member_count:
                log.info("[Regime] %s skipped: data for %d of %d stocks", day,
                         int(b["members"]), member_count)
                continue
            v, v3 = vix.get(day, (None, None))
            fear = fear_reading(v, v3, str(r["volatility"]), _num(b["pct_above_50"]))
            notes = [n for n in (fear.note, members_note) if n]
            if stale and ts.date() == data_day:
                notes.append("candles stale")
            regimes.append(RegimeRow(
                day, str(r["regime"]), str(r["volatility"]), float(r["vol20"]),
                float(r["vol_pct"]), float(r["spy_close"]), float(r["sma50"]),
                float(r["sma200"]), v, v3, fear.label, fear.score, "; ".join(notes), stamp,
            ))
            breadths.append(BreadthRow(
                day, int(b["members"]), _num(b["pct_above_20"]), _num(b["pct_above_50"]),
                _num(b["pct_above_200"]), int(b["new_highs"]), int(b["new_lows"]),
                int(b["advancers"]), int(b["decliners"]),
            ))
        store.write_days(regimes, breadths)
        if regimes:
            top = regimes[-1]
            log.info("[Regime] Latest %s: %s, volatility %s, fear %s%s", top.date, top.regime,
                     top.volatility, top.fear, f" ({top.note})" if top.note else "")
        if stale:
            log.warning("[Regime] Candles end on %s; open the app to update them", data_day)
        return len(regimes)
