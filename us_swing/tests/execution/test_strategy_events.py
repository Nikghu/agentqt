"""
Module: MD-EXE-011.001.M05 — tests
Parent SRD: SRD-EXE-011.015
"""
from __future__ import annotations

import dataclasses

import pytest

from us_swing.execution.strategy_engine._events import (
    StrategyEntered,
    StrategyErrored,
    StrategyExited,
    StrategySignalDropped,
    StrategySignalPending,
    StrategySquaredOff,
)
from us_swing.execution.strategy_engine._signals import Action, TradeSignal

_ALL_EVENT_CLASSES = [
    StrategyEntered,
    StrategyExited,
    StrategySquaredOff,
    StrategyErrored,
    StrategySignalDropped,
    StrategySignalPending,
]


def _make_signal() -> TradeSignal:
    return TradeSignal(action=Action.ENTRY, symbol="AAPL", strategy_id="strat1")


def test_all_events_frozen_and_slots() -> None:
    """UT-EXE-011.001.M05.T01: All 6 event classes have slots=True and frozen=True."""
    signal = _make_signal()

    instances = [
        StrategyEntered(strategy_id="s", symbol="AAPL", entry_price=150.0, qty=10),
        StrategyExited(strategy_id="s", symbol="AAPL", exit_price=155.0, qty=10, reason="fill"),
        StrategySquaredOff(strategy_id="s", symbol="AAPL", reason="end_time"),
        StrategyErrored(strategy_id="s", symbol="AAPL", message="oops"),
        StrategySignalDropped(signal=signal, reason="risk"),
        StrategySignalPending(signal=signal),
    ]

    for cls, inst in zip(_ALL_EVENT_CLASSES, instances):
        assert "__slots__" in cls.__dict__, f"{cls.__name__} missing __slots__"
        with pytest.raises(dataclasses.FrozenInstanceError):
            inst.schema_version = 99  # type: ignore[misc]


def test_all_events_default_schema_version() -> None:
    """UT-EXE-011.001.M05.T02: Construct each event without version arg → schema_version==1."""
    signal = _make_signal()

    assert StrategyEntered(strategy_id="s", symbol="AAPL", entry_price=150.0, qty=10).schema_version == 1
    assert StrategyExited(strategy_id="s", symbol="AAPL", exit_price=155.0, qty=10, reason="fill").schema_version == 1
    assert StrategySquaredOff(strategy_id="s", symbol="AAPL", reason="end_time").schema_version == 1
    assert StrategyErrored(strategy_id="s", symbol="AAPL", message="err").schema_version == 1
    assert StrategySignalDropped(signal=signal, reason="r").schema_version == 1
    assert StrategySignalPending(signal=signal).schema_version == 1


def test_mutation_raises_frozen_instance_error() -> None:
    """UT-EXE-011.001.M05.T03: Mutate any frozen event → FrozenInstanceError."""
    event = StrategySquaredOff(strategy_id="s", symbol="AAPL", reason="end_time")
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.reason = "tampered"  # type: ignore[misc]
