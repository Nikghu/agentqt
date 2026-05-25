"""
Module: MD-EXE-011.001.M07 — PassthroughRiskValidator
Parent SRD: SRD-EXE-011.011
"""
from __future__ import annotations

from us_swing.execution.strategy_engine._protocols import (
    CanAllocateResult,
    ValidationResult,
)
from us_swing.execution.strategy_engine._signals import TradeSignal


class PassthroughRiskValidator:
    """Always approves; capital checks added in a future phase."""

    def validate(self, signal: TradeSignal) -> ValidationResult:
        return ValidationResult(ok=True, qty=signal.qty_recommended)

    def can_allocate(self, strategy_id: str, capital_max_pct: int) -> CanAllocateResult:
        return CanAllocateResult(ok=True)
