"""
Module: MD-MKT-005.012.M07 — market/risk_check.py
Parent SRD: SRD-MKT-005.012
Also: SRD-MKT-005.013 (one ``risk_check`` row per listed idea), SRD-MKT-006.010 (news tags
in the facts)

The risk check skill. The hard limits in code veto listed ideas first and are stored
before any model is asked, so they hold even when the call fails or the budget is used
up. The model may then veto more of the ideas that passed, never fewer.
Uses only ``core`` types; it never imports the desk harness.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.market.candles import CANDLE_DB
from us_swing.market.risk_limits import code_vetoes
from us_swing.market.setup_review import (
    ideas_day,
    listed_frame,
    listed_ideas,
    rule_regime,
    table,
)
from us_swing.market.store import MarketStore, RiskCheckRow

log = logging.getLogger(__name__)

KEY = "risk_check"
WITHIN_LIMITS = "Within the hard limits"
Reason = Annotated[str, StringConstraints(min_length=5, max_length=120)]


class RiskVeto(BaseModel):
    """One extra veto from the risk check model."""

    model_config = ConfigDict(extra="forbid")

    side: Literal["long", "short"]
    symbol: str = Field(min_length=1, max_length=12)
    reason: Reason


class RiskVetoes(BaseModel):
    """The model's answer for the risk check skill, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    vetoes: list[RiskVeto] = Field(default_factory=list, max_length=20)


def views_text(store: MarketStore, day: str, keys: tuple[str, ...]) -> str:
    """The AI views of ``day`` named by skill ``keys`` as text; a missing view is noted."""
    parts: list[str] = []
    if "regime_view" in keys:
        f = store.read_frame("SELECT regime, confidence, brief FROM regime_view WHERE date = ?",
                             (day,))
        parts.append("Regime view: not available today" if f.empty else
                     f"Regime view: {f['regime'].iloc[0]} (confidence "
                     f"{float(f['confidence'].iloc[0]):.2f}) - {f['brief'].iloc[0]}")
    if "sector_flow_view" in keys:
        f = store.read_frame("SELECT favour, avoid, rotation FROM sector_view WHERE date = ?",
                             (day,))
        parts.append("Sector view: not available today" if f.empty else
                     f"Sector view: favour {', '.join(json.loads(f['favour'].iloc[0]))}; "
                     f"avoid {', '.join(json.loads(f['avoid'].iloc[0])) or 'none'}; "
                     f"{f['rotation'].iloc[0]}")
    if "setup_review" in keys:
        f = store.read_frame("SELECT side, symbol, grade, note FROM setup_review "
                             "WHERE date = ? ORDER BY side, grade, symbol", (day,))
        parts.append("Setup review: not available today" if f.empty else
                     f"Setup review grades:\n{table(f)}")
    if "news_review" in keys:
        f = store.read_frame("SELECT side, symbol, tone, points, final_score AS final, reason "
                             "FROM news_tags WHERE date = ? ORDER BY side, final_score DESC",
                             (day,))
        parts.append("News review: not available today" if f.empty else
                     f"News review (points out of 10; final = 0.9 x score + points):\n"
                     f"{table(f)}")
    if "risk_check" in keys:
        f = store.read_frame("SELECT side, symbol, verdict, by, reason FROM risk_check "
                             "WHERE date = ? ORDER BY side, verdict, symbol", (day,))
        parts.append("Risk check: not available today" if f.empty else
                     f"Risk check:\n{table(f)}")
    return "\n\n".join(parts)


class RiskCheckSkill:
    """The risk check skill (a ``Skill``)."""

    key = KEY
    needs: tuple[str, ...] = ("regime_view", "sector_flow_view", "setup_review", "news_review")
    answer = RiskVetoes

    def __init__(self, candles: Path = CANDLE_DB) -> None:
        """Use ``candles`` to check that the ideas are up to date."""
        self._candles = candles

    def facts(self, home: Path) -> Facts:
        """Build the facts: the day's views and the listed ideas that passed the limits."""
        store = MarketStore(home)
        try:
            day, why = ideas_day(store, self._candles)
            if why:
                return Facts("", day, False, why)
            listed = listed_frame(store, day)
            if listed.empty:
                return Facts("", day, False, f"no listed ideas for {day}")
            regime = rule_regime(store, day)
            vetoed = code_vetoes(listed_ideas(listed), regime)
            keep = [(str(s), str(y)) not in vetoed for s, y in
                    zip(listed["side"], listed["symbol"], strict=True)]
            passed = listed[keep][["side", "symbol", "score", "sector", "setup", "trigger",
                                   "stop"]]
            text = "\n\n".join([
                f"Data day: {day}",
                f"Regime by the rules: {regime or 'unknown'}",
                views_text(store, day, self.needs),
                f"Already vetoed by the hard limits: {len(vetoed)} idea(s); do not list them.",
                f"Ideas that passed the hard limits (you may veto any of these):\n"
                f"{table(passed)}",
            ])
            return Facts(text, day, True)
        finally:
            store.close()

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Store the code vetoes, then ask the model for more and store those too.

        Without a valid answer the code vetoes stay and no brief is posted, so a later run
        on the same data day tries the review again.
        """
        store = MarketStore(ctx.home)
        try:
            day = facts.data_day
            listed = listed_ideas(listed_frame(store, day))
            if not listed:
                return []
            vetoed = code_vetoes(listed, rule_regime(store, day))
            earlier = store.read_frame("SELECT side, symbol, reason FROM risk_check WHERE "
                                       "date = ? AND verdict = 'veto' AND by = 'ai'", (day,))
            kept = {(str(s), str(y)): str(r) for s, y, r in earlier.itertuples(index=False)}
            rows: dict[tuple[str, str], RiskCheckRow] = {}
            for i in listed:
                idea = (i.side, i.symbol)
                if idea in vetoed:
                    rows[idea] = RiskCheckRow(day, i.side, i.symbol, "veto", "code",
                                              vetoed[idea])
                elif idea in kept:
                    rows[idea] = RiskCheckRow(day, i.side, i.symbol, "veto", "ai", kept[idea])
                else:
                    rows[idea] = RiskCheckRow(day, i.side, i.symbol, "pass", "code",
                                              WITHIN_LIMITS)
            store.replace_day("risk_check", day, list(rows.values()))
            need_ai = len(vetoed) < len(listed)
            answer = ctx.ask(facts.text, RiskVetoes) if need_ai else None
            if need_ai and answer is None:
                return []
            by_ai = dropped = 0
            for v in answer.vetoes if answer else []:
                idea = (v.side, v.symbol.upper())
                if idea not in rows or rows[idea].verdict == "veto":
                    dropped += 1
                    continue
                rows[idea] = RiskCheckRow(day, idea[0], idea[1], "veto", "ai", v.reason)
                by_ai += 1
            if dropped:
                log.info("[AI Desk] Risk check named %d stock(s) that were not open to a veto",
                         dropped)
            if by_ai:
                store.replace_day("risk_check", day, list(rows.values()))
        finally:
            store.close()
        total = len(vetoed) + by_ai
        return [FeedItem("info", f"Risk check: {total} of {len(listed)} idea(s) vetoed "
                         f"({len(vetoed)} by the hard limits, {by_ai} by review)", day)]
