"""
Module: MD-EXE-012.002.M03 — execution/trade_cycle/__init__.py
Parent SRD: SRD-EXE-012.002, .010, .011, .012

Public surface of the trade-cycle ledger package.  Consumers MUST
type-annotate against the ``TradeCycleQuery`` / ``TradeCycleCommand``
Protocols re-exported here; the concrete service and repository are
intentionally NOT re-exported.

The trade-cycle service publishes its events on the existing FO-EXE-009
``MonitoringEventBus``; this package does not own a bus implementation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy import Engine

from us_swing.core.monitoring_session import MonitoringEventBus
from us_swing.execution.trade_cycle._dto import (
    CYCLE_STATES,
    EXIT_REASONS,
    NON_TERMINAL_STATES,
    STOPLOSS_TYPES,
    TARGET_TYPES,
    TERMINAL_STATES,
    TRAILING_MODES,
    CycleSnapshot,
    DuplicateOpenCycleError,
    InvalidStateTransitionError,
    InvariantViolation,
)
from us_swing.execution.trade_cycle._events import (
    CycleAborted,
    CycleClosed,
    CycleClosing,
    CycleOpened,
    CycleUpdated,
    ExitTrigger,
    RiskUpdated,
    TradeCycleEvent,
)
from us_swing.execution.trade_cycle._protocols import (
    TradeCycleCommand,
    TradeCycleQuery,
)


def build_default_service(
    engine: Engine,
    bus: MonitoringEventBus,
    *,
    set_active_symbols: Callable[[frozenset[str]], None] | None = None,
    clock: Callable[[], datetime] | None                        = None,
) -> tuple[TradeCycleQuery, TradeCycleCommand]:
    """Wire up a ``TradeCycleService`` against ``engine`` and ``bus``.

    A single concrete instance implements both Protocols and is returned
    twice so the caller can hold a narrow reference per consumer.

    Args:
        engine: SQLAlchemy engine for the project DB.
        bus: The FO-EXE-009 monitoring event bus.  Re-used so trade-cycle
            and lifecycle events share one subscription surface.
        set_active_symbols: Optional callback invoked with the union of
            symbols held by open cycles.  Wire to
            ``LiveTickWorker.set_contracts(...)`` at the AppService
            integration site.
        clock: Optional UTC-clock override for tests.

    Returns:
        ``(query, command)`` — the same concrete service object.
    """
    from us_swing.execution.trade_cycle._repository import TradeCycleRepository
    from us_swing.execution.trade_cycle._service import TradeCycleService

    repo = TradeCycleRepository(engine)
    svc  = TradeCycleService(
        repo               = repo,
        bus                = bus,
        set_active_symbols = set_active_symbols,
        clock              = clock,
    )
    return svc, svc


__all__ = [
    "TradeCycleQuery",
    "TradeCycleCommand",
    "MonitoringEventBus",
    "CycleSnapshot",
    "TradeCycleEvent",
    "CycleOpened",
    "CycleUpdated",
    "ExitTrigger",
    "CycleClosing",
    "CycleClosed",
    "CycleAborted",
    "RiskUpdated",
    "InvariantViolation",
    "InvalidStateTransitionError",
    "DuplicateOpenCycleError",
    "CYCLE_STATES",
    "NON_TERMINAL_STATES",
    "TERMINAL_STATES",
    "EXIT_REASONS",
    "TARGET_TYPES",
    "STOPLOSS_TYPES",
    "TRAILING_MODES",
    "build_default_service",
]
