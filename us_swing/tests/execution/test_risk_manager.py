"""Tests for execution/risk_manager.py — RiskManager."""
from __future__ import annotations

import pytest

from us_swing.data.models import AccountState, OpenPosition, RiskConfig
from us_swing.execution.risk_manager import RiskManager
from us_swing.execution.strategy_engine._signals import Action, TradeSignal

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from us_swing.db.schema import create_schema as _create_schema
from us_swing.db.manager import DatabaseManager


class _FakeTracker:
    """In-memory stand-in for the retired PositionTracker; RiskManager only
    needs ``get_all(user_id)`` for capital checks."""

    def __init__(self) -> None:
        self._positions: list[OpenPosition] = []

    def open(self, pos: OpenPosition) -> None:
        self._positions.append(pos)

    def get_all(self, user_id: int) -> list[OpenPosition]:
        return [p for p in self._positions if p.user_id == user_id]


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
    max_cap: float = 2_000.0,
) -> RiskConfig:
    return RiskConfig(
        risk_per_trade_pct=risk_pct,
        max_position_value=max_pos,
        max_capital_value=max_cap,
    )


def _manager(
    config: RiskConfig | None = None,
    equity: float = 100_000.0,
    deployed: float = 0.0,
    cb: bool = False,
    tracker: _FakeTracker | None = None,
    effective_capital: float | None = None,
) -> RiskManager:
    cfg = config or _config()
    account = _account(equity=equity, deployed=deployed)
    return RiskManager(
        config=cfg,
        account_provider=lambda: account,
        cb_state_provider=lambda: cb,
        user_id=1,
        tracker=tracker,
        effective_capital_provider=(
            (lambda: effective_capital) if effective_capital is not None else None
        ),
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
    """UT-EXE-001.001.M01.T03: validate_signal passes for a normal signal."""
    rm = _manager(deployed=20_000.0)
    result = rm.validate_signal(_signal(), _account(deployed=20_000.0), cb_active=False)
    assert result.ok is True


def test_validate_signal_capital_is_advisory():
    """UT-EXE-017.006.M01.T07: capital/position limits no longer block (advisory)."""
    # Even a huge deployment does not reject — only the circuit breaker blocks.
    rm = _manager(deployed=48_000.0)
    result = rm.validate_signal(_signal(), _account(deployed=48_000.0), cb_active=False)
    assert result.ok is True


def test_validate_signal_rejects_circuit_breaker():
    """UT-EXE-001.001.M01.T05: validate_signal rejects when circuit breaker active."""
    rm = _manager(cb=True)
    result = rm.validate_signal(_signal(), _account(), cb_active=True)
    assert result.ok is False
    assert "circuit breaker" in result.reason


# ── margin_available (replaces the retired can_enter_new) ─────────────────────

def test_margin_available_with_room(db: DatabaseManager):
    """UT-EXE-017.015.M10.T01: margin_available = budget − deployed across cycles."""
    tracker = _FakeTracker()
    pos = OpenPosition(
        symbol="MSFT", user_id=1, quantity=400, average_price=50.0,
        stop_loss=48.0, target_price=55.0, mode="live",
    )  # $20k deployed
    tracker.open(pos)
    rm = _manager(tracker=tracker, equity=100_000.0)
    assert rm.margin_available() == 80_000.0


def test_margin_available_exhausted(db: DatabaseManager):
    """UT-EXE-017.015.M10.T02: margin floors at zero when deployed nears the budget."""
    tracker = _FakeTracker()
    pos = OpenPosition(
        symbol="MSFT", user_id=1, quantity=900, average_price=50.0,
        stop_loss=48.0, target_price=55.0, mode="live",
    )  # $45k deployed
    tracker.open(pos)
    rm = _manager(tracker=tracker, equity=100_000.0, effective_capital=50_000.0)
    assert rm.margin_available() == 5_000.0


def test_margin_available_scoped_per_user(db: DatabaseManager):
    """UT-EXE-017.017.M10: margin_available is scoped to the manager's user_id."""
    tracker = _FakeTracker()
    pos = OpenPosition(
        symbol="GOOGL", user_id=1, quantity=400, average_price=100.0,
        stop_loss=98.0, target_price=105.0, mode="live",
    )  # $40k deployed for user 1 only
    tracker.open(pos)
    rm1 = _manager(tracker=tracker, equity=100_000.0)  # user_id=1
    rm2 = RiskManager(
        config=_config(),
        account_provider=lambda: _account(equity=100_000.0),
        cb_state_provider=lambda: False,
        user_id=2,
        tracker=tracker,
    )
    assert rm1.margin_available() == 60_000.0    # 100k − 40k (user 1 position)
    assert rm2.margin_available() == 100_000.0   # user 2 has no positions
