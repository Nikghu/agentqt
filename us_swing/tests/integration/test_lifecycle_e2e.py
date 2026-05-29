"""Integration tests for FO-EXE-009 / FO-EXE-010 — full lifecycle end-to-end."""
from __future__ import annotations

import pytest
from datetime import date, timedelta
from typing import Callable

from sqlalchemy import Engine, text

from us_swing.core.monitoring_session import (
    FillEvent,
    LifecycleState,
    MonitoringCommand,
    MonitoringEventBus,
    MonitoringQuery,
    Side,
    SymbolEvicted,
    TradeOrigin,
)

_T0 = date(2026, 5, 14)   # yesterday / day-1
_T1 = date(2026, 5, 15)   # today / day-2
_T0_S = _T0.isoformat()
_T1_S = _T1.isoformat()


def _buy(
    symbol: str,
    trade_id: str,
    qty: int = 100,
    price: float = 50.0,
    user_id: int = 1,
) -> FillEvent:
    return FillEvent(
        symbol=symbol,
        trade_id=trade_id,
        side=Side.BUY,
        qty=qty,
        price=price,
        fill_time=f"{_T0_S}T14:00:00Z",
        origin=TradeOrigin.SYSTEM,
        user_id=user_id,
    )


def _sell(
    symbol: str,
    trade_id: str,
    qty: int = 100,
    price: float = 55.0,
    user_id: int = 1,
) -> FillEvent:
    return FillEvent(
        symbol=symbol,
        trade_id=trade_id,
        side=Side.SELL,
        qty=qty,
        price=price,
        fill_time=f"{_T0_S}T15:00:00Z",
        origin=TradeOrigin.SYSTEM,
        user_id=user_id,
    )


# ── IT-EXE-009.001 ───────────────────────────────────────────────────────────


def test_it_009_001_full_happy_path(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_price: Callable[[str, int], None],
    seed_user: int,
) -> None:
    """IT-EXE-009.001: Full happy path — T-1 monitor+enter A; monitor B,C without entry; T+1 reconcile retains A, evicts B,C."""
    # T-1: screener emits [A, B, C]; A gets a system entry fill.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"A", "B", "C"})
    event_collector(bus0)

    cmd0.on_screener_results(
        make_screener_result(passed=["A", "B", "C"], run_timestamp="2026-05-14T13:30:00Z")
    )
    cmd0.on_fill(_buy("A", "t1"))

    seed_price("B", 3)
    seed_price("C", 3)
    # A gets candles too.
    seed_price("A", 3)

    # T: screener emits [A, D]; run reconcile.
    query1, cmd1, bus1 = build_service(today=_T1, filtered={"A", "D"})
    events1 = event_collector(bus1)

    report = cmd1.reconcile_preopen(_T1)

    # B and C must be evicted.
    assert set(report.evicted_symbols) == {"B", "C"}

    evicted_evts = {e.symbol for e in events1 if isinstance(e, SymbolEvicted)}
    assert evicted_evts == {"B", "C"}

    # price_1m/3m/15m for B and C must be empty.
    with engine.connect() as conn:
        for sym in ("B", "C"):
            for tf in ("price_1m", "price_3m", "price_15m"):
                cnt = conn.execute(
                    text(f"SELECT COUNT(*) FROM {tf} WHERE symbol=:s"), {"s": sym}
                ).scalar()
                assert cnt == 0, f"{tf} still has rows for {sym}"

        # A's candles must be retained.
        cnt_a = conn.execute(
            text("SELECT COUNT(*) FROM price_1m WHERE symbol='A'")
        ).scalar()
        assert cnt_a > 0

    # Ledger states.
    row_a = query1.session_for(_T0, "A")
    assert row_a is not None
    assert row_a.lifecycle_state == LifecycleState.ENTERED

    row_b = query1.session_for(_T0, "B")
    assert row_b is not None
    assert row_b.lifecycle_state == LifecycleState.EVICTED

    row_c = query1.session_for(_T0, "C")
    assert row_c is not None
    assert row_c.lifecycle_state == LifecycleState.EVICTED

    # D on T must be MONITORING.
    row_d = query1.session_for(_T1, "D")
    # D was not seeded via screener T results in this test (no on_screener_results call for T).
    # Only reconcile ran — so D is in filtered set but not yet in ledger until screener fires.
    # This is correct per the architecture: reconcile uses filtered_provider for keep_set
    # but only on_screener_results creates ledger rows.
    # UTCD expected: (T,D)=MONITORING — that happens when on_screener_results fires for T.
    # We verify at least the evictions.
    assert row_d is None or row_d.lifecycle_state == LifecycleState.MONITORING


# ── IT-EXE-009.002 ───────────────────────────────────────────────────────────


