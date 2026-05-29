"""
Module: MD-EXE-009.001.M01 — core/monitoring_session/_dto.py
Parent SRD: SRD-EXE-009.012

Frozen, slotted, version-stamped data transfer objects shared across the
package boundary.  Every cross-module payload carries ``schema_version: int``
so consumers can branch on protocol evolution.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from us_swing.core.monitoring_session._enums import Side, TradeOrigin
from us_swing.execution import ExecutionEnums


@dataclass(frozen=True, slots=True)
class KeepSet:
    """Authoritative answer to 'which symbols should have candles today'."""

    filtered:       frozenset[str]
    carryover:      frozenset[str]
    as_of:          date
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class ReconcileError:
    symbol:         str
    message:        str
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class ReconcileReport:
    filtered_n:      int
    carryover_n:     int
    skipped_n:       int
    evicted_n:       int
    evicted_symbols: tuple[str, ...]
    duration_ms:     int
    errors:          tuple[ReconcileError, ...] = ()
    schema_version:  int = 1


@dataclass(frozen=True, slots=True)
class MonitoringSessionRow:
    """One row of the ledger.  Mirrors the ``monitoring_session`` table."""

    session_date:    str             # YYYY-MM-DD
    symbol:          str
    preset_id:       str
    run_timestamp:   str             # ISO-8601 UTC
    added_at:        str             # ISO-8601 UTC
    lifecycle_state: ExecutionEnums.LifecycleState
    entered_at:      str | None      = None
    exited_at:       str | None      = None
    evicted_at:      str | None      = None
    trade_id:        str | None      = None
    schema_version:  int             = 1


@dataclass(frozen=True, slots=True)
class FillEvent:
    """Order-fill payload routed to ``MonitoringCommand.on_fill``."""

    symbol:         str
    trade_id:       str
    side:           Side
    qty:            int
    price:          float
    fill_time:      str              # ISO-8601 UTC
    origin:         TradeOrigin
    order_state:    ExecutionEnums.BuyOrderState | ExecutionEnums.SellOrderState | None = None
    user_id:        int              = 0
    schema_version: int              = 1


@dataclass(frozen=True, slots=True)
class InvariantReport:
    """Result of `MonitoringQuery.check_invariant()`."""

    ok:             bool
    only_in_a:      tuple[str, ...]  = ()   # in ledger ENTERED, not in open positions
    only_in_b:      tuple[str, ...]  = ()   # in open positions, not in ledger ENTERED
    schema_version: int              = 1


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """Post-fill view of a position, returned by the repository so the service
    can decide whether the fill closed the position."""

    symbol:              str
    quantity:            int
    average_price:       float
    state:               str         # FO-EXE-005 state machine value
    origin:              TradeOrigin
    anchor_session_date: str | None
    realised_pnl:        float       = 0.0
    schema_version:      int         = 1
