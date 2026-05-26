"""
Module: MD-EXE-004.001.M02 — ExecutionRouter
Parent SRD: SRD-EXE-004.005
"""
from __future__ import annotations

from collections.abc import Callable

from us_swing.execution.execution_engine import ExecutionEngine
from us_swing.execution.paper_engine import PaperEngine
from us_swing.execution.strategy_engine._signals import TradeSignal


class ExecutionRouter:
    """Routes signals to PaperEngine or ExecutionEngine based on mode_provider()."""

    def __init__(
        self,
        paper: PaperEngine,
        live: ExecutionEngine,
        mode_provider: Callable[[], str],
    ) -> None:
        self._paper = paper
        self._live = live
        self._mode_provider = mode_provider

    def submit(self, signal: TradeSignal, qty: int) -> int | None:
        """ExecutionSubmitter protocol: route to paper or live at call time."""
        if self._mode_provider() == "live":
            return self._live.submit(signal, qty)
        return self._paper.submit(signal, qty)

    def route_signal(
        self,
        user_id: int,
        signal: TradeSignal,
        qty: int = 0,
    ) -> int | None:
        """Explicit-user-id variant for future multi-user expansion."""
        return self.submit(signal, qty)
