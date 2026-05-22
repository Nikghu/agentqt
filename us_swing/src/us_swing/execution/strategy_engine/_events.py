"""
Module: MD-EXE-011.001.M05 — Sealed StrategyEvent union
Parent SRD: SRD-EXE-011.015
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from ._signals import TradeSignal


@dataclass(frozen=True, slots=True)
class StrategyEntered:
    strategy_id: str
    symbol: str
    entry_price: float
    qty: int
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class StrategyExited:
    strategy_id: str
    symbol: str
    exit_price: float
    qty: int
    reason: str
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class StrategySquaredOff:
    strategy_id: str
    symbol: str
    reason: str
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class StrategyErrored:
    strategy_id: str
    symbol: str | None
    message: str
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class StrategySignalDropped:
    signal: TradeSignal
    reason: str
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class StrategySignalPending:
    signal: TradeSignal
    schema_version: int = 1


StrategyEvent = Union[
    StrategyEntered,
    StrategyExited,
    StrategySquaredOff,
    StrategyErrored,
    StrategySignalDropped,
    StrategySignalPending,
]
