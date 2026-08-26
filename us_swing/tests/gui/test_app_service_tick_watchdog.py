"""
Module: MD-GUI-004.001.M01 test cases (FO-GUI-012)
Parent SRD: SRD-GUI-012.001

Unit tests for the live tick worker watchdog in AppService.

A refused IBKR handshake ends the worker's event loop, so the QThread finishes
and live prices stop for the rest of the session.  These tests cover the restart
path and prove it stays quiet while the worker is healthy.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from us_swing.gui.app_service import ConnectionStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def svc(qapp):
    """Minimal AppService with all side-effect entry points patched."""
    mock_net_watcher = MagicMock()
    mock_net_watcher.start = MagicMock()
    mock_net_watcher.status_changed = MagicMock()
    mock_net_watcher.status_changed.connect = MagicMock()

    with (
        patch("us_swing.gui.app_service.NetWatcher", return_value=mock_net_watcher),
        patch("us_swing.gui.app_service.load_users", return_value=[]),
        patch("us_swing.gui.app_service.load_system_config") as mock_cfg,
        patch("us_swing.gui.app_service.QTimer") as mock_qtimer_cls,
    ):
        from us_swing.gui.system_store import SystemConfig

        cfg = SystemConfig()
        cfg.ibkr_tick_client_id = 14
        mock_cfg.return_value = cfg

        mock_qtimer_cls.return_value = MagicMock()
        mock_qtimer_cls.singleShot = MagicMock()

        from us_swing.gui.app_service import AppService

        service = AppService()
        service._tick_worker = None
        service._connection_status = ConnectionStatus.CONNECTED
        yield service


def _worker(finished: bool) -> MagicMock:
    """A MagicMock mimicking LiveTickWorker, with a settable isFinished()."""
    w = MagicMock()
    w.isFinished.return_value = finished
    return w


# ---------------------------------------------------------------------------
# Watchdog — restart on silent death
# ---------------------------------------------------------------------------

class TestTickWatchdog:
    def test_restarts_worker_when_thread_has_finished(self, svc):
        """UT-GUI-012.001.M01.T20: a finished worker is replaced by a fresh one."""
        dead = _worker(finished=True)
        svc._tick_worker = dead
        fresh = _worker(finished=False)

        with (
            patch("us_swing.execution.live_tick_worker.LiveTickWorker",
                  return_value=fresh) as mock_cls,
            patch.object(svc, "_sync_tick_subscriptions"),
        ):
            svc._check_tick_health()

        assert mock_cls.called, "watchdog did not build a replacement worker"
        assert svc._tick_worker is fresh
        fresh.start.assert_called_once()

    def test_restart_warns_once_per_outage(self, svc):
        """UT-GUI-012.001.M01.T21: the outage warning is not repeated every check."""
        messages: list[tuple[str, str]] = []
        svc.log_message.connect(lambda lvl, msg: messages.append((lvl, msg)))
        svc._tick_worker = _worker(finished=True)

        with (
            patch("us_swing.execution.live_tick_worker.LiveTickWorker",
                  return_value=_worker(finished=False)),
            patch.object(svc, "_sync_tick_subscriptions"),
        ):
            svc._check_tick_health()
            svc._tick_worker = _worker(finished=True)
            svc._check_tick_health()

        outage = [m for _, m in messages if "Live prices stopped" in m]
        assert len(outage) == 1

    def test_healthy_worker_is_left_alone(self, svc):
        """UT-GUI-012.001.M01.T22: a running worker is never restarted."""
        alive = _worker(finished=False)
        svc._tick_worker = alive

        with patch("us_swing.execution.live_tick_worker.LiveTickWorker") as mock_cls:
            svc._check_tick_health()

        mock_cls.assert_not_called()
        assert svc._tick_worker is alive

    def test_does_nothing_while_feed_disconnected(self, svc):
        """UT-GUI-012.001.M01.T23: a user disconnect is not undone by the watchdog."""
        svc._connection_status = ConnectionStatus.DISCONNECTED
        svc._tick_worker = None

        with patch("us_swing.execution.live_tick_worker.LiveTickWorker") as mock_cls:
            svc._check_tick_health()

        mock_cls.assert_not_called()
        assert svc._tick_worker is None


# ---------------------------------------------------------------------------
# finished signal — identity guard
# ---------------------------------------------------------------------------

class TestWorkerFinished:
    def test_finished_clears_the_current_worker(self, svc):
        """UT-GUI-012.001.M01.T24: the finished worker is released for replacement."""
        tw = _worker(finished=True)
        svc._tick_worker = tw

        svc._on_tick_worker_finished(tw)

        assert svc._tick_worker is None
        tw.deleteLater.assert_called_once()

    def test_late_signal_does_not_drop_a_newer_worker(self, svc):
        """UT-GUI-012.001.M01.T25: a stale finished signal leaves the new worker in place."""
        old = _worker(finished=True)
        new = _worker(finished=False)
        svc._tick_worker = new

        svc._on_tick_worker_finished(old)

        assert svc._tick_worker is new
        new.deleteLater.assert_not_called()


# ---------------------------------------------------------------------------
# Stale ticks — reported, never acted on
# ---------------------------------------------------------------------------

class TestStaleTicks:
    def test_silence_warns_but_does_not_restart(self, svc):
        """UT-GUI-012.001.M01.T26: a quiet market never triggers a reconnect."""
        messages: list[str] = []
        svc.log_message.connect(lambda _lvl, msg: messages.append(msg))
        alive = _worker(finished=False)
        svc._tick_worker = alive
        svc._last_tick_at = None
        svc._market_status = {"nyse": "open", "nasdaq": "open"}

        with patch("us_swing.execution.live_tick_worker.LiveTickWorker") as mock_cls:
            svc._check_tick_health()

        mock_cls.assert_not_called()
        assert svc._tick_worker is alive
        assert any("No live price updates" in m for m in messages)

    def test_no_warning_when_market_is_closed(self, svc):
        """UT-GUI-012.001.M01.T27: overnight silence is normal and stays quiet."""
        messages: list[str] = []
        svc.log_message.connect(lambda _lvl, msg: messages.append(msg))
        svc._tick_worker = _worker(finished=False)
        svc._last_tick_at = None
        svc._market_status = {"nyse": "closed", "nasdaq": "closed"}

        svc._check_tick_health()

        assert not any("No live price updates" in m for m in messages)

    def test_recent_tick_clears_the_warning_latch(self, svc):
        """UT-GUI-012.001.M01.T28: a fresh tick re-arms the warning for the next outage."""
        import time

        svc._tick_worker = _worker(finished=False)
        svc._market_status = {"nyse": "open", "nasdaq": "open"}
        svc._tick_stale_logged = True
        svc._last_tick_at = time.monotonic()

        svc._check_tick_health()

        assert svc._tick_stale_logged is False
