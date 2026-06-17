"""
Module: cross-cut for FO-EXE-011 — PendingSignalStore
Parent SRD: SRD-EXE-011.009
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, pyqtSignal

from us_swing.execution.strategy_engine import Action, TradeSignal


class PendingSignalStore(QObject):
    """Thread-safe in-memory store of `TradeSignal`s awaiting user action.

    Implements the `PendingSignalSink` Protocol from
    `us_swing.execution.strategy_engine._signals` while also exposing
    `dismiss()`, `execute()`, and `list()` for GUI consumers (FO-GUI-014).
    """

    pending_signal_added = pyqtSignal(object)
    pending_signal_removed = pyqtSignal(str)
    pending_signal_dismissed = pyqtSignal(str)
    pending_signal_executed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._signals: dict[str, TradeSignal] = {}

    def add(self, signal: TradeSignal) -> None:
        with self._lock:
            if signal.signal_id in self._signals:
                return
            self._signals[signal.signal_id] = signal
        self.pending_signal_added.emit(signal)

    def dismiss(self, signal_id: str) -> TradeSignal | None:
        with self._lock:
            sig = self._signals.pop(signal_id, None)
        if sig is not None:
            self.pending_signal_dismissed.emit(signal_id)
        return sig

    def execute(self, signal_id: str) -> TradeSignal | None:
        with self._lock:
            sig = self._signals.pop(signal_id, None)
        if sig is not None:
            self.pending_signal_executed.emit(signal_id)
        return sig

    def dismiss_for(
        self, strategy_id: str, symbol: str, action: Action
    ) -> list[str]:
        """Dismiss every pending signal matching ``(strategy_id, symbol, action)``.

        Invalidates a stale signal when the position it targets is closed by
        another route (force-exit, tick exit, square-off), so the user cannot
        execute a duplicate exit for an already-closed position (ISS-EXE-0010,
        SRD-EXE-011.024).

        Args:
            strategy_id: Owning strategy of the signals to drop.
            symbol: Ticker of the signals to drop.
            action: Signal action to match (e.g. ``Action.EXIT``).

        Returns:
            The signal ids that were removed.
        """
        with self._lock:
            ids = [
                sid for sid, s in self._signals.items()
                if s.strategy_id == strategy_id
                and s.symbol == symbol
                and s.action == action
            ]
            for sid in ids:
                self._signals.pop(sid, None)
        for sid in ids:
            self.pending_signal_dismissed.emit(sid)
        return ids

    def list(self) -> tuple[TradeSignal, ...]:
        with self._lock:
            return tuple(self._signals.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._signals)
