"""
Module: MD-MKT-019.001.M01 — market/strategy_test.py
Parent SRD: SRD-MKT-019.001
Also: SRD-MKT-019.002 (card topic), SRD-MKT-019.008 (verdict), SRD-MKT-019.009 (save and gain),
SRD-MKT-019.010 (candidate lesson), SRD-MKT-019.013 (report only), SRD-MKT-019.014 (logs)

The strategy test research skill. One ticket tests one strategy card as a chain of steps,
one per desk tick: the AI writes a recipe from the shared blocks, code checks it, code
replays it on all Backtest Data daily bars, and the AI writes a short verdict. Code decides
pass or fail, and the skill never changes a live strategy, setting, signal or trade.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_cards import KIND, CardRow, CardTest, card, card_id_of, save_test
from us_swing.core.desk_lessons import add_candidate
from us_swing.core.desk_research import StepResult, Ticket
from us_swing.data.market_calendar import ET
from us_swing.market.card_recipe import Recipe, block_menu, check_recipe, recipe_text
from us_swing.market.card_replay import Score, Stock, TooSlow, baseline, load_data, replay, score
from us_swing.market.card_replay import score_text

log = logging.getLogger(__name__)

STEP_TOKENS = 6_000
_RECIPE_RULES = (
    "Rules: rewrite the card's entry and stop as a test recipe using only the blocks listed "
    "above, by their exact ids and inside their ranges. Use 1 to 4 indicator rules and up to "
    "3 price patterns for the entry. Pick one entry type and one stop. Put every card rule "
    "that no block can express in unmapped, in a few words each; never drop a rule quietly "
    "and never invent one. Exits are fixed by code: a 2R target and a 10-day limit."
)
_VERDICT_RULES = (
    "Rules: in 2 or 3 short lines say what the table shows and whether the card looks worth "
    "a closer look. Code has already decided pass or fail; do not change it. Never invent a "
    "number that is not in the table."
)


class CardVerdict(BaseModel):
    """The model's answer for the verdict step."""

    model_config = ConfigDict(extra="forbid")

    verdict: str = Field(min_length=10, max_length=600)


def _now() -> datetime:
    return datetime.now(ET)


def _card_text(c: CardRow) -> str:
    return "\n".join([f"Card SC-{c.id}: {c.name}", f"Idea: {c.idea}",
                      f"Market: {c.market or '-'}", f"Entry: {c.entry or '-'}",
                      f"Exit: {c.exit or '-'}", f"Stop: {c.stop or '-'}"])


def _lines(text: str) -> str:
    return "\n".join(line.strip()[:200] for line in text.strip().splitlines()[:3] if line.strip())


