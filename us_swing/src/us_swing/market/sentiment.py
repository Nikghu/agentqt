"""
Module: MD-MKT-017.001.M01 — market/sentiment.py
Parent SRD: SRD-MKT-017.001
Also: SRD-MKT-017.002–.003 (pick step and checks), SRD-MKT-017.005 (judge answer),
SRD-MKT-017.008 (result and gain), SRD-MKT-017.009 (default employee), SRD-MKT-017.010 (logs)

The sentiment research skill. A ticket runs in three steps, one per desk tick: the AI
chooses up to 30 of the latest ideas and open trades, code gathers their headlines, then
the AI judges each stock's news for its side. Code saves one tone card per stock for the
lead; no idea score is changed.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_research import StepResult, Ticket
from us_swing.core.desk_watch import open_trades
from us_swing.data.market_calendar import ET
from us_swing.market.sentiment_cards import CardRow, save_cards
from us_swing.market.sentiment_news import Gathered, gather_news

log = logging.getLogger(__name__)

KIND = "sentiment"
STEP_TOKENS = 6_000
MAX_SHOWN = 150
_PICK_RULES = (
    "Rules: choose 1 to 30 stocks from the list above that fit the ticket's goal, by their "
    "exact key (side|symbol)."
)
_JUDGE_RULES = (
    "Rules: for each stock, judge its headlines for its side only: supports (good for that "
    "side), neutral, against (bad for that side) or none (no news). Give a short reason "
    "from the headlines. End with a summary of at most 4 short sentences. Never invent a "
    "headline, a price or a number."
)


class StockChoice(BaseModel):
    """The model's answer for the pick step."""

    model_config = ConfigDict(extra="forbid")

    stocks: list[str] = Field(min_length=1, max_length=30)


class Card(BaseModel):
    """One stock's news tone for its side."""

    model_config = ConfigDict(extra="forbid")

    stock: str = Field(min_length=3, max_length=30)
    tone: Literal["supports", "neutral", "against", "none"]
    reason: str = Field(min_length=3, max_length=150)


class SentimentJudge(BaseModel):
    """The model's answer for the judge step."""

    model_config = ConfigDict(extra="forbid")

    cards: list[Card] = Field(default_factory=list, max_length=30)
    summary: str = Field(min_length=10, max_length=600)


def _now() -> datetime:
    return datetime.now(ET)


def _ideas(home: Path) -> dict[str, str]:
    """Listed and watch ideas of the latest ideas day as ``side|symbol`` → label."""
    path = home / DB_NAME
    if not path.exists():
        return {}
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                           "name='ideas'").fetchone():
            return {}
        rows = con.execute(
            "SELECT side, symbol, status, setup, score FROM ideas WHERE date = "
            "(SELECT MAX(date) FROM ideas) AND status IN ('list', 'watch') "
            "ORDER BY status, rank").fetchall()
    finally:
        con.close()
    return {f"{side}|{sym}": f"{status} idea, {setup or 'no setup'}, score {float(score):.0f}"
            for side, sym, status, setup, score in rows}


