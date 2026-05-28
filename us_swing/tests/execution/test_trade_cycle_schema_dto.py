"""
Module: MD-EXE-012.001.M01/M02 — schema and DTO tests
Parent SRD: SRD-EXE-012.001, .010, .011
"""
from __future__ import annotations

import dataclasses

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect

from us_swing.db.schema import create_schema
from us_swing.execution.trade_cycle._dto import (
    EXIT_REASONS,
    CycleSnapshot,
    TradeCycleState,
    coerce_state,
)


@pytest.fixture
def mem_engine() -> sa.Engine:
    eng = sa.create_engine("sqlite:///:memory:")
    create_schema(eng)
    return eng


def test_trade_cycles_table_created(mem_engine: sa.Engine) -> None:
    """UT-EXE-012.001.M01.T01: trade_cycles table exists with all required columns."""
    insp = inspect(mem_engine)
    assert insp.has_table("trade_cycles")
    cols = {c["name"] for c in insp.get_columns("trade_cycles")}
    required = {
        "cycle_id", "strategy_id", "symbol", "user_id", "state",
        "entry_price", "entry_qty", "entry_order_id", "hard_stop_loss",
        "realized_pnl_usd", "monitoring_session_date", "opened_at",
    }
    for col in required:
        assert col in cols, f"Column {col!r} missing from trade_cycles"


def test_composite_indexes_exist(mem_engine: sa.Engine) -> None:
    """UT-EXE-012.001.M01.T02: idx_trade_cycles_state_symbol and strategy_symbol_state indexes present."""
    insp = inspect(mem_engine)
    idx_names = {idx["name"] for idx in insp.get_indexes("trade_cycles")}
    assert "idx_trade_cycles_state_symbol" in idx_names
    assert "idx_trade_cycles_strategy_symbol_state" in idx_names


def test_cycle_snapshot_frozen_schema_version_1() -> None:
    """UT-EXE-012.001.M02.T01: CycleSnapshot is frozen and schema_version defaults to 1."""
    snap = CycleSnapshot()
    assert snap.schema_version == 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.schema_version = 99  # type: ignore[misc]


def test_cycle_state_enum_values_match_srd() -> None:
    """UT-EXE-012.001.M02.T02: TradeCycleState enum has 5 members with the expected wire values."""
    values = {s.value for s in TradeCycleState}
    assert values == {"OPENING", "OPEN", "CLOSING", "CLOSED", "ABORTED"}


def test_exit_reasons_match_srd() -> None:
    """UT-EXE-012.001.M02.T03: EXIT_REASONS includes all 8 reason strings (squaring_off added Phase 1)."""
    expected = {
        "strategy", "hard_sl", "target", "trailing_sl",
        "end_time", "manual", "emergency", "squaring_off",
    }
    assert EXIT_REASONS == expected


def test_trade_cycle_state_terminal_helpers() -> None:
    """UT-EXE-012.001.M02.T04: is_terminal()/is_non_terminal() classify correctly."""
    assert TradeCycleState.CLOSED.is_terminal() is True
    assert TradeCycleState.ABORTED.is_terminal() is True
    assert TradeCycleState.OPENING.is_terminal() is False
    assert TradeCycleState.OPEN.is_terminal() is False
    assert TradeCycleState.CLOSING.is_terminal() is False
    assert TradeCycleState.OPENING.is_non_terminal() is True
    assert TradeCycleState.CLOSED.is_non_terminal() is False


def test_coerce_state_rejects_unknown() -> None:
    """UT-EXE-012.001.M02.T05: coerce_state raises ValueError on unknown wire value."""
    assert coerce_state("OPEN") is TradeCycleState.OPEN
    assert coerce_state(TradeCycleState.OPENING) is TradeCycleState.OPENING
    with pytest.raises(ValueError):
        coerce_state("BOGUS_STATE")
