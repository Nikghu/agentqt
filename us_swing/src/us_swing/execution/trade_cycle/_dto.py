"""
Module: MD-EXE-012.001.M02 — execution/trade_cycle/_dto.py
Parent SRD: SRD-EXE-012.010, SRD-EXE-012.011

Frozen, slotted, version-stamped DTOs and enum frozensets shared across
the ``trade_cycle`` package boundary.  Validation helpers are used by
``_repository`` and ``_service`` to fail fast on invalid string-enum
values; SQLite enforces nothing here.
"""
from __future__ import annotations

from dataclasses import dataclass

CYCLE_STATES:   frozenset[str] = frozenset({"OPENING", "OPEN", "CLOSING", "CLOSED", "ABORTED"})
EXIT_REASONS:   frozenset[str] = frozenset({
    "strategy", "hard_sl", "target", "trailing_sl",
    "end_time", "manual", "emergency",
})
TARGET_TYPES:   frozenset[str] = frozenset({"fixed", "trailing"})
STOPLOSS_TYPES: frozenset[str] = frozenset({"fixed", "trailing"})
TRAILING_MODES: frozenset[str] = frozenset({"$", "%"})

NON_TERMINAL_STATES: frozenset[str] = frozenset({"OPENING", "OPEN", "CLOSING"})
TERMINAL_STATES:     frozenset[str] = frozenset({"CLOSED", "ABORTED"})


@dataclass(frozen=True, slots=True)
class CycleSnapshot:
    """Immutable read view of a ``trade_cycles`` row."""

    schema_version:      int   = 1
    cycle_id:            int   = 0
    strategy_id:         str   = ""
    symbol:              str   = ""
    user_id:             int   = 0
    monitoring_session_date: str = ""
    state:               str   = "OPENING"
    entry_time:          str   = ""
    entry_price:         float = 0.0
    entry_qty:           int   = 0
    entry_order_id:      str   = ""
    hard_stop_loss:      float = 0.0
    target_price:        float | None = None
    target_type:         str   = "fixed"
    stoploss_type:       str   = "fixed"
    trailing_mode:       str | None   = None
    trailing_offset:     float | None = None
    current_price:       float | None = None
    current_pnl_usd:     float | None = None
    current_pnl_pct:     float | None = None
    highest_price_seen:  float | None = None
    trailing_stop_level: float | None = None
    effective_stop:      float | None = None
    last_updated_at:     str | None   = None
    exit_time:           str | None   = None
    exit_price:          float | None = None
    exit_qty:            int | None   = None
    exit_order_id:       str | None   = None
    exit_reason:         str | None   = None
    realized_pnl_usd:    float | None = None
    realized_pnl_pct:    float | None = None
    opened_at:           str          = ""
    closed_at:           str | None   = None


class InvariantViolation(ValueError):
    """Raised by ``update_risk`` when the requested edit fails validation."""


class InvalidStateTransitionError(RuntimeError):
    """Raised by the repository when an illegal state move is requested."""


class DuplicateOpenCycleError(RuntimeError):
    """Raised by ``insert_open`` when a non-terminal cycle already exists
    for the same ``(strategy_id, symbol)`` pair."""


def validate_state(value: str) -> str:
    if value not in CYCLE_STATES:
        raise ValueError(f"unknown cycle state: {value!r}")
    return value


def validate_exit_reason(value: str) -> str:
    if value not in EXIT_REASONS:
        raise ValueError(f"unknown exit reason: {value!r}")
    return value


def validate_target_type(value: str) -> str:
    if value not in TARGET_TYPES:
        raise ValueError(f"unknown target_type: {value!r}")
    return value


def validate_stoploss_type(value: str) -> str:
    if value not in STOPLOSS_TYPES:
        raise ValueError(f"unknown stoploss_type: {value!r}")
    return value


def validate_trailing_mode(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in TRAILING_MODES:
        raise ValueError(f"unknown trailing_mode: {value!r}")
    return value


__all__ = [
    "CycleSnapshot",
    "CYCLE_STATES",
    "EXIT_REASONS",
    "TARGET_TYPES",
    "STOPLOSS_TYPES",
    "TRAILING_MODES",
    "NON_TERMINAL_STATES",
    "TERMINAL_STATES",
    "InvariantViolation",
    "InvalidStateTransitionError",
    "DuplicateOpenCycleError",
    "validate_state",
    "validate_exit_reason",
    "validate_target_type",
    "validate_stoploss_type",
    "validate_trailing_mode",
]
