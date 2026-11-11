"""
Module: MD-MKT-009.001.M01 — market/pick_results.py
Parent SRD: SRD-MKT-009.001
Also: SRD-MKT-009.002 (entry), SRD-MKT-009.003 (exit and R), SRD-MKT-009.008 (log line),
SRD-DSK-009.002 and .007 (daily lesson review after the results are written)

Desk step "Pick results": the paper result of every lead pick from daily candles, whether
the Master approved, rejected or let it expire. No AI call. Entry is the trigger and exits
are the stop or target price; daily bars have no open, so gaps are not modelled.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.core.desk_lessons import review_lessons
from us_swing.core.desk_trades import pick_target
from us_swing.market.candles import CANDLE_DB, CandleReader
from us_swing.market.store import MarketStore, PickResultRow

log = logging.getLogger(__name__)

ENTRY_DAYS = 5
HOLD_DAYS = 10


@dataclass(frozen=True)
class Bar:
    """One daily bar of one stock."""

    day: str
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class PaperResult:
    """How one pick turned out on paper."""

    status: str
    entry_day: str | None = None
    entry: float | None = None
    exit_day: str | None = None
    exit: float | None = None
    r: float | None = None


def _r(side: str, entry: float, stop: float, exit_: float) -> float:
    risk = entry - stop if side == "long" else stop - entry
    gain = exit_ - entry if side == "long" else entry - exit_
    return round(gain / risk, 2)


def _levels_ok(side: str, trigger: float, stop: float, target: float) -> bool:
    if side == "long":
        return stop < trigger < target
    return side == "short" and target < trigger < stop


def paper_result(side: str, trigger: float, stop: float, target: float,
                 bars: Sequence[Bar]) -> PaperResult | None:
    """Paper result of a pick from the bars after its data day, oldest first.

    Returns ``None`` when the levels do not fit the side.
    """
    if not _levels_ok(side, trigger, stop, target):
        return None
    long = side == "long"
    start = next((i for i, b in enumerate(bars[:ENTRY_DAYS])
                  if (b.high >= trigger if long else b.low <= trigger)), None)
    if start is None:
        return PaperResult("no_fill" if len(bars) >= ENTRY_DAYS else "open")
    day0 = bars[start].day
    held = bars[start:start + HOLD_DAYS]
    for bar in held:
        hit_stop = bar.low <= stop if long else bar.high >= stop
        hit_target = bar.high >= target if long else bar.low <= target
        if hit_stop or hit_target:
            exit_ = stop if hit_stop else target
            return PaperResult("stop" if hit_stop else "target", day0, trigger, bar.day, exit_,
                               _r(side, trigger, stop, exit_))
    last = held[-1]
    if len(held) == HOLD_DAYS:
        return PaperResult("time", day0, trigger, last.day, last.close,
                           _r(side, trigger, stop, last.close))
    return PaperResult("open", day0, trigger, None, last.close, _r(side, trigger, stop, last.close))


def _bars_after(highs: pd.Series, lows: pd.Series, closes: pd.Series, day: str) -> list[Bar]:
    out: list[Bar] = []
    for when, close in closes.items():
        d = pd.Timestamp(str(when)).date().isoformat()
        hi, lo = highs.get(when), lows.get(when)
        if d <= day or any(v is None or (isinstance(v, float) and math.isnan(v))
                           for v in (hi, lo, close)):
            continue
        out.append(Bar(d, float(hi), float(lo), float(close)))  # type: ignore[arg-type]
    return out


class PickResultsStep:
    """Works out the paper result of every lead pick on each desk run."""

    name = "Pick results"

    def __init__(self, candles: Path = CANDLE_DB) -> None:
        """Set the candle file; injectable for tests."""
        self._candles = candles

    def __call__(self, ctx: StepContext) -> None:
        """Run the step inside a desk run, then check the lessons against the results."""
        home = ctx.home or desk_home()
        self._results(home)
        try:
            review_lessons(home, ctx.started_at)
        except Exception:  # noqa: BLE001 — a lesson check must never fail the run
            log.exception("[Memory] Could not check the lessons")

    def _results(self, home: Path) -> None:
        store = MarketStore(home)
        try:
            picks = store.read_frame(
                "SELECT l.date, l.side, l.symbol, i.trigger, i.stop FROM lead_picks l "
                "JOIN ideas i ON i.date = l.date AND i.side = l.side AND i.symbol = l.symbol")
            if picks.empty:
                log.info("[Results] No lead picks yet")
                return
            try:
                bars = CandleReader(self._candles, home).read(picks["symbol"].unique())
            except FileNotFoundError:
                log.warning("[Results] No candle file yet; open the app to download candles")
                return
            r_mult = load_settings(home).trade_target_r
            rows = []
            for d, side, sym, trigger, stop in picks.itertuples(index=False):
                if trigger is None or stop is None or sym not in bars.closes.columns:
                    continue
                target = pick_target(side, float(trigger), float(stop), r_mult)
                if target is None:
                    continue
                res = paper_result(side, float(trigger), float(stop), target, _bars_after(
                    bars.highs[sym], bars.lows[sym], bars.closes[sym], str(d)))
                if res is not None:
                    rows.append(PickResultRow(str(d), side, sym, res.status, res.entry_day,
                                              res.entry, res.exit_day, res.exit, res.r))
            store.replace_pick_results(rows)
        finally:
            store.close()
        log.info("[Results] %d pick(s) worked out, %d still open", len(rows),
                 sum(1 for r in rows if r.status == "open"))
