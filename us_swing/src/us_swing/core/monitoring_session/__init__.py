"""
Module: MD-EXE-009.002.M03 — core/monitoring_session/__init__.py
Parent SRD: SRD-EXE-009.010, SRD-EXE-009.012

Public surface of the monitoring-session package.  This is the ONLY module
consumers should import from.  Concrete classes (``MonitoringSessionService``,
``MonitoringRepository``, ``_InProcessBus``) are deliberately NOT re-exported —
type-annotate against the Protocols and use the factory.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from sqlalchemy import Engine

from us_swing.core.monitoring_session._dto import (
    FillEvent,
    InvariantReport,
    KeepSet,
    MonitoringSessionRow,
    PositionSnapshot,
    ReconcileError,
    ReconcileReport,
)
from us_swing.core.monitoring_session._enums import (
    Side,
    TradeOrigin,
)
from us_swing.core.monitoring_session._events import (
    MonitoringEvent,
    ReconcileCompleted,
    SymbolEnteredPosition,
    SymbolEvicted,
    SymbolExitedPosition,
    SymbolPositionScaled,
    SymbolSkipped,
    SymbolStartedMonitoring,
)
from us_swing.core.monitoring_session._protocols import (
    MonitoringCommand,
    MonitoringEventBus,
    MonitoringQuery,
    Subscription,
)
from us_swing.core.monitoring_session._scheduler import _ReconcileScheduler
from us_swing.execution import ExecutionEnums

# Re-exported from the canonical ExecutionEnums container — the monitoring
# ledger's public DTO surface (MonitoringSessionRow.lifecycle_state) is typed
# against it.  See SRD-EXE-009.012.
LifecycleState = ExecutionEnums.LifecycleState


def build_default_service(
    engine: Engine,
    *,
    today_provider: Callable[[], date] | None                  = None,
    clock: Callable[[], datetime] | None                       = None,
    filtered_provider: Callable[[date], frozenset[str]] | None = None,
) -> tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]:
    """Wire up a default ``MonitoringSessionService`` with an in-process event bus.

    A single concrete instance implements both ``MonitoringQuery`` and
    ``MonitoringCommand`` and is returned three times so the caller can hold a
    narrow Protocol reference per consumer.

    Args:
        engine: SQLAlchemy engine for the project DB.
        today_provider: Override for trading-date resolution (tests).
        clock: Override for UTC clock (tests).
        filtered_provider: Callable returning today's filtered symbol set.
            Defaults to an empty frozenset — wire to
            ``ScreenerResultsStorage.load_for_execution(...)`` at the
            ``AppService`` integration site.

    Returns:
        ``(query, command, bus)`` — the first two reference the same concrete
        object; the bus is the same instance subscribed to by all consumers.
    """
    # Local imports keep the underscore-prefixed concrete classes out of the
    # package's public surface.
    from us_swing.core.monitoring_session._events     import _InProcessBus
    from us_swing.core.monitoring_session._repository import MonitoringRepository
    from us_swing.core.monitoring_session._service    import MonitoringSessionService

    bus  = _InProcessBus()
    repo = MonitoringRepository(engine)
    svc  = MonitoringSessionService(
        repo              = repo,
        bus               = bus,
        clock             = clock,
        today_provider    = today_provider,
        filtered_provider = filtered_provider,
    )
    return svc, svc, bus


def wire_cycle_ledger_projection(
    bus: MonitoringEventBus,
    command: MonitoringCommand,
    terminal_event_types: tuple[type, ...],
    *,
    clock: Callable[[], datetime] | None = None,
) -> None:
    """Flip a symbol's ledger row to EXITED whenever its trade cycle ends.

    Wired at the composition root. ``terminal_event_types`` are the trade-cycle
    terminal event classes (``CycleClosed`` / ``CycleAborted``), injected so this
    package stays ignorant of the ``execution`` tool. Each event must carry a
    ``symbol`` attribute. ``mark_exited`` is a no-op when no ENTERED row exists,
    so the projection is idempotent and safe for manual/unscreened trades — it
    only ever closes a ledger row that the position store has already ended,
    which is what prevents orphaned ENTERED rows.

    Args:
        bus: The shared in-process lifecycle event bus.
        command: The monitoring command surface to drive.
        terminal_event_types: Trade-cycle event classes that mean "cycle ended".
        clock: Override for the exit-timestamp clock (tests).
    """
    now = clock or (lambda: datetime.now())

    def _handler(event: object) -> None:
        symbol = getattr(event, "symbol", None)
        if symbol is None:
            return
        command.mark_exited(symbol, now().isoformat(timespec="seconds"))

    for event_type in terminal_event_types:
        bus.subscribe(event_type, _handler)


def build_scheduler(
    command: MonitoringCommand,
    bus: MonitoringEventBus,
    cron_register: Callable[[str, Callable[[], None]], None],
    *,
    clock: Callable[[], datetime] | None      = None,
    today_provider: Callable[[], date] | None = None,
) -> _ReconcileScheduler:
    """Construct the pre-open reconcile scheduler.

    ``cron_register`` should be supplied by the application's existing
    scheduler service — typically ``app_service.scheduler.register_cron``.
    """
    return _ReconcileScheduler(
        command         = command,
        bus             = bus,
        cron_register   = cron_register,
        clock           = clock,
        today_provider  = today_provider,
    )


__all__ = [
    # Protocols
    "MonitoringQuery",
    "MonitoringCommand",
    "MonitoringEventBus",
    "Subscription",
    # DTOs
    "KeepSet",
    "ReconcileReport",
    "ReconcileError",
    "MonitoringSessionRow",
    "FillEvent",
    "InvariantReport",
    "PositionSnapshot",
    # Enums
    "LifecycleState",
    "TradeOrigin",
    "Side",
    # Events (sealed union)
    "MonitoringEvent",
    "SymbolStartedMonitoring",
    "SymbolEnteredPosition",
    "SymbolPositionScaled",
    "SymbolExitedPosition",
    "SymbolSkipped",
    "SymbolEvicted",
    "ReconcileCompleted",
    # Factories
    "build_default_service",
    "build_scheduler",
    "wire_cycle_ledger_projection",
]
