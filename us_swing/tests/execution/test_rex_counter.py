"""
Module: MD-EXE-011.001.M08 — tests
Parent SRD: SRD-EXE-011.016 — SRD-EXE-011.019
"""
from __future__ import annotations

import sqlalchemy as sa

from us_swing.db.schema import metadata
from us_swing.execution.strategy_engine._rex_counter import (
    RexCounterRepository,
    strategy_rex_counters,
)


def _make_engine() -> sa.Engine:
    return sa.create_engine("sqlite:///:memory:", future=True)


def test_table_created_on_first_use() -> None:
    """UT-EXE-011.001.M08.T01: strategy_rex_counters table exists after repository init."""
    engine = _make_engine()
    RexCounterRepository(engine)
    inspector = sa.inspect(engine)
    assert inspector.has_table("strategy_rex_counters")
    cols = {c["name"] for c in inspector.get_columns("strategy_rex_counters")}
    assert {"strategy_id", "symbol", "remaining", "last_updated"} <= cols


def test_get_returns_none_when_row_absent() -> None:
    """UT-EXE-011.001.M08.T02: get on empty table returns None."""
    repo = RexCounterRepository(_make_engine())
    assert repo.get("S1", "AAPL") is None


def test_decrement_inserts_with_init_value_minus_one_when_missing() -> None:
    """UT-EXE-011.001.M08.T03: decrement on missing row writes init_value - 1."""
    repo = RexCounterRepository(_make_engine())
    new_value = repo.decrement("S1", "AAPL", init_value=5)
    assert new_value == 4
    assert repo.get("S1", "AAPL") == 4


def test_decrement_subtracts_one_from_existing_row() -> None:
    """UT-EXE-011.001.M08.T04: decrement on existing row reduces remaining by 1; init_value ignored."""
    engine = _make_engine()
    repo = RexCounterRepository(engine)
    with engine.begin() as conn:
        conn.execute(
            sa.insert(strategy_rex_counters).values(
                strategy_id="S1",
                symbol="AAPL",
                remaining=3,
                last_updated="2026-05-27T00:00:00",
            )
        )
    new_value = repo.decrement("S1", "AAPL", init_value=99)
    assert new_value == 2
    assert repo.get("S1", "AAPL") == 2


def test_reset_deletes_all_rows_for_strategy() -> None:
    """UT-EXE-011.001.M08.T05: reset returns count and only deletes the named strategy's rows."""
    engine = _make_engine()
    repo = RexCounterRepository(engine)
    for sym in ("AAPL", "MSFT", "TSLA"):
        repo.decrement("S1", sym, init_value=2)
    for sym in ("AAPL", "NVDA"):
        repo.decrement("S2", sym, init_value=2)
    deleted = repo.reset("S1")
    assert deleted == 3
    assert repo.get("S1", "AAPL") is None
    assert repo.get("S2", "AAPL") == 1
    assert repo.get("S2", "NVDA") == 1


def test_reset_returns_zero_when_no_rows() -> None:
    """UT-EXE-011.001.M08.T06: reset on empty table returns 0, no exception."""
    repo = RexCounterRepository(_make_engine())
    assert repo.reset("S1") == 0


def test_get_on_other_strategy_returns_none() -> None:
    """UT-EXE-011.001.M08.T07: get with mismatched strategy_id returns None."""
    repo = RexCounterRepository(_make_engine())
    repo.decrement("S1", "AAPL", init_value=3)
    assert repo.get("S2", "AAPL") is None


def test_counter_survives_new_repository_instance() -> None:
    """UT-EXE-011.001.M08.T08: new repository on same engine sees previously stored counter."""
    engine = _make_engine()
    repo1 = RexCounterRepository(engine)
    repo1.decrement("S1", "AAPL", init_value=5)
    del repo1
    repo2 = RexCounterRepository(engine)
    assert repo2.get("S1", "AAPL") == 4
