"""
Module: MD-GUI-014.001.M01 — Active Trades order-routing badge
Parent SRD: SRD-GUI-014.001

The Active Trades tab is where live orders are watched, and it carried no
indication of where those orders actually go.
"""
from __future__ import annotations

from unittest.mock import MagicMock

# `db.manager` and `data.engine` import each other, so whichever side loads first
# decides whether the cycle resolves. Importing `data.engine` up front settles it —
# the same thing the other GUI suites get for free by importing `app_service`.
import us_swing.data.engine  # noqa: F401


def _panel(qapp, mode: str):
    from us_swing.gui.active_cycles_panel import ActiveCyclesPanel
    from us_swing.execution.pending_signal_store import PendingSignalStore

    cycle_query = MagicMock()
    cycle_query.open_cycles.return_value = []
    cycle_query.cycles_for_session.return_value = []

    app = MagicMock(spec=["get_active_user", "viewing_uid", "circuit_breaker_active"])
    app.get_active_user.return_value = MagicMock(mode=mode)
    app.viewing_uid = None
    app.circuit_breaker_active = False

    return ActiveCyclesPanel(
        cycle_query=cycle_query,
        cycle_cmd=MagicMock(),
        pending_store=PendingSignalStore(),
        app_service=app,
        exit_executor=MagicMock(),
        execute_executor=MagicMock(),
    )


class TestModeBadge:
    def test_live_user_shows_live_badge(self, qapp):
        """UT-GUI-014.001.M01.T01: a live user sees a LIVE badge on Active Trades."""
        panel = _panel(qapp, "live")
        assert "LIVE" in panel._mode_badge.text()
        assert panel._mode_badge.isHidden() is False

    def test_paper_user_shows_paper_badge(self, qapp):
        """UT-GUI-014.001.M01.T02: a paper user sees PAPER, not LIVE."""
        panel = _panel(qapp, "paper")
        assert "PAPER" in panel._mode_badge.text()
        assert "LIVE" not in panel._mode_badge.text()

    def test_tooltip_explains_where_orders_go(self, qapp):
        """UT-GUI-014.001.M01.T03: each mode's tooltip states the routing plainly."""
        assert "IBKR" in _panel(qapp, "live")._mode_badge.toolTip()
        assert "simulated" in _panel(qapp, "paper")._mode_badge.toolTip()

    def test_badge_hidden_when_no_active_user(self, qapp):
        """UT-GUI-014.001.M01.T04: a service with no user hides the badge, never crashes."""
        from us_swing.gui.active_cycles_panel import ActiveCyclesPanel
        from us_swing.execution.pending_signal_store import PendingSignalStore

        cycle_query = MagicMock()
        cycle_query.open_cycles.return_value = []
        app = MagicMock(spec=["get_active_user", "viewing_uid"])
        app.get_active_user.side_effect = IndexError("no users")
        app.viewing_uid = None

        panel = ActiveCyclesPanel(
            cycle_query=cycle_query,
            cycle_cmd=MagicMock(),
            pending_store=PendingSignalStore(),
            app_service=app,
            exit_executor=MagicMock(),
            execute_executor=MagicMock(),
        )
        assert panel._mode_badge.isHidden() is True