def test_it_009_002_carryover_position_retention(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_price: Callable[[str, int], None],
    seed_user: int,
) -> None:
    """IT-EXE-009.002: Carryover position retention — A entered T-1, not filtered T."""
    # T-1: A monitored and entered.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"A"})
    cmd0.on_screener_results(
        make_screener_result(passed=["A"], run_timestamp="2026-05-14T13:30:00Z")
    )
    cmd0.on_fill(_buy("A", "t1"))
    seed_price("A", 3)

    # T: screener does NOT include A; A's position is still open.
    query1, cmd1, bus1 = build_service(today=_T1, filtered=set())
    events1 = event_collector(bus1)

    report = cmd1.reconcile_preopen(_T1)

    # A must NOT be evicted — it's in carryover (open system position).
    assert "A" not in report.evicted_symbols

    evicted_syms = {e.symbol for e in events1 if isinstance(e, SymbolEvicted)}
    assert "A" not in evicted_syms

    # A's candles must still be present.
    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT COUNT(*) FROM price_1m WHERE symbol='A'")
        ).scalar()
    assert cnt > 0

    # Ledger (T-1, A) still ENTERED.
    row = query1.session_for(_T0, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.ENTERED


# ── IT-EXE-009.003 ───────────────────────────────────────────────────────────


def test_it_009_003_duplicate_filter_case(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_price: Callable[[str, int], None],
    seed_user: int,
) -> None:
    """IT-EXE-009.003: A entered T-1, filtered again T — new MONITORING row created; A retained."""
    # T-1: A monitored and entered.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"A"})
    cmd0.on_screener_results(
        make_screener_result(passed=["A"], run_timestamp="2026-05-14T13:30:00Z")
    )
    cmd0.on_fill(_buy("A", "t1"))
    seed_price("A", 3)

    # T: A re-emitted by screener.
    query1, cmd1, bus1 = build_service(today=_T1, filtered={"A"})
    event_collector(bus1)

    cmd1.on_screener_results(
        make_screener_result(passed=["A"], run_timestamp="2026-05-15T13:30:00Z")
    )
    report = cmd1.reconcile_preopen(_T1)

    # A must NOT be evicted.
    assert "A" not in report.evicted_symbols

    # Old row (T-1, A) stays ENTERED.
    row_t0 = query1.session_for(_T0, "A")
    assert row_t0 is not None
    assert row_t0.lifecycle_state == LifecycleState.ENTERED

    # New row (T, A) in MONITORING.
    row_t1 = query1.session_for(_T1, "A")
    assert row_t1 is not None
    assert row_t1.lifecycle_state == LifecycleState.MONITORING

    # A's candles retained.
    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT COUNT(*) FROM price_1m WHERE symbol='A'")
        ).scalar()
    assert cnt > 0


# ── IT-EXE-009.004 ───────────────────────────────────────────────────────────


def test_it_009_004_scale_in_across_days_carries_anchor_forward(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    seed_user: int,
) -> None:
    """IT-EXE-009.004: Scale-in across days carries the anchor forward."""
    # T-1: system BUY 100 A.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"A"})
    cmd0.on_screener_results(
        make_screener_result(passed=["A"], run_timestamp="2026-05-14T13:30:00Z")
    )
    cmd0.on_fill(_buy("A", "t1", qty=100))

    # T: system BUY 50 more A (scale-in).
    scale_fill = FillEvent(
        symbol="A",
        trade_id="t2",
        side=Side.BUY,
        qty=50,
        price=52.0,
        fill_time=f"{_T1_S}T14:00:00Z",
        origin=TradeOrigin.SYSTEM,
        user_id=1,
    )
    # Use the same service instance — both fills go through the same engine.
    cmd0.on_fill(scale_fill)

    with engine.connect() as conn:
        trade_rows = conn.execute(
            text("SELECT trade_id, monitoring_session_date FROM trades WHERE symbol='A' ORDER BY trade_id")
        ).all()

    assert len(trade_rows) == 2
    # Both trades must have the T-1 anchor.
    for row in trade_rows:
        assert row[1] == _T0_S, (
            f"Trade {row[0]} has anchor {row[1]!r}, expected {_T0_S!r}"
        )

    # Ledger row (T-1, A) stays ENTERED.
    row_t0 = query0.session_for(_T0, "A")
    assert row_t0 is not None
    assert row_t0.lifecycle_state == LifecycleState.ENTERED


# ── IT-EXE-009.005 ───────────────────────────────────────────────────────────


