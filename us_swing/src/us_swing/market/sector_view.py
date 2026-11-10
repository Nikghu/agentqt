"""
Module: MD-MKT-005.006.M04 — market/sector_view.py
Parent SRD: SRD-MKT-005.006
Also: SRD-MKT-005.007 (typed view), SRD-MKT-005.008 (kept in ``sector_view``, feed brief)

The sector/flow view skill: reads sector ranks, rotation and money flow from ``desk.db``
and asks for the sectors to favour and to avoid. Uses only ``core`` types; it never
imports the desk harness.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.market.candles import CANDLE_DB
from us_swing.market.regime_view import latest_spy_day
from us_swing.market.setup_review import rule_regime, table
from us_swing.market.store import MarketStore, SectorViewRow

KEY = "sector_flow_view"
HISTORY_DAYS = 5


class SectorView(BaseModel):
    """The model's answer for the sector/flow view skill, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    favour: list[str] = Field(min_length=1, max_length=3)
    avoid: list[str] = Field(default_factory=list, max_length=3)
    rotation: str = Field(min_length=10, max_length=200)
    brief: str = Field(min_length=20, max_length=400)

    @model_validator(mode="after")
    def _not_both(self) -> SectorView:
        both = set(self.favour) & set(self.avoid)
        if both:
            raise ValueError(f"sector in both favour and avoid: {sorted(both)[0]}")
        return self


def schema_for(sectors: list[str]) -> type[SectorView]:
    """``SectorView`` whose sector names must be one of ``sectors``."""
    name: Any = Literal[tuple(sectors)]
    model: type[SectorView] = create_model(
        "SectorView", __base__=SectorView,
        favour=(list[name], Field(min_length=1, max_length=3)),
        avoid=(list[name], Field(default_factory=list, max_length=3)))
    return model


def _sectors(store: MarketStore, day: str) -> list[str]:
    frame = store.read_frame("SELECT sector FROM sector_daily WHERE date = ? ORDER BY rank",
                             (day,))
    return [str(s) for s in frame["sector"]]


class SectorViewSkill:
    """The sector/flow view skill (a ``Skill``)."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = SectorView

    def __init__(self, candles: Path = CANDLE_DB) -> None:
        """Use ``candles`` to check that the sector data is up to date."""
        self._candles = candles

    def facts(self, home: Path) -> Facts:
        """Build the facts from ``desk.db``; stale when the sectors lag SPY's candles."""
        store = MarketStore(home)
        try:
            return self._facts(store)
        finally:
            store.close()

    def _facts(self, store: MarketStore) -> Facts:
        days = store.read_frame(
            f"SELECT DISTINCT date FROM sector_daily ORDER BY date DESC "  # noqa: S608
            f"LIMIT {HISTORY_DAYS}")
        if days.empty:
            return Facts("", "", False, "no sector data yet")
        day = str(days["date"].iloc[0])
        spy_day = latest_spy_day(self._candles, store)
        if spy_day != day:
            return Facts("", day, False,
                         f"sector data is for {day} but the latest SPY candle is {spy_day}")
        first = str(days["date"].iloc[-1])
        history = store.read_frame(
            "SELECT date, rank, sector, quadrant, ROUND(rel_1m * 100, 1) AS rel_1m_pct, "
            "ROUND(rel_3m * 100, 1) AS rel_3m_pct FROM sector_daily WHERE date >= ? "
            "ORDER BY date DESC, rank", (first,))
        flow = store.read_frame(
            "SELECT r.sector, s.side, ROUND(AVG(s.flow_part), 1) AS avg_flow, "
            "COUNT(*) AS stocks FROM stock_score s JOIN stock_rs r ON r.date = s.date "
            "AND r.symbol = s.symbol WHERE s.date = ? GROUP BY r.sector, s.side "
            "ORDER BY s.side, avg_flow DESC", (day,))
        text = "\n\n".join([
            f"Data day: {day}",
            f"Regime by the rules: {rule_regime(store, day) or 'unknown'}",
            f"Sectors against SPY, last {len(days)} days (newest first):\n{table(history)}",
            f"Money flow today, average flow points (0 to 20) per sector and side:\n"
            f"{table(flow)}",
            f"Sector names you may use: {', '.join(_sectors(store, day))}",
        ])
        return Facts(text, day, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Ask for the view, keep it in ``sector_view`` and return the feed brief."""
        store = MarketStore(ctx.home)
        try:
            sectors = _sectors(store, facts.data_day)
            if not sectors:
                return []
            view = ctx.ask(facts.text, schema_for(sectors))
            if view is None:
                return []
            store.replace_day("sector_view", facts.data_day, [SectorViewRow(
                facts.data_day, json.dumps(view.favour), json.dumps(view.avoid), view.rotation,
                view.brief)])
        finally:
            store.close()
        return [FeedItem("info", view.brief, facts.data_day)]