class SentimentSkill:
    """Works sentiment tickets: choose stocks, gather headlines, judge them."""

    key = KIND
    needs: tuple[str, ...] = ()
    answer = StockChoice
    kinds: tuple[str, ...] = (KIND,)
    step_tokens = STEP_TOKENS

    def __init__(
        self,
        clock: Callable[[], datetime] = _now,
        gather: Callable[[Path, Sequence[str], dict[str, str]], Gathered] = gather_news,
    ) -> None:
        """Set the clock and the headline gatherer; injectable for tests."""
        self._clock = clock
        self._gather = gather

    def facts(self, home: Path) -> Facts:
        """This employee works research tickets only, so events never wake it."""
        return Facts("", self._clock().date().isoformat(), False,
                     "works research tickets only")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Nothing to do outside a research ticket."""
        return []

    def step(self, ctx: AgentContext, ticket: Ticket) -> StepResult | None:
        """Do the next step of ``ticket``: pick, gather or judge."""
        state: dict[str, Any] = json.loads(ticket.state or "{}")
        phase = state.get("phase", "pick")
        if phase == "pick":
            return self._pick(ctx, ticket)
        if phase == "gather":
            return self._gather_step(ctx.home, ticket, state)
        return self._judge(ctx, ticket, state)

    @staticmethod
    def _choices(home: Path) -> dict[str, str]:
        shown = _ideas(home)
        for trade in open_trades(home) if (home / DB_NAME).exists() else []:
            shown.setdefault(f"{trade.side}|{trade.symbol}",
                             f"open trade, {trade.strategy or 'no strategy'}")
        return dict(list(shown.items())[:MAX_SHOWN])

    def _pick(self, ctx: AgentContext, ticket: Ticket) -> StepResult:
        shown = self._choices(ctx.home)
        if not shown:
            return StepResult("No ideas or open trades to judge", "pick", "failed")
        text = "\n".join([f"Ticket {ticket.id}: {ticket.topic}", f"Goal: {ticket.goal}",
                          f"Done when: {ticket.done_test}", "",
                          "Latest ideas and open trades (key: what it is):",
                          *(f"{k}: {v}" for k, v in shown.items()), "", _PICK_RULES])
        reply = ctx.ask(text, StockChoice)
        if reply is None:
            return StepResult("", "pick", "go")
        stocks = list(dict.fromkeys(s for s in reply.stocks if s in shown))
        if not stocks:
            return StepResult("None of the chosen stocks is a current idea or open trade",
                              "pick", "failed")
        log.info("[Research] Ticket %d will judge %d stock(s)", ticket.id, len(stocks))
        return StepResult(f"Chose {len(stocks)} stock(s)", "pick", "go",
                          state={"phase": "gather", "stocks": stocks,
                                 "labels": {s: shown[s] for s in stocks}})

    def _gather_step(self, home: Path, ticket: Ticket, state: dict[str, Any]) -> StepResult:
        got = self._gather(home, state["stocks"], state.get("labels", {}))
        total = sum(got.counts.values())
        log.info("[Research] Ticket %d gathered %d headline(s), %d stock(s) fetched",
                 ticket.id, total, got.fetched)
        return StepResult(f"Gathered {total} headline(s) for {len(got.records)} stock(s), "
                          f"{got.fetched} fetched", "gather", "go",
                          state={**state, "phase": "judge", "records": got.records,
                                 "counts": got.counts})

    def _judge(self, ctx: AgentContext, ticket: Ticket, state: dict[str, Any]) -> StepResult:
        text = "\n".join([f"Ticket {ticket.id}: {ticket.topic}", f"Goal: {ticket.goal}",
                          f"Done when: {ticket.done_test}", "",
                          "Headlines per stock (key (what it is): date title; ...):",
                          *state["records"], "", _JUDGE_RULES])
        reply = ctx.ask(text, SentimentJudge)
        if reply is None:
            return StepResult("", "judge", "go")
        chosen, counts = set(state["stocks"]), state.get("counts", {})
        cards: dict[str, Card] = {}
        for card in reply.cards:
            if card.stock in chosen:
                cards.setdefault(card.stock, card)
        now = self._clock()
        rows = []
        for key, c in cards.items():
            side, _, symbol = key.partition("|")
            rows.append(CardRow(side, symbol, c.tone, c.reason.strip(), int(counts.get(key, 0))))
        save_cards(ctx.home, now.date().isoformat(), ticket.id, rows,
                   now.isoformat(timespec="seconds"))
        against = sum(1 for c in cards.values() if c.tone == "against")
        log.info("[Research] Ticket %d judged %d stock(s), %d against their side", ticket.id,
                 len(cards), against)
        lines = [f"Summary: {reply.summary.strip()}",
                 *(f"{key}: {c.tone}, {c.reason.strip()}" for key, c in cards.items())]
        return StepResult("\n".join(lines), "judge", "done", gain=against > 0)
