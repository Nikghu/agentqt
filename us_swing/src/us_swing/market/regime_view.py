"""
Module: MD-MKT-005.001.M01 — market/regime_view.py
Parent SRD: SRD-MKT-005.001
Also: SRD-MKT-005.002 (typed view), SRD-MKT-005.004 (feed brief)

The regime view skill: reads the rule-based market data from ``desk.db``, asks the
employee's model for a typed view of the market and returns a brief for the AI feed.
Which employee uses this skill, and under what name, is data in the employee files.
Uses only ``core`` types; it never imports the desk harness.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Annotated, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.market.candles import BENCHMARK, CANDLE_DB
from us_swing.market.store import MarketStore, RegimeViewRow

KEY = "regime_view"
HISTORY_DAYS = 20
Reason = Annotated[str, StringConstraints(min_length=5, max_length=140)]


class RegimeView(BaseModel):
    """The model's answer for the regime view skill, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    regime: Literal["Uptrend", "Choppy", "Downtrend"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[Reason] = Field(min_length=1, max_length=3)
    brief: str = Field(min_length=20, max_length=400)


def latest_spy_day(candles: Path) -> str | None:
    """The newest SPY daily candle day in `candles`, or `None`."""
    if not candles.exists():
        return None
    con = sqlite3.connect(f"{candles.as_uri()}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT MAX(datetime) FROM price_1d WHERE symbol = ?",
                          (BENCHMARK,)).fetchone()
    finally:
        con.close()
    return str(row[0])[:10] if row and row[0] else None


def _table(frame: pd.DataFrame) -> str:
    return frame.to_string(index=False) if not frame.empty else "(none)"


class RegimeViewSkill:
    """The regime view skill (a ``Skill``)."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = RegimeView

    def __init__(self, candles: Path = CANDLE_DB) -> None:
        """Use ``candles`` to check that the regime data is up to date."""
        self._candles = candles

    def facts(self, home: Path) -> Facts:
        """Build the facts text from ``desk.db``; stale when the regime lags SPY's candles."""
        store = MarketStore(home)
        try:
            return self._facts(store)
        finally:
            store.close()

    def _facts(self, store: MarketStore) -> Facts:
        regime = store.read_frame(
            f"SELECT date, regime, volatility, fear, vix FROM regime_snapshot "  # noqa: S608
            f"ORDER BY date DESC LIMIT {HISTORY_DAYS}")
        if regime.empty:
            return Facts("", "", False, "no market regime data yet")
        day = str(regime["date"].iloc[0])
        spy_day = latest_spy_day(self._candles)
        if spy_day != day:
            return Facts("", day, False,
                         f"regime data is for {day} but the latest SPY candle is {spy_day}")
        breadth = store.read_frame(
            "SELECT pct_above_20, pct_above_50, pct_above_200, new_highs, new_lows, "
            "advancers, decliners FROM breadth_daily ORDER BY date DESC LIMIT 1")
        sectors = store.read_frame(
            "SELECT s.rank, s.sector, s.quadrant, ROUND(s.rel_1m * 100, 1) AS rel_1m_pct, "
            "p.rank AS rank_5_days_ago FROM sector_daily s LEFT JOIN sector_daily p "
            "ON p.sector = s.sector AND p.date = (SELECT date FROM (SELECT DISTINCT date "
            "FROM sector_daily ORDER BY date DESC LIMIT 6) ORDER BY date LIMIT 1) "
            "WHERE s.date = (SELECT MAX(date) FROM sector_daily) ORDER BY s.rank")
        ideas = store.read_frame(
            "SELECT side, status, COUNT(*) AS n FROM ideas "
            "WHERE date = (SELECT MAX(date) FROM ideas) GROUP BY side, status")
        proof = store.read_frame(
            "SELECT scored_first, scored_last, years, long_result, short_result "
            "FROM proof_run ORDER BY run_id DESC LIMIT 1")
        proof_text = "no proof run yet"
        if not proof.empty:
            first, last, years, long_result, short_result = proof.iloc[0].tolist()
            proof_text = (f"{first} to {last} ({float(years):.1f} years): long {long_result},"
                          f" short {short_result}")
        text = "\n\n".join([
            f"Data day: {day}",
            f"Regime by the rules, last {len(regime)} days (newest first):\n"
            f"{_table(regime)}",
            f"Breadth today (percent of S&P 500 stocks):\n{_table(breadth)}",
            f"Sectors today against SPY:\n{_table(sectors)}",
            f"Ideas today by side and status:\n{_table(ideas)}",
            f"Score proof on past data: {proof_text}",
        ])
        return Facts(text, day, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Ask for the view, keep it in ``regime_view`` and return the feed brief."""
        view = ctx.ask(facts.text, RegimeView)
        if view is None:
            return []
        store = MarketStore(ctx.home)
        try:
            rule = store.read_frame("SELECT regime FROM regime_snapshot WHERE date = ?",
                                    (facts.data_day,))
            rule_regime = str(rule["regime"].iloc[0]) if not rule.empty else ""
            agrees = view.regime == rule_regime
            store.write_regime_view(RegimeViewRow(
                facts.data_day, view.regime, view.confidence, json.dumps(view.reasons),
                view.brief, rule_regime, agrees))
        finally:
            store.close()
        text = view.brief
        if not agrees:
            text += f" I read the market as {view.regime}; the rules say {rule_regime}."
        return [FeedItem("info", text, facts.data_day)]
