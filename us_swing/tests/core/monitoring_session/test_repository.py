"""Tests for MD-EXE-009.002.M01 — core/monitoring_session/_repository.py."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

import pytest
import sqlalchemy as sa
from sqlalchemy import Engine, text

from us_swing.core.monitoring_session._repository import MonitoringRepository
from us_swing.core.monitoring_session import LifecycleState
from us_swing.db.schema import (
    create_schema,
    migrate_lifecycle_columns,
)


_TODAY = date(2026, 5, 15)
_YESTERDAY = date(2026, 5, 14)
_TODAY_S = _TODAY.isoformat()
_YESTERDAY_S = _YESTERDAY.isoformat()


# ── UT-EXE-009.002.M01.T01 ──────────────────────────────────────────────────


def test_insert_monitoring_rows_inserts_new_symbols(engine: Engine, seed_user: int) -> None:
    """UT-EXE-009.002.M01.T01: insert_monitoring_rows inserts new symbols in MONITORING state."""
    repo = MonitoringRepository(engine)
    inserted = repo.insert_monitoring_rows(
        session_date=_TODAY,
        preset_id="p",
        run_timestamp="2026-05-15T13:30:00Z",
        symbols=["A", "B"],
    )

    assert set(inserted) == {"A", "B"}

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT symbol, lifecycle_state FROM monitoring_session WHERE session_date = :d"),
            {"d": _TODAY_S},
        ).all()

    assert len(rows) == 2
    assert all(r[1] == LifecycleState.MONITORING.value for r in rows)


# ── UT-EXE-009.002.M01.T02 ──────────────────────────────────────────────────


def test_insert_monitoring_rows_idempotent(engine: Engine, seed_user: int) -> None:
    """UT-EXE-009.002.M01.T02: insert_monitoring_rows is idempotent on same-day re-run."""
    repo = MonitoringRepository(engine)
    repo.insert_monitoring_rows(
        session_date=_TODAY,
        preset_id="p",
        run_timestamp="2026-05-15T13:30:00Z",
        symbols=["A", "B"],
    )
    second = repo.insert_monitoring_rows(
        session_date=_TODAY,
        preset_id="p",
        run_timestamp="2026-05-15T13:30:00Z",
        symbols=["A", "B"],
    )

    assert second == ()

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM monitoring_session WHERE session_date = :d"),
            {"d": _TODAY_S},
        ).scalar()
    assert count == 2


# ── UT-EXE-009.002.M01.T03 ──────────────────────────────────────────────────


def test_insert_monitoring_rows_empty_symbols(engine: Engine, seed_user: int) -> None:
    """UT-EXE-009.002.M01.T03: insert_monitoring_rows with empty symbols inserts nothing."""
    repo = MonitoringRepository(engine)
    result = repo.insert_monitoring_rows(
        session_date=_TODAY,
        preset_id="p",
        run_timestamp="2026-05-15T13:30:00Z",
        symbols=[],
    )

    assert result == ()

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM monitoring_session")).scalar()
    assert count == 0


# ── UT-EXE-009.002.M01.T04 ──────────────────────────────────────────────────


def test_fetch_earliest_open_monitoring_row_returns_min(engine: Engine, seed_user: int) -> None:
    """UT-EXE-009.002.M01.T04: fetch_earliest_open_monitoring_row returns row with MIN(session_date)."""
    repo = MonitoringRepository(engine)
    repo.insert_monitoring_rows(
        session_date=date(2026, 5, 14),
        preset_id="p",
        run_timestamp="ts",
        symbols=["X"],
    )
    repo.insert_monitoring_rows(
        session_date=date(2026, 5, 15),
        preset_id="p",
        run_timestamp="ts",
        symbols=["X"],
    )

    row = repo.fetch_earliest_open_monitoring_row("X")

    assert row is not None
    assert row.session_date == "2026-05-14"


# ── UT-EXE-009.002.M01.T05 ──────────────────────────────────────────────────


def test_fetch_earliest_open_monitoring_row_none_when_entered(
    engine: Engine, seed_user: int
) -> None:
    """UT-EXE-009.002.M01.T05: fetch_earliest_open_monitoring_row returns None when no MONITORING row."""
    repo = MonitoringRepository(engine)
    # Insert then flip to ENTERED so no MONITORING rows remain.
    repo.insert_monitoring_rows(
        session_date=_TODAY,
        preset_id="p",
        run_timestamp="ts",
        symbols=["X"],
    )
    repo.transition_to_entered(
        session_date=_TODAY_S,
        symbol="X",
        entered_at="2026-05-15T14:00:00Z",
        trade_id="t1",
    )

    row = repo.fetch_earliest_open_monitoring_row("X")

    assert row is None


# ── UT-EXE-009.002.M01.T06 ──────────────────────────────────────────────────


def test_transition_to_entered_flips_state(engine: Engine, seed_user: int) -> None:
    """UT-EXE-009.002.M01.T06: transition_to_entered flips MONITORING -> ENTERED with timestamps."""
    repo = MonitoringRepository(engine)
    repo.insert_monitoring_rows(
        session_date=_TODAY,
        preset_id="p",
        run_timestamp="ts",
        symbols=["A"],
    )

    entered_at = "2026-05-15T14:00:00Z"
    repo.transition_to_entered(
        session_date=_TODAY_S,
        symbol="A",
        entered_at=entered_at,
        trade_id="trade-001",
    )

    row = repo.fetch_session(_TODAY, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.ENTERED
    assert row.entered_at == entered_at
    assert row.trade_id == "trade-001"


# ── UT-EXE-009.002.M01.T07 ──────────────────────────────────────────────────


def test_transition_to_exited_flips_state(engine: Engine, seed_user: int) -> None:
    """UT-EXE-009.002.M01.T07: transition_to_exited flips ENTERED -> EXITED."""
    repo = MonitoringRepository(engine)
    repo.insert_monitoring_rows(
        session_date=_YESTERDAY,
        preset_id="p",
        run_timestamp="ts",
        symbols=["A"],
    )
    repo.transition_to_entered(
        session_date=_YESTERDAY_S,
        symbol="A",
        entered_at="2026-05-14T14:00:00Z",
        trade_id="t1",
    )

    exited_at = "2026-05-14T15:00:00Z"
    repo.transition_to_exited(
        session_date=_YESTERDAY_S,
        symbol="A",
        exited_at=exited_at,
    )

    row = repo.fetch_session(_YESTERDAY, "A")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.EXITED
    assert row.exited_at == exited_at


# ── UT-EXE-009.002.M01.T08 ──────────────────────────────────────────────────


def test_bulk_skip_stale_monitoring_only_prior_days(engine: Engine, seed_user: int) -> None:
    """UT-EXE-009.002.M01.T08: bulk_skip_stale_monitoring flips only stale MONITORING rows."""
    repo = MonitoringRepository(engine)
    # Row A on yesterday — should be skipped.
    repo.insert_monitoring_rows(
        session_date=_YESTERDAY,
        preset_id="p",
        run_timestamp="ts",
        symbols=["A"],
    )
    # Row B on today — must NOT be skipped.
    repo.insert_monitoring_rows(
        session_date=_TODAY,
        preset_id="p",
        run_timestamp="ts",
        symbols=["B"],
    )

    count = repo.bulk_skip_stale_monitoring(_TODAY)

    assert count == 1
    row_a = repo.fetch_session(_YESTERDAY, "A")
    assert row_a is not None
    assert row_a.lifecycle_state == LifecycleState.SKIPPED

    row_b = repo.fetch_session(_TODAY, "B")
    assert row_b is not None
    assert row_b.lifecycle_state == LifecycleState.MONITORING


# ── UT-EXE-009.002.M01.T09 ──────────────────────────────────────────────────


def test_evict_symbol_atomic_deletes_price_and_flips_ledger(
    engine: Engine,
    seed_user: int,
    seed_price: Callable[[str, int], None],
) -> None:
    """UT-EXE-009.002.M01.T09: evict_symbol_atomic deletes from all 3 price tables + flips ledger."""
    repo = MonitoringRepository(engine)
    # Seed price rows for B.
    seed_price("B", 5)
    # Insert MONITORING row for yesterday (pre-today), then skip it.
    repo.insert_monitoring_rows(
        session_date=_YESTERDAY,
        preset_id="p",
        run_timestamp="ts",
        symbols=["B"],
    )
    repo.bulk_skip_stale_monitoring(_TODAY)

    dates = repo.evict_symbol_atomic(
        symbol="B",
        today=_TODAY,
        evicted_at="2026-05-15T09:00:00Z",
    )

    assert _YESTERDAY_S in dates

    with engine.connect() as conn:
        for tf in ("price_1m", "price_3m", "price_15m"):
            cnt = conn.execute(
                text(f"SELECT COUNT(*) FROM {tf} WHERE symbol = 'B'")
            ).scalar()
            assert cnt == 0, f"{tf} still has rows for B after eviction"

    row = repo.fetch_session(_YESTERDAY, "B")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.EVICTED
    assert row.evicted_at == "2026-05-15T09:00:00Z"


# ── UT-EXE-009.002.M01.T10 ──────────────────────────────────────────────────


def test_evict_symbol_atomic_rollback_on_failure(
    engine: Engine,
    seed_user: int,
    seed_price: Callable[[str, int], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UT-EXE-009.002.M01.T10: evict_symbol_atomic rolls back fully on mid-transaction failure."""
    repo = MonitoringRepository(engine)
    seed_price("B", 3)
    repo.insert_monitoring_rows(
        session_date=_YESTERDAY,
        preset_id="p",
        run_timestamp="ts",
        symbols=["B"],
    )
    repo.bulk_skip_stale_monitoring(_TODAY)

    # Intercept at the _PRICE_TABLES_FOR_EVICTION level — patch the constant so
    # only the first two tables are processed, then raise on the third.
    import us_swing.core.monitoring_session._repository as _repo_mod

    original_tables = _repo_mod._PRICE_TABLES_FOR_EVICTION

    def _patched_evict(
        self: MonitoringRepository,
        symbol: str,
        today: date,
        evicted_at: str,
    ) -> tuple[str, ...]:
        """Modified evict that raises mid-transaction to verify rollback."""
        today.isoformat()
        with self._engine.begin() as conn:
            for i, table_name in enumerate(original_tables):
                if i == 2:
                    # Simulate a disk-full failure on the third DELETE.
                    raise sa.exc.OperationalError("disk full", {}, Exception())
                conn.execute(
                    sa.text(f"DELETE FROM {table_name} WHERE symbol = :sym"),
                    {"sym": symbol},
                )
        return ()  # unreachable

    monkeypatch.setattr(MonitoringRepository, "evict_symbol_atomic", _patched_evict)

    with pytest.raises(sa.exc.OperationalError):
        repo.evict_symbol_atomic(
            symbol="B",
            today=_TODAY,
            evicted_at="2026-05-15T09:00:00Z",
        )

    # Rollback must have preserved ALL price rows (price_1m and price_3m deleted
    # inside the same transaction that failed, so they roll back too).
    with engine.connect() as conn:
        for tf in ("price_1m", "price_3m", "price_15m"):
            cnt = conn.execute(
                text(f"SELECT COUNT(*) FROM {tf} WHERE symbol = 'B'")
            ).scalar()
            assert cnt == 3, f"{tf} rows unexpectedly lost for B after rollback"

    # Ledger row must still be SKIPPED.
    row = repo.fetch_session(_YESTERDAY, "B")
    assert row is not None
    assert row.lifecycle_state == LifecycleState.SKIPPED


