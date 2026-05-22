"""
Module: MD-EXE-012.001.M03 — execution/trade_cycle/_events.py
Parent SRD: SRD-EXE-012.012

Seven frozen event dataclasses forming the ``TradeCycleEvent`` sealed
union.  Events are published on the existing FO-EXE-009 monitoring event
bus (``MonitoringEventBus`` Protocol); the trade-cycle package does NOT
own a separate bus.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from us_swing.execution.trade_cycle._dto import CycleSnapshot


@dataclass(frozen=True, slots=True)
class CycleOpened:
    cycle_id:       int
    symbol:         str
    strategy_id:    str
    snapshot:       CycleSnapshot
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class CycleUpdated:
    cycle_id:       int
    symbol:         str
    snapshot:       CycleSnapshot
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class ExitTrigger:
    cycle_id:       int
    symbol:         str
    reason:         str
    trigger_price:  float
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class CycleClosing:
    cycle_id:       int
    symbol:         str
    reason:         str
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class CycleClosed:
    cycle_id:         int
    symbol:           str
    exit_reason:      str
    realized_pnl_usd: float
    realized_pnl_pct: float
    snapshot:         CycleSnapshot
    schema_version:   int = 1


@dataclass(frozen=True, slots=True)
class CycleAborted:
    cycle_id:       int
    symbol:         str
    reason:         str
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class RiskUpdated:
    cycle_id:       int
    symbol:         str
    snapshot:       CycleSnapshot
    schema_version: int = 1


TradeCycleEvent = Union[
    CycleOpened,
    CycleUpdated,
    ExitTrigger,
    CycleClosing,
    CycleClosed,
    CycleAborted,
    RiskUpdated,
]


__all__ = [
    "TradeCycleEvent",
    "CycleOpened",
    "CycleUpdated",
    "ExitTrigger",
    "CycleClosing",
    "CycleClosed",
    "CycleAborted",
    "RiskUpdated",
]
