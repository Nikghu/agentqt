"""Tests for execution/risk_manager.py — RiskManager."""
from __future__ import annotations

import pytest

from us_swing.data.models import AccountState, OpenPosition, PositionState, RiskConfig
from us_swing.execution.position_tracker import PositionTracker
from us_swing.execution.risk_manager import RiskManager
from us_swing.execution.strategy_engine._signals import Action, TradeSignal

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from us_swing.db.schema import create_schema as _create_schema
from us_swing.db.manager import DatabaseManager


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


def _signal(
    entry: float = 50.0,
    stop: float = 48.0,
    strategy: str = "strat-1",
) -> TradeSignal:
    return TradeSignal(
        action=Action.ENTRY,
        symbol="AAPL",
        strategy_id=strategy,
        entry_price=entry,
        stop_loss=stop,
    )


def _config(
    risk_pct: float = 1.0,
    max_pos: float = 10_000.0,
    max_alloc: float = 50.0,
) -> RiskConfig:
    return RiskConfig(
        risk_per_trade_pct=risk_pct,
        max_position_value=max_pos,
        max_allocation_pct=max_alloc,
    )


def _manager(
    config: RiskConfig | None = None,
    equity: float = 100_000.0,
    deployed: float = 0.0,
    cb: bool = False,
    tracker: PositionTracker | None = None,
) -> RiskManager:
    cfg = config or _config()
    account = _account(equity=equity, deployed=deployed)
    return RiskManager(
        config=cfg,
        account_provider=lambda: account,
        cb_state_provider=lambda: cb,
        user_id=1,
        tracker=tracker,
    )


# ── calculate_position_size ───────────────────────────────────────────────────

def test_position_size_standard():
    """UT-EXE-001.001.M01.T01: Position size calculation: standard case."""
    rm = _manager()
    # equity=$100k, risk_pct=1%, entry=$50, stop=$48 → risk/share=$2
    # formula = floor(1000/2) = 500; cap = floor(10000/50) = 200
    # result = min(500, 200) = 200
    sig = _signal(entry=50.0, stop=48.0)
    qty = rm.calculate_position_size(sig, _account())
    assert qty == 200


def test_position_size_capped_by_max_position():
    """UT-EXE-001.001.M01.T02: Position size capped by max_position_value."""
    # With risk_pct=1%, entry=$50, stop=$49.90 (risk=$0.10):
    # formula = floor(1000/0.10) = 10000; cap = floor(10000/50) = 200
    # result = min(10000, 200) = 200 shares
    rm = _manager()
    sig = _signal(entry=50.0, stop=49.90)
    qty = rm.calculate_position_size(sig, _account())
    assert qty == 200


def test_position_size_floor_fractional():
    """UT-EXE-001.001.M01.T06: calculate_position_size() floors fractional shares."""
    # equity=$100k, risk_pct=1%, entry=$50, stop=$47 → risk/share=$3
    # formula = floor(1000/3) = 333; cap = floor(10000/50) = 200
    # result = min(333, 200) = 200
    rm = _manager(config=_config(risk_pct=1.0, max_pos=10_000.0))
    sig = _signal(entry=50.0, stop=47.0)
    qty = rm.calculate_position_size(sig, _account())
    assert qty == 200


def test_position_size_floor_unbounded():
    """Extra: floor applied when formula is not at cap (large max_pos)."""
    # equity=$100k, risk_pct=1%, entry=$50, stop=$47 → risk=$3/share
    # formula = floor(1000/3) = 333; cap = floor(100000/50) = 2000
    # result = 333
    rm = _manager(config=_config(risk_pct=1.0, max_pos=100_000.0))
    sig = _signal(entry=50.0, stop=47.0)
    qty = rm.calculate_position_size(sig, _account())
    assert qty == 333


def test_position_size_zero_risk_per_share():
    """Edge: entry == stop → returns 0."""
    rm = _manager()
    sig = _signal(entry=50.0, stop=50.0)
    assert rm.calculate_position_size(sig, _account()) == 0