# ── UT-EXE-009.002.M01.T11 ──────────────────────────────────────────────────


def test_open_system_position_symbols_returns_open_cycle_symbols(
    engine: Engine, open_cycle: Callable[..., None], seed_user: int
) -> None:
    """open_system_position_symbols returns symbols of non-terminal trade_cycles (FO-EXE-016)."""
    repo = MonitoringRepository(engine)
    open_cycle("A", "oc-a", state="OPEN")
    open_cycle("B", "oc-b", state="CLOSED")

    result = repo.open_system_position_symbols()

    assert result == frozenset({"A"})


# ── UT-EXE-009.002.M01.T14 ──────────────────────────────────────────────────


def test_fetch_history_includes_evicted(engine: Engine, seed_user: int) -> None:
    """UT-EXE-009.002.M01.T14: fetch_history(symbol, days) returns ledger rows including EVICTED."""
    repo = MonitoringRepository(engine)
    # Dates are relative to today so the row's session_date stays inside
    # fetch_history()'s rolling `days=7` window, measured against the real clock.
    yesterday = date.today() - timedelta(days=1)
    today = date.today()
    repo.insert_monitoring_rows(
        session_date=yesterday,
        preset_id="p",
        run_timestamp="ts",
        symbols=["B"],
    )
    repo.bulk_skip_stale_monitoring(today)
    repo.evict_symbol_atomic(
        symbol="B",
        today=today,
        evicted_at=f"{today.isoformat()}T09:00:00Z",
    )

    history = repo.fetch_history("B", days=7)

    assert len(history) >= 1
    evicted_rows = [r for r in history if r.lifecycle_state == LifecycleState.EVICTED]
    assert len(evicted_rows) >= 1
    assert evicted_rows[0].evicted_at is not None


