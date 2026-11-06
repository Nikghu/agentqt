"""
Module: MD-MKT-003.011.M07 — market/idea_step.py
Parent SRD: SRD-MKT-003.011

Desk step "Ideas": scores every stock long and short and saves the daily idea and
Watch lists with their reasons.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.market.candles import BENCHMARK, CANDLE_DB, CandleReader, member_sectors
from us_swing.market.earnings import next_earnings
from us_swing.market.score import SIDES, Idea, MarketInputs, pick_ideas, score_frame
from us_swing.market.setups import Bars
from us_swing.market.step import MIN_COVERAGE, RECOMPUTE_DAYS
from us_swing.market.store import IdeaRow, MarketStore, ReasonRow, ScoreRow

log = logging.getLogger(__name__)

EARNINGS_CHECKED = 30
_SCORE_COLUMNS = ["score", "rs_part", "flow_part", "setup_part", "sector_part", "regime_part",
                  "penalty", "setup", "trigger", "stop"]


def _wide(frame: pd.DataFrame, column: str, key: str) -> pd.DataFrame:
    out = frame.pivot(index="date", columns=key, values=column)
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index))
    return out


def _num(value: object) -> float | None:
    out = float(value)  # type: ignore[arg-type]
    return None if out != out else out


class IdeaStep:
    """Computes and stores readiness scores and ideas for every new candle day."""

    name = "Ideas"

    def __init__(
        self,
        candles: Path = CANDLE_DB,
        universe: Callable[[], list[tuple[str, str, str]]] | None = None,
        earnings: Callable[[Iterable[str]], dict[str, date | None]] = next_earnings,
    ) -> None:
        """Set the data sources; all are injectable for tests."""
        self._candles = candles
        self._universe = universe
        self._earnings = earnings

    def __call__(self, ctx: StepContext) -> None:
        """Run the step inside a desk run."""
        store = MarketStore(ctx.home or desk_home())
        try:
            added = self._add_days(store)
        finally:
            store.close()
        log.info("[Ideas] %d day(s) added", added)

    def _inputs(self, store: MarketStore) -> tuple[MarketInputs, int] | None:
        try:
            reader = CandleReader(self._candles)
        except FileNotFoundError:
            log.warning("[Ideas] No candle file yet; open the app to download candles")
            return None
        members = member_sectors(reader.symbols(), self._universe)
        regime = store.read_frame("SELECT date, regime FROM regime_snapshot")
        sectors = store.read_frame("SELECT date, sector, quadrant, rank FROM sector_daily")
        ratings = store.read_frame("SELECT date, symbol, rs_rating FROM stock_rs")
        if regime.empty or sectors.empty or ratings.empty or not members.sectors:
            log.warning("[Ideas] No regime, sector or stock rating rows yet; nothing computed")
            return None
        bars = reader.read([*members.sectors, BENCHMARK])
        if BENCHMARK not in bars.closes.columns:
            log.warning("[Ideas] SPY has no daily candles; nothing computed")
            return None
        spy = bars.closes[BENCHMARK].dropna()
        cols = [s for s in members.sectors if s in bars.closes.columns]

        def align(frame: pd.DataFrame) -> pd.DataFrame:
            return frame[cols].reindex(spy.index)

        regime_by_day = pd.Series(regime["regime"].to_numpy(),
                                  index=pd.DatetimeIndex(pd.to_datetime(regime["date"])))
        return MarketInputs(
            Bars(align(bars.closes), align(bars.highs), align(bars.lows), align(bars.volumes)),
            spy, _wide(ratings, "rs_rating", "symbol"), {s: members.sectors[s] for s in cols},
            _wide(sectors, "quadrant", "sector"), _wide(sectors, "rank", "sector"),
            regime_by_day,
        ), members.listed

    def _add_days(self, store: MarketStore) -> int:
        found = self._inputs(store)
        if found is None:
            return 0
        inp, listed = found
        days = self._days_to_write(store, inp, listed)
        if not days:
            return 0
        table = score_frame(inp, days)
        scored = table.index.get_level_values("date")
        last = scored.max() if len(scored) else None
        earnings = self._check_earnings(table, last) if last is not None else {}
        scores: list[ScoreRow] = []
        ideas: list[IdeaRow] = []
        reasons: list[ReasonRow] = []
        latest: list[Idea] = []
        for (ts, side), group in table.groupby(level=["date", "side"], sort=True):
            day = pd.Timestamp(str(ts)).date()
            iso = day.isoformat()
            rows = group.droplevel(["date", "side"])
            scores.extend(_score_rows(iso, str(side), rows))
            picked = pick_ideas(rows, str(side), day, earnings if ts == last else None)
            for idea in picked:
                ideas.append(IdeaRow(iso, idea.side, idea.symbol, idea.status, idea.rank,
                                     idea.score, idea.sector, idea.setup, _num(idea.trigger),
                                     _num(idea.stop)))
                reasons.extend(ReasonRow(iso, idea.side, idea.symbol, i, text)
                               for i, text in enumerate(idea.reasons, start=1))
            if ts == last:
                latest.extend(picked)
        store.write_idea_days([d.date().isoformat() for d in days], scores, ideas, reasons)
        if last is not None:
            _log_latest(pd.Timestamp(last).date(), latest)
        return len(days)

    @staticmethod
    def _days_to_write(store: MarketStore, inp: MarketInputs, listed: int) -> list[pd.Timestamp]:
        index = inp.bars.closes.index
        ready = (set(index) & set(inp.regime.index) & set(inp.quadrant.index)
                 & set(inp.ratings.index))
        stored = store.stored_idea_dates()
        redo_from = (date.fromisoformat(max(stored)) - timedelta(days=RECOMPUTE_DAYS)
                     if stored else None)
        coverage = inp.bars.closes.notna().sum(axis=1)
        out: list[pd.Timestamp] = []
        for ts in sorted(ready):
            iso = ts.date().isoformat()
            if redo_from is not None and iso in stored and ts.date() <= redo_from:
                continue
            have = int(coverage.loc[ts])
            if have < MIN_COVERAGE * listed:
                log.info("[Ideas] %s skipped: data for %d of %d stocks", iso, have, listed)
                continue
            out.append(ts)
        return out

    def _check_earnings(self, table: pd.DataFrame, last: pd.Timestamp) -> dict[str, date | None]:
        today = table.xs(last, level="date")
        names: list[str] = []
        for side in SIDES:
            if side in today.index.get_level_values("side"):
                top = today.xs(side, level="side")["score"].nlargest(EARNINGS_CHECKED)
                names.extend(str(s) for s in top.index if s not in names)
        return self._earnings(names) if names else {}


def _score_rows(iso: str, side: str, rows: pd.DataFrame) -> list[ScoreRow]:
    picked = rows[_SCORE_COLUMNS].reset_index()
    return [
        ScoreRow(iso, str(sym), side, float(score), float(rs), float(flow), float(setup_p),
                 float(sector), float(regime), float(penalty), str(setup), _num(trigger),
                 _num(stop))
        for sym, score, rs, flow, setup_p, sector, regime, penalty, setup, trigger, stop
        in picked.itertuples(index=False, name=None)
    ]


def _log_latest(day: date, ideas: list[Idea]) -> None:
    for side in SIDES:
        listed = [i for i in ideas if i.side == side and i.status == "list"]
        watch = sum(1 for i in ideas if i.side == side and i.status == "watch")
        top = ", ".join(f"{i.symbol} {i.score:.0f}" for i in listed[:3]) or "none"
        log.info("[Ideas] Latest %s: %d %s idea(s), %d on Watch; top %s", day.isoformat(),
                 len(listed), side, watch, top)
