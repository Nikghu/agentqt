"""
Module: cross-cut for FO-EXE-011 — PendingSignalStore
Parent SRD: SRD-EXE-011.009
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, pyqtSignal

from us_swing.execution.strategy_engine import TradeSignal


class PendingSignalStore(QObject):
    """Thread-safe in-memory store of `TradeSignal`s awaiting user action.

    Implements the `PendingSignalSink` Protocol from
    `us_swing.execution.strategy_engine._signals` while also exposing
    `dismiss()`, `execute()`, and `list()` for GUI consumers (FO-GUI-014).
    """

    pending_signal_added = pyqtSignal(object)
    pending_signal_removed = pyqtSignal(str)

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
            self.pending_signal_removed.emit(signal_id)
        return sig

    def execute(self, signal_id: str) -> TradeSignal | None:
        with self._lock:
            sig = self._signals.pop(signal_id, None)
        if sig is not None:
            self.pending_signal_removed.emit(signal_id)
        return sig

    def list(self) -> tuple[TradeSignal, ...]:
        with self._lock:
            return tuple(self._signals.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._signals)
