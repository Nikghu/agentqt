"""
Module: MD-EXE-014.007.M01 — force-exit resolution by cycle id (ISS-EXE-0007)
Parent SRD: SRD-EXE-014.007

The Active Trades stop button and the automatic target/SL trigger both know the
exact cycle they mean.  Resolving that back to ``(strategy_id, symbol)`` takes the
first match, so a strategy holding two cycles on one symbol exits the wrong one.
``force_exit_cycle`` resolves on the cycle's own id instead.
"""
from __future__ import annotations

from types import SimpleNamespace
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


def _snap(cycle_id: int, symbol: str = "QCOM", strategy: str = "SUPERTREND",
          entry_price: float = 100.0, entry_qty: int = 10) -> SimpleNamespace:
    """A CycleSnapshot stand-in carrying only the fields the exit path reads."""
    return SimpleNamespace(
        cycle_id      = cycle_id,
        symbol        = symbol,
        strategy_id   = strategy,
        entry_price   = entry_price,
        entry_qty     = entry_qty,
        current_price = None,
    )


def _wire(svc, snaps: list[SimpleNamespace]) -> MagicMock:
    """Point the service at *snaps* as its open cycles; return the fake submitter."""
    svc._tc_query = MagicMock()
    svc._tc_query.open_cycles.return_value = tuple(snaps)
    submitter = MagicMock()
    submitter.submit.return_value = 4242
    svc._submitter = submitter
    return submitter


class TestForceExitCycle:
    def test_picks_the_named_cycle_not_the_first_match(self, svc):
        """UT-EXE-014.007.M01.T04: two cycles on one (strategy, symbol) — the id wins."""
        older = _snap(1, entry_price=202.95, entry_qty=2)
        newer = _snap(2, entry_price=16.96, entry_qty=16)
        submitter = _wire(svc, [older, newer])

        with patch.object(svc, "get_latest_close", return_value=None):
            order_id = svc.force_exit_cycle(2)

        assert order_id == 4242
        _sig, qty = submitter.submit.call_args[0]
        assert qty == 16, "exited the first match instead of the named cycle"

    def test_carries_the_exit_reason(self, svc):
        """UT-EXE-014.007.M01.T05: the reason reaches the pending-exit slot."""
        submitter = _wire(svc, [_snap(1)])

        with patch.object(svc, "get_latest_close", return_value=None):
            svc.force_exit_cycle(1, reason="hard_sl")

        assert svc._pending_exit_reason == "hard_sl"
        assert submitter.submit.called

    def test_unknown_cycle_id_submits_nothing(self, svc):
        """UT-EXE-014.007.M01.T06: an id with no open cycle returns None, no order."""
        submitter = _wire(svc, [_snap(1)])

        order_id = svc.force_exit_cycle(99)

        assert order_id is None
        submitter.submit.assert_not_called()

    def test_no_submitter_returns_minus_one(self, svc):
        """UT-EXE-014.007.M01.T07: an unavailable submitter is reported, not silent."""
        _wire(svc, [_snap(1)])
        svc._submitter = None

        with patch.object(svc, "get_latest_close", return_value=None):
            assert svc.force_exit_cycle(1) == -1

    def test_no_cycle_query_returns_none(self, svc):
        """UT-EXE-014.007.M01.T08: without a cycle query the call is a safe no-op."""
        svc._tc_query = None

        assert svc.force_exit_cycle(1) is None


class TestForceExitPositionWrapper:
    def test_wrapper_still_resolves_by_strategy_and_symbol(self, svc):
        """UT-EXE-014.007.M01.T09: the legacy signature keeps working unchanged."""
        submitter = _wire(svc, [_snap(1, symbol="PCG", entry_qty=16)])

        with patch.object(svc, "get_latest_close", return_value=None):
            order_id = svc.force_exit_position("SUPERTREND", "PCG")

        assert order_id == 4242
        _sig, qty = submitter.submit.call_args[0]
        assert qty == 16

    def test_wrapper_returns_none_for_an_unheld_pair(self, svc):
        """UT-EXE-014.007.M01.T10: no open cycle for the pair means no order."""
        submitter = _wire(svc, [_snap(1, symbol="PCG")])

        assert svc.force_exit_position("SUPERTREND", "QCOM") is None
        submitter.submit.assert_not_called()


class TestExitPriceFallback:
    def test_falls_back_to_entry_price_when_no_close_or_tick(self, svc):
        """UT-EXE-014.007.M01.T11: a forced exit with no bar still prices the order."""
        submitter = _wire(svc, [_snap(1, entry_price=123.45)])

        with patch.object(svc, "get_latest_close", return_value=None):
            svc.force_exit_cycle(1)

        sig, _qty = submitter.submit.call_args[0]
        assert sig.entry_price == pytest.approx(123.45)

    def test_prefers_the_latest_close(self, svc):
        """UT-EXE-014.007.M01.T12: the latest close wins over the entry price."""
        submitter = _wire(svc, [_snap(1, entry_price=123.45)])

        with patch.object(svc, "get_latest_close", return_value=200.0):
            svc.force_exit_cycle(1)

        sig, _qty = submitter.submit.call_args[0]
        assert sig.entry_price == pytest.approx(200.0)
