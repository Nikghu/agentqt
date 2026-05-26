"""Tests for execution/position_tracker.py — PositionTracker."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from us_swing.data.models import IBKRPosition, OpenPosition, PositionState
from us_swing.db.manager import DatabaseManager
from us_swing.db.schema import create_schema as _create_schema
from us_swing.exceptions import InvalidStateTransitionError
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
    state: str = PositionState.NEW.value,
) -> OpenPosition:
    return OpenPosition(
        symbol=symbol,
        user_id=user_id,
        quantity=qty,
        average_price=price,
        stop_loss=48.0,
        target_price=55.0,
        mode="live",
        state=state,
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


# ── state machine ─────────────────────────────────────────────────────────────

def test_new_position_starts_in_new_state(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T01: New position starts in state NEW."""
    tracker.open(_pos())
    pos = tracker.get_all(user_id=1)[0]
    assert pos.state == PositionState.NEW.value


def test_new_to_partial_entry(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T02: Partial entry fill transitions NEW → PARTIAL_ENTRY."""
    tracker.open(_pos())
    tracker.update_state(1, "AAPL", PositionState.PARTIAL_ENTRY, filled_qty=200)
    pos = tracker.get_all(user_id=1)[0]
    assert pos.state == PositionState.PARTIAL_ENTRY.value
    assert pos.filled_quantity == 200


def test_new_to_open(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T03: Full entry fill transitions NEW → OPEN."""
    tracker.open(_pos())
    tracker.update_state(1, "AAPL", PositionState.OPEN, filled_qty=500)
    pos = tracker.get_all(user_id=1)[0]
    assert pos.state == PositionState.OPEN.value
    assert pos.filled_quantity == 500


def test_partial_entry_to_open(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T04: PARTIAL_ENTRY → OPEN on final fill."""
    tracker.open(_pos())
    tracker.update_state(1, "AAPL", PositionState.PARTIAL_ENTRY, filled_qty=200)
    tracker.update_state(1, "AAPL", PositionState.OPEN, filled_qty=500)
    pos = tracker.get_all(user_id=1)[0]
    assert pos.state == PositionState.OPEN.value
    assert pos.filled_quantity == 500


def test_open_to_partial_exit(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T05: OPEN → PARTIAL_EXIT on partial exit."""
    tracker.open(_pos())
    tracker.update_state(1, "AAPL", PositionState.OPEN, filled_qty=500)
    tracker.update_state(1, "AAPL", PositionState.PARTIAL_EXIT, filled_qty=300)
    pos = tracker.get_all(user_id=1)[0]
    assert pos.state == PositionState.PARTIAL_EXIT.value


def test_partial_exit_to_closed(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T06: PARTIAL_EXIT → CLOSED on final exit."""
    tracker.open(_pos())
    tracker.update_state(1, "AAPL", PositionState.OPEN, filled_qty=500)
    tracker.update_state(1, "AAPL", PositionState.PARTIAL_EXIT, filled_qty=300)
    tracker.update_state(1, "AAPL", PositionState.CLOSED, filled_qty=500)
    pos = tracker.get_all(user_id=1)[0]
    assert pos.state == PositionState.CLOSED.value


def test_invalid_closed_to_open_raises(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T07: Invalid transition CLOSED → OPEN raises error."""
    tracker.open(_pos())
    tracker.update_state(1, "AAPL", PositionState.OPEN)
    tracker.update_state(1, "AAPL", PositionState.CLOSED)
    with pytest.raises(InvalidStateTransitionError):
        tracker.update_state(1, "AAPL", PositionState.OPEN)


def test_invalid_new_to_partial_exit_raises(tracker: PositionTracker):
    """UT-EXE-005.001.M01.T08: Invalid transition NEW → PARTIAL_EXIT raises error."""
    tracker.open(_pos())
    with pytest.raises(InvalidStateTransitionError):
        tracker.update_state(1, "AAPL", PositionState.PARTIAL_EXIT)


def test_load_from_db_restores_open_positions(
    tracker: PositionTracker, db: DatabaseManager
):
    """UT-EXE-005.001.M01.T09: load_from_db() restores non-CLOSED positions."""
    # Persist 2 OPEN and 1 CLOSED positions directly via DB
    for symbol, state in [("AAPL", "OPEN"), ("MSFT", "OPEN"), ("GOOG", "CLOSED")]:
        pos = OpenPosition(
            symbol=symbol,
            user_id=1,
            quantity=100,
            average_price=50.0,
            stop_loss=48.0,
            target_price=55.0,
            mode="live",
            state=state,
        )
        db.upsert_position(pos)

    new_tracker = PositionTracker(db)
    new_tracker.load_from_db(user_id=1)
    loaded = new_tracker.get_all(user_id=1)
    symbols = {p.symbol for p in loaded}
    assert symbols == {"AAPL", "MSFT"}
    assert not new_tracker.has_open(1, "GOOG")
