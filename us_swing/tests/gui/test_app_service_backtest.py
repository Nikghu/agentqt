"""
Module: MD-GUI-030.004.M02 — tests
Parent SRD: SRD-GUI-030.004

AppService backtest wiring: auto delta starts once when due; Clear is refused while
a download runs.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from us_swing.backtest.settings import BacktestDataSettings, DownloadState
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
    BacktestDataSettings(start_date=last).save(store.root)
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)

    store.save("AAPL", "1d", _bars("2026-01-02"), now)
    store.save("AAPL", "3m", _bars(f"{last} 15:00"), now)
    store.save("MSFT", "1d", _bars("2026-01-02"), now)

    cov = svc.get_backtest_symbol_coverage()

    assert cov["AAPL"] == (last.isoformat(), last.isoformat(), "ok")
    assert cov["MSFT"] == ("2026-01-02", "2026-01-02", "partial")
    assert cov["NVDA"] == (None, None, "none")


def test_universe_etf_rows(svc: Any) -> None:
    """UT-GUI-030.013.M02.T01: SPY, RSP and the 11 sector ETFs get rows; daily candles that
    cover the range are ok, short ones partial, none missing."""
    from us_swing.gui.app_service import _compute_last_trading_day

    last = _compute_last_trading_day()
    store = svc._bkt_store
    BacktestDataSettings(start_date=date(2024, 1, 2)).save(store.root)
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    store.save("SPY", "1d", pd.concat([_bars("2023-09-25"), _bars(last.isoformat())]), now)
    store.save("XLK", "1d", pd.concat([_bars("2025-01-02"), _bars(last.isoformat())]), now)

    rows = {r[0]: r for r in svc.get_backtest_etf_rows()}

    assert len(rows) == 13 and list(rows)[:2] == ["SPY", "RSP"]
    assert rows["SPY"] == ("SPY", "S&P 500 (SPY)", "2023-09-25", last.isoformat(), "ok")
    assert rows["XLK"][1:] == ("Technology sector", "2025-01-02", last.isoformat(), "partial")
    assert rows["RSP"][2:] == (None, None, "none")


def _bars(day: str) -> pd.DataFrame:
    return pd.DataFrame({"ts": [pd.Timestamp(day, tz="UTC")], "open": [1.0], "high": [1.0],
                         "low": [1.0], "close": [1.0], "volume": [1.0]})


def test_universe_coverage_partial_ignores_floor(svc: Any) -> None:
    """UT-GUI-030.011.M02.T01: Dates that do not cover the range are partial, even with a
    saved listing date (ISS-BKT-0003)."""
    svc._sp500 = [Sp500Record(s, s, s, "Tech") for s in ("AAPL", "NEWCO")]
    store = svc._bkt_store
    BacktestDataSettings(start_date=date(2024, 1, 1)).save(store.root)
    DownloadState(floors={"NEWCO": date(2025, 3, 3)}).save(store.root)
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    store.save("AAPL", "3m", _bars("2024-04-05 15:00"), now)
    store.save("NEWCO", "3m", _bars("2025-03-03 15:00"), now)

    cov = svc.get_backtest_symbol_coverage()

    assert cov["AAPL"][2] == "partial"
    assert cov["NEWCO"][2] == "partial"


def test_missing_3m_day_is_partial(svc: Any) -> None:
    """UT-GUI-030.011.M02.T02: A stock covering the range but missing a 3m day inside it is
    partial, and the day is listed (ISS-BKT-0003)."""
    from us_swing.gui.app_service import _compute_last_trading_day

    last = _compute_last_trading_day()
    svc._sp500 = [Sp500Record("META", "META", "Meta", "Comm")]
    store = svc._bkt_store
    first = date(2024, 1, 3)
    BacktestDataSettings(start_date=first).save(store.root)
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    days = [first, date(2024, 1, 4), last]
    store.save("META", "1d", pd.concat([_bars(d.isoformat()) for d in days]), now)
    store.save("META", "3m", pd.concat([_bars(f"{d} 15:00") for d in (first, last)]), now)
    assert svc.get_backtest_symbol_coverage()["META"][2] == "ok"  # gap cache not built yet

    store.refresh_gaps(["META"])

    assert svc.get_backtest_symbol_coverage()["META"][2] == "partial"
    assert svc.get_backtest_gaps() == {"META": ["2024-01-04"]}


def test_fill_selected_clears_floor_and_downloads_only_those(svc: Any) -> None:
    """UT-GUI-030.008.M02.T02: Fill selected drops the ticked stocks' listing dates and
    downloads only them; other floors stay (ISS-BKT-0003)."""
    svc._sp500 = [Sp500Record(s, s, s, "Tech") for s in ("UNP", "UPS", "V")]
    root = svc._bkt_store.root
    DownloadState(floors={"UNP": date(2024, 1, 2), "V": date(2024, 1, 2)}).save(root)
    fake_cls = MagicMock()
    with patch("us_swing.gui.app_service.BacktestDownloader", fake_cls):
        assert svc.fill_backtest_symbols(["UNP", "UPS"]) is True

    assert DownloadState.load(root).floors == {"V": date(2024, 1, 2)}
    jobs = fake_cls.call_args.args[0]()
    from us_swing.gui.sector_rotation import SECTOR_SYMBOLS

    assert {j.symbol for j in jobs} - {"SPY", *SECTOR_SYMBOLS} == {"UNP", "UPS"}


def test_fill_selected_refused_while_running(svc: Any) -> None:
    """UT-GUI-030.008.M02.T03: Fill selected does nothing while a download runs or with no ticks."""
    root = svc._bkt_store.root
    DownloadState(floors={"AAPL": date(2024, 1, 2)}).save(root)
    assert svc.fill_backtest_symbols([]) is False
    svc._bkt_downloader = MagicMock()

    assert svc.fill_backtest_symbols(["AAPL"]) is False
    assert DownloadState.load(root).floors == {"AAPL": date(2024, 1, 2)}


def test_coverage_for_one_stock(svc: Any) -> None:
    """UT-GUI-030.012.M02.T01: One stock's coverage by IBKR symbol; None when not listed."""
    svc._sp500 = [Sp500Record("BRK.B", "BRK B", "Berkshire", "Fin")]
    store = svc._bkt_store
    BacktestDataSettings(start_date=date(2024, 1, 1)).save(store.root)
    store.save("BRK B", "1d", _bars("2024-01-02"), datetime(2030, 1, 1, tzinfo=timezone.utc))

    assert svc.get_backtest_coverage_for("BRK B") == ("BRK.B",
                                                      ("2024-01-02", "2024-01-02", "partial"))
    assert svc.get_backtest_coverage_for("ZZZZ") is None


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


def test_stats_worker_counts_partial(tmp_path: Path) -> None:
    """UT-GUI-030.009.M02.T02: The stats worker adds the partial stock count."""
    from us_swing.gui.app_service import _BacktestStatsWorker

    worker = _BacktestStatsWorker(BacktestStore(tmp_path), lambda: [], lambda: 224)
    seen: list[Any] = []
    worker.done.connect(seen.append)
    worker.run()

    assert seen[0].partial_stocks == 224