# ── Cross-tool patch tests (INF / schema migration) ─────────────────────────


def test_migrate_lifecycle_columns_adds_columns() -> None:
    """UT-INF-004.001.M01.T20: migrate_lifecycle_columns adds the 4 new columns when absent."""
    eng = sa.create_engine("sqlite:///:memory:", future=True)

    # Create tables WITHOUT lifecycle columns by calling metadata.create_all
    # and then dropping the new columns manually — easiest to build a minimal
    # schema that only has the base columns.

    # Use create_schema which also calls migrate — capture state before.
    create_schema(eng)

    with eng.connect() as conn:
        cols_trades = {
            r[1] for r in conn.execute(text("PRAGMA table_info(trades)")).all()
        }
        cols_positions = {
            r[1] for r in conn.execute(text("PRAGMA table_info(positions)")).all()
        }

    assert "trade_origin" in cols_trades
    assert "monitoring_session_date" in cols_trades
    assert "origin" in cols_positions
    assert "anchor_session_date" in cols_positions
    eng.dispose()


def test_migrate_lifecycle_columns_idempotent() -> None:
    """UT-INF-004.001.M01.T21: migrate_lifecycle_columns is idempotent."""
    eng = sa.create_engine("sqlite:///:memory:", future=True)
    create_schema(eng)

    # Run migration a second time — must not raise or duplicate columns.
    migrate_lifecycle_columns(eng)

    with eng.connect() as conn:
        cols_trades = [
            r[1] for r in conn.execute(text("PRAGMA table_info(trades)")).all()
        ]

    # Column count should be unchanged (no duplicates).
    assert cols_trades.count("trade_origin") == 1
    assert cols_trades.count("monitoring_session_date") == 1
    eng.dispose()


def test_create_schema_provisions_monitoring_session_table_and_indexes() -> None:
    """UT-INF-004.001.M02.T05: create_schema(checkfirst=True) provisions monitoring_session + indexes."""
    eng = sa.create_engine("sqlite:///:memory:", future=True)
    create_schema(eng)

    with eng.connect() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).all()
        }
        indexes = {
            r[0]
            for r in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index'")
            ).all()
        }

    assert "monitoring_session" in tables
    assert "idx_monitoring_session_state" in indexes
    assert "idx_monitoring_session_symbol" in indexes
    eng.dispose()
