"""
Module: MD-SCR-020.007.M42 — core/stock_context/_review.py
Parent SRD: SRD-SCR-020.007, SRD-SCR-020.008

Blind bull vs bear review for the final AI picks: one Claude Code CLI request per
stock with no tools, 3 at a time. The reviewer gets only facts — never the ranking
score, rank, reason, news tone, the preset Query or other stocks.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Any

from us_swing.core.notifications import AiAnswer, AiConfig, ask_ai
from us_swing.core.stock_context._context import (
    _REGIME_TEXT,
    StockContext,
    analysts_text,
    earnings_when,
    fundamentals_text,
    short_text,
    surprise_text,
)
from us_swing.core.stock_context._research import Research

_log = logging.getLogger(__name__)

REVIEW_WORKERS = 3
REVIEW_TIMEOUT_S = 180.0
VERDICTS = ("Long", "Short", "Wait", "Avoid")
_CONFIDENCE = ("low", "medium", "high")
_MAX_POINTS = 3
_ACTION_WORDS = {"up": "upgrade to", "down": "downgrade to", "main": "kept at",
                 "init": "started at", "reit": "repeated"}

REVIEW_INSTRUCTION = (
    "You review one US stock as a possible swing trade, long or short, over any holding "
    "period.\n\n"
    "You get only facts: price and trend, and any of earnings, sector, market, fundamentals, "
    "short interest, analyst changes, news headlines, web research and rule-based red flags. "
    "Some parts may be missing.\n\n"
    "Do this:\n"
    "1. Bull case: up to 3 strongest reasons the price could rise.\n"
    "2. Bear case: up to 3 strongest reasons the price could fall.\n"
    "3. Weigh both sides fairly. Do not lean to either side by default.\n"
    "4. Give a verdict:\n"
    '   - "Long": bull case clearly stronger and no near-term event risk.\n'
    '   - "Short": bear case clearly stronger, the trend supports a short and no near-term '
    "event risk.\n"
    '   - "Wait": a near-term event should pass first (for example earnings within 5 days '
    "or fresh news), or the signals are mixed.\n"
    '   - "Avoid": a serious risk, or no edge either way.\n'
    '5. Give a confidence: "low", "medium" or "high". Use "low" when key data is missing.\n\n'
    "Rules:\n"
    "- Use only the facts given. Do not invent numbers, dates, events or news.\n"
    '- Each point must name the fact it rests on (for example "earnings in 3 days").\n'
    "- Each point is at most 20 words. Plain words, no jargon.\n"
    "- If a side truly has fewer than 3 points, give fewer. Do not pad.\n"
    "- No disclaimers.\n\n"
    "Reply with only this JSON, no other text:\n"
    '{"bull": ["..."], "bear": ["..."], "verdict": "Long" | "Short" | "Wait" | "Avoid", '
    '"confidence": "low" | "medium" | "high", "summary": "one sentence, at most 25 words"}'
)

Ask = Callable[[AiConfig, str, str, float], AiAnswer]


@dataclass(frozen=True, slots=True)
class Review:
    """The reviewer's bull and bear points, verdict and confidence for one stock."""

    bull: tuple[str, ...]
    bear: tuple[str, ...]
    verdict: str
    confidence: str
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"bull": list(self.bull), "bear": list(self.bear), "verdict": self.verdict,
                "confidence": self.confidence, "summary": self.summary}


@dataclass(frozen=True, slots=True)
class ReviewRun:
    """One review request and reply, for the AI transcript."""

    facts: str
    reply: str
    review: Review | None
    seconds: float = 0.0


def price_line(closes: Sequence[float], highs: Sequence[float], lows: Sequence[float]) -> str:
    """"close 151.20; above 50-day (+3.1%); ...; 20-day range 138.50-158.90"; "" without bars."""
    if not closes:
        return ""
    last = closes[-1]
    parts = [f"close {last:.2f}"]
    for days in (50, 200):
        if len(closes) >= days:
            average = sum(closes[-days:]) / days
            side = "above" if last >= average else "below"
            parts.append(f"{side} {days}-day ({(last / average - 1) * 100:+.1f}%)")
    if highs and lows:
        parts.append(f"20-day range {min(lows[-20:]):.2f}-{max(highs[-20:]):.2f}")
    return "; ".join(parts)


