"""Tests for execution/position_tracker.py — PositionTracker.

Phase-3 refactor (Final_Execution.md §5.3): the legacy 5-state PositionState
machine was removed; open/closed is derived from ``quantity > 0``.
Per-side broker-order progress is now on ``trades.order_state``
(see ``test_order_state_machine.py``).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from us_swing.data.models import IBKRPosition, OpenPosition
from us_swing.db.manager import DatabaseManager
from us_swing.db.schema import create_schema as _create_schema
from us_swing.execution.position_tracker import PositionTracker


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    e = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_schema(e)
    return e


@pytest.fixture
def db(engine):
    m = DatabaseManager.__new__(DatabaseManager)
    m._engine = engine
    return m


@pytest.fixture
def tracker(db: DatabaseManager) -> PositionTracker:
    return PositionTracker(db)


def _pos(
    symbol: str = "AAPL",
    user_id: int = 1,
    qty: int = 500,
    price: float = 50.0,
) -> OpenPosition:
    return OpenPosition(
        symbol=symbol,
        user_id=user_id,
        quantity=qty,
        average_price=price,
        stop_loss=48.0,
        target_price=55.0,
        mode="live",
    )


# ── Basic open / has_open / close ─────────────────────────────────────────────

def test_has_open_initially_false(tracker: PositionTracker):
    """UT-EXE-002.001.M01.T01: has_open() returns False initially."""
    assert tracker.has_open(1, "AAPL") is False


def test_open_and_has_open_round_trip(tracker: PositionTracker):
    """UT-EXE-002.001.M01.T02: open() + has_open() round-trip with user_id."""
    tracker.open(_pos(symbol="AAPL", user_id=1))
    assert tracker.has_open(1, "AAPL") is True
    assert tracker.has_open(2, "AAPL") is False  # different user


def test_close_removes_position(tracker: PositionTracker):
    """UT-EXE-002.001.M01.T03: close() removes position from tracker."""
    tracker.open(_pos())
    tracker.close(1, "AAPL")
    assert tracker.has_open(1, "AAPL") is False


def test_update_stop(tracker: PositionTracker):
    """UT-EXE-002.001.M01.T05: update_stop() changes stop_loss per user."""
    tracker.open(_pos())
    tracker.update_stop(1, "AAPL", 49.0)
    positions = tracker.get_all(user_id=1)
    assert positions[0].stop_loss == 49.0


# ── reconcile ────────────────────────────────────────────────────────────────

def test_reconcile_adopts_ibkr_position(tracker: PositionTracker, caplog):
    """UT-EXE-002.001.M01.T04: reconcile() adopts unrecognised IBKR positions."""
    ibkr = [IBKRPosition(symbol="MSFT", quantity=100, average_price=300.0, market_value=30_000.0)]
    import logging
    with caplog.at_level(logging.WARNING):
        adopted = tracker.reconcile(ibkr, user_id=1)
    assert "MSFT" in adopted
    assert tracker.has_open(1, "MSFT") is True
    assert any("MSFT" in r.message for r in caplog.records)


# ── Quantity-derived openness (replaces legacy PositionState tests) ──────────

def test_open_position_has_positive_quantity(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T01: A registered position with qty>0 is open."""
    tracker.open(_pos(qty=500))
    pos = tracker.get_all(user_id=1)[0]
    assert pos.quantity > 0
    assert tracker.has_open(1, "AAPL") is True


def test_apply_partial_entry_fill(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T02: Partial entry fill bumps quantity + filled_quantity."""
    tracker.open(_pos(qty=200))
    tracker.apply_fill(1, "AAPL", delta_qty=200, filled_qty=200)
    pos = tracker.get_all(user_id=1)[0]
    assert pos.quantity == 400
    assert pos.filled_quantity == 200


def test_apply_full_entry_fill_then_partial_exit(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T03: Full entry then partial exit decrements quantity."""
    tracker.open(_pos(qty=500))
    tracker.apply_fill(1, "AAPL", delta_qty=-300)
    pos = tracker.get_all(user_id=1)[0]
    assert pos.quantity == 200
    assert tracker.has_open(1, "AAPL") is True


def test_full_exit_drops_position(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T04: Final SELL fill drives quantity to 0 and removes the position."""
    tracker.open(_pos(qty=500))
    tracker.apply_fill(1, "AAPL", delta_qty=-500)
    assert tracker.has_open(1, "AAPL") is False
    assert tracker.get_all(user_id=1) == []


def test_load_from_db_restores_only_open_positions(
    tracker: PositionTracker, db: DatabaseManager
):
    """UT-EXE-005.001.M01.T05: load_from_db() restores only qty>0 positions."""
    for symbol, qty in [("AAPL", 100), ("MSFT", 100), ("GOOG", 0)]:
        pos = OpenPosition(
            symbol=symbol,
            user_id=1,
            quantity=qty,
            average_price=50.0,
            stop_loss=48.0,
            target_price=55.0,
            mode="live",
        )
        db.upsert_position(pos)

    new_tracker = PositionTracker(db)
    new_tracker.load_from_db(user_id=1)
    loaded = new_tracker.get_all(user_id=1)
    symbols = {p.symbol for p in loaded}
    assert symbols == {"AAPL", "MSFT"}
    assert not new_tracker.has_open(1, "GOOG")
