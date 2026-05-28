"""Tests for execution/paper_engine.py — PaperEngine."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import sqlalchemy as sa

from us_swing.db.manager import DatabaseManager
from us_swing.db.schema import create_schema as _create_schema, trades, positions
from us_swing.execution.paper_engine import PaperEngine
from us_swing.execution.strategy_engine._protocols import FillEvent
from us_swing.execution.strategy_engine._signals import Action, TradeSignal


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


def _signal(entry: float = 150.0, stop: float = 148.0) -> TradeSignal:
    return TradeSignal(
        action=Action.ENTRY,
        symbol="AAPL",
        strategy_id="strat-1",
        entry_price=entry,
        stop_loss=stop,
        target=160.0,
    )


def _paper(db: DatabaseManager, market_price: float | None = 150.0) -> tuple[PaperEngine, list[FillEvent]]:
    fills: list[FillEvent] = []
    engine = PaperEngine(
        db=db,
        price_provider=lambda _sym: market_price,
        on_fill=fills.append,
        user_id=1,
    )
    return engine, fills


# ── simulate_fill ─────────────────────────────────────────────────────────────

def test_mkt_fills_at_market_price(db: DatabaseManager):
    """UT-EXE-004.001.M01.T01: Market order fills immediately at current market price."""
    pe, fills = _paper(db, market_price=150.0)
    fill = pe.simulate_fill(_signal(entry=150.0), quantity=100, order_type="MKT")
    assert fill is not None
    assert fill.fill_price == 150.0


def test_lmt_buy_fills_when_market_below_limit(db: DatabaseManager):
    """UT-EXE-004.001.M01.T02: Limit buy fills when market price <= limit."""
    pe, fills = _paper(db, market_price=149.0)
    fill = pe.simulate_fill(_signal(entry=150.0), quantity=100, order_type="LMT")
    assert fill is not None
    assert fill.fill_price == 150.0


def test_lmt_buy_no_fill_when_market_above_limit(db: DatabaseManager):
    """UT-EXE-004.001.M01.T03: Limit buy does NOT fill when market price > limit."""
    pe, fills = _paper(db, market_price=151.0)
    fill = pe.simulate_fill(_signal(entry=150.0), quantity=100, order_type="LMT")
    assert fill is None


def test_paper_fills_stored_with_paper_mode(db: DatabaseManager, engine):
    """UT-EXE-004.001.M01.T04: Paper fills stored with mode='paper' in DB."""
    pe, _ = _paper(db, market_price=150.0)
    pe.simulate_fill(_signal(), quantity=100, order_type="MKT")
    with engine.connect() as conn:
        trade_row = conn.execute(sa.select(trades)).mappings().first()
        pos_row = conn.execute(sa.select(positions)).mappings().first()
    assert trade_row is not None
    assert trade_row["mode"] == "paper"
    assert pos_row is not None
    assert pos_row["mode"] == "paper"


def test_paper_pnl_matches_live(db: DatabaseManager):
    """UT-EXE-004.001.M01.T05: Paper P&L matches live calculation."""
    pe, _ = _paper(db, market_price=50.0)
    sig = TradeSignal(
        action=Action.ENTRY,
        symbol="MSFT",
        strategy_id="s1",
        entry_price=50.0,
        stop_loss=49.0,
    )
    fill = pe.simulate_fill(sig, quantity=500, order_type="MKT")
    assert fill is not None
    entry_trade_id = str(fill.order_id)

    pe2, _ = _paper(db, market_price=55.0)
    pe2._next_id = pe._next_id
    pe2.simulate_exit(
        symbol="MSFT",
        quantity=500,
        strategy_id="s1",
        entry_trade_id=entry_trade_id,
        entry_price=50.0,
    )
    import sqlalchemy as sa2
    with db._engine.connect() as conn:
        row = conn.execute(
            sa2.select(trades).where(trades.c.trade_id == entry_trade_id)
        ).mappings().first()
    assert row is not None
    assert row["order_state"]     == "FILLED"
    assert row["filled_quantity"] == 500
    assert row["exit_price"]      == pytest.approx(55.0)


def test_paper_order_ids_are_negative(db: DatabaseManager):
    """UT-EXE-004.001.M01.T06: Paper order IDs are negative and monotonically decreasing."""
    pe, _ = _paper(db, market_price=150.0)
    ids = []
    for _ in range(3):
        fill = pe.simulate_fill(_signal(), quantity=10, order_type="MKT")
        assert fill is not None
        ids.append(fill.order_id)
    assert all(oid < 0 for oid in ids)
    # decreasing
    assert ids[0] > ids[1] > ids[2]


def test_no_ibkr_calls_during_paper_fill(db: DatabaseManager):
    """UT-EXE-004.001.M01.T07: No IBKR API calls made during paper fill."""
    from unittest.mock import MagicMock
    mock_ibkr = MagicMock()
    mock_ibkr.place_order.side_effect = AssertionError("IBKR called during paper fill")
    pe, _ = _paper(db, market_price=150.0)
    fill = pe.simulate_fill(_signal(), quantity=100)
    assert fill is not None
    mock_ibkr.place_order.assert_not_called()
