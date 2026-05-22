"""
Module: MD-EXE-011.001.M04 (dispatch protocols)
Parent SRD: SRD-EXE-011.008 — SRD-EXE-011.011

Protocol-typed dependencies consumed by `_Router`. Concrete
implementations (`RiskManager`, `ExecutionRouter`, FO-EXE-009 bus)
live outside this package; binding happens at engine construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ._events import StrategyEvent
from ._signals import TradeSignal


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    reason: str = ""
    qty: int = 0
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class CanAllocateResult:
    ok: bool
    reason: str = ""
    schema_version: int = 1


class RiskValidator(Protocol):
    """Synchronous risk gate consumed by the router."""

    def validate(self, signal: TradeSignal) -> ValidationResult: ...
    def can_allocate(self, strategy_id: str, capital_max_pct: int) -> CanAllocateResult: ...


class ExecutionSubmitter(Protocol):
    """Synchronous broker-side dispatch. Returns an order id or None on rejection."""

    def submit(self, signal: TradeSignal, qty: int) -> int | None: ...


class EventBus(Protocol):
    """Minimal publish-only surface; consumers attach via the FO-EXE-009 bus."""

    def publish(self, event: StrategyEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class FillEvent:
    """Broker fill payload routed in from FO-EXE-002.

    A single dataclass covers both entry and exit fills; the cycle they
    belong to is identified by `strategy_id` + `symbol` + `is_entry`.
    """

    strategy_id: str
    symbol: str
    is_entry: bool
    fill_price: float
    fill_qty: int
    order_id: int
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class RejectEvent:
    """Broker reject payload routed in from FO-EXE-002."""

    strategy_id: str
    symbol: str
    is_entry: bool
    reason: str
    schema_version: int = 1
