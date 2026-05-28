"""Tests for FO-EXE-014 — BuyOrderState / SellOrderState broker-order
state machines on the ``trades`` table (Final_Execution.md §5.3).

Drives the `db/manager.py` write paths (`insert_trade`, `update_trade_fill`)
to verify `order_state` and `filled_quantity` transitions and validates the
legacy `status → order_state` backfill in `migrate_lifecycle_columns()`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from us_swing.data.models import TradeRecord
from us_swing.db.manager import DatabaseManager
from us_swing.db.schema import create_schema as _create_schema
from us_swing.db.schema import migrate_lifecycle_columns
from us_swing.execution._enums import ExecutionEnums


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
def db(engine) -> DatabaseManager:
    # users row required for trades.user_id FK.
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users (user_id, username, display_name, "
                "ibkr_client_id, mode) VALUES (1, 'u', 'U', 100, 'paper')"
            )
        )
    m = DatabaseManager.__new__(DatabaseManager)
    m._engine = engine
    return m


def _buy_record(trade_id: str = "B1") -> TradeRecord:
    return TradeRecord(
        trade_id=trade_id,
        user_id=1,
        symbol="AAPL",
        side="BUY",
        quantity=100,
        entry_price=180.0,
        mode="paper",
        strategy_id="strat-1",
        entry_time=datetime(2026, 5, 28, 10, 30, tzinfo=timezone.utc),
        order_state=ExecutionEnums.BuyOrderState.NEW.value,
        filled_quantity=0,
    )


def _fetch_state(db: DatabaseManager, trade_id: str) -> tuple[str, int]:
    with db._engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT order_state, filled_quantity "
                "FROM trades WHERE trade_id = :tid"
            ),
            {"tid": trade_id},
        ).mappings().first()
    assert row is not None
    return row["order_state"], row["filled_quantity"]


# ── BuyOrderState transitions ────────────────────────────────────────────────

def test_buy_new_then_partial_filled_then_filled(db: DatabaseManager):
    """UT-EXE-014.001.M01.T01: BUY NEW → PARTIAL_FILLED → FILLED."""
    db.insert_trade(_buy_record())
    assert _fetch_state(db, "B1") == ("NEW", 0)

    db.update_trade_fill(
        "B1", filled_quantity=50,
        order_state=ExecutionEnums.BuyOrderState.PARTIAL_FILLED.value,
    )
    assert _fetch_state(db, "B1") == ("PARTIAL_FILLED", 50)

    db.update_trade_fill(
        "B1", filled_quantity=100,
        order_state=ExecutionEnums.BuyOrderState.FILLED.value,
    )
    assert _fetch_state(db, "B1") == ("FILLED", 100)


def test_buy_new_then_rejected_qty_zero(db: DatabaseManager):
    """UT-EXE-014.001.M01.T02: Broker rejection leaves filled_quantity=0."""
    db.insert_trade(_buy_record(trade_id="B2"))
    db.update_trade_fill(
        "B2", filled_quantity=0,
        order_state=ExecutionEnums.BuyOrderState.REJECTED.value,
    )
    assert _fetch_state(db, "B2") == ("REJECTED", 0)


def test_buy_partial_filled_then_cancelled_preserves_filled(db: DatabaseManager):
    """UT-EXE-014.001.M01.T03: CANCELLED after partial fill keeps filled_quantity."""
    db.insert_trade(_buy_record(trade_id="B3"))
    db.update_trade_fill(
        "B3", filled_quantity=40,
        order_state=ExecutionEnums.BuyOrderState.PARTIAL_FILLED.value,
    )
    db.update_trade_fill(
        "B3", filled_quantity=40,
        order_state=ExecutionEnums.BuyOrderState.CANCELLED.value,
    )
    assert _fetch_state(db, "B3") == ("CANCELLED", 40)


# ── SellOrderState transitions ───────────────────────────────────────────────

def test_sell_partial_then_full_filled_records_exit_fields(db: DatabaseManager):
    """UT-EXE-014.001.M01.T04: SELL FILLED writes exit_time + exit_price."""
    sell = TradeRecord(
        trade_id="S1",
        user_id=1,
        symbol="AAPL",
        side="SELL",
        quantity=100,
        entry_price=0.0,
        mode="paper",
        strategy_id="strat-1",
        entry_time=datetime(2026, 5, 28, 11, 0, tzinfo=timezone.utc),
        order_state=ExecutionEnums.SellOrderState.NEW.value,
        filled_quantity=0,
    )
    db.insert_trade(sell)

    exit_time = datetime(2026, 5, 28, 11, 5, tzinfo=timezone.utc)
    db.update_trade_fill(
        "S1", filled_quantity=100,
        order_state=ExecutionEnums.SellOrderState.FILLED.value,
        exit_time=exit_time,
        exit_price=190.5,
    )
    with db._engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT order_state, filled_quantity, exit_price, exit_time "
                "FROM trades WHERE trade_id = 'S1'"
            )
        ).mappings().first()
    assert row is not None
    assert row["order_state"]      == "FILLED"
    assert row["filled_quantity"]  == 100
    assert row["exit_price"]       == 190.5
    assert row["exit_time"] is not None


def test_sell_cancelled_after_partial_fill_keeps_filled(db: DatabaseManager):
    """UT-EXE-014.001.M01.T05: SELL CANCELLED after partial fill keeps filled_quantity."""
    sell = TradeRecord(
        trade_id="S2",
        user_id=1,
        symbol="AAPL",
        side="SELL",
        quantity=100,
        entry_price=0.0,
        mode="paper",
        strategy_id="strat-1",
        entry_time=datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc),
        order_state=ExecutionEnums.SellOrderState.NEW.value,
        filled_quantity=0,
    )
    db.insert_trade(sell)
    db.update_trade_fill(
        "S2", filled_quantity=40,
        order_state=ExecutionEnums.SellOrderState.PARTIAL_FILLED.value,
    )
    db.update_trade_fill(
        "S2", filled_quantity=40,
        order_state=ExecutionEnums.SellOrderState.CANCELLED.value,
    )
    assert _fetch_state(db, "S2") == ("CANCELLED", 40)


# ── Migration backfill ───────────────────────────────────────────────────────

def test_migration_backfills_legacy_status_into_order_state():
    """UT-EXE-014.001.M01.T06: legacy `status` values backfill to `order_state`."""
    e = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Build a pre-Phase-3 trades table (with `status`/`pnl`/no order_state).
    with e.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE trades ("
            " trade_id TEXT PRIMARY KEY,"
            " user_id INTEGER NOT NULL,"
            " symbol TEXT NOT NULL,"
            " side TEXT,"
            " entry_time TEXT,"
            " entry_price REAL,"
            " exit_time TEXT,"
            " exit_price REAL,"
            " quantity INTEGER,"
            " pnl REAL,"
            " strategy_id TEXT,"
            " mode TEXT NOT NULL DEFAULT 'paper',"
            " status TEXT DEFAULT 'SUBMITTED'"
            ")"
        ))
        conn.execute(sa.text(
            "CREATE TABLE positions ("
            " symbol TEXT NOT NULL,"
            " user_id INTEGER NOT NULL,"
            " quantity INTEGER,"
            " average_price REAL,"
            " stop_loss REAL,"
            " target_price REAL,"
            " trailing_stop REAL,"
            " mode TEXT NOT NULL DEFAULT 'paper',"
            " state TEXT NOT NULL DEFAULT 'NEW',"
            " PRIMARY KEY (user_id, symbol)"
            ")"
        ))
        for tid, status in [("L1", "SUBMITTED"), ("L2", "FILLED"), ("L3", "CLOSED")]:
            conn.execute(sa.text(
                "INSERT INTO trades (trade_id, user_id, symbol, status, quantity) "
                "VALUES (:tid, 1, 'AAPL', :st, 100)"
            ), {"tid": tid, "st": status})

    migrate_lifecycle_columns(e)

    with e.connect() as conn:
        rows = {
            r["trade_id"]: r["order_state"]
            for r in conn.execute(sa.text(
                "SELECT trade_id, order_state FROM trades"
            )).mappings()
        }
        cols_trades = {
            r["name"] for r in conn.execute(sa.text("PRAGMA table_info(trades)")).mappings()
        }
        cols_positions = {
            r["name"] for r in conn.execute(sa.text("PRAGMA table_info(positions)")).mappings()
        }

    assert rows == {"L1": "NEW", "L2": "FILLED", "L3": "FILLED"}
    assert "status" not in cols_trades
    assert "pnl"    not in cols_trades
    assert "state"  not in cols_positions
    assert "order_state"     in cols_trades
    assert "filled_quantity" in cols_trades
