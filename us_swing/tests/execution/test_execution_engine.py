"""Tests for execution/execution_engine.py — ExecutionEngine."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import sqlalchemy as sa

from us_swing.data.models import (
    AccountState,
    IBKRFill,
    OpenPosition,
    RiskConfig,
)
from us_swing.execution._enums import ExecutionEnums
from us_swing.db.manager import DatabaseManager
from us_swing.db.schema import create_schema as _create_schema, trades
from us_swing.exceptions import OrderSubmissionError
from us_swing.execution.execution_engine import ExecutionEngine
from us_swing.execution.position_tracker import PositionTracker
from us_swing.execution.risk_manager import RiskManager
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


def _account(equity: float = 100_000.0, deployed: float = 0.0) -> AccountState:
    return AccountState(
        user_id=1,
        equity=equity,
        start_of_day_equity=equity,
        open_position_value=deployed,
    )


def _signal(entry: float = 50.0, stop: float = 48.0) -> TradeSignal:
    return TradeSignal(
        action=Action.ENTRY,
        symbol="AAPL",
        strategy_id="s1",
        entry_price=entry,
        stop_loss=stop,
    )


def _risk(ok: bool = True, qty: int = 100) -> RiskManager:
    cfg = RiskConfig(
        risk_per_trade_pct=1.0,
        max_position_value=100_000.0,
        max_allocation_pct=50.0,
    )
    account = _account()
    return RiskManager(
        config=cfg,
        account_provider=lambda: account,
        cb_state_provider=lambda: False,
        user_id=1,
    )


def _engine_under_test(
    db: DatabaseManager,
    ibkr: MagicMock,
    risk: RiskManager | None = None,
    fills: list[FillEvent] | None = None,
    timeout: float = 2.0,
) -> ExecutionEngine:
    tracker = PositionTracker(db)
    fill_list: list[FillEvent] = fills if fills is not None else []
    r = risk or _risk()
    loop = asyncio.new_event_loop()
    ee = ExecutionEngine(
        ibkr=ibkr,
        risk=r,
        tracker=tracker,
        db=db,
        on_fill=fill_list.append,
        user_id=1,
        loop=loop,
        timeout=timeout,
    )
    return ee


def _mock_ibkr(order_id: int = 123) -> MagicMock:
    ibkr = MagicMock()
    ibkr.place_order = AsyncMock(return_value=order_id)
    return ibkr


# ── submit_signal ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_signal_calls_place_order(db: DatabaseManager):
    """UT-EXE-001.001.M02.T01: submit_signal() calls IBKR place_order when validation passes."""
    ibkr = _mock_ibkr(order_id=123)
    ee = _engine_under_test(db, ibkr)
    with patch("ib_insync.MarketOrder") as mo_cls, \
         patch("ib_insync.Stock") as stock_cls:
        mo_cls.return_value = MagicMock()
        stock_cls.return_value = MagicMock()
        result = await ee.submit_signal(_signal(), _account())
    assert result == 123
    ibkr.place_order.assert_called_once()


@pytest.mark.asyncio
async def test_submit_signal_returns_none_when_validation_fails(db: DatabaseManager, caplog):
    """UT-EXE-001.001.M02.T02: submit_signal() returns None when validation fails."""
    ibkr = _mock_ibkr()
    # Deploy nearly all capital so new signal fails
    cfg = RiskConfig(
        risk_per_trade_pct=1.0,
        max_position_value=10_000.0,
        max_allocation_pct=50.0,
    )
    r = RiskManager(
        config=cfg,
        account_provider=lambda: _account(equity=100_000.0, deployed=48_000.0),
        cb_state_provider=lambda: False,
        user_id=1,
    )
    ee = _engine_under_test(db, ibkr, risk=r)
    import logging
    with caplog.at_level(logging.WARNING):
        result = await ee.submit_signal(_signal(), _account(deployed=48_000.0))
    assert result is None
    ibkr.place_order.assert_not_called()
    assert any("REJECTED" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_submit_signal_persists_trade_to_db(db: DatabaseManager, engine):
    """UT-EXE-001.001.M02.T03: submit_signal() persists trade to DB on success."""
    ibkr = _mock_ibkr(order_id=123)
    ee = _engine_under_test(db, ibkr)
    with patch("ib_insync.MarketOrder") as mo_cls, \
         patch("ib_insync.Stock") as stock_cls:
        mo_cls.return_value = MagicMock()
        stock_cls.return_value = MagicMock()
        await ee.submit_signal(_signal(), _account())
    with engine.connect() as conn:
        row = conn.execute(sa.select(trades)).mappings().first()
    assert row is not None
    assert row["trade_id"] == "123"


@pytest.mark.asyncio
async def test_submit_signal_raises_on_ibkr_timeout(db: DatabaseManager):
    """UT-EXE-001.001.M02.T04: submit_signal() raises OrderSubmissionError on IBKR timeout."""
    async def _slow(*_args: object, **_kw: object) -> int:
        await asyncio.sleep(10)
        return 0

    ibkr = MagicMock()
    ibkr.place_order = _slow
    ee = _engine_under_test(db, ibkr, timeout=0.05)
    with patch("ib_insync.MarketOrder") as mo_cls, \
         patch("ib_insync.Stock") as stock_cls:
        mo_cls.return_value = MagicMock()
        stock_cls.return_value = MagicMock()
        with pytest.raises(OrderSubmissionError):
            await ee.submit_signal(_signal(), _account())


# ── handle_order_fill ─────────────────────────────────────────────────────────

def test_handle_fill_entry_creates_open_position(db: DatabaseManager):
    """UT-EXE-001.001.M02.T05: handle_order_fill() on entry fill creates OpenPosition."""
    ibkr = _mock_ibkr()
    fills: list[FillEvent] = []
    ee = _engine_under_test(db, ibkr, fills=fills)
    fill = IBKRFill(
        order_id=100,
        symbol="AAPL",
        filled_quantity=500,
        fill_price=50.0,
        fill_time=datetime.now(tz=timezone.utc),
    )
    ee.handle_order_fill(fill)
    assert ee._tracker.has_open(1, "AAPL")
    pos = ee._tracker.get_all(1)[0]
    assert pos.quantity == 500
    assert len(fills) == 1
    assert fills[0].is_entry is True


def test_handle_fill_exit_records_order_state(db: DatabaseManager, engine):
    """UT-EXE-001.001.M02.T06: handle_order_fill() on exit fill stamps order_state=FILLED."""
    ibkr = _mock_ibkr()
    fills: list[FillEvent] = []
    ee = _engine_under_test(db, ibkr, fills=fills)

    # First, open a position with a known trade record
    now = datetime.now(tz=timezone.utc)
    from us_swing.data.models import TradeRecord
    trade = TradeRecord(
        trade_id="100",
        user_id=1,
        symbol="AAPL",
        side="BUY",
        quantity=500,
        entry_price=50.0,
        mode="live",
        strategy_id="s1",
        entry_time=now,
        order_state=ExecutionEnums.BuyOrderState.NEW.value,
        filled_quantity=0,
    )
    db.insert_trade(trade)
    pos = OpenPosition(
        symbol="AAPL",
        user_id=1,
        quantity=500,
        average_price=50.0,
        stop_loss=48.0,
        target_price=55.0,
        mode="live",
        trade_id="100",
    )
    ee._tracker.open(pos)
    ee._pending[100] = "100"

    exit_fill = IBKRFill(
        order_id=200,
        symbol="AAPL",
        filled_quantity=500,
        fill_price=55.0,
        fill_time=datetime.now(tz=timezone.utc),
    )
    ee.handle_order_fill(exit_fill)

    assert not ee._tracker.has_open(1, "AAPL")
    with engine.connect() as conn:
        row = conn.execute(sa.select(trades).where(trades.c.trade_id == "100")).mappings().first()
    assert row is not None
    assert row["order_state"]     == "FILLED"
    assert row["filled_quantity"] == 500
    assert row["exit_price"]      == pytest.approx(55.0)


# ── exit_position ─────────────────────────────────────────────────────────────

def test_exit_position_submits_sell(db: DatabaseManager):
    """UT-EXE-001.001.M02.T07: exit_position() submits SELL for full open quantity."""
    ibkr = _mock_ibkr()
    fills: list[FillEvent] = []
    ee = _engine_under_test(db, ibkr, fills=fills)

    pos = OpenPosition(
        symbol="AAPL",
        user_id=1,
        quantity=500,
        average_price=50.0,
        stop_loss=48.0,
        target_price=55.0,
        mode="live",
    )
    ee._tracker.open(pos)

    with patch("ib_insync.MarketOrder") as mo_cls, \
         patch("ib_insync.Stock") as stock_cls:
        mo_cls.return_value = MagicMock()
        stock_cls.return_value = MagicMock()
        result = ee.exit_position("AAPL")

    assert result is not None
    stock_cls.assert_called_once_with("AAPL", "SMART", "USD")
    mo_cls.assert_called_once_with("SELL", 500)


# ── quantity override ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quantity_override_used(db: DatabaseManager):
    """UT-EXE-005.005.M02.T01: submit_signal() with quantity_override uses override."""
    ibkr = _mock_ibkr(order_id=999)
    ee = _engine_under_test(db, ibkr)
    with patch("ib_insync.MarketOrder") as mo_cls, \
         patch("ib_insync.Stock") as stock_cls:
        mo_cls.return_value = MagicMock()
        stock_cls.return_value = MagicMock()
        await ee.submit_signal(_signal(), _account(), quantity_override=100)
    # MarketOrder should be called with qty=100
    mo_cls.assert_called_once_with("BUY", 100)


@pytest.mark.asyncio
async def test_quantity_override_zero_raises(db: DatabaseManager):
    """UT-EXE-005.005.M02.T03: Override quantity <= 0 raises ValueError."""
    ibkr = _mock_ibkr()
    ee = _engine_under_test(db, ibkr)
    with pytest.raises(ValueError):
        await ee.submit_signal(_signal(), _account(), quantity_override=0)


@pytest.mark.asyncio
async def test_quantity_override_checked_by_risk(db: DatabaseManager):
    """UT-EXE-005.005.M02.T02: Override quantity still checked by capital availability."""
    ibkr = _mock_ibkr()
    # Nearly all capital deployed → override of 5000 * $50 = $250k >> allowed
    cfg = RiskConfig(
        risk_per_trade_pct=1.0,
        max_position_value=100_000.0,
        max_allocation_pct=50.0,
    )
    account = _account(equity=50_000.0, deployed=20_000.0)
    r = RiskManager(
        config=cfg,
        account_provider=lambda: account,
        cb_state_provider=lambda: False,
        user_id=1,
    )
    ee = _engine_under_test(db, ibkr, risk=r)
    # override=5000 shares @ $50 = $250k > allowed=50k*50%=$25k
    result = await ee.submit_signal(
        _signal(entry=50.0, stop=48.0),
        account,
        quantity_override=5000,
    )
    assert result is None
    ibkr.place_order.assert_not_called()
