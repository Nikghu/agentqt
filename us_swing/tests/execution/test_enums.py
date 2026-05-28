"""
Tests for MD-EXE-013.001.M01 — execution/_enums.py
Parent SRD: SRD-EXE-013.001 (forthcoming in Phase 1)

Phase 0 acceptance: trivial value/name assertions on the ExecutionEnums
container. Verifies StrEnum string equality and that the public import
path resolves.
"""
from __future__ import annotations

from enum import StrEnum

import pytest

from us_swing.execution import ExecutionEnums as E


class TestPublicImport:
    def test_container_is_importable_from_package_root(self) -> None:
        """UT-EXE-013.001.M01.T01: ExecutionEnums re-exported from us_swing.execution."""
        from us_swing.execution import ExecutionEnums

        assert ExecutionEnums is E

    def test_container_exposes_all_six_enums(self) -> None:
        """UT-EXE-013.001.M01.T02: container surfaces every planned enum class."""
        expected = {
            "StrategyRunState",
            "TradeCycleState",
            "BuyOrderState",
            "SellOrderState",
            "LifecycleState",
            "Action",
        }
        actual = {name for name in vars(E) if not name.startswith("_") and isinstance(vars(E)[name], type)}
        assert expected.issubset(actual)


class TestStrategyRunState:
    def test_string_equality(self) -> None:
        """UT-EXE-013.001.M01.T03: StrEnum members compare equal to their string value."""
        assert E.StrategyRunState.STOPPED == "STOPPED"
        assert E.StrategyRunState.RUNNING == "RUNNING"
        assert E.StrategyRunState.SQUARING_OFF == "SQUARING_OFF"

    def test_member_count(self) -> None:
        """UT-EXE-013.001.M01.T04: exactly three lifecycle states."""
        assert len(list(E.StrategyRunState)) == 3

    def test_is_str_enum(self) -> None:
        """UT-EXE-013.001.M01.T05: enum is a StrEnum subclass."""
        assert issubclass(E.StrategyRunState, StrEnum)


class TestTradeCycleState:
    def test_string_equality(self) -> None:
        """UT-EXE-013.001.M01.T06: trade-cycle members map to their wire-string values."""
        assert E.TradeCycleState.OPENING == "OPENING"
        assert E.TradeCycleState.OPEN == "OPEN"
        assert E.TradeCycleState.CLOSING == "CLOSING"
        assert E.TradeCycleState.CLOSED == "CLOSED"
        assert E.TradeCycleState.ABORTED == "ABORTED"

    def test_member_count(self) -> None:
        """UT-EXE-013.001.M01.T07: exactly five trade-cycle states."""
        assert len(list(E.TradeCycleState)) == 5


class TestBuyOrderState:
    def test_string_equality(self) -> None:
        """UT-EXE-013.001.M01.T08: BUY broker-order members map to their wire strings."""
        assert E.BuyOrderState.NEW == "NEW"
        assert E.BuyOrderState.PARTIAL_FILLED == "PARTIAL_FILLED"
        assert E.BuyOrderState.FILLED == "FILLED"
        assert E.BuyOrderState.REJECTED == "REJECTED"
        assert E.BuyOrderState.CANCELLED == "CANCELLED"

    def test_member_count(self) -> None:
        """UT-EXE-013.001.M01.T09: exactly five BUY-order states."""
        assert len(list(E.BuyOrderState)) == 5


class TestSellOrderState:
    def test_string_equality(self) -> None:
        """UT-EXE-013.001.M01.T10: SELL broker-order members map to their wire strings."""
        assert E.SellOrderState.NEW == "NEW"
        assert E.SellOrderState.PARTIAL_FILLED == "PARTIAL_FILLED"
        assert E.SellOrderState.FILLED == "FILLED"
        assert E.SellOrderState.REJECTED == "REJECTED"
        assert E.SellOrderState.CANCELLED == "CANCELLED"

    def test_member_count(self) -> None:
        """UT-EXE-013.001.M01.T11: exactly five SELL-order states."""
        assert len(list(E.SellOrderState)) == 5

    def test_distinct_class_from_buy(self) -> None:
        """UT-EXE-013.001.M01.T12: BuyOrderState and SellOrderState are distinct types."""
        assert E.BuyOrderState is not E.SellOrderState


class TestLifecycleState:
    def test_string_equality(self) -> None:
        """UT-EXE-013.001.M01.T13: lifecycle members map to their wire strings."""
        assert E.LifecycleState.MONITORING == "MONITORING"
        assert E.LifecycleState.ENTERED == "ENTERED"
        assert E.LifecycleState.SKIPPED == "SKIPPED"
        assert E.LifecycleState.EVICTED == "EVICTED"
        assert E.LifecycleState.EXITED == "EXITED"

    def test_member_count(self) -> None:
        """UT-EXE-013.001.M01.T14: exactly five lifecycle states."""
        assert len(list(E.LifecycleState)) == 5


class TestAction:
    def test_lowercase_wire_values(self) -> None:
        """UT-EXE-013.001.M01.T15: Action uses lowercase wire values matching TradeSignal payload."""
        assert E.Action.ENTRY == "entry"
        assert E.Action.EXIT == "exit"

    def test_member_count(self) -> None:
        """UT-EXE-013.001.M01.T16: exactly two action directions."""
        assert len(list(E.Action)) == 2


class TestNegative:
    def test_unknown_value_raises(self) -> None:
        """UT-EXE-013.001.M01.T17: constructing an enum from an unknown wire string raises ValueError."""
        with pytest.raises(ValueError):
            E.TradeCycleState("NOT_A_STATE")

    def test_buy_state_rejects_sell_value_collision_is_string_only(self) -> None:
        """UT-EXE-013.001.M01.T18: BuyOrderState.FILLED and SellOrderState.FILLED share a wire value but are not the same enum member."""
        assert E.BuyOrderState.FILLED == E.SellOrderState.FILLED  # StrEnum string equality
        assert E.BuyOrderState.FILLED is not E.SellOrderState.FILLED  # distinct members
