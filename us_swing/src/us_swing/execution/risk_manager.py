"""
Module: MD-EXE-001.001.M01 — RiskManager
Parent SRD: SRD-EXE-001.001, SRD-EXE-001.002, SRD-EXE-005.004
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from us_swing.data.models import AccountState, RiskConfig
from us_swing.execution.strategy_engine._protocols import (
    CanAllocateResult,
    ValidationResult,
)
from us_swing.execution.strategy_engine._signals import TradeSignal

if TYPE_CHECKING:
    from us_swing.execution.position_tracker import PositionTracker

log = logging.getLogger(__name__)


class RiskManager:
    """Synchronous risk gate: position sizing, capital checks, circuit-breaker guard."""

    def __init__(
        self,
        config: RiskConfig,
        account_provider: Callable[[], AccountState],
        cb_state_provider: Callable[[], bool],
        user_id: int,
        tracker: PositionTracker | None = None,
    ) -> None:
        self._config = config
        self._account_provider = account_provider
        self._cb_state_provider = cb_state_provider
        self._user_id = user_id
        self._tracker = tracker

    # ── RiskValidator protocol ────────────────────────────────────────────────

    def validate(self, signal: TradeSignal) -> ValidationResult:
        """Full gate: resolves account + CB state, validates, computes qty."""
        account = self._account_provider()
        cb_active = self._cb_state_provider()
        result = self.validate_signal(signal, account, cb_active)
        if not result.ok:
            return result
        qty = self.calculate_position_size(signal, account)
        return ValidationResult(ok=True, qty=qty)

    def can_allocate(self, strategy_id: str, capital_max_pct: int) -> CanAllocateResult:
        """Check if a strategy has room under its per-strategy capital cap."""
        if self._tracker is None:
            return CanAllocateResult(ok=True)
        account = self._account_provider()
        limit = account.equity * capital_max_pct / 100
        deployed = sum(
            p.average_price * p.quantity
            for p in self._tracker.get_all(self._user_id)
            if p.strategy_id == strategy_id
        )
        if deployed >= limit:
            return CanAllocateResult(
                ok=False,
                reason=f"strategy {strategy_id!r} at capital limit",
            )
        return CanAllocateResult(ok=True)

    # ── Public helpers ────────────────────────────────────────────────────────

    def validate_signal(
        self,
        signal: TradeSignal,
        account_state: AccountState,
        cb_active: bool,
    ) -> ValidationResult:
        """Three-check gate; synchronous, no IBKR calls."""
        if cb_active:
            return ValidationResult(ok=False, reason="circuit breaker active")

        entry = signal.entry_price or 0.0
        qty = self.calculate_position_size(signal, account_state)
        proposed = entry * qty

        if proposed > self._config.max_position_value:
            return ValidationResult(
                ok=False,
                reason=(
                    f"position value {proposed:.2f} exceeds limit"
                    f" {self._config.max_position_value:.2f}"
                ),
            )

        deployed = account_state.open_position_value
        allowed = account_state.equity * self._config.max_allocation_pct / 100
        if deployed + proposed > allowed:
            return ValidationResult(
                ok=False,
                reason=(
                    f"capital allocation limit: deployed {deployed:.2f} + required"
                    f" {proposed:.2f} > allowed {allowed:.2f}"
                ),
            )

        return ValidationResult(ok=True)

    def calculate_position_size(
        self,
        signal: TradeSignal,
        account_state: AccountState,
    ) -> int:
        """floor(equity*risk_pct / risk_per_share), capped at max_position_value/entry."""
        entry = signal.entry_price or 0.0
        stop = signal.stop_loss or 0.0
        if entry <= 0 or stop <= 0 or entry == stop:
            return 0
        risk_per_share = abs(entry - stop)
        risk_dollars = account_state.equity * self._config.risk_per_trade_pct / 100
        formula_qty = math.floor(risk_dollars / risk_per_share)
        cap = math.floor(self._config.max_position_value / entry)
        return min(formula_qty, cap)

    def can_enter_new(
        self,
        signal: TradeSignal,
        account_state: AccountState,
        user_id: int,
    ) -> bool:
        """True if projected position fits within user's max_allocation_pct."""
        entry = signal.entry_price or 0.0
        if entry <= 0:
            return False
        qty = self.calculate_position_size(signal, account_state)
        required = entry * qty
        positions = self._tracker.get_all(user_id) if self._tracker else []
        deployed = sum(p.average_price * p.quantity for p in positions)
        allowed = account_state.equity * self._config.max_allocation_pct / 100
        return deployed + required <= allowed
