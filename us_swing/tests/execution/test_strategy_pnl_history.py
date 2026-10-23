"""
Module: MD-EXE-019.001.M01 / MD-EXE-019.002.M02 / MD-EXE-019.004.M03 — Strategy P&L history tests
Parent SRD: SRD-EXE-019.001, .002, .003, .004
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from PyQt6.QtCore import QObject

from us_swing.db.schema import create_schema
from us_swing.execution.trade_cycle import CycleSnapshot, TradeCycleState
from us_swing.execution.trade_cycle._pnl_history import StrategyPnlSummary, summarise
from us_swing.execution.trade_cycle._repository import TradeCycleRepository
from us_swing.execution.trade_cycle._schema import trade_cycles
from us_swing.gui.app_service import AppService


@pytest.fixture
def engine() -> sa.Engine:
    eng = sa.create_engine("sqlite:///:memory:")
    create_schema(eng)
    return eng


_SEQ = iter(range(1, 10_000))


def _add_cycle(
    engine: sa.Engine,
    *,
    strategy: str = "S1",
    symbol: str = "AAPL",
    user_id: int = 1,
    closed_at: str | None = "2026-10-20T15:00:00",
    pnl: float | None = 10.0,
) -> None:
    """Insert one cycle through the repository, then close it in place."""
    repo = TradeCycleRepository(engine)
    n = next(_SEQ)
    snap = repo.insert_open(row={
        "strategy_id":             strategy,
        "symbol":                  f"{symbol}{n}",
        "user_id":                 user_id,
        "monitoring_session_date": "2026-10-20",
        "entry_time":              "2026-10-20T13:35:00",
        "entry_price":             100.0,
        "entry_qty":               10,
        "entry_order_id":          f"ord-{n}",
        "hard_stop_loss":          95.0,
        "target_price":            None,
        "target_type":             "fixed",
        "stoploss_type":           "fixed",
        "trailing_mode":           None,
        "trailing_offset":         None,
        "state":                   "OPEN",
    })
    if closed_at is None:
        return
    with engine.begin() as conn:
        conn.execute(
            sa.update(trade_cycles)
            .where(trade_cycles.c.cycle_id == snap.cycle_id)
            .values(state="CLOSED", closed_at=closed_at, realized_pnl_usd=pnl)
        )


def _snap(pnl: float | None, closed_at: str = "2026-10-20T15:00:00") -> CycleSnapshot:
    return CycleSnapshot(
        strategy_id="S1", symbol="AAPL", state=TradeCycleState.CLOSED,
        realized_pnl_usd=pnl, closed_at=closed_at,
    )


# ── Repository read ───────────────────────────────────────────────────────────

def test_closed_for_strategy_only_closed_in_order(engine: sa.Engine) -> None:
    """UT-EXE-019.001.M01.T01: Returns only the strategy's CLOSED cycles in close order."""
    _add_cycle(engine, closed_at="2026-10-21T15:00:00", pnl=2.0)
    _add_cycle(engine, closed_at="2026-10-19T15:00:00", pnl=1.0)
    _add_cycle(engine, closed_at="2026-10-22T15:00:00", pnl=3.0)
    _add_cycle(engine, closed_at=None)
    _add_cycle(engine, strategy="S2", closed_at="2026-10-20T15:00:00", pnl=9.0)

    rows = TradeCycleRepository(engine).closed_for_strategy("S1")

    assert [r.realized_pnl_usd for r in rows] == [1.0, 2.0, 3.0]
    assert all(r.state == "CLOSED" for r in rows)


def test_closed_for_strategy_since(engine: sa.Engine) -> None:
    """UT-EXE-019.001.M01.T02: Start filter keeps closes on or after since_iso."""
    for day in ("2026-10-19", "2026-10-20", "2026-10-21"):
        _add_cycle(engine, closed_at=f"{day}T15:00:00")

    rows = TradeCycleRepository(engine).closed_for_strategy(
        "S1", since_iso="2026-10-20T00:00:00"
    )

    assert len(rows) == 2


def test_closed_for_strategy_user(engine: sa.Engine) -> None:
    """UT-EXE-019.001.M01.T03: User filter keeps only that user's cycles."""
    _add_cycle(engine, user_id=1)
    _add_cycle(engine, user_id=2)
    _add_cycle(engine, user_id=2)

    rows = TradeCycleRepository(engine).closed_for_strategy("S1", user_id=2)

    assert len(rows) == 2
    assert {r.user_id for r in rows} == {2}


