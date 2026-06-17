"""
Module: MD-EXE-011.024.M01 — PendingSignalStore.dismiss_for tests (ISS-EXE-0010)
Parent SRD: SRD-EXE-011.024
"""
from __future__ import annotations

from us_swing.execution.pending_signal_store import PendingSignalStore
from us_swing.execution.strategy_engine import Action, TradeSignal


def _sig(action: Action, symbol: str, strategy_id: str) -> TradeSignal:
    return TradeSignal(action=action, symbol=symbol, strategy_id=strategy_id)


def test_dismiss_for_removes_matching_exit_signal(qapp: object) -> None:
    """UT-EXE-011.024.M01.T01: dismiss_for removes the matching EXIT signal and emits dismissed."""
    store = PendingSignalStore()
    exit_sig = _sig(Action.EXIT, "PRU", "SUPERTREND")
    store.add(exit_sig)
    dismissed: list[str] = []
    store.pending_signal_dismissed.connect(dismissed.append)

    removed = store.dismiss_for("SUPERTREND", "PRU", Action.EXIT)

    assert removed == [exit_sig.signal_id]
    assert store.list() == ()
    assert dismissed == [exit_sig.signal_id]


def test_dismiss_for_leaves_non_matching_signals(qapp: object) -> None:
    """UT-EXE-011.024.M01.T02: dismiss_for ignores other symbols, strategies, and ENTRY actions."""
    store = PendingSignalStore()
    keep_entry      = _sig(Action.ENTRY, "PRU", "SUPERTREND")
    keep_other_sym  = _sig(Action.EXIT, "TER", "SUPERTREND")
    keep_other_strat = _sig(Action.EXIT, "PRU", "OTHER")
    for s in (keep_entry, keep_other_sym, keep_other_strat):
        store.add(s)

    removed = store.dismiss_for("SUPERTREND", "PRU", Action.EXIT)

    assert removed == []
    assert len(store) == 3
