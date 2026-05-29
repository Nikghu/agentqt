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
from sqlalchemy import Engine, text

from us_swing.core.monitoring_session import (
    FillEvent,
    LifecycleState,
    MonitoringCommand,
    MonitoringEventBus,
    MonitoringQuery,
    ReconcileError,
    ReconcileReport,
    Side,
    SymbolEnteredPosition,
    SymbolEvicted,
    SymbolExitedPosition,
    SymbolPositionScaled,
    SymbolStartedMonitoring,
    TradeOrigin,
    build_default_service,
)
from us_swing.db.schema import monitoring_session
from us_swing.execution import ExecutionEnums


_T0 = date(2026, 5, 14)   # "yesterday"
_T1 = date(2026, 5, 15)   # "today"
_T0_S = _T0.isoformat()
_T1_S = _T1.isoformat()


def _buy_fill(
    symbol: str = "A",
    trade_id: str = "t1",
    qty: int = 100,
    price: float = 50.0,
    origin: TradeOrigin = TradeOrigin.SYSTEM,
    user_id: int = 1,
    order_state: ExecutionEnums.BuyOrderState | None = None,
) -> FillEvent:
    return FillEvent(
        symbol=symbol,
        trade_id=trade_id,
        side=Side.BUY,
        qty=qty,
        price=price,
        fill_time="2026-05-14T14:00:00Z",
        origin=origin,
        user_id=user_id,
        order_state=order_state,
    )


def _sell_fill(
    symbol: str = "A",
    trade_id: str = "t2",
    qty: int = 100,
    price: float = 55.0,
    origin: TradeOrigin = TradeOrigin.SYSTEM,
    user_id: int = 1,
    order_state: ExecutionEnums.SellOrderState | None = None,
) -> FillEvent:
    return FillEvent(
        symbol=symbol,
        trade_id=trade_id,
        side=Side.SELL,
        qty=qty,
        price=price,
        fill_time="2026-05-14T15:00:00Z",
        origin=origin,
        user_id=user_id,
        order_state=order_state,
    )


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


# ── UT-EXE-009.002.M02.T04 ──────────────────────────────────────────────────