def test_closed_for_strategy_unknown(engine: sa.Engine) -> None:
    """UT-EXE-019.001.M01.T04: Unknown strategy returns an empty tuple."""
    _add_cycle(engine)
    assert TradeCycleRepository(engine).closed_for_strategy("NOPE") == ()


def test_strategy_closed_index_created(engine: sa.Engine) -> None:
    """UT-EXE-019.003.M01.T05: create_schema adds idx_trade_cycles_strategy_closed."""
    names = {ix["name"] for ix in sa.inspect(engine).get_indexes("trade_cycles")}
    assert "idx_trade_cycles_strategy_closed" in names


# ── Summary ───────────────────────────────────────────────────────────────────

_DAY = ("2026-10-20T04:00:00", "2026-10-21T04:00:00")


def test_summary_running_total() -> None:
    """UT-EXE-019.002.M02.T01: Running total and total."""
    s = summarise([_snap(10), _snap(-4), _snap(6)], *_DAY)
    assert [p.cumulative for p in s.points] == [10, 6, 12]
    assert s.total == 12
    assert s.trades == 3


def test_summary_win_rate_and_averages() -> None:
    """UT-EXE-019.002.M02.T02: Win rate and averages."""
    s = summarise([_snap(10), _snap(-4), _snap(6), _snap(-2)], *_DAY)
    assert s.wins == 2
    assert s.win_rate == pytest.approx(0.5)
    assert s.avg_win == pytest.approx(8)
    assert s.avg_loss == pytest.approx(-3)


def test_summary_max_drawdown_span() -> None:
    """UT-EXE-019.002.M02.T03: Max drawdown and its span."""
    s = summarise([_snap(10), _snap(5), _snap(-8), _snap(-4), _snap(20)], *_DAY)
    assert s.max_drawdown == pytest.approx(-12)
    assert (s.dd_start, s.dd_end) == (1, 3)


def test_summary_skips_missing_pnl() -> None:
    """UT-EXE-019.002.M02.T04: A cycle without realized P&L is skipped."""
    s = summarise([_snap(5), _snap(None), _snap(5)], *_DAY)
    assert len(s.points) == 2
    assert s.total == 10


def test_summary_empty() -> None:
    """UT-EXE-019.002.M02.T05: Empty input gives a zero summary."""
    s = summarise([], *_DAY)
    assert s == StrategyPnlSummary()
    assert s.dd_start == -1


def test_summary_today() -> None:
    """UT-EXE-019.002.M02.T06: Today only counts closes inside today's bounds."""
    s = summarise(
        [
            _snap(7, "2026-10-19T18:00:00"),
            _snap(-3, "2026-10-20T15:00:00"),
            _snap(1, "2026-10-20T19:00:00"),
        ],
        *_DAY,
    )
    assert s.today == pytest.approx(-2)


def test_summary_losing_from_start() -> None:
    """UT-EXE-019.002.M02.T07: Drawdown from the zero start."""
    s = summarise([_snap(-5), _snap(-5)], *_DAY)
    assert s.max_drawdown == pytest.approx(-10)
    assert (s.dd_start, s.dd_end) == (-1, 1)


# ── App service accessor ──────────────────────────────────────────────────────

def _svc(tc_query: object | None, viewing_uid: int | None) -> AppService:
    svc = AppService.__new__(AppService)
    QObject.__init__(svc)
    svc._tc_query = tc_query          # type: ignore[attr-defined]
    svc._viewing_uid = viewing_uid    # type: ignore[attr-defined]
    return svc


def test_get_strategy_pnl_viewing_user(engine: sa.Engine) -> None:
    """UT-EXE-019.004.M03.T01: The viewing user is the filter."""
    _add_cycle(engine, user_id=1, pnl=100.0)
    _add_cycle(engine, user_id=2, pnl=5.0)
    svc = _svc(TradeCycleRepository(engine), viewing_uid=2)

    s = svc.get_strategy_pnl("S1")

    assert s.trades == 1
    assert s.total == pytest.approx(5.0)


def test_get_strategy_pnl_no_ledger() -> None:
    """UT-EXE-019.004.M03.T02: No ledger returns an empty summary."""
    assert _svc(None, viewing_uid=None).get_strategy_pnl("S1") == StrategyPnlSummary()
