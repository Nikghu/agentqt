"""
Module: MD-EXE-015.004.M01 — GUI submit-failure guard
Parent SRD: SRD-EXE-015.004

The liveness gate raises ``BrokerConnectionError`` before touching a dead socket.
The router catches that and rolls back, but the two GUI order paths called the
submitter bare, so the exception reached the Qt slot and the pending signal — already
popped from the store — was lost with no way to retry.
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


def _entry_signal(symbol: str = "PRU", strategy: str = "SUPERTREND"):
    from us_swing.execution.strategy_engine import Action, TradeSignal
    return TradeSignal(action=Action.ENTRY, symbol=symbol, strategy_id=strategy)


def _open_snap(symbol: str = "PRU", strategy: str = "SUPERTREND"):
    snap = MagicMock()
    snap.symbol = symbol
    snap.strategy_id = strategy
    snap.entry_qty = 3
    snap.entry_price = 10.0
    snap.current_price = 10.0
    return snap


class TestExecuteSignalSubmitFailure:
    def test_dead_socket_returns_minus_one_instead_of_raising(self, svc):
        """UT-EXE-015.004.M01.T32: a submit that raises never escapes into the GUI."""
        from us_swing.exceptions import BrokerConnectionError

        sig = _entry_signal()
        svc._tc_query = MagicMock()
        svc._tc_query.has_open_cycle.return_value = False
        svc._pending_store = MagicMock()
        svc._pending_store.execute.return_value = sig
        svc._submitter = MagicMock()
        svc._submitter.submit.side_effect = BrokerConnectionError(
            "IBKR order connection is not live — the order was not sent"
        )

        assert svc.execute_signal(sig, 1) == -1

    def test_failed_submit_returns_the_signal_to_the_pending_store(self, svc):
        """UT-EXE-015.004.M01.T33: the popped signal is re-added so the user can retry."""
        from us_swing.exceptions import BrokerConnectionError

        sig = _entry_signal()
        svc._tc_query = MagicMock()
        svc._tc_query.has_open_cycle.return_value = False
        svc._pending_store = MagicMock()
        svc._pending_store.execute.return_value = sig
        svc._submitter = MagicMock()
        svc._submitter.submit.side_effect = BrokerConnectionError("socket down")

        svc.execute_signal(sig, 1)

        svc._pending_store.add.assert_called_once_with(sig)

    def test_successful_submit_does_not_re_add(self, svc):
        """UT-EXE-015.004.M01.T34: the happy path is unchanged — no re-add, real order id."""
        sig = _entry_signal()
        svc._tc_query = MagicMock()
        svc._tc_query.has_open_cycle.return_value = False
        svc._pending_store = MagicMock()
        svc._pending_store.execute.return_value = sig
        svc._submitter = MagicMock()
        svc._submitter.submit.return_value = 77

        assert svc.execute_signal(sig, 1) == 77
        svc._pending_store.add.assert_not_called()


class TestCycleExitSubmitFailure:
    def test_dead_socket_on_exit_returns_minus_one(self, svc):
        """UT-EXE-015.004.M01.T35: a force-exit into a dead socket reports, never raises."""
        from us_swing.exceptions import BrokerConnectionError

        svc._submitter = MagicMock()
        svc._submitter.submit.side_effect = BrokerConnectionError("socket down")

        with patch.object(svc, "get_latest_close", return_value=11.0):
            assert svc._submit_cycle_exit(_open_snap(), "manual") == -1

    def test_successful_exit_submit_returns_order_id(self, svc):
        """UT-EXE-015.004.M01.T36: a healthy exit submit still returns the broker order id."""
        svc._submitter = MagicMock()
        svc._submitter.submit.return_value = 91

        with patch.object(svc, "get_latest_close", return_value=11.0):
            assert svc._submit_cycle_exit(_open_snap(), "manual") == 91
