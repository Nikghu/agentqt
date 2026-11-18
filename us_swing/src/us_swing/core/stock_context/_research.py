"""
Module: MD-SCR-019.005.M39 — core/stock_context/_research.py
Parent SRD: SRD-SCR-019.005, SRD-SCR-019.006

Web research for the final AI picks: one Claude Code CLI request per stock with
only the web search tool, 3 at a time. Sync and slow (about a minute per stock).
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Any

from us_swing.core.notifications import AiAnswer, AiConfig, ask_ai

_log = logging.getLogger(__name__)

RESEARCH_WORKERS = 3
RESEARCH_TIMEOUT_S = 180.0
_SUMMARY_WORDS = 60
_MAX_SOURCES = 3
_INSTRUCTION = (
    "Search the web for news from the last 14 days about the US stock with the ticker "
    "below. Reply with ONLY a JSON object, no prose: "
    '{"summary": "at most 60 words on what matters for a 1 to 3 week swing trade", '
    '"risk": "" or a few words naming a major risk (lawsuit, share offering, guidance cut, '
    'probe, delisting), "sources": ["url", ...up to 3]}'
)

Ask = Callable[[AiConfig, str, str, float], AiAnswer]


@dataclass(frozen=True, slots=True)
class Research:
    """What web research found for one stock."""

    summary: str
    sources: tuple[str, ...] = ()
    risk: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"summary": self.summary, "sources": list(self.sources), "risk": self.risk}


def _parse(text: str) -> Research | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    summary = " ".join(str(data.get("summary", "")).split()[:_SUMMARY_WORDS])
    if not summary:
        return None
    sources = tuple(str(s) for s in data.get("sources") or [] if str(s).startswith("http"))
    return Research(summary, sources[:_MAX_SOURCES], str(data.get("risk") or "").strip())


def research_picks(
    symbols: Sequence[str],
    model: str,
    today: date,
    ask: Ask = ask_ai,
    workers: int = RESEARCH_WORKERS,
) -> dict[str, Research]:
    """Research each symbol on the web (SRD-SCR-019.005).

    Args:
        symbols: The final picks.
        model: Claude model for the CLI.
        today: The run date, given to the AI.
        ask: AI call, injectable for tests.
        workers: How many CLI runs at once.

    Returns:
        Symbol → research for the stocks that got a readable answer, in input order.
    """
    config = AiConfig(claude_model=model, claude_tools=("WebSearch",))

    def one(symbol: str) -> Research | None:
        answer = ask(config, _INSTRUCTION, f"Ticker: {symbol}\nToday: {today.isoformat()}",
                     RESEARCH_TIMEOUT_S)
        return None if answer.error else _parse(answer.text)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        found = dict(zip(symbols, pool.map(one, symbols)))
    missing = [sym for sym, research in found.items() if research is None]
    if missing:
        _log.warning("[Screener] Web research failed for %d of %d stock(s)",
                     len(missing), len(symbols))
    return {sym: research for sym, research in found.items() if research is not None}
