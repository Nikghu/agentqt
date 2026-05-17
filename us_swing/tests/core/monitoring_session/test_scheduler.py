"""Tests for MD-EXE-010.001.M01 — core/monitoring_session/_scheduler.py."""
from __future__ import annotations

from datetime import date, datetime
from typing import Callable
from unittest.mock import patch
from zoneinfo import ZoneInfo

from sqlalchemy import Engine

from us_swing.core.monitoring_session import (
    MonitoringCommand,
    MonitoringEventBus,
    ReconcileReport,
    build_default_service,
    build_scheduler,
)
from us_swing.core.monitoring_session._events import ReconcileCompleted
from us_swing.core.monitoring_session._scheduler import _ReconcileScheduler, _CRON_EXPR

_NY = ZoneInfo("America/New_York")
_T1 = date(2026, 5, 15)  # Friday


def _make_scheduler(
    engine: Engine,
    cron_register: Callable[[str, Callable[[], None]], None],
    clock: Callable[[], datetime] | None = None,
    today_provider: Callable[[], date] | None = None,
    filtered: frozenset[str] | None = None,
) -> tuple[_ReconcileScheduler, MonitoringCommand, MonitoringEventBus]:
    query, cmd, bus = build_default_service(
        engine,
        clock=clock,
        filtered_provider=(lambda _d, f=filtered or frozenset(): f) if filtered is not None else None,
    )
    sched = build_scheduler(
        command=cmd,
        bus=bus,
        cron_register=cron_register,
        clock=clock,
        today_provider=today_provider,
    )
    return sched, cmd, bus


# ── UT-EXE-010.001.M01.T01 ──────────────────────────────────────────────────


def test_start_registers_cron_expression(engine: Engine) -> None:
    """UT-EXE-010.001.M01.T01: start() registers a '15 9 * * MON-FRI' cron job."""
    registered: list[tuple[str, Callable[[], None]]] = []

    def _spy(expr: str, fn: Callable[[], None]) -> None:
        registered.append((expr, fn))

    sched, _, _ = _make_scheduler(engine, _spy)
    sched.start()

    assert len(registered) == 1
    expr, fn = registered[0]
    assert expr == _CRON_EXPR
    assert callable(fn)


# ── UT-EXE-010.001.M01.T02 ──────────────────────────────────────────────────


def test_maybe_run_on_startup_calls_reconcile_on_weekday(engine: Engine, seed_user: int) -> None:
    """UT-EXE-010.001.M01.T02: maybe_run_on_startup() invokes reconcile_preopen(today) when conditions hold."""
    # Friday 2026-05-15 at 10:30 ET.
    frozen_dt = datetime(2026, 5, 15, 10, 30, 0, tzinfo=_NY)


    sched, cmd, bus = _make_scheduler(
        engine,
        cron_register=lambda e, f: None,
        clock=lambda: frozen_dt,
        today_provider=lambda: _T1,
    )

    # Patch reconcile_preopen to record calls.
    reconcile_calls: list[date] = []
    original = cmd.reconcile_preopen  # type: ignore[attr-defined]

    def _spy(today: date) -> ReconcileReport:
        reconcile_calls.append(today)
        return original(today)

    with patch.object(cmd, "reconcile_preopen", _spy):
        sched.maybe_run_on_startup()

    assert len(reconcile_calls) == 1
    assert reconcile_calls[0] == _T1


# ── UT-EXE-010.001.M01.T03 ──────────────────────────────────────────────────


def test_maybe_run_on_startup_skips_weekend(engine: Engine) -> None:
    """UT-EXE-010.001.M01.T03: maybe_run_on_startup() returns None on weekends."""
    # Saturday 2026-05-16 at 10:30 ET.
    saturday_dt = datetime(2026, 5, 16, 10, 30, 0, tzinfo=_NY)
    saturday = date(2026, 5, 16)

    sched, cmd, bus = _make_scheduler(
        engine,
        cron_register=lambda e, f: None,
        clock=lambda: saturday_dt,
        today_provider=lambda: saturday,
    )

    reconcile_calls: list[date] = []
    with patch.object(cmd, "reconcile_preopen", lambda d: reconcile_calls.append(d)):
        result = sched.maybe_run_on_startup()

    assert result is None
    assert reconcile_calls == []


# ── UT-EXE-010.001.M01.T04 ──────────────────────────────────────────────────


def test_maybe_run_on_startup_skips_outside_window(engine: Engine) -> None:
    """UT-EXE-010.001.M01.T04: maybe_run_on_startup() returns None outside [09:15, 16:00] ET."""
    # Friday at 08:30 ET — before the window.
    early_dt = datetime(2026, 5, 15, 8, 30, 0, tzinfo=_NY)

    sched, cmd, bus = _make_scheduler(
        engine,
        cron_register=lambda e, f: None,
        clock=lambda: early_dt,
        today_provider=lambda: _T1,
    )

    reconcile_calls: list[date] = []
    with patch.object(cmd, "reconcile_preopen", lambda d: reconcile_calls.append(d)):
        result = sched.maybe_run_on_startup()

    assert result is None
    assert reconcile_calls == []


# ── UT-EXE-010.001.M01.T05 ──────────────────────────────────────────────────


def test_maybe_run_on_startup_skips_when_already_seen(engine: Engine, seed_user: int) -> None:
    """UT-EXE-010.001.M01.T05: maybe_run_on_startup() skips when ReconcileCompleted already observed."""
    frozen_dt = datetime(2026, 5, 15, 10, 30, 0, tzinfo=_NY)

    sched, cmd, bus = _make_scheduler(
        engine,
        cron_register=lambda e, f: None,
        clock=lambda: frozen_dt,
        today_provider=lambda: _T1,
    )

    # Simulate a prior ReconcileCompleted event being published.
    from us_swing.core.monitoring_session import ReconcileReport
    from uuid import uuid4

    dummy_report = ReconcileReport(
        filtered_n=0,
        carryover_n=0,
        skipped_n=0,
        evicted_n=0,
        evicted_symbols=(),
        duration_ms=1,
    )
    bus.publish(ReconcileCompleted(
        event_id=uuid4().hex,
        occurred_at="2026-05-15T09:15:00",
        report=dummy_report,
    ))

    reconcile_calls: list[date] = []
    with patch.object(cmd, "reconcile_preopen", lambda d: reconcile_calls.append(d)):
        result = sched.maybe_run_on_startup()

    assert result is None
    assert reconcile_calls == []
