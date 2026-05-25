"""
Module: MD-EXE-011.001.M02 — tests
Parent SRD: SRD-EXE-011.002, .004, .005, .007, .010
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from us_swing.execution.strategy_engine._context import _CycleState, _StrategyContext

_ET = ZoneInfo("America/New_York")


@dataclass
class _Cfg:
    name: str = "test_strat"
    mode: str = "auto"
    symbol_mode: str = "all"
    symbols_include: list[str] = field(default_factory=list)
    symbols_exclude: list[str] = field(default_factory=list)
    start_time: str = "09:30"
    end_time: str = "15:30"
    start_date: str = "2026-01-01"
    end_date: str = "2099-12-31"
    days: list[str] = field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    trade_type: str = "Intraday"
    auto_trade: bool = True
    capital_max: int = 10
    entry_condition: str = ""
    exit_condition: str = ""
    stoploss_enabled: bool = False
    stoploss_value: float = 1.0
    target_enabled: bool = False
    target_value: float = 2.0
    strategy_signal: dict[str, Any] = field(default_factory=lambda: {"Status": "Active"})


def _ctx(**kwargs: Any) -> _StrategyContext:
    return _StrategyContext(cfg=_Cfg(**kwargs))  # type: ignore[arg-type]


def test_accepts_all_mode_returns_true_for_any_symbol() -> None:
    """UT-EXE-011.001.M02.T01: accepts() in 'all' mode returns True for any symbol."""
    ctx = _ctx(symbol_mode="all")
    assert ctx.accepts("AAPL") is True
    assert ctx.accepts("RANDOM_XYZ") is True


def test_accepts_include_only_true_for_listed_false_for_unlisted() -> None:
    """UT-EXE-011.001.M02.T02: include_only → True for AAPL, False for MSFT."""
    ctx = _ctx(symbol_mode="include", symbols_include=["AAPL"])
    assert ctx.accepts("AAPL") is True
    assert ctx.accepts("MSFT") is False


def test_accepts_exclude_these_false_for_excluded_true_for_others() -> None:
    """UT-EXE-011.001.M02.T03: exclude_these → False for TSLA, True for NVDA."""
    ctx = _ctx(symbol_mode="exclude", symbols_exclude=["TSLA"])
    assert ctx.accepts("TSLA") is False
    assert ctx.accepts("NVDA") is True


def test_within_schedule_false_outside_time_window() -> None:
    """UT-EXE-011.001.M02.T04: within_schedule False when time is 08:00 ET."""
    ctx = _ctx()
    now = datetime(2026, 5, 19, 8, 0, tzinfo=_ET)  # Monday, 08:00 ET — before open
    assert ctx.within_schedule(now) is False


def test_within_schedule_half_open_true_at_start_false_at_end() -> None:
    """UT-EXE-011.001.M02.T05: Half-open: True at exactly 09:30, False at exactly 15:30."""
    ctx = _ctx()
    at_open = datetime(2026, 5, 19, 9, 30, tzinfo=_ET)
    at_close = datetime(2026, 5, 19, 15, 30, tzinfo=_ET)
    assert ctx.within_schedule(at_open) is True
    assert ctx.within_schedule(at_close) is False


def test_within_schedule_false_on_saturday() -> None:
    """UT-EXE-011.001.M02.T06: Saturday → within_schedule returns False."""
    ctx = _ctx()
    saturday = datetime(2026, 5, 23, 10, 0, tzinfo=_ET)  # Saturday
    assert ctx.within_schedule(saturday) is False


def test_state_unknown_symbol_returns_active() -> None:
    """UT-EXE-011.001.M02.T07: state(unknown_symbol) → _CycleState.ACTIVE."""
    ctx = _ctx()
    assert ctx.state("UNKNOWN") == _CycleState.ACTIVE


def test_lock_for_same_symbol_returns_same_instance() -> None:
    """UT-EXE-011.001.M02.T08: lock_for('AAPL') called twice → same Lock instance."""
    ctx = _ctx()
    lock1 = ctx.lock_for("AAPL")
    lock2 = ctx.lock_for("AAPL")
    assert lock1 is lock2
    assert isinstance(lock1, asyncio.Lock)
