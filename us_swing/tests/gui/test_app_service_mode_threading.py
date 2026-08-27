"""
Module: MD-GUI-004.001.M01 — real mode on ledger rows and rehydrated positions
Parent SRD: SRD-EXE-015.002, SRD-EXE-015.003

The trades ledger and the rehydrated display lists used to stamp a hardcoded
``"paper"``.  The account poller tags live rows ``"live"``, so a live session
produced two disagreeing sets of records and every mode-filtered view hid the
live ones.  All of it now follows the active user's real mode.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from us_swing.data.models import OpenPosition, UserProfile


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

        yield AppService()


def _set_mode(svc, mode: str) -> None:
    user = MagicMock(spec=UserProfile)
    user.user_id  = 1
    user.mode     = mode
    user.username = "trader"
    svc._users      = [user]
    svc._active_uid = 1


def _snap(symbol: str = "AAPL", closed: bool = False) -> SimpleNamespace:
    """A CycleSnapshot stand-in carrying the fields rehydrate reads."""
    return SimpleNamespace(
        cycle_id        = 1,
        symbol          = symbol,
        user_id         = 1,
        strategy_id     = "SUPERTREND",
        entry_order_id  = "ord-1",
        entry_qty       = 10,
        entry_price     = 100.0,
        entry_time      = "2026-08-27T10:00:00",
        hard_stop_loss  = 90.0,
        target_price    = 120.0,
        current_price   = 110.0,
        exit_order_id   = "ord-2" if closed else None,
        exit_time       = "2026-08-27T11:00:00" if closed else None,
        exit_price      = 105.0 if closed else None,
        exit_qty        = 10 if closed else None,
    )


def _wire_query(svc, open_snaps=(), hist_snaps=()) -> None:
    q = MagicMock()
    q.open_cycles.return_value = tuple(open_snaps)
    q.history.return_value     = tuple(hist_snaps)
    svc._tc_query = q


class TestRehydrateStampsRealMode:
    def test_open_position_carries_live_mode(self, svc):
        """UT-EXE-015.002.M01.T16: a live user's rehydrated position is tagged live."""
        _set_mode(svc, "live")
        _wire_query(svc, open_snaps=[_snap()])

        svc._rehydrate_positions_from_cycles()

        assert [p.mode for p in svc._positions] == ["live"]

    def test_open_position_still_paper_for_a_paper_user(self, svc):
        """UT-EXE-015.002.M01.T17: paper users are unaffected."""
        _set_mode(svc, "paper")
        _wire_query(svc, open_snaps=[_snap()])

        svc._rehydrate_positions_from_cycles()

        assert [p.mode for p in svc._positions] == ["paper"]

    def test_history_rows_carry_live_mode(self, svc):
        """UT-EXE-015.003.M01.T18: both the BUY and SELL ledger rows are tagged live."""
        _set_mode(svc, "live")
        _wire_query(svc, hist_snaps=[_snap(closed=True)])

        svc._rehydrate_positions_from_cycles()

        assert len(svc._trades) == 2, "expected a BUY and a SELL row"
        assert {t.mode for t in svc._trades} == {"live"}


class TestActivePositionFilter:
    def test_live_positions_are_visible_in_live_mode(self, svc):
        """UT-EXE-015.002.M01.T19: the filter no longer hides live positions."""
        _set_mode(svc, "live")
        svc._positions = [_open_position("AAPL", "live")]

        assert [p.symbol for p in svc.get_active_strategy_positions()] == ["AAPL"]

    def test_paper_positions_hidden_from_a_live_user(self, svc):
        """UT-EXE-015.002.M01.T20: modes do not bleed across."""
        _set_mode(svc, "live")
        svc._positions = [_open_position("AAPL", "paper")]

        assert svc.get_active_strategy_positions() == []

    def test_closed_positions_excluded(self, svc):
        """UT-EXE-015.002.M01.T21: a zero-quantity row is not an open position."""
        _set_mode(svc, "paper")
        svc._positions = [_open_position("AAPL", "paper", qty=0)]

        assert svc.get_active_strategy_positions() == []


class TestCyclePositionSource:
    def test_source_stamps_the_active_mode(self, svc):
        """UT-EXE-015.002.M01.T22: the risk-manager position source follows the user."""
        from us_swing.gui.app_service import _CyclePositionSource

        query = MagicMock()
        query.open_cycles.return_value = (_snap(),)
        src = _CyclePositionSource(query, lambda: "live")

        assert [p.mode for p in src.get_all(1)] == ["live"]

    def test_source_is_empty_without_a_query(self, svc):
        """UT-EXE-015.002.M01.T23: no cycle query means no positions, not a crash."""
        from us_swing.gui.app_service import _CyclePositionSource

        assert _CyclePositionSource(None, lambda: "paper").get_all(1) == []


def _open_position(symbol: str, mode: str, qty: int = 10) -> OpenPosition:
    return OpenPosition(
        symbol          = symbol,
        user_id         = 1,
        quantity        = qty,
        average_price   = 100.0,
        stop_loss       = 90.0,
        target_price    = 120.0,
        mode            = mode,
        current_price   = 110.0,
        strategy_id     = "SUPERTREND",
        filled_quantity = qty,
        total_quantity  = qty,
    )
