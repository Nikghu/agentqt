"""
Module: MD-EXE-011.001.M07 — Strategy Engine public surface
Parent SRD: SRD-EXE-011.001 — SRD-EXE-011.015
"""
from __future__ import annotations

from ._context import _CycleState, _StrategyContext
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
    "_CycleState",
    "_StrategyContext",
]
