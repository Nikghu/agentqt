"""
Module: MD-MKT-018.001.M01 — market/book_strategy.py
Parent SRD: SRD-MKT-018.001
Also: SRD-MKT-018.007 (card answer), SRD-MKT-018.008 (quote check), SRD-MKT-018.009 (result
and gain), SRD-MKT-018.011 (default employee), SRD-MKT-018.012 (logs)

The book to strategy research skill. Book tickets never auto-approve, so the owner's
approval is the permission to read the one chapter the ticket names. Code reads that
chapter once; one AI call turns it into a strategy card, and code keeps only the quotes
that really are in the chapter.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_research import StepResult, Ticket
from us_swing.data.market_calendar import ET
from us_swing.market.book_cards import CardText, already_read, save_card
from us_swing.market.book_text import TOPIC_HELP, BookError, chapter, load_text, parse_topic
from us_swing.market.book_text import gutenberg_get
from us_swing.market.news import Getter

log = logging.getLogger(__name__)

KIND = "book_to_strategy"
STEP_TOKENS = 9_000
_RULES = (
    "Rules: turn this one chapter into one strategy card a swing trader of S&P 500 stocks "
    "could test: a short name, the idea, the market it suits, the entry, the exit and the "
    "stop, each in plain words. Leave a field empty when the chapter does not say it. Give "
    "1 to 3 short quotes copied word for word from the chapter that back the rules. Never "
    "invent a rule, a number or a quote."
)
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
Quote = Annotated[str, Field(min_length=10, max_length=200)]


class StrategyCard(BaseModel):
    """The model's answer for the card step."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=80)
    idea: str = Field(min_length=10, max_length=300)
    market: str = Field(default="", max_length=300)
    entry: str = Field(default="", max_length=300)
    exit: str = Field(default="", max_length=300)
    stop: str = Field(default="", max_length=300)
    quotes: list[Quote] = Field(min_length=1, max_length=3)


def _now() -> datetime:
    return datetime.now(ET)


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", text.translate(_QUOTES)).strip().lower()


def found_quotes(quotes: list[str], text: str) -> list[str]:
    """The quotes that appear in ``text``, ignoring spacing, case and curly quote marks."""
    body = _plain(text)
    return [q for q in quotes if _plain(q) and _plain(q) in body]


class BookStrategySkill:
    """Works book tickets: read one approved chapter once, write one strategy card."""

    key = KIND
    needs: tuple[str, ...] = ()
    answer = StrategyCard
    kinds: tuple[str, ...] = (KIND,)
    step_tokens = STEP_TOKENS

    def __init__(
        self,
        clock: Callable[[], datetime] = _now,
        folder: Callable[[Path], Path] = lambda home: home / "books",
        get: Getter = gutenberg_get,
    ) -> None:
        """Set the clock, the books folder and the web getter; injectable for tests."""
        self._clock = clock
        self._folder = folder
        self._get = get

    def facts(self, home: Path) -> Facts:
        """This employee works research tickets only, so events never wake it."""
        return Facts("", self._clock().date().isoformat(), False,
                     "works research tickets only")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Nothing to do outside a research ticket."""
        return []

    def step(self, ctx: AgentContext, ticket: Ticket) -> StepResult | None:
        """Do the next step of ``ticket``: read the chapter, or write the card."""
        state: dict[str, Any] = json.loads(ticket.state or "{}")
        if state.get("phase") == "card":
            return self._card(ctx, ticket, state)
        return self._read(ctx.home, ticket)

    def _read(self, home: Path, ticket: Ticket) -> StepResult:
        ref = parse_topic(ticket.topic)
        if ref is None:
            return StepResult(TOPIC_HELP, "read", "failed")
        earlier = already_read(home, ref.key, ref.chapter)
        if earlier:
            return StepResult(f"Chapter {ref.chapter} of {ref.source} was read by ticket "
                              f"{earlier[1]}; see card SC-{earlier[0]}", "read", "failed")
        try:
            text = chapter(load_text(ref, self._folder(home), self._get), ref.chapter)
        except BookError as exc:
            return StepResult(str(exc), "read", "failed")
        words = len(text.split())
        log.info("[Research] Ticket %d read chapter %d of %s (%s words)", ticket.id,
                 ref.chapter, ref.source, f"{words:,}")
        return StepResult(f"Read chapter {ref.chapter} of {ref.source} ({words:,} words)",
                          "read", "go", state={"phase": "card", "source": ref.source,
                                               "key": ref.key, "chapter": ref.chapter,
                                               "text": text})

    def _card(self, ctx: AgentContext, ticket: Ticket, state: dict[str, Any]) -> StepResult:
        text = str(state["text"])
        facts = "\n".join([f"Ticket {ticket.id}: {ticket.topic}", f"Goal: {ticket.goal}",
                           f"Done when: {ticket.done_test}", "",
                           f"Chapter {state['chapter']} of {state['source']}:", text, "",
                           _RULES])
        reply = ctx.ask(facts, StrategyCard)
        if reply is None:
            return StepResult("", "card", "go")
        kept = found_quotes(list(reply.quotes), text)
        card = CardText(reply.name.strip(), reply.idea.strip(), reply.market.strip(),
                        reply.entry.strip(), reply.exit.strip(), reply.stop.strip(), kept)
        card_id = save_card(ctx.home, str(state.get("key", state["source"])),
                            int(state["chapter"]), ticket.id, card,
                            self._clock().isoformat(timespec="seconds"))
        log.info("[Research] Ticket %d saved card SC-%d, %d of %d quotes found", ticket.id,
                 card_id, len(kept), len(reply.quotes))
        gain = bool(card.entry and card.exit and card.stop and kept)
        lines = [f"Card SC-{card_id}: {card.name}", f"Idea: {card.idea}",
                 f"Market: {card.market or '-'}", f"Entry: {card.entry or '-'}",
                 f"Exit: {card.exit or '-'}", f"Stop: {card.stop or '-'}",
                 f"Quotes kept: {len(kept)} of {len(reply.quotes)}"]
        done = {"phase": "done", "source": state["source"], "chapter": state["chapter"],
                "card": card_id}
        return StepResult("\n".join(lines), "card", "done", gain=gain, state=done)
