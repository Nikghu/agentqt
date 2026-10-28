"""
Module: MD-GUI-030.004.M02 — tests
Parent SRD: SRD-GUI-030.004

AppService backtest wiring: auto delta starts once when due; Clear is refused while
a download runs.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from us_swing.backtest.store import BacktestStore
from us_swing.universe.store import Sp500Record


@pytest.fixture()
def svc(qapp: Any, tmp_path: Path) -> Iterator[Any]:
    """Minimal AppService with side-effect entry points patched and a temp store."""
    net = MagicMock()
    with (
        patch("us_swing.gui.app_service.NetWatcher", return_value=net),
        patch("us_swing.gui.app_service.load_users", return_value=[]),
        patch("us_swing.gui.app_service.save_users"),
        patch("us_swing.gui.app_service.load_system_config") as mock_cfg,
        patch("us_swing.gui.app_service.QTimer") as mock_qtimer_cls,
    ):
        from us_swing.gui.system_store import SystemConfig

        mock_cfg.return_value = SystemConfig()
        mock_qtimer_cls.return_value = MagicMock()
        mock_qtimer_cls.singleShot = MagicMock()

        from us_swing.gui.app_service import AppService, ConnectionStatus

        service = AppService()
        service._bkt_store = BacktestStore(tmp_path)
        service._connection_status = ConnectionStatus.CONNECTED
        service._sp500 = [Sp500Record("AAPL", "AAPL", "Apple", "Tech")]
        yield service


def test_auto_delta_starts_once_when_due(svc: Any) -> None:
    """UT-GUI-030.004.M02.T01: A due delta starts once; no second start while it runs."""
    fake_cls = MagicMock()
    with (
        patch("us_swing.gui.app_service.BacktestDownloader", fake_cls),
        patch("us_swing.gui.app_service.delta_due", return_value=True),
    ):
        svc._check_backtest_delta()
        svc._check_backtest_delta()

    assert fake_cls.call_count == 1
    assert fake_cls.call_args.kwargs["delta"] is True
    assert fake_cls.call_args.kwargs["client_id"] == 16
    fake_cls.return_value.start.assert_called_once()
    assert svc.is_backtest_running()


def test_clear_refused_while_downloading(svc: Any, tmp_path: Path) -> None:
    """UT-GUI-030.004.M02.T02: Clear returns False and keeps files while a run is active."""
    df = pd.DataFrame({"ts": [pd.Timestamp("2025-01-02")], "open": [1.0], "high": [1.0],
                       "low": [1.0], "close": [1.0], "volume": [1.0]})
    svc._bkt_store.save("AAPL", "1d", df, datetime(2026, 1, 1, tzinfo=timezone.utc))
    svc._bkt_downloader = MagicMock()

    assert svc.clear_backtest_data() is False
    assert (tmp_path / "1d" / "AAPL.parquet").exists()