def test_first_system_buy_transitions_monitoring_to_entered(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T04: First system BUY fill flips earliest MONITORING row -> ENTERED + anchor + event."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.on_fill(_buy_fill("A", trade_id="t1", qty=100))

    entered_evts = [e for e in events if isinstance(e, SymbolEnteredPosition)]
    assert len(entered_evts) == 1
    assert entered_evts[0].symbol == "A"
    assert entered_evts[0].anchor_session_date == _T0_S

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.ENTERED

    with engine.connect() as conn:
        anchor = conn.execute(
            text("SELECT anchor_session_date FROM positions WHERE symbol='A'")
        ).scalar()
    assert anchor == _T0_S


# ── UT-EXE-009.002.M02.T05 ──────────────────────────────────────────────────


def test_scale_in_buy_publishes_scaled_event(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T05: Scale-in BUY leaves ledger unchanged, publishes SymbolPositionScaled."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.on_fill(_buy_fill("A", trade_id="t1", qty=100))
    cmd.on_fill(_buy_fill("A", trade_id="t2", qty=50))

    scaled_evts = [e for e in events if isinstance(e, SymbolPositionScaled)]
    assert len(scaled_evts) == 1
    assert scaled_evts[0].symbol == "A"

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.ENTERED


# ── UT-EXE-009.002.M02.T06 ──────────────────────────────────────────────────


def test_partial_sell_leaves_ledger_entered(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T06: Partial SELL leaves ledger state unchanged, publishes SymbolPositionScaled."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.on_fill(_buy_fill("A", trade_id="t1", qty=150))
    cmd.on_fill(_sell_fill("A", trade_id="t2", qty=70))

    scaled_evts = [e for e in events if isinstance(e, SymbolPositionScaled)]
    assert len(scaled_evts) == 1

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.ENTERED


# ── UT-EXE-009.002.M02.T07 ──────────────────────────────────────────────────


def test_closing_sell_flips_ledger_to_exited(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T07: Closing SELL flips ledger -> EXITED, publishes SymbolExitedPosition."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.on_fill(_buy_fill("A", trade_id="t1", qty=80))
    cmd.on_fill(_sell_fill("A", trade_id="t2", qty=80))

    exited_evts = [e for e in events if isinstance(e, SymbolExitedPosition)]
    assert len(exited_evts) == 1

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.EXITED
    assert row.exited_at is not None


# ── UT-EXE-009.002.M02.T08 ──────────────────────────────────────────────────


def test_manual_fill_is_ledger_noop(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T08: Manual-origin fill is a ledger no-op."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    cmd.on_screener_results(make_screener_result(passed=["A"]))
    row_before = query.session_for(_T0, "A")

    cmd.on_fill(_buy_fill("A", trade_id="tm1", origin=TradeOrigin.MANUAL))

    # Ledger row must not have changed.
    row_after = query.session_for(_T0, "A")
    assert row_before is not None
    assert row_after is not None
    assert row_after.lifecycle_state == row_before.lifecycle_state

    # No lifecycle events published.
    lifecycle_evts = [
        e for e in events
        if isinstance(e, (SymbolEnteredPosition, SymbolPositionScaled, SymbolExitedPosition))
    ]
    assert lifecycle_evts == []

    # But the trade row must have been inserted.
    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT COUNT(*) FROM trades WHERE trade_origin='manual'")
        ).scalar()
    assert cnt == 1


# ── UT-EXE-009.002.M02.T09 ──────────────────────────────────────────────────


def test_system_buy_with_no_monitoring_row_logs_error(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """UT-EXE-009.002.M02.T09: System BUY with no MONITORING row logs ERROR and defensively records trade."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    with caplog.at_level(logging.ERROR):
        cmd.on_fill(_buy_fill("UNKNOWN", trade_id="t1"))

    assert any("[Lifecycle]" in r.message for r in caplog.records if r.levelno == logging.ERROR)

    # Trade must have been inserted with monitoring_session_date=NULL.
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT monitoring_session_date FROM trades WHERE symbol='UNKNOWN'")
        ).first()
    assert row is not None
    assert row[0] is None

    # No lifecycle event published.
    assert not any(isinstance(e, SymbolEnteredPosition) for e in events)


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
    cmd0.on_fill(_buy_fill("A", trade_id="t1"))

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
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T11: keep_set(today) returns filtered | carryover."""
    # T0: establish open system position for C.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"C"})
    cmd0.on_screener_results(make_screener_result(passed=["C"], run_timestamp="2026-05-14T13:30:00Z"))
    cmd0.on_fill(_buy_fill("C", trade_id="tc1"))

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
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T13: check_invariant() returns ok=True when ledger and positions agree."""
    query, cmd, bus = build_service(today=_T0)
    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.on_fill(_buy_fill("A", trade_id="t1"))

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
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T15: reconcile_preopen evicts SKIPPED-not-in-keep-set, retains the rest."""
    # T0: monitor A (and enter), B, C.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"A", "B", "C"})
    event_collector(bus0)
    cmd0.on_screener_results(
        make_screener_result(passed=["A", "B", "C"], run_timestamp="2026-05-14T13:30:00Z")
    )
    cmd0.on_fill(_buy_fill("A", trade_id="t1"))

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
    seed_user: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """UT-EXE-009.002.M02.T21: ReconcileReport carries expected counts and INFO log emitted."""
    # T0: monitor A (enter), B, C.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"A", "B", "C"})
    cmd0.on_screener_results(
        make_screener_result(passed=["A", "B", "C"], run_timestamp="2026-05-14T13:30:00Z")
    )
    cmd0.on_fill(_buy_fill("A", trade_id="t1"))
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


# ── UT-EXE-009.002.M02.T22 ──────────────────────────────────────────────────


def test_entered_set_equals_open_positions_through_fills(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    seed_user: int,
) -> None:
    """UT-EXE-009.002.M02.T22: ENTERED ledger set equals open system positions across a fill sequence."""
    query, cmd, bus = build_service(today=_T0)
    cmd.on_screener_results(make_screener_result(passed=["A", "B"]))

    # Before any fill: nothing entered, no open positions, invariant holds.
    assert query.open_system_positions() == frozenset()
    assert query.check_invariant().ok is True

    # First system BUY fill per symbol drives MONITORING -> ENTERED.
    cmd.on_fill(_buy_fill("A", trade_id="ta", qty=100))
    cmd.on_fill(_buy_fill("B", trade_id="tb", qty=100))

    row_a = query.session_for(_T0, "A")
    row_b = query.session_for(_T0, "B")
    assert row_a is not None and row_a.lifecycle_state == LifecycleState.ENTERED
    assert row_b is not None and row_b.lifecycle_state == LifecycleState.ENTERED
    assert query.open_system_positions() == frozenset({"A", "B"})
    assert query.check_invariant().ok is True

    # Closing SELL on A drives ENTERED -> EXITED; A leaves both sets together.
    cmd.on_fill(_sell_fill("A", trade_id="ta2", qty=100))

    row_a_after = query.session_for(_T0, "A")
    assert row_a_after is not None and row_a_after.lifecycle_state == LifecycleState.EXITED
    assert query.open_system_positions() == frozenset({"B"})
    report = query.check_invariant()
    assert report.ok is True
    assert report.only_in_a == () and report.only_in_b == ()


# ── SRD-EXE-014.008 — order-state-gated lifecycle transitions ────────────────


def test_filled_buy_flips_monitoring_to_entered(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-014.008.M01.T01: A fully FILLED system BUY flips MONITORING -> ENTERED."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.on_fill(_buy_fill("A", trade_id="t1", qty=100,
                          order_state=ExecutionEnums.BuyOrderState.FILLED))

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.ENTERED
    assert any(isinstance(e, SymbolEnteredPosition) for e in events)


def test_partial_buy_holds_monitoring(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-014.008.M01.T02: A PARTIAL_FILLED entry BUY records the position but leaves the row MONITORING."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.on_fill(_buy_fill("A", trade_id="t1", qty=40,
                          order_state=ExecutionEnums.BuyOrderState.PARTIAL_FILLED))

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.MONITORING
    assert not any(isinstance(e, SymbolEnteredPosition) for e in events)
    assert any(isinstance(e, SymbolPositionScaled) for e in events)


def test_partial_then_filled_buy_enters(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-014.008.M01.T03: The FILLED fill that completes a partial entry flips MONITORING -> ENTERED."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.on_fill(_buy_fill("A", trade_id="t1", qty=40,
                          order_state=ExecutionEnums.BuyOrderState.PARTIAL_FILLED))
    cmd.on_fill(_buy_fill("A", trade_id="t2", qty=60,
                          order_state=ExecutionEnums.BuyOrderState.FILLED))

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.ENTERED
    assert any(isinstance(e, SymbolEnteredPosition) for e in events)


def test_filled_sell_closing_flips_to_exited(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-014.008.M01.T04: A fully FILLED SELL that closes the position flips ENTERED -> EXITED."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.on_fill(_buy_fill("A", trade_id="t1", qty=100,
                          order_state=ExecutionEnums.BuyOrderState.FILLED))
    cmd.on_fill(_sell_fill("A", trade_id="t2", qty=100,
                           order_state=ExecutionEnums.SellOrderState.FILLED))

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.EXITED
    assert any(isinstance(e, SymbolExitedPosition) for e in events)


def test_unfilled_sell_does_not_exit_even_when_quantity_zero(
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_user: int,
) -> None:
    """UT-EXE-014.008.M01.T05: A SELL whose order is not fully FILLED does not flip ENTERED -> EXITED."""
    query, cmd, bus = build_service(today=_T0)
    events = event_collector(bus)

    cmd.on_screener_results(make_screener_result(passed=["A"]))
    cmd.on_fill(_buy_fill("A", trade_id="t1", qty=100,
                          order_state=ExecutionEnums.BuyOrderState.FILLED))
    cmd.on_fill(_sell_fill("A", trade_id="t2", qty=100,
                           order_state=ExecutionEnums.SellOrderState.PARTIAL_FILLED))

    row = query.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.ENTERED
    assert not any(isinstance(e, SymbolExitedPosition) for e in events)