def _analyst_line(ctx: StockContext) -> str:
    items = []
    for change in ctx.analyst_changes:
        words = _ACTION_WORDS.get(change.action, change.action)
        target = f" (target {change.target:.0f})" if change.target is not None else ""
        items.append(f"{change.day[5:10]} {change.firm} {words} {change.grade}".strip() + target)
    if ctx.analyst_target_pct is not None:
        items.append(f"average target {ctx.analyst_target_pct:+.0f}% vs price")
    return "; ".join(items)


def review_facts(
    symbol: str,
    today: date,
    price: str,
    ctx: StockContext | None,
    research: Research | None,
) -> str:
    """The facts sent to the reviewer (SRD-SCR-020.007); lines for missing parts left out.

    ``ctx`` must be the context before the ranking AI's news tone is applied.
    """
    lines = [f"Ticker: {symbol}", f"Today: {today.isoformat()}"]
    if price:
        lines.append(f"Price: {price}")
    if ctx is not None:
        lines += _context_lines(ctx)
    if research is not None:
        risk = f" Risk: {research.risk}" if research.risk else ""
        lines.append(f"Web research: {research.summary}{risk}")
    if ctx is not None and ctx.flags:
        lines.append("Red flags: " + "; ".join(ctx.flags))
    return "\n".join(lines)


def _context_lines(ctx: StockContext) -> list[str]:
    lines = []
    if ctx.earnings_days is not None:
        lines.append(f"Earnings: next {ctx.earnings_date} ({earnings_when(ctx.earnings_days)})")
    if ctx.eps_surprise_pct is not None:
        lines.append(f"Last EPS: {surprise_text(ctx.eps_surprise_pct)}")
    if ctx.sector_rank is not None and ctx.sector_move_pct is not None:
        lines.append(f"Sector: {ctx.sector}, #{ctx.sector_rank} of {ctx.sector_count}, "
                     f"{ctx.sector_move_pct:+.1f}% vs equal-weight (1 month)")
    if ctx.market:
        lines.append(f"Market: {_REGIME_TEXT.get(ctx.market, ctx.market)}")
    if fundamentals := fundamentals_text(ctx):
        lines.append(f"Fundamentals: {fundamentals}")
    if short := short_text(ctx):
        lines.append(f"Short interest: {short.removeprefix('short ')}")
    if analysts_text(ctx):
        lines.append(f"Analysts (30 days): {_analyst_line(ctx)}")
    if ctx.news:
        lines.append("Headlines (5 days):")
        lines += [f"  {h.published[5:10]} · {h.source} · {h.title}" for h in ctx.news]
    return lines


def _points(value: Any) -> tuple[str, ...]:
    items = value if isinstance(value, list) else []
    return tuple(str(item).strip() for item in items if str(item).strip())[:_MAX_POINTS]


def parse_review(text: str) -> Review | None:
    """The review in ``text``, or None when it has no readable JSON or verdict."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    verdict = str(data.get("verdict", "")).strip().capitalize()
    if verdict not in VERDICTS:
        return None
    confidence = str(data.get("confidence", "")).strip().lower()
    return Review(
        bull=_points(data.get("bull")),
        bear=_points(data.get("bear")),
        verdict=verdict,
        confidence=confidence if confidence in _CONFIDENCE else "low",
        summary=str(data.get("summary") or "").strip(),
    )


def review_picks(
    facts: Mapping[str, str],
    model: str,
    ask: Ask = ask_ai,
    workers: int = REVIEW_WORKERS,
) -> dict[str, ReviewRun]:
    """Review each stock from its facts alone (SRD-SCR-020.007–.008).

    Args:
        facts: Symbol → text from ``review_facts()``.
        model: Claude model for the CLI.
        ask: AI call, injectable for tests.
        workers: How many CLI runs at once.

    Returns:
        Symbol → request and reply, in input order; ``review`` is None when the reply
        failed or could not be read.
    """
    config = AiConfig(claude_model=model)

    def one(symbol: str) -> ReviewRun:
        answer = ask(config, REVIEW_INSTRUCTION, facts[symbol], REVIEW_TIMEOUT_S)
        review = None if answer.error else parse_review(answer.text)
        return ReviewRun(facts[symbol], answer.error or answer.text, review, answer.seconds)

    symbols = list(facts)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        runs = dict(zip(symbols, pool.map(one, symbols)))
    failed = sum(1 for run in runs.values() if run.review is None)
    if failed:
        _log.warning("[Screener] Bull vs bear review failed for %d of %d stock(s)",
                     failed, len(symbols))
    return runs
