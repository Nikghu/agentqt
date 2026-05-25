"""
Module: MD-EXE-012.002.M01 — TradeCycleRepository tests
Parent SRD: SRD-EXE-012.003, .007, .008, .009, .010, .013
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from us_swing.db.schema import create_schema
from us_swing.execution.trade_cycle._dto import (
    DuplicateOpenCycleError,
    InvalidStateTransitionError,
)
from us_swing.execution.trade_cycle._repository import TradeCycleRepository


@pytest.fixture
def repo() -> TradeCycleRepository:
    eng = sa.create_engine("sqlite:///:memory:")
    create_schema(eng)
    return TradeCycleRepository(eng)


def _base_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "strategy_id":             "boss_ema",
        "symbol":                  "AAPL",
        "user_id":                 1,
        "monitoring_session_date": "2026-05-25",
        "entry_time":              "2026-05-25T09:35:00",
        "entry_price":             182.5,
        "entry_qty":               25,
        "entry_order_id":          "ord-001",
        "hard_stop_loss":          179.0,
        "target_price":            190.0,
        "target_type":             "fixed",
        "stoploss_type":           "fixed",
        "trailing_mode":           None,
        "trailing_offset":         None,
        "state":                   "OPEN",
    }
    row.update(overrides)
    return row


def test_insert_open_returns_snapshot_with_correct_fields(repo: TradeCycleRepository) -> None:
    """UT-EXE-012.002.M01.T01: insert_open inserts one row and returns matching CycleSnapshot."""
    snap = repo.insert_open(row=_base_row())
    assert snap.state == "OPEN"
    assert snap.symbol == "AAPL"
    assert snap.entry_price == pytest.approx(182.5)
    assert snap.entry_qty == 25
    assert snap.cycle_id > 0


def test_duplicate_open_guard_raises(repo: TradeCycleRepository) -> None:
    """UT-EXE-012.002.M01.T02: insert_open for same (strategy_id, symbol) raises DuplicateOpenCycleError."""
    repo.insert_open(row=_base_row())
    with pytest.raises(DuplicateOpenCycleError):
        repo.insert_open(row=_base_row(entry_order_id="ord-002"))


def test_update_live_updates_only_live_columns(repo: TradeCycleRepository) -> None:
    """UT-EXE-012.002.M01.T03: update_live changes live fields; entry/risk columns untouched."""
    snap = repo.insert_open(row=_base_row())
    repo.update_live(snap.cycle_id, fields={
        "current_price":   185.0,
        "current_pnl_usd": 62.5,
        "effective_stop":  182.5,
    })
    fresh = repo.cycle(snap.cycle_id)
    assert fresh is not None
    assert fresh.current_price == pytest.approx(185.0)
    assert fresh.current_pnl_usd == pytest.approx(62.5)
    assert fresh.entry_price == pytest.approx(182.5)   # unchanged
    assert fresh.hard_stop_loss == pytest.approx(179.0)  # unchanged


def test_update_state_cas_succeeds_open_to_closing(repo: TradeCycleRepository) -> None:
    """UT-EXE-012.002.M01.T04: update_state OPEN → CLOSING succeeds and returns updated snapshot."""
    snap = repo.insert_open(row=_base_row())
    updated = repo.update_state(snap.cycle_id, "CLOSING")
    assert updated.state == "CLOSING"
    assert updated.cycle_id == snap.cycle_id


def test_update_state_rejects_illegal_transition_closed_to_opening(
    repo: TradeCycleRepository,
) -> None:
    """UT-EXE-012.002.M01.T05: update_state CLOSED → OPENING raises InvalidStateTransitionError."""
    snap = repo.insert_open(row=_base_row())
    repo.update_state(snap.cycle_id, "CLOSING")
    repo.close(snap.cycle_id, exit_fields={
        "exit_order_id":    "exit-001",
        "exit_price":       187.8,
        "exit_qty":         25,
        "exit_time":        "2026-05-25T10:00:00",
        "exit_reason":      "target",
        "realized_pnl_usd": 132.5,
        "realized_pnl_pct": 2.9,
    })
    with pytest.raises(InvalidStateTransitionError):
        repo.update_state(snap.cycle_id, "OPENING")


def test_close_sets_exit_fields_and_freezes_pnl(repo: TradeCycleRepository) -> None:
    """UT-EXE-012.002.M01.T06: close() sets exit fields; realized_pnl_usd == 132.5 ± 0.01."""
    snap = repo.insert_open(row=_base_row())
    repo.update_state(snap.cycle_id, "CLOSING")
    closed = repo.close(snap.cycle_id, exit_fields={
        "exit_order_id":    "exit-001",
        "exit_price":       187.8,
        "exit_qty":         25,
        "exit_time":        "2026-05-25T10:00:00",
        "exit_reason":      "target",
        "realized_pnl_usd": (187.8 - 182.5) * 25,
        "realized_pnl_pct": (187.8 - 182.5) / 182.5 * 100.0,
    })
    assert closed.state == "CLOSED"
    assert closed.exit_price == pytest.approx(187.8)
    assert closed.realized_pnl_usd == pytest.approx(132.5, abs=0.01)
    assert closed.closed_at is not None


def test_abort_transitions_opening_to_aborted(repo: TradeCycleRepository) -> None:
    """UT-EXE-012.002.M01.T07: abort() transitions OPENING → ABORTED with reason and closed_at."""
    opening_snap = repo.insert_open(row=_base_row(state="OPENING"))
    aborted = repo.abort(opening_snap.cycle_id, "broker_reject")
    assert aborted.state == "ABORTED"
    assert aborted.exit_reason == "broker_reject"
    assert aborted.closed_at is not None


def test_open_cycles_returns_only_non_terminal_rows(repo: TradeCycleRepository) -> None:
    """UT-EXE-012.002.M01.T08: open_cycles() excludes CLOSED and ABORTED rows."""
    snap = repo.insert_open(row=_base_row())
    repo.update_state(snap.cycle_id, "CLOSING")
    repo.close(snap.cycle_id, exit_fields={
        "exit_order_id":    "e1",
        "exit_price":       187.0,
        "exit_qty":         25,
        "exit_time":        "2026-05-25T10:00:00",
        "exit_reason":      "target",
        "realized_pnl_usd": 112.5,
        "realized_pnl_pct": 2.47,
    })
    snap2 = repo.insert_open(row=_base_row(symbol="MSFT", entry_order_id="ord-msft"))

    open_snaps = repo.open_cycles()
    assert len(open_snaps) == 1
    assert open_snaps[0].symbol == "MSFT"


def test_find_by_entry_order_returns_matching_row(repo: TradeCycleRepository) -> None:
    """UT-EXE-012.002.M01.T09: find_by_entry_order('ord-001') returns the correct CycleSnapshot."""
    repo.insert_open(row=_base_row())
    found = repo.find_by_entry_order("ord-001")
    assert found is not None
    assert found.entry_order_id == "ord-001"
    assert found.symbol == "AAPL"


def test_history_excludes_rows_older_than_days(repo: TradeCycleRepository) -> None:
    """UT-EXE-012.002.M01.T10: history(days=7) excludes rows with opened_at > 7 days ago."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    old_iso = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S")

    snap_recent = repo.insert_open(row=_base_row(opened_at=now_iso))
    snap_old = repo.insert_open(row=_base_row(
        symbol="MSFT",
        entry_order_id="ord-msft",
        opened_at=old_iso,
    ))

    results = repo.history(days=7)
    result_ids = {r.cycle_id for r in results}
    assert snap_recent.cycle_id in result_ids
    assert snap_old.cycle_id not in result_ids
