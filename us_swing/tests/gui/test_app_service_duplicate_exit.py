"""
Module: MD-EXE-011.024.M01 / MD-EXE-011.025.M01 — duplicate-exit guards (ISS-EXE-0010)
Parent SRD: SRD-EXE-011.024, SRD-EXE-011.025

A position closed by one route (force-exit) must drop its stale pending exit
signal, and executing a pending exit against a position that is no longer OPEN
must be rejected — so a duplicate exit order is never placed.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def svc(qapp):
    """Minimal AppService with side-effect entry points patched."""
    mock_net_watcher = MagicMock()
    mock_net_watcher.status_changed = MagicMock()
    mock_net_watcher.status_changed.connect = MagicMock()

    with (
        patch("us_swing.gui.app_service.NetWatcher", return_value=mock_net_watcher),
        patch("us_swing.gui.app_service.load_users", return_value=[]),
        patch("us_swing.gui.app_service.load_system_config") as mock_cfg,
        patch("us_swing.gui.app_service.QTimer") as mock_qtimer_cls,
    ):
        from us_swing.gui.system_store import SystemConfig

        mock_cfg.return_value = SystemConfig()
        mock_qtimer_cls.return_value = MagicMock()
        mock_qtimer_cls.singleShot = MagicMock()

        from us_swing.gui.app_service import AppService

        service = AppService()
        yield service


def _exit_signal(symbol: str = "PRU", strategy: str = "SUPERTREND"):
    from us_swing.execution.strategy_engine import Action, TradeSignal
    return TradeSignal(action=Action.EXIT, symbol=symbol, strategy_id=strategy)


def _open_snap(symbol: str, strategy: str):
    from us_swing.execution.trade_cycle import TradeCycleState
    snap = MagicMock()
    snap.symbol = symbol
    snap.strategy_id = strategy
    snap.state = TradeCycleState.OPEN
    return snap


class TestExecuteSignalGuard:
    def test_stale_exit_dropped_when_no_open_cycle(self, svc):
        """UT-EXE-011.025.M01.T01: executing an exit with no OPEN cycle drops it, no submit."""
        sig = _exit_signal()
        svc._pending_store = MagicMock()
        svc._submitter = MagicMock()
        svc._tc_query = MagicMock()
        svc._tc_query.open_cycles.return_value = []

        result = svc.execute_signal(sig, 4)

        assert result == -1
        svc._pending_store.dismiss.assert_called_once_with(sig.signal_id)
        svc._submitter.submit.assert_not_called()

    def test_exit_submits_when_cycle_open(self, svc):
        """UT-EXE-011.025.M01.T02: an exit with a matching OPEN cycle submits normally."""
        sig = _exit_signal()
        svc._tc_query = MagicMock()
        svc._tc_query.open_cycles.return_value = [_open_snap("PRU", "SUPERTREND")]
        svc._pending_store = MagicMock()
        svc._pending_store.execute.return_value = sig
        svc._submitter = MagicMock()
        svc._submitter.submit.return_value = 777

        result = svc.execute_signal(sig, 4)

        assert result == 777
        svc._submitter.submit.assert_called_once()


class TestClearPendingOnClose:
    def test_clear_pending_exits_dismisses_for_symbol(self, svc):
        """UT-EXE-011.024.M01.T03: a closed cycle clears matching pending exit signals."""
        from us_swing.execution.strategy_engine import Action
        svc._pending_store = MagicMock()
        svc._pending_store.dismiss_for.return_value = ["sig-1"]

        svc._clear_pending_exits("SUPERTREND", "PRU")

        svc._pending_store.dismiss_for.assert_called_once_with("SUPERTREND", "PRU", Action.EXIT)

    def test_cycle_closed_marshals_to_clear_signal(self, svc):
        """UT-EXE-011.024.M01.T04: CycleClosed emits the GUI-thread pending-clear signal."""
        from us_swing.execution.trade_cycle import CycleClosed
        captured: list[tuple[str, str]] = []
        svc._clear_pending_exits_requested.connect(lambda s, sym: captured.append((s, sym)))
        snap = MagicMock()
        snap.strategy_id = "SUPERTREND"
        evt = CycleClosed(
            cycle_id=1, symbol="PRU", exit_reason="manual",
            realized_pnl_usd=0.0, realized_pnl_pct=0.0, snapshot=snap,
        )

        svc._on_cycle_closed_clear_pending(evt)

        assert captured == [("SUPERTREND", "PRU")]
