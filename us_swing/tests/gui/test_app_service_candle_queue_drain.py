"""
Module: MD-EXE-006.008.M01 — tests (ISS-EXE-0011)
Parent SRD: SRD-EXE-006.008

A batch queued while a download is running must actually start once that
download's thread ends. Draining on `load_complete` re-queued the batch forever,
because that signal fires from inside the worker's `run()` while the thread is
still alive.
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
        service._intraday_loader = None
        service._readiness_worker = None
        service._pending_candle_symbols = None
        yield service


def _running_loader() -> MagicMock:
    loader = MagicMock()
    loader.isRunning.return_value = True
    return loader


class TestQueuedBatchDrain:
    def test_busy_loader_queues_batch(self, svc):
        """UT-EXE-006.008.M01.T01: a batch arriving mid-download is queued, not dropped."""
        svc._intraday_loader = _running_loader()

        svc._start_intraday_loader(["CDW", "DG"])

        assert svc._pending_candle_symbols == ["CDW", "DG"]

    def test_queued_batch_starts_when_thread_finishes(self, svc):
        """UT-EXE-006.008.M01.T02: the queued batch starts on the loader's finished signal."""
        loader = _running_loader()
        svc._intraday_loader = loader
        svc._pending_candle_symbols = ["CDW", "DG"]

        with patch.object(svc, "_start_intraday_loader") as mock_start:
            svc._on_intraday_loader_finished(loader)

        mock_start.assert_called_once_with(["CDW", "DG"])
        assert svc._pending_candle_symbols is None
        assert svc._intraday_loader is None

    def test_load_complete_does_not_drain(self, svc):
        """UT-EXE-006.008.M01.T03: load_complete leaves the queue alone (thread still alive)."""
        svc._intraday_loader = _running_loader()
        svc._pending_candle_symbols = ["CDW", "DG"]

        with patch.object(svc, "_start_intraday_loader") as mock_start:
            svc._on_candle_load_complete([])

        mock_start.assert_not_called()
        assert svc._pending_candle_symbols == ["CDW", "DG"]

    def test_drain_sees_a_free_loader_slot(self, svc):
        """UT-EXE-006.008.M01.T04: the busy guard is clear when the drain starts the batch."""
        loader = _running_loader()
        svc._intraday_loader = loader
        svc._pending_candle_symbols = ["CDW", "DG"]
        busy_at_call: list[bool] = []

        # The thread object still reports isRunning() when its finished signal is
        # delivered, so the drain must release the slot before restarting.
        def _record(_symbols: list[str]) -> None:
            busy_at_call.append(svc._intraday_loader is not None)

        with patch.object(svc, "_start_intraday_loader", side_effect=_record):
            svc._on_intraday_loader_finished(loader)

        assert busy_at_call == [False]

    def test_stale_loader_does_not_clear_current(self, svc):
        """UT-EXE-006.008.M01.T05: a late finished signal never clears a newer loader."""
        current = _running_loader()
        stale = _running_loader()
        svc._intraday_loader = current

        svc._on_intraday_loader_finished(stale)

        assert svc._intraday_loader is current

    def test_no_queue_is_a_noop(self, svc):
        """UT-EXE-006.008.M01.T06: finishing with an empty queue starts nothing."""
        loader = _running_loader()
        svc._intraday_loader = loader

        with patch.object(svc, "_start_intraday_loader") as mock_start:
            svc._on_intraday_loader_finished(loader)

        mock_start.assert_not_called()
        assert svc._intraday_loader is None