class StrategyTestSkill:
    """Works strategy test tickets: recipe, check, replay and verdict."""

    key = KIND
    needs: tuple[str, ...] = ()
    answer = Recipe
    kinds: tuple[str, ...] = (KIND,)
    step_tokens = STEP_TOKENS

    def __init__(self, clock: Callable[[], datetime] = _now,
                 data: Callable[[], Sequence[Stock]] = load_data) -> None:
        """Set the clock and the Backtest Data loader; injectable for tests."""
        self._clock = clock
        self._data = data

    def facts(self, home: Path) -> Facts:
        """This employee works research tickets only, so events never wake it."""
        return Facts("", self._clock().date().isoformat(), False,
                     "works research tickets only")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Nothing to do outside a research ticket."""
        return []

    def step(self, ctx: AgentContext, ticket: Ticket) -> StepResult | None:
        """Do the next step of ``ticket``: recipe, check, replay or verdict."""
        state: dict[str, Any] = json.loads(ticket.state or "{}")
        phase = state.get("phase", "recipe")
        if phase == "recipe":
            return self._recipe(ctx, ticket)
        if phase == "check":
            return self._check(ctx.home, ticket, state)
        if phase == "replay":
            return self._replay(ticket, state)
        return self._verdict(ctx, ticket, state)

    def _recipe(self, ctx: AgentContext, ticket: Ticket) -> StepResult:
        cid = card_id_of(ticket.topic)
        found = card(ctx.home, cid) if cid is not None else None
        if found is None:
            log.info("[Research] Ticket %d has no card for topic %s", ticket.id, ticket.topic)
            return StepResult(f"Card {ticket.topic} not found; the topic must be SC-<n>",
                              "recipe", "failed")
        text = "\n".join([f"Ticket {ticket.id}: {ticket.topic}", f"Goal: {ticket.goal}", "",
                          _card_text(found), "", block_menu(), "", _RECIPE_RULES])
        reply = ctx.ask(text, Recipe)
        if reply is None:
            return StepResult("", "recipe", "go")
        log.info("[Research] Ticket %d card SC-%d recipe: %s", ticket.id, found.id,
                 recipe_text(reply))
        return StepResult(f"Recipe for SC-{found.id}: {recipe_text(reply)}", "recipe", "go",
                          state={"phase": "check", "card": found.id,
                                 "recipe": reply.model_dump()})

    def _check(self, home: Path, ticket: Ticket, state: dict[str, Any]) -> StepResult:
        recipe = Recipe.model_validate(state["recipe"])
        problems = check_recipe(recipe)
        cid = int(state["card"])
        if problems:
            reason = "; ".join(problems)
            save_test(home, CardTest(cid, ticket.id, self._stamp(), "cant_test", reason,
                                    json.dumps(state["recipe"])))
            log.info("[Research] Ticket %d card SC-%d can't test: %s", ticket.id, cid, reason)
            return StepResult(f"Can't test: {reason}", "check", "failed")
        return StepResult(f"Recipe for SC-{cid} uses only known blocks", "check", "go",
                          state={**state, "phase": "replay"})

    def _replay(self, ticket: Ticket, state: dict[str, Any]) -> StepResult:
        data = self._data()
        if not data:
            return StepResult("No S&P 500 daily candles in Backtest Data to test on",
                              "replay", "failed")
        recipe = Recipe.model_validate(state["recipe"])
        try:
            trades = replay(recipe, data)
        except TooSlow:
            log.warning("[Research] Ticket %d card SC-%s test took longer than 10 minutes",
                        ticket.id, state["card"])
            return StepResult("The test took longer than 10 minutes; a simpler recipe may run",
                              "replay", "failed")
        result = score(trades, baseline(recipe, data))
        log.info("[Research] Ticket %d card SC-%s replay: %s trades, %+.2fR, baseline %+.2fR, %s",
                 ticket.id, state["card"], f"{result.trades:,}", result.avg_r, result.base_r,
                 "pass" if result.passed else "fail")
        return StepResult(score_text(result), "replay", "go",
                          state={**state, "phase": "verdict", "score": asdict(result)})

    def _verdict(self, ctx: AgentContext, ticket: Ticket, state: dict[str, Any]) -> StepResult:
        result = Score(**state["score"])
        cid, table = int(state["card"]), score_text(result)
        text = "\n".join([f"Ticket {ticket.id}: {ticket.topic}", f"Goal: {ticket.goal}", "",
                          f"Test of card SC-{cid} on all Backtest Data:", table, "",
                          _VERDICT_RULES])
        reply = ctx.ask(text, CardVerdict)
        if reply is None:
            return StepResult("", "verdict", "go")
        verdict = _lines(reply.verdict)
        save_test(ctx.home, CardTest(
            cid, ticket.id, self._stamp(), "pass" if result.passed else "fail", "",
            json.dumps(state["recipe"]), result.first_day, result.last_day, result.trades,
            result.win_rate, result.avg_r, result.worst_run, result.base_trades, result.base_r,
            verdict))
        if result.passed:
            self._lesson(ctx.home, ticket, cid, state, result)
        log.info("[Research] Ticket %d card SC-%d test %s", ticket.id, cid,
                 "passed" if result.passed else "failed")
        return StepResult(f"{table}\nVerdict: {verdict}", "verdict", "done",
                          gain=result.passed)

    def _lesson(self, home: Path, ticket: Ticket, cid: int, state: dict[str, Any],
                result: Score) -> None:
        side = str(state["recipe"].get("side", "long"))
        text = (f"Strategy card SC-{cid} ({side}s) averaged {result.avg_r:+.2f}R on "
                f"{result.trades:,} backtest trades, above the {result.base_r:+.2f}R baseline")
        proof = [f"ticket {ticket.id}: {result.trades:,} trades, win rate "
                 f"{result.win_rate:.0%}, worst losing run {result.worst_run}"]
        try:
            add_candidate(home, text, {"setup": f"card SC-{cid}", "side": side}, "better",
                          proof, self._clock())
        except Exception:  # noqa: BLE001 — a lost lesson must not repeat the paid verdict
            log.warning("[Research] Ticket %d could not save its lesson", ticket.id)

    def _stamp(self) -> str:
        return self._clock().isoformat(timespec="seconds")
