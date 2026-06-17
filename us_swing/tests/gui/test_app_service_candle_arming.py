"""
Module: MD-EXE-006.013.M01 — tests (ISS-EXE-0009)
Parent SRD: SRD-EXE-006.013

Opening a trade cycle must arm the candle feeds (historical download + live
3m/15m subscription) for the held symbol, symmetric with the tick feed, so its
indicators always have data — even when the symbol is not in the screened set.
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
        service._cycle_symbols = frozenset()
        service._filtered_symbols = []
        service._live_bar_worker = None
        # Production wires this inside the trade-cycle init block (needs a DB),
        # which the fixture skips — connect it explicitly to mirror runtime.
        service._arm_candle_feeds_requested.connect(service._arm_candle_feeds)
        yield service


class TestCycleOpenCandleArming:
    def test_offscreen_open_arms_both_feeds(self, svc):
        """UT-EXE-006.013.M01.T01: off-screen cycle-open arms loader + live bars."""
        svc._filtered_symbols = ["AAA"]
        worker = MagicMock()
        worker.isRunning.return_value = True
        svc._live_bar_worker = worker

        with (
            patch.object(svc, "_sync_tick_subscriptions"),
            patch.object(svc, "_start_intraday_loader") as mock_loader,
        ):
            svc._on_cycle_symbols_changed(frozenset({"ZZZ"}))

        mock_loader.assert_called_once_with(["ZZZ"])
        assert "ZZZ" in svc._filtered_symbols
        worker.set_symbols.assert_called_once()
        assert "ZZZ" in worker.set_symbols.call_args[0][0]

    def test_already_covered_is_noop(self, svc):
        """UT-EXE-006.013.M01.T02: a just-opened symbol already covered is a no-op."""
        svc._filtered_symbols = ["ZZZ"]
        worker = MagicMock()
        worker.isRunning.return_value = True
        svc._live_bar_worker = worker

        with (
            patch.object(svc, "_sync_tick_subscriptions"),
            patch.object(svc, "_start_intraday_loader") as mock_loader,
        ):
            svc._on_cycle_symbols_changed(frozenset({"ZZZ"}))

        mock_loader.assert_not_called()
        worker.set_symbols.assert_not_called()

    def test_no_live_worker_still_downloads(self, svc):
        """UT-EXE-006.013.M01.T03: no live worker → download armed, no crash."""
        svc._filtered_symbols = ["AAA"]
        svc._live_bar_worker = None

        with (
            patch.object(svc, "_sync_tick_subscriptions"),
            patch.object(svc, "_start_intraday_loader") as mock_loader,
        ):
            svc._on_cycle_symbols_changed(frozenset({"ZZZ"}))  # must not raise

        mock_loader.assert_called_once_with(["ZZZ"])

    def test_arming_marshalled_via_signal(self, svc):
        """UT-EXE-006.013.M01.T04: arming emitted via signal once; tick feed still synced."""
        svc._filtered_symbols = ["AAA"]
        captured: list[list[str]] = []
        svc._arm_candle_feeds_requested.disconnect(svc._arm_candle_feeds)
        svc._arm_candle_feeds_requested.connect(lambda syms: captured.append(syms))

        with patch.object(svc, "_sync_tick_subscriptions") as mock_sync:
            svc._on_cycle_symbols_changed(frozenset({"ZZZ"}))

        assert captured == [["ZZZ"]]
        mock_sync.assert_called_once()
