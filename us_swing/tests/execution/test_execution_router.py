"""Tests for execution/execution_router.py — ExecutionRouter."""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from us_swing.execution.execution_router import ExecutionRouter
from us_swing.execution.strategy_engine._signals import Action, TradeSignal


def _signal() -> TradeSignal:
    return TradeSignal(
        action=Action.ENTRY,
        symbol="AAPL",
        strategy_id="s1",
        entry_price=50.0,
        stop_loss=48.0,
    )


def _router(mode: str) -> tuple[ExecutionRouter, MagicMock, MagicMock]:
    paper = MagicMock()
    paper.submit.return_value = -1
    live = MagicMock()
    live.submit.return_value = 42
    _mode = [mode]
    router = ExecutionRouter(
        paper=paper,
        live=live,
        mode_provider=lambda: _mode[0],
    )
    return router, paper, live


def test_routes_to_paper_in_paper_mode():
    """UT-EXE-004.001.M02.T01: Routes to PaperEngine when user mode is 'paper'."""
    router, paper, live = _router("paper")
    result = router.submit(_signal(), 100)
    paper.submit.assert_called_once()
    live.submit.assert_not_called()
    assert result == -1


def test_routes_to_live_in_live_mode():
    """UT-EXE-004.001.M02.T02: Routes to live ExecutionEngine when user mode is 'live'."""
    router, paper, live = _router("live")
    result = router.submit(_signal(), 100)
    live.submit.assert_called_once()
    paper.submit.assert_not_called()
    assert result == 42


def test_mode_check_per_signal():
    """UT-EXE-004.001.M02.T03: Mode check per-signal, not cached."""
    paper = MagicMock()
    paper.submit.return_value = -1
    live = MagicMock()
    live.submit.return_value = 42
    _mode = ["paper"]
    router = ExecutionRouter(
        paper=paper,
        live=live,
        mode_provider=lambda: _mode[0],
    )
    sig = _signal()
    router.submit(sig, 100)
    assert paper.submit.call_count == 1
    assert live.submit.call_count == 0

    _mode[0] = "live"
    router.submit(sig, 100)
    assert live.submit.call_count == 1
    assert paper.submit.call_count == 1  # still 1 — no additional call
