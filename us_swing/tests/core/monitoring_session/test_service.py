"""Tests for MD-EXE-009.002.M02 — core/monitoring_session/_service.py."""
from __future__ import annotations

import logging
import threading
import time
from datetime import date
from typing import Callable
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy import Engine

from us_swing.core.monitoring_session import (
    LifecycleState,
    MonitoringCommand,
    MonitoringEventBus,
    MonitoringQuery,
    ReconcileError,
    ReconcileReport,
    SymbolEvicted,
    SymbolStartedMonitoring,
    build_default_service,
)
from us_swing.db.schema import monitoring_session


_T0 = date(2026, 5, 14)   # "yesterday"
_T1 = date(2026, 5, 15)   # "today"
_T0_S = _T0.isoformat()
_T1_S = _T1.isoformat()


# ── UT-EXE-009.002.M02.T01 ──────────────────────────────────────────────────


def test_on_screener_results_inserts_and_publishes(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T01: on_screener_results inserts MONITORING rows and publishes SymbolStartedMonitoring."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    result = make_screener_result(passed=["A", "B"], failed=["C"])
    keep = cmd.on_screener_results(result)

    assert keep.filtered == frozenset({"A", "B"})
    started = [e for e in events if isinstance(e, SymbolStartedMonitoring)]
    assert len(started) == 2
    assert {e.symbol for e in started} == {"A", "B"}


# ── UT-EXE-009.002.M02.T02 ──────────────────────────────────────────────────


def test_on_screener_results_idempotent(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T02: on_screener_results is idempotent on same-day re-run."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)
    result = make_screener_result(passed=["A"])

    cmd.on_screener_results(result)
    before = len(events)
    cmd.on_screener_results(result)

    # Second call must produce no new events.
    assert len(events) == before


# ── UT-EXE-009.002.M02.T03 ──────────────────────────────────────────────────


def test_on_screener_results_ignores_failed_symbols(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T03: on_screener_results ignores passed=False symbols."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    result = make_screener_result(failed=["A", "B"])
    keep = cmd.on_screener_results(result)

    assert keep.filtered == frozenset()
    assert events == []


# ── FO-EXE-016 — ingestion-driven lifecycle seam ────────────────────────────


def test_mark_entered_flips_monitoring_to_entered(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    seed_user: int,
) -> None:
    """mark_entered flips the earliest open MONITORING row to ENTERED."""
    query, cmd, bus = build_service(today=_T0)
    cmd.on_screener_results(make_screener_result(passed=["A"]))

    cmd.mark_entered("A", "2026-05-14T14:00:00Z", "t1")

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.ENTERED


def test_mark_entered_is_noop_without_monitoring_row(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    seed_user: int,
) -> None:
    """mark_entered is a no-op when the symbol has no open MONITORING row."""
    query, cmd, bus = build_service(today=_T0)
    cmd.mark_entered("UNKNOWN", "2026-05-14T14:00:00Z", "t1")
    assert query.session_for(_T0, "UNKNOWN") is None


def test_mark_exited_flips_entered_to_exited(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    seed_user: int,
) -> None:
    """mark_exited flips an ENTERED row to EXITED on cycle close."""
    query, cmd, bus = build_service(today=_T0)
    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.mark_entered("A", "2026-05-14T14:00:00Z", "t1")

    cmd.mark_exited("A", "2026-05-14T15:00:00Z")

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.EXITED
    assert row.exited_at is not None


# ── UT-EXE-009.002.M02.T10 ──────────────────────────────────────────────────


def test_duplicate_filter_creates_new_monitoring_row(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T10: Re-emitted symbol stays MONITORING while prior anchor stays ENTERED."""
    # T0: enter A.
    query0, cmd0, bus0 = build_service(today=_T0)
    event_collector(bus0)
    cmd0.on_screener_results(make_screener_result(passed=["A"], run_timestamp="2026-05-14T13:30:00Z"))
    cmd0.mark_entered("A", "2026-05-14T14:00:00Z", "t1")

    row_t0 = query0.session_for(_T0, "A")
    assert row_t0 is not None
    assert row_t0.lifecycle_state == LifecycleState.ENTERED

    # T1: re-emit A — must create a NEW MONITORING row, old stays ENTERED.
    query1, cmd1, bus1 = build_service(today=_T1)
    events1 = event_collector(bus1)
    cmd1.on_screener_results(make_screener_result(passed=["A"], run_timestamp="2026-05-15T13:30:00Z"))

    # Old row still ENTERED.
    row_t0_after = query1.session_for(_T0, "A")
    assert row_t0_after is not None
    assert row_t0_after.lifecycle_state == LifecycleState.ENTERED

    # New row for T1 in MONITORING.
    row_t1 = query1.session_for(_T1, "A")
    assert row_t1 is not None
    assert row_t1.lifecycle_state == LifecycleState.MONITORING

    started_t1 = [e for e in events1 if isinstance(e, SymbolStartedMonitoring)]
    assert len(started_t1) == 1
    assert started_t1[0].session_date == _T1_S


# ── UT-EXE-009.002.M02.T11 ──────────────────────────────────────────────────


def test_keep_set_returns_filtered_and_carryover(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    open_cycle: Callable[..., None],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T11: keep_set(today) returns filtered | carryover."""
    # T0: establish an open trade cycle for C (the live position surface).
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"C"})
    cmd0.on_screener_results(make_screener_result(passed=["C"], run_timestamp="2026-05-14T13:30:00Z"))
    open_cycle("C")

    # T1: screener returns [A, B]; carryover should include C.
    query1, cmd1, bus1 = build_service(today=_T1, filtered={"A", "B"})
    ks = query1.keep_set(_T1)

    assert ks.filtered == frozenset({"A", "B"})
    assert "C" in ks.carryover


# ── UT-EXE-009.002.M02.T12 ──────────────────────────────────────────────────


def test_keep_set_empty_filtered_when_no_screener_run(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T12: keep_set(today) returns empty filtered when no screener run for today."""
    # No filtered_provider override — defaults to empty frozenset.
    query, cmd, bus = build_service(today=_T1)
    ks = query.keep_set(_T1)

    assert ks.filtered == frozenset()


# ── UT-EXE-009.002.M02.T13 ──────────────────────────────────────────────────


def test_check_invariant_ok_when_ledger_matches_positions(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    open_cycle: Callable[..., None],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T13: check_invariant() returns ok=True when ledger and open cycles agree."""
    query, cmd, bus = build_service(today=_T0)
    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.mark_entered("A", "2026-05-14T14:00:00Z", "t1")
    open_cycle("A")

    report = query.check_invariant()

    assert report.ok is True
    assert report.only_in_a == ()
    assert report.only_in_b == ()


# ── UT-EXE-009.002.M02.T14 ──────────────────────────────────────────────────


def test_check_invariant_flags_entered_without_position(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    seed_user: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """UT-EXE-009.002.M02.T14: check_invariant() flags symbol in ledger ENTERED but not in positions."""
    query, cmd, bus = build_service(today=_T0)

    # Force-insert an ENTERED ledger row without a matching position.
    with engine.begin() as conn:
        conn.execute(
            monitoring_session.insert().values(
                session_date="2026-05-14",
                symbol="X",
                preset_id="p",
                run_timestamp="ts",
                added_at="2026-05-14T13:30:00Z",
                lifecycle_state=LifecycleState.ENTERED.value,
            )
        )

    with caplog.at_level(logging.ERROR):
        report = query.check_invariant()

    assert report.ok is False
    assert "X" in report.only_in_a
    assert any("[Lifecycle]" in r.message for r in caplog.records if r.levelno == logging.ERROR)


# ── UT-EXE-009.002.M02.T15 ──────────────────────────────────────────────────


def test_reconcile_preopen_evicts_stale_non_keepset(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_price: Callable[[str, int], None],
    open_cycle: Callable[..., None],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T15: reconcile_preopen evicts SKIPPED-not-in-keep-set, retains the rest."""
    # T0: monitor A (and enter), B, C.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"A", "B", "C"})
    event_collector(bus0)
    cmd0.on_screener_results(
        make_screener_result(passed=["A", "B", "C"], run_timestamp="2026-05-14T13:30:00Z")
    )
    cmd0.mark_entered("A", "2026-05-14T14:00:00Z", "t1")
    open_cycle("A")

    seed_price("B", 3)
    seed_price("C", 3)

    # T1: reconcile — only A and D are in today's filtered set.
    query1, cmd1, bus1 = build_service(today=_T1, filtered={"A", "D"})
    events1 = event_collector(bus1)
    report = cmd1.reconcile_preopen(_T1)

    assert report.evicted_n == 2
    assert set(report.evicted_symbols) == {"B", "C"}

    evicted_evts = [e for e in events1 if isinstance(e, SymbolEvicted)]
    assert {e.symbol for e in evicted_evts} == {"B", "C"}

    reconcile_evts = [e for e in events1 if isinstance(e, __import__(
        "us_swing.core.monitoring_session", fromlist=["ReconcileCompleted"]
    ).ReconcileCompleted)]
    assert len(reconcile_evts) == 1


# ── UT-EXE-009.002.M02.T16 ──────────────────────────────────────────────────


def test_reconcile_preopen_idempotent(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_price: Callable[[str, int], None],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T16: reconcile_preopen is idempotent for the same today."""
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"B"})
    cmd0.on_screener_results(make_screener_result(passed=["B"], run_timestamp="2026-05-14T13:30:00Z"))
    seed_price("B", 2)

    query1, cmd1, bus1 = build_service(today=_T1, filtered=set())
    events1 = event_collector(bus1)
    cmd1.reconcile_preopen(_T1)

    before = len([e for e in events1 if isinstance(e, SymbolEvicted)])

    # Second run.
    cmd1.reconcile_preopen(_T1)
    after = len([e for e in events1 if isinstance(e, SymbolEvicted)])

    # No additional evictions.
    assert after == before


# ── UT-EXE-009.002.M02.T17 ──────────────────────────────────────────────────


def test_invariant_violation_aborts_symbol_eviction(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    seed_price: Callable[[str, int], None],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T17: Invariant violation aborts that symbol's eviction."""
    # Force X into ENTERED state without a position to create an invariant breach.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"X"})
    cmd0.on_screener_results(make_screener_result(passed=["X"], run_timestamp="2026-05-14T13:30:00Z"))

    # Manually transition to ENTERED (without upsert_position) to create the breach.
    with engine.begin() as conn:
        conn.execute(
            monitoring_session.update()
            .where(
                monitoring_session.c.session_date == _T0_S,
                monitoring_session.c.symbol == "X",
            )
            .values(lifecycle_state=LifecycleState.ENTERED.value, entered_at="2026-05-14T14:00:00Z")
        )

    seed_price("X", 2)

    # SRD-EXE-010.003 — reconcile must detect the asymmetric case
    # (X in `entered_symbols` but not in `open_system_position_symbols`) and
    # add a `ReconcileError("X","invariant_violation",1)` to the report.
    # X's price rows stay intact because R3 protects it from the evict set.

    query1, cmd1, bus1 = build_service(today=_T1, filtered=set())
    report = cmd1.reconcile_preopen(_T1)

    assert "X" not in report.evicted_symbols
    assert ReconcileError("X", "invariant_violation", 1) in report.errors


# ── UT-EXE-009.002.M02.T18 ──────────────────────────────────────────────────


def test_concurrent_reconcile_returns_sentinel(tmp_path: object) -> None:
    """UT-EXE-009.002.M02.T18: Concurrent reconcile_preopen returns sentinel report."""
    from us_swing.db.schema import create_schema as _cs

    # Use a file-based SQLite so multiple threads can share it.
    db_path = str(tmp_path) + "/test_concurrent.db"  # type: ignore[operator]
    file_eng = sa.create_engine(f"sqlite:///{db_path}", future=True)
    _cs(file_eng)

    with file_eng.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users (user_id, username, display_name, ibkr_client_id) "
                "VALUES (1, 'sys', 'System', 11)"
            )
        )

    query, cmd, bus = build_default_service(
        file_eng,
        today_provider=lambda: _T1,
    )

    reports: list[ReconcileReport] = []
    reports_lock = threading.Lock()
    first_entered = threading.Event()

    original_bulk_skip = cmd._repo.bulk_skip_stale_monitoring  # type: ignore[attr-defined]

    def _slow_bulk_skip(today: date) -> int:
        first_entered.set()
        time.sleep(0.15)  # hold lock long enough for t2 to attempt acquire
        return original_bulk_skip(today)

    def _call_slow() -> None:
        with patch.object(cmd._repo, "bulk_skip_stale_monitoring", _slow_bulk_skip):  # type: ignore[attr-defined]
            r = cmd.reconcile_preopen(_T1)
        with reports_lock:
            reports.append(r)

    def _call_fast() -> None:
        first_entered.wait(timeout=5)
        r = cmd.reconcile_preopen(_T1)
        with reports_lock:
            reports.append(r)

    t1 = threading.Thread(target=_call_slow)
    t2 = threading.Thread(target=_call_fast)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    file_eng.dispose()

    assert len(reports) == 2
    sentinels = [
        r for r in reports
        if any(e.message == "already_running" for e in r.errors)
    ]
    assert len(sentinels) >= 1, "Expected at least one sentinel report from concurrent call"


# ── UT-EXE-009.002.M02.T19 ──────────────────────────────────────────────────


def test_per_symbol_failure_isolates_other_symbols(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_price: Callable[[str, int], None],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T19: Per-symbol failure isolates other symbols."""
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"Y", "Z"})
    cmd0.on_screener_results(
        make_screener_result(passed=["Y", "Z"], run_timestamp="2026-05-14T13:30:00Z")
    )
    seed_price("Y", 2)
    seed_price("Z", 2)

    query1, cmd1, bus1 = build_service(today=_T1, filtered=set())
    events1 = event_collector(bus1)

    from us_swing.core.monitoring_session._repository import MonitoringRepository

    call_count: list[int] = [0]
    original_evict = MonitoringRepository.evict_symbol_atomic

    def _patched_evict(self: MonitoringRepository, symbol: str, **kwargs: object) -> tuple[str, ...]:
        call_count[0] += 1
        if symbol == "Y":
            raise Exception("permanent failure for Y")
        return original_evict(self, symbol=symbol, **kwargs)

    with patch.object(MonitoringRepository, "evict_symbol_atomic", _patched_evict):
        report = cmd1.reconcile_preopen(_T1)

    assert len(report.errors) == 1
    assert report.errors[0].symbol == "Y"
    assert report.evicted_n == 1
    assert "Z" in report.evicted_symbols

    evicted_evts = [e for e in events1 if isinstance(e, SymbolEvicted)]
    assert len(evicted_evts) == 1
    assert evicted_evts[0].symbol == "Z"


# ── UT-EXE-009.002.M02.T20 ──────────────────────────────────────────────────


def test_retry_once_on_operational_error_succeeds(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_price: Callable[[str, int], None],
    seed_user: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UT-EXE-009.002.M02.T20: Retry-once on transient OperationalError succeeds on second attempt."""
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"R"})
    cmd0.on_screener_results(
        make_screener_result(passed=["R"], run_timestamp="2026-05-14T13:30:00Z")
    )
    seed_price("R", 2)

    query1, cmd1, bus1 = build_service(today=_T1, filtered=set())
    event_collector(bus1)

    from us_swing.core.monitoring_session._repository import MonitoringRepository

    attempt_count: list[int] = [0]
    original_evict = MonitoringRepository.evict_symbol_atomic

    def _flaky_evict(self: MonitoringRepository, symbol: str, **kwargs: object) -> tuple[str, ...]:
        attempt_count[0] += 1
        if attempt_count[0] == 1:
            raise sa.exc.OperationalError("transient", {}, Exception())
        return original_evict(self, symbol=symbol, **kwargs)

    # Monkeypatch time.sleep to skip the 200 ms backoff.
    monkeypatch.setattr("us_swing.core.monitoring_session._service.time.sleep", lambda _: None)

    with patch.object(MonitoringRepository, "evict_symbol_atomic", _flaky_evict):
        report = cmd1.reconcile_preopen(_T1)

    assert report.errors == ()
    assert report.evicted_n == 1
    assert "R" in report.evicted_symbols


# ── UT-EXE-009.002.M02.T21 ──────────────────────────────────────────────────


def test_reconcile_report_counts_and_info_log(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_price: Callable[[str, int], None],
    open_cycle: Callable[..., None],
    seed_user: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """UT-EXE-009.002.M02.T21: ReconcileReport carries expected counts and INFO log emitted."""
    # T0: monitor A (enter), B, C.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"A", "B", "C"})
    cmd0.on_screener_results(
        make_screener_result(passed=["A", "B", "C"], run_timestamp="2026-05-14T13:30:00Z")
    )
    cmd0.mark_entered("A", "2026-05-14T14:00:00Z", "t1")
    open_cycle("A")
    seed_price("B", 2)
    seed_price("C", 2)

    # T1: filtered={A, D}.
    query1, cmd1, bus1 = build_service(today=_T1, filtered={"A", "D"})

    with caplog.at_level(logging.INFO):
        report = cmd1.reconcile_preopen(_T1)

    # UTCD: filtered_n==2, carryover_n==1, skipped_n>=2, evicted_n==2
    assert report.filtered_n == 2
    assert report.carryover_n == 1
    assert report.skipped_n >= 2
    assert report.evicted_n == 2
    assert report.duration_ms > 0

    info_lifecycle = [
        r for r in caplog.records
        if r.levelno == logging.INFO and "[Lifecycle]" in r.message
    ]
    assert len(info_lifecycle) == 1


# ── Order-state-gated lifecycle (SRD-EXE-014.008) now lives in OrderIngestion
# (FO-EXE-016); partial-vs-filled gating is covered by the ingestion-layer tests.