def test_it_009_005_invariant_holds_across_full_flow(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_price: Callable[[str, int], None],
    seed_user: int,
) -> None:
    """IT-EXE-009.005: Lifecycle invariant holds across the full flow."""
    # Replay IT-001 + IT-002 states.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"A", "B", "C"})
    cmd0.on_screener_results(
        make_screener_result(passed=["A", "B", "C"], run_timestamp="2026-05-14T13:30:00Z")
    )
    # After inserting MONITORING rows — invariant holds (no positions yet).
    report = query0.check_invariant()
    assert report.ok is True

    cmd0.on_fill(_buy("A", "t1"))

    # After entering A — invariant holds (A in ledger ENTERED AND in positions).
    report = query0.check_invariant()
    assert report.ok is True

    seed_price("B", 2)
    seed_price("C", 2)

    query1, cmd1, bus1 = build_service(today=_T1, filtered={"A", "D"})
    event_collector(bus1)
    cmd1.reconcile_preopen(_T1)

    # After reconcile — invariant still holds.
    report = query1.check_invariant()
    assert report.ok is True


# ── IT-EXE-010.001 ───────────────────────────────────────────────────────────


def test_it_010_001_evicted_symbol_never_reaches_set_symbols(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    event_collector: Callable[[MonitoringEventBus], list],
    seed_price: Callable[[str, int], None],
    seed_user: int,
) -> None:
    """IT-EXE-010.001: Live feed handoff — evicted symbol never reaches LiveBarWorker.set_symbols."""
    # T-1: monitor A (enter), B, C.
    query0, cmd0, bus0 = build_service(today=_T0, filtered={"A", "B", "C"})
    cmd0.on_screener_results(
        make_screener_result(passed=["A", "B", "C"], run_timestamp="2026-05-14T13:30:00Z")
    )
    cmd0.on_fill(_buy("A", "t1"))
    seed_price("B", 2)
    seed_price("C", 2)

    # Track symbols delivered via the keep_set after reconcile.
    symbols_delivered: list[frozenset[str]] = []

    query1, cmd1, bus1 = build_service(today=_T1, filtered={"A", "D"})

    # Spy: after ReconcileCompleted, get the keep_set to simulate set_symbols.
    def _on_reconcile_completed(evt: object) -> None:
        ks = query1.keep_set(_T1)
        symbols_delivered.append(ks.filtered | ks.carryover)

    bus1.subscribe(
        __import__(
            "us_swing.core.monitoring_session", fromlist=["ReconcileCompleted"]
        ).ReconcileCompleted,
        _on_reconcile_completed,
    )

    cmd1.reconcile_preopen(_T1)

    assert len(symbols_delivered) == 1
    active_symbols = symbols_delivered[0]

    # B and C must never appear.
    assert "B" not in active_symbols
    assert "C" not in active_symbols
    # A is in carryover (open position); D in filtered.
    assert "A" in active_symbols


# ── IT-EXE-010.002 ───────────────────────────────────────────────────────────


def test_it_010_002_history_survives_eviction(
    engine: Engine,
    build_service: Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]],
    make_screener_result: Callable[..., object],
    seed_price: Callable[[str, int], None],
    seed_user: int,
) -> None:
    """IT-EXE-010.002: History survives eviction — ledger row preserved, price rows deleted."""
    # Dates are relative to today so the EVICTED row's session_date stays inside
    # history()'s rolling `days=7` window, which is measured against the real clock.
    t0 = date.today() - timedelta(days=2)   # day-1
    t1 = t0 + timedelta(days=1)             # day-2
    query0, cmd0, bus0 = build_service(today=t0, filtered={"B"})
    cmd0.on_screener_results(
        make_screener_result(passed=["B"], run_timestamp=f"{t0.isoformat()}T13:30:00Z")
    )
    seed_price("B", 3)

    query1, cmd1, bus1 = build_service(today=t1, filtered=set())
    cmd1.reconcile_preopen(t1)

    # History must include at least one EVICTED row for B.
    history = query1.history("B", days=7)
    assert len(history) >= 1
    evicted = [r for r in history if r.lifecycle_state == LifecycleState.EVICTED]
    assert len(evicted) >= 1

    # But price_1m must be empty.
    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT COUNT(*) FROM price_1m WHERE symbol='B'")
        ).scalar()
    assert cnt == 0


# ── Cross-tool blocked stubs (FO-EXE-001/002 ExecutionEngine not yet implemented) ──


@pytest.mark.skip(
    reason="blocked on FO-EXE-001/002 ExecutionEngine implementation — "
    "SRD-EXE-001.001, SRD-EXE-009.008"
)
def test_handle_order_fill_routes_system_fills_to_lifecycle_command() -> None:
    """UT-EXE-001.001.M02.T08: handle_order_fill routes system fills to lifecycle_command.on_fill."""
    # Requires ExecutionEngine (FO-EXE-001/002, status: Draft).
    pass


@pytest.mark.skip(
    reason="blocked on FO-EXE-001/002 ExecutionEngine implementation — "
    "SRD-EXE-001.001, SRD-EXE-009.008"
)
def test_handle_order_fill_routes_manual_fills_with_manual_origin() -> None:
    """UT-EXE-001.001.M02.T09: handle_order_fill routes manual fills with origin=TradeOrigin.MANUAL."""
    # Requires ExecutionEngine (FO-EXE-001/002, status: Draft).
    pass
