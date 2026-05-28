"""
Module: MD-EXE-011.001.M07 — Strategy Engine public surface
Parent SRD: SRD-EXE-011.001 — SRD-EXE-011.019
"""
from __future__ import annotations

from ._context import _StrategyContext
from ._engine import StrategyEngine
from ._evaluator import ConditionEvaluator, EvaluatorError
from ._events import (
    StrategyEntered,
    StrategyErrored,
    StrategyEvent,
    StrategyExited,
    StrategySignalDropped,
    StrategySignalPending,
    StrategySquaredOff,
)
from ._protocols import (
    CanAllocateResult,
    EventBus,
    ExecutionSubmitter,
    FillEvent,
    RejectEvent,
    RiskValidator,
    ValidationResult,
)
from ._rex_counter import RexCounterRepository
from ._signals import Action, PendingSignalSink, TradeSignal

__all__ = [
    "Action",
    "CanAllocateResult",
    "ConditionEvaluator",
    "EvaluatorError",
    "EventBus",
    "ExecutionSubmitter",
    "FillEvent",
    "PendingSignalSink",
    "RejectEvent",
    "RexCounterRepository",
    "RiskValidator",
    "StrategyEngine",
    "StrategyEntered",
    "StrategyErrored",
    "StrategyEvent",
    "StrategyExited",
    "StrategySignalDropped",
    "StrategySignalPending",
    "StrategySquaredOff",
    "TradeSignal",
    "ValidationResult",
    "_StrategyContext",
]
