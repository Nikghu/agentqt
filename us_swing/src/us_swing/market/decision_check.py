"""
Module: MD-MKT-020.014.M06 — market/decision_check.py
Parent SRD: SRD-MKT-020.014
Also: SRD-MKT-020.015 (market part), .016 (sector part), .017 (vote results), .024 (log line)

Desk step "Decision check" (AI Desk v3 M5): each lead day call is checked 5 trading days
later. The market part by SPY's move, the sector part by the favoured sectors' average move
against SPY; each expert's vote takes the result of its part, flipped when it disagreed.
Runs only while the company day is on. Design: DD-MKT-020.001.D01 §7.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.core.desk_day import CHECK_DAYS, Decision, due_calls, save_results, votes_of
from us_swing.market.candles import BENCHMARK, CANDLE_DB, CandleReader
from us_swing.market.store import MarketStore

log = logging.getLogger(__name__)

TREND_PCT = 1.0
CHOPPY_WRONG_PCT = 2.0
SECTOR_GAP = 0.5
_FLIP = {"right": "wrong", "wrong": "right", "neutral": "neutral"}


def market_result(market: str, move: float) -> str:
    """``right``, ``wrong`` or ``neutral`` for a market call when SPY moved ``move`` percent."""
    if market == "Choppy":
        if abs(move) < TREND_PCT:
            return "right"
        return "wrong" if abs(move) >= CHOPPY_WRONG_PCT else "neutral"
    signed = move if market == "Uptrend" else -move
    if signed >= TREND_PCT:
        return "right"
    return "wrong" if signed <= -TREND_PCT else "neutral"


def sector_result(gap: float | None) -> str:
    """Result of the sector part when the favoured sectors beat SPY by ``gap`` points."""
    if gap is None:
        return "neutral"
    if gap >= SECTOR_GAP:
        return "right"
    return "wrong" if gap <= -SECTOR_GAP else "neutral"


def vote_result(stance: str, part_result: str) -> str:
    """The part's result for an agreeing vote, the opposite for a disagreeing one."""
    return part_result if stance == "agreed" else _FLIP.get(part_result, "neutral")


def window_move(series: pd.Series, day: str) -> tuple[float, str] | None:
    """Percent move from ``day``'s close to the 5th close after it, and that end day."""
    values = series.dropna()
    start_at = pd.Timestamp(day)
    before = values[values.index <= start_at]
    after = values[values.index > start_at]
    if before.empty or len(after) < CHECK_DAYS:
        return None
    start = float(before.iloc[-1])
    if start <= 0:
        return None
    end = float(after.iloc[CHECK_DAYS - 1])
    return (end - start) / start * 100, after.index[CHECK_DAYS - 1].date().isoformat()


def sector_move(home: Path, sectors: Sequence[str], start: str, end: str) -> float | None:
    """Average percent move of the sector lines from ``start`` to ``end``; ``None`` if missing."""
    store = MarketStore(home)
    try:
        frame = store.read_frame("SELECT date, sector, line FROM sector_daily WHERE date IN "
                                 "(?, ?)", (start, end))
    finally:
        store.close()
    moves: list[float] = []
    for sector in sectors:
        mine = frame[frame["sector"] == sector].set_index("date")["line"]
        if start not in mine.index or end not in mine.index or float(mine[start]) <= 0:
            return None
        moves.append((float(mine[end]) - float(mine[start])) / float(mine[start]) * 100)
    return sum(moves) / len(moves) if moves else None


class DecisionCheckStep:
    """Checks due day calls against SPY and sector moves on each desk run."""

    name = "Decision check"

    def __init__(self, candles: Path = CANDLE_DB) -> None:
        """Set the candle file; injectable for tests."""
        self._candles = candles

    def __call__(self, ctx: StepContext) -> None:
        """Check the due day calls; a failure never stops the run."""
        home = ctx.home or desk_home()
        if not load_settings(home).company_day_on:
            return
        try:
            self._check(home, ctx.started_at.date().isoformat())
        except Exception:  # noqa: BLE001 — a decision check must never fail the run
            log.exception("[Company day] Could not check the day calls")

    def _check(self, home: Path, today: str) -> None:
        calls = due_calls(home, today)
        if not calls:
            return
        try:
            bars = CandleReader(self._candles, home).read({BENCHMARK})
        except FileNotFoundError:
            log.warning("[Company day] No candle file yet; day calls are checked later")
            return
        if BENCHMARK not in bars.closes.columns:
            return
        done = {"right": 0, "wrong": 0, "neutral": 0}
        for call in calls:
            result = self._one(home, call, bars.closes[BENCHMARK], today)
            if result:
                done[result] += 1
        checked = sum(done.values())
        if checked:
            log.info("[Company day] Checked %d day call(s): %d right, %d wrong", checked,
                     done["right"], done["wrong"])

    def _one(self, home: Path, call: Decision, spy: pd.Series, today: str) -> str:
        found = window_move(spy, call.day)
        if found is None:
            return ""
        move, end = found
        market = market_result(call.market, move)
        sectors = sector_move(home, call.favour, call.day, end)
        sector = sector_result(None if sectors is None else sectors - move)
        parts = {"market": market, "sector": sector}
        results = {v.skill: vote_result(v.stance, parts.get(v.part, "neutral"))
                   for v in votes_of(home, call.day)}
        save_results(home, call.day, market, sector, move, sectors, results, today)
        return market
