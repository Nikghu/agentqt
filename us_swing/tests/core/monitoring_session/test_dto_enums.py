"""Tests for MD-EXE-009.001.M01 — core/monitoring_session/_dto.py + _enums.py."""
from __future__ import annotations

import dataclasses

import pytest

from us_swing.core.monitoring_session import (
    FillEvent,
    InvariantReport,
    KeepSet,
    LifecycleState,
    MonitoringSessionRow,
    ReconcileError,
    ReconcileReport,
    Side,
    TradeOrigin,
)


# ── UT-EXE-009.001.M01.T01 ──────────────────────────────────────────────────


def test_dtos_are_frozen_and_slotted() -> None:
    """UT-EXE-009.001.M01.T01: Every DTO is frozen and slotted."""
    today_s = "2026-05-14"

    instances = [
        KeepSet(
            filtered=frozenset({"A"}),
            carryover=frozenset(),
            as_of=__import__("datetime").date(2026, 5, 14),
        ),
        ReconcileReport(
            filtered_n=1,
            carryover_n=0,
            skipped_n=0,
            evicted_n=0,
            evicted_symbols=(),
            duration_ms=10,
        ),
        MonitoringSessionRow(
            session_date=today_s,
            symbol="A",
            preset_id="p",
            run_timestamp="2026-05-14T13:30:00Z",
            added_at="2026-05-14T13:30:00Z",
            lifecycle_state=LifecycleState.MONITORING,
        ),
        FillEvent(
            symbol="A",
            trade_id="t1",
            side=Side.BUY,
            qty=100,
            price=50.0,
            fill_time="2026-05-14T14:00:00Z",
            origin=TradeOrigin.SYSTEM,
            user_id=1,
        ),
        InvariantReport(ok=True),
        ReconcileError(symbol="X", message="err"),
    ]

    for inst in instances:
        # Verify __slots__ is declared (class attribute on a slotted dataclass).
        cls = type(inst)
        assert hasattr(cls, "__slots__"), f"{cls.__name__} missing __slots__"
        # Verify frozen — use the public assignment path which goes through
        # dataclass's __setattr__ and raises FrozenInstanceError.
        first_field = next(f.name for f in dataclasses.fields(inst))  # type: ignore[arg-type]
        with pytest.raises(dataclasses.FrozenInstanceError):
            # Direct attribute assignment must trigger the frozen guard.
            inst.__class__.__setattr__(inst, first_field, None)  # type: ignore[misc]


# ── UT-EXE-009.001.M02.T01 ──────────────────────────────────────────────────


def test_dtos_expose_schema_version_one() -> None:
    """UT-EXE-009.001.M02.T01: Every DTO exposes schema_version: int = 1."""
    today_s = "2026-05-14"
    dt = __import__("datetime").date(2026, 5, 14)

    instances = [
        KeepSet(filtered=frozenset(), carryover=frozenset(), as_of=dt),
        ReconcileReport(
            filtered_n=0,
            carryover_n=0,
            skipped_n=0,
            evicted_n=0,
            evicted_symbols=(),
            duration_ms=0,
        ),
        MonitoringSessionRow(
            session_date=today_s,
            symbol="A",
            preset_id="p",
            run_timestamp="2026-05-14T13:30:00Z",
            added_at="2026-05-14T13:30:00Z",
            lifecycle_state=LifecycleState.MONITORING,
        ),
        FillEvent(
            symbol="A",
            trade_id="t1",
            side=Side.BUY,
            qty=100,
            price=50.0,
            fill_time="2026-05-14T14:00:00Z",
            origin=TradeOrigin.SYSTEM,
        ),
        InvariantReport(ok=True),
        ReconcileError(symbol="X", message="err"),
    ]

    for inst in instances:
        assert inst.schema_version == 1, (
            f"{type(inst).__name__}.schema_version != 1"
        )


# ── UT-EXE-009.001.M03.T01 ──────────────────────────────────────────────────


def test_frozen_dto_mutation_raises() -> None:
    """UT-EXE-009.001.M03.T01: Mutation attempt fails on a frozen DTO."""
    dt = __import__("datetime").date(2026, 5, 14)
    ks = KeepSet(filtered=frozenset({"A"}), carryover=frozenset(), as_of=dt)

    with pytest.raises(dataclasses.FrozenInstanceError):
        ks.filtered = frozenset({"X"})  # type: ignore[misc]


# ── UT-EXE-009.001.M04.T01 ──────────────────────────────────────────────────


def test_enum_round_trip_raw_strings() -> None:
    """UT-EXE-009.001.M04.T01: LifecycleState, TradeOrigin, Side round-trip raw strings."""
    ls = LifecycleState("ENTERED")
    to = TradeOrigin("system")
    sd = Side("BUY")

    assert ls is LifecycleState.ENTERED
    assert ls.value == "ENTERED"

    assert to is TradeOrigin.SYSTEM
    assert to.value == "system"

    assert sd is Side.BUY
    assert sd.value == "BUY"
