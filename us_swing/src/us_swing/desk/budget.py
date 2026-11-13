"""
Module: MD-DSK-004.003.M12 — desk/budget.py
Parent SRD: SRD-DSK-004.003
Also: SRD-DSK-011.030 (``Part.message``: the thread starter pays)
Also: SRD-DSK-004.004 — Claude CLI token cap and calls per day
Also: SRD-DSK-004.007 (50/20/30 split), SRD-DSK-004.009 (part and ticket caps, the raiser
pays for a ticket), SRD-DSK-004.010 (refusal log)

Decides, from the activity records, whether one more model call is allowed.
Only OpenRouter (API) calls carry cost; Claude Code CLI runs on the user's
subscription, so it counts only tokens against a daily cap. On top, each employee's daily
tokens are split into a plan, a market-hours and a research part.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_research import SHARES
from us_swing.desk.recorder import Recorder, ny_now

log = logging.getLogger(__name__)

TRIES_PER_CALL = 4  # primary twice, then backup twice
PartName = Literal["plan", "market", "research"]
_PART_LABELS = {"plan": "plan", "market": "market-hours", "research": "research"}


@dataclass(frozen=True)
class Part:
    """The budget part a call is paid from; ``payer`` is the employee whose part it is."""

    name: PartName
    payer: str
    payer_name: str
    tokens_per_day: int
    ticket: int | None = None
    ticket_cap: int | None = None
    message: int | None = None


def part_cap(part: Part) -> int:
    """Tokens a day in this part of the payer's budget."""
    return int(part.tokens_per_day * SHARES[part.name])


class Budget:
    """Checks the monthly budget, the employee's cap and the daily limits."""

    def __init__(self, recorder: Recorder, settings: DeskAiSettings,
                 clock: Callable[[], datetime] = ny_now) -> None:
        """Use ``recorder`` for the sums and ``clock`` for New York time."""
        self._rec = recorder
        self._settings = settings
        self._clock = clock

    def refusal(self, employee_id: str, name: str, monthly_cap: float, calls_per_day: int,
                source: str, part: Part | None = None) -> str | None:
        """Return why a call is refused, or ``None`` when it is allowed.

        Sums use the employee's stable id; ``name`` is only for the message.
        """
        now = self._clock()
        month, day = now.strftime("%Y-%m"), now.strftime("%Y-%m-%d")
        budget = self._settings.monthly_budget_usd
        if source == "openrouter" and self._rec.month_cost(month) >= budget:
            return f"monthly budget USD {budget:.2f} used up"
        if source == "openrouter" and self._rec.month_cost(month, employee_id) >= monthly_cap:
            return f"{name} monthly cap USD {monthly_cap:.2f} used up"
        if self._rec.day_tries(day, employee_id) >= calls_per_day * TRIES_PER_CALL:
            return f"{name} reached {calls_per_day} call(s) for today"
        tokens_cap = self._settings.claude_tokens_per_day
        if source == "claude" and self._rec.day_tokens(day, "claude") >= tokens_cap:
            return f"Claude Code CLI reached {tokens_cap:,} tokens for today"
        return None if part is None else self._part_refusal(part, day)

    def _part_refusal(self, part: Part, day: str) -> str | None:
        used, cap = self._rec.part_tokens(day, part.payer, part.name), part_cap(part)
        if used >= cap:
            label = _PART_LABELS[part.name]
            log.warning("[Budget] %s: %s tokens for today used up (%s of %s)", part.payer_name,
                        label, f"{used:,}", f"{cap:,}")
            return f"{part.payer_name} {label} tokens for today used up"
        if part.ticket is not None and part.ticket_cap is not None:
            if self._rec.ticket_tokens(part.ticket) >= part.ticket_cap:
                return f"ticket {part.ticket} reached its cap of {part.ticket_cap:,} tokens"
        return None
