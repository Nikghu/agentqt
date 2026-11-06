"""
Module: MD-MKT-005.011.M06 — market/risk_limits.py
Parent SRD: SRD-MKT-005.011

Hard risk limits for listed ideas. They are plain constants in code, kept out of every
file an AI employee reads or writes, so no prompt or answer can change them. The risk
check and the lead brief both apply them.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

MIN_TRIGGER_USD = 5.0
STOP_MIN_PCT = 1.0
STOP_MAX_PCT = 10.0
MAX_PER_SECTOR_SIDE = 3

_ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
             "ninth", "tenth")


@dataclass(frozen=True)
class ListedIdea:
    """One listed idea as the limits see it."""

    side: str
    symbol: str
    rank: int
    sector: str
    trigger: float | None
    stop: float | None


def _single_veto(idea: ListedIdea, rule_regime: str) -> str | None:
    if idea.side == "long" and rule_regime == "Downtrend":
        return "Long idea while the market is in a Downtrend"
    if idea.side == "short" and rule_regime == "Uptrend":
        return "Short idea while the market is in an Uptrend"
    if idea.trigger is None or idea.stop is None or idea.trigger <= 0:
        return "No trigger or stop"
    if idea.trigger < MIN_TRIGGER_USD:
        return f"Trigger is below ${MIN_TRIGGER_USD:.0f}"
    stop_pct = abs(idea.trigger - idea.stop) / idea.trigger * 100
    if stop_pct < STOP_MIN_PCT or stop_pct > STOP_MAX_PCT:
        return (f"Stop is {stop_pct:.1f}% from the trigger (allowed {STOP_MIN_PCT:.0f}% to "
                f"{STOP_MAX_PCT:.0f}%)")
    return None


def code_vetoes(ideas: Sequence[ListedIdea], rule_regime: str) -> dict[tuple[str, str], str]:
    """Return ``{(side, symbol): reason}`` for every idea that breaks a hard limit.

    The sector cap counts only ideas that pass the other limits, best rank first.

    Args:
        ideas: The day's listed ideas.
        rule_regime: The rule regime of the day (Uptrend, Choppy or Downtrend).
    """
    vetoes: dict[tuple[str, str], str] = {}
    per_sector: Counter[tuple[str, str]] = Counter()
    for idea in sorted(ideas, key=lambda i: (i.side, i.rank)):
        reason = _single_veto(idea, rule_regime)
        if reason is None:
            per_sector[(idea.side, idea.sector)] += 1
            count = per_sector[(idea.side, idea.sector)]
            if count > MAX_PER_SECTOR_SIDE:
                nth = _ORDINALS[count - 1] if count <= len(_ORDINALS) else f"{count}th"
                reason = f"{nth.capitalize()} idea in {idea.sector} on the {idea.side} side"
        if reason is not None:
            vetoes[(idea.side, idea.symbol)] = reason
    return vetoes
