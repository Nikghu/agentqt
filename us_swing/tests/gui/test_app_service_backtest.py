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


def test_universe_backtest_coverage(svc: Any) -> None:
    """UT-GUI-030.008.M02.T01: Per-stock backtest dates and status for the Universe table."""
    from us_swing.gui.app_service import _compute_last_trading_day

    last = _compute_last_trading_day()
    svc._sp500 = [Sp500Record(s, s, s, "Tech") for s in ("AAPL", "MSFT", "NVDA")]
    store = svc._bkt_store
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)

    def bars(day: str) -> pd.DataFrame:
        return pd.DataFrame({"ts": [pd.Timestamp(day, tz="UTC")], "open": [1.0], "high": [1.0],
                             "low": [1.0], "close": [1.0], "volume": [1.0]})

    store.save("AAPL", "1d", bars("2026-01-02"), now)
    store.save("AAPL", "3m", bars(f"{last} 15:00"), now)
    store.save("MSFT", "1d", bars("2026-01-02"), now)

    cov = svc.get_backtest_symbol_coverage()

    assert cov["AAPL"] == (last.isoformat(), last.isoformat(), "ok")
    assert cov["MSFT"] == ("2026-01-02", "2026-01-02", "1d")
    assert cov["NVDA"] == (None, None, "none")


def test_stats_worker_counts_missing(tmp_path: Path) -> None:
    """UT-GUI-030.009.M02.T01: The stats worker adds missing requests and stocks from the plan."""
    from datetime import date

    from us_swing.backtest.planner import Job
    from us_swing.gui.app_service import _BacktestStatsWorker

    jobs = [Job("AAPL", "1d", date(2025, 1, 1), date(2025, 2, 1), "1 Y"),
            Job("AAPL", "3m", date(2025, 1, 1), date(2025, 2, 1), "3 M"),
            Job("MSFT", "3m", date(2025, 1, 1), date(2025, 2, 1), "3 M")]
    worker = _BacktestStatsWorker(BacktestStore(tmp_path), lambda: jobs)
    seen: list[Any] = []
    worker.done.connect(seen.append)
    worker.run()

    assert (seen[0].missing_1d, seen[0].missing_3m, seen[0].short_stocks) == (1, 2, 2)
