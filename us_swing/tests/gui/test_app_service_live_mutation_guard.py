"""
Module: MD-GUI-004.001.M01 — live-mode guard on unrouted position edits
Parent SRD: SRD-EXE-015.004

``close_position``, ``partial_close_position`` and ``set_stop_loss`` only mutate the
in-memory position list.  They never reach the broker and never write to the
trade-cycle ledger, so in live mode they would show a position as closed while the
broker still holds it.  They are refused until the actions are properly routed.
"""
from __future__ import annotations

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


def _position(symbol: str = "AAPL", qty: int = 10) -> OpenPosition:
    return OpenPosition(
        symbol          = symbol,
        user_id         = 1,
        quantity        = qty,
        average_price   = 100.0,
        stop_loss       = 90.0,
        target_price    = 120.0,
        mode            = "live",
        current_price   = 110.0,
        strategy_id     = "SUPERTREND",
        filled_quantity = qty,
        total_quantity  = qty,
    )


def _set_mode(svc, mode: str) -> None:
    """Put a single active user in *mode*."""
    user = MagicMock(spec=UserProfile)
    user.user_id  = 1
    user.mode     = mode
    user.username = "trader"
    svc._users      = [user]
    svc._active_uid = 1


class TestLiveModeGuard:
    def test_close_position_refused_in_live(self, svc):
        """UT-EXE-015.004.M01.T20: a live close leaves the position untouched."""
        _set_mode(svc, "live")
        pos = _position()
        svc._positions = [pos]

        svc.close_position("AAPL", user_id=1)

        assert pos.quantity == 10, "position was mutated in live mode"

    def test_partial_close_refused_in_live(self, svc):
        """UT-EXE-015.004.M01.T21: a live partial close leaves the quantity untouched."""
        _set_mode(svc, "live")
        pos = _position()
        svc._positions = [pos]

        svc.partial_close_position("AAPL", 4, user_id=1)

        assert pos.quantity == 10

    def test_set_stop_loss_refused_in_live(self, svc):
        """UT-EXE-015.004.M01.T22: a live stop-loss edit leaves the stop untouched."""
        _set_mode(svc, "live")
        pos = _position()
        svc._positions = [pos]

        svc.set_stop_loss("AAPL", price=95.0, user_id=1)

        assert pos.stop_loss == 90.0

    def test_refusal_is_explained_in_the_log(self, svc):
        """UT-EXE-015.004.M01.T23: the block is reported, never silent."""
        _set_mode(svc, "live")
        svc._positions = [_position()]
        messages: list[str] = []
        svc.log_message.connect(lambda _lvl, msg: messages.append(msg))

        svc.close_position("AAPL", user_id=1)

        assert any("not available in live mode" in m for m in messages)
        assert any("Active Trades" in m for m in messages)


class TestPaperModeUnaffected:
    def test_close_position_still_works_in_paper(self, svc):
        """UT-EXE-015.004.M01.T24: paper mode behaviour is unchanged."""
        _set_mode(svc, "paper")
        pos = _position()
        svc._positions = [pos]

        svc.close_position("AAPL", user_id=1)

        assert pos.quantity == 0

    def test_partial_close_still_works_in_paper(self, svc):
        """UT-EXE-015.004.M01.T25: paper partial close still reduces the quantity."""
        _set_mode(svc, "paper")
        pos = _position()
        svc._positions = [pos]

        svc.partial_close_position("AAPL", 4, user_id=1)

        assert pos.quantity == 6

    def test_set_stop_loss_still_works_in_paper(self, svc):
        """UT-EXE-015.004.M01.T26: paper stop-loss edit still applies."""
        _set_mode(svc, "paper")
        pos = _position()
        svc._positions = [pos]

        svc.set_stop_loss("AAPL", price=95.0, user_id=1)

        assert pos.stop_loss == pytest.approx(95.0)


class TestPredicate:
    def test_blocked_only_in_live(self, svc):
        """UT-EXE-015.004.M01.T27: the predicate tracks the active user's mode."""
        _set_mode(svc, "paper")
        assert svc.live_mutations_blocked() is False
        _set_mode(svc, "live")
        assert svc.live_mutations_blocked() is True

    def test_no_users_is_not_blocked_and_does_not_raise(self, svc):
        """UT-EXE-015.004.M01.T28: an empty user list is safe, not an IndexError."""
        svc._users = []

        assert svc.live_mutations_blocked() is False
