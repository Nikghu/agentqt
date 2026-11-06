"""
Module: MD-DSK-004.003.M12 — desk/budget.py
Parent SRD: SRD-DSK-004.003
Also: SRD-DSK-004.004 — Claude CLI token cap and calls per day

Decides, from the activity records, whether one more model call is allowed.
Only OpenRouter (API) calls carry cost; Claude Code CLI runs on the user's
subscription, so it counts only tokens against a daily cap.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.desk.recorder import Recorder, ny_now

TRIES_PER_CALL = 4  # primary twice, then backup twice


class Budget:
    """Checks the monthly budget, the employee's cap and the daily limits."""

    def __init__(self, recorder: Recorder, settings: DeskAiSettings,
                 clock: Callable[[], datetime] = ny_now) -> None:
        """Use ``recorder`` for the sums and ``clock`` for New York time."""
        self._rec = recorder
        self._settings = settings
        self._clock = clock

    def refusal(self, employee_id: str, name: str, monthly_cap: float, calls_per_day: int,
                source: str) -> str | None:
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
        return None