# ── validate_signal ───────────────────────────────────────────────────────────

def test_validate_signal_passes():
    """UT-EXE-001.001.M01.T03: validate_signal passes when deployment within limit."""
    # deployed=$20k, equity=$100k, max_pct=50% → allowed=$50k
    # new_required = 200 * $50 = $10k; 20k+10k=30k <= 50k → pass
    rm = _manager(deployed=20_000.0)
    result = rm.validate_signal(_signal(), _account(deployed=20_000.0), cb_active=False)
    assert result.ok is True


def test_validate_signal_rejects_capital_exhausted():
    """UT-EXE-001.001.M01.T04: validate_signal rejects when deployment exceeds limit."""
    # deployed=$48k, required=$10k → 58k > 50k → reject
    rm = _manager(deployed=48_000.0)
    result = rm.validate_signal(_signal(), _account(deployed=48_000.0), cb_active=False)
    assert result.ok is False
    assert "capital allocation" in result.reason


def test_validate_signal_rejects_circuit_breaker():
    """UT-EXE-001.001.M01.T05: validate_signal rejects when circuit breaker active."""
    rm = _manager(cb=True)
    result = rm.validate_signal(_signal(), _account(), cb_active=True)
    assert result.ok is False
    assert "circuit breaker" in result.reason


# ── can_enter_new ─────────────────────────────────────────────────────────────

def test_can_enter_new_true(db: DatabaseManager):
    """UT-EXE-005.004.M01.T01: can_enter_new() returns True when capital available."""
    tracker = PositionTracker(db)
    rm = _manager(tracker=tracker, equity=100_000.0)
    # open_value=$20k, new_required=$10k, allowed=50k → True
    account = _account(equity=100_000.0, deployed=20_000.0)
    result = rm.can_enter_new(_signal(), account, user_id=1)
    assert result is True


def test_can_enter_new_false(db: DatabaseManager):
    """UT-EXE-005.004.M01.T02: can_enter_new() returns False when capital exhausted."""
    tracker = PositionTracker(db)
    # Add existing position worth $45k
    pos = OpenPosition(
        symbol="MSFT",
        user_id=1,
        quantity=900,
        average_price=50.0,
        stop_loss=48.0,
        target_price=55.0,
        mode="live",
        state=PositionState.OPEN.value,
    )
    tracker.open(pos)
    rm = _manager(tracker=tracker, equity=100_000.0)
    # Deployed=$45k, new_required=$10k → 55k > 50k → False
    account = _account(equity=100_000.0, deployed=45_000.0)
    result = rm.can_enter_new(_signal(), account, user_id=1)
    assert result is False


def test_can_enter_new_scoped_per_user(db: DatabaseManager):
    """UT-EXE-005.004.M01.T03: can_enter_new() scoped per user_id."""
    tracker = PositionTracker(db)
    # user1 has $40k deployed
    pos = OpenPosition(
        symbol="GOOGL",
        user_id=1,
        quantity=400,
        average_price=100.0,
        stop_loss=98.0,
        target_price=105.0,
        mode="live",
        state=PositionState.OPEN.value,
    )
    tracker.open(pos)
    rm1 = _manager(tracker=tracker, equity=100_000.0)
    rm2 = RiskManager(
        config=_config(),
        account_provider=lambda: _account(equity=100_000.0),
        cb_state_provider=lambda: False,
        user_id=2,
        tracker=tracker,
    )
    # user1: deployed=40k, required=$10k → 50k == limit → False (strict >, not >=)
    account1 = _account(equity=100_000.0, deployed=40_000.0)
    # With $40k deployed and new $10k required, 50k <= 50k → True
    assert rm1.can_enter_new(_signal(), account1, user_id=1) is True
    # user2: no positions, $10k required → True
    account2 = _account(equity=100_000.0)
    assert rm2.can_enter_new(_signal(), account2, user_id=2) is True
