"""Tests for MD-BKT-001.006.M04 — backtest/downloader.py (fake IB, no TWS)."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from us_swing.backtest.downloader import BacktestDownloader
from us_swing.backtest.planner import Job
from us_swing.backtest.settings import DownloadState
from us_swing.backtest.store import BacktestStore
from us_swing.broker.pacing import PacingQueue


@dataclass
class _Bar:
    date: Any
    open: float = 10.0
    high: float = 11.0
    low: float = 9.0
    close: float = 10.0
    volume: float = 100.0


Handler = Callable[[str, str], list[_Bar]]


class _FakeIB:
    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.calls: list[tuple[str, str]] = []

    async def reqHistoricalDataAsync(self, contract: Any, **kwargs: Any) -> list[_Bar]:
        self.calls.append((contract.symbol, kwargs["durationStr"]))
        return self.handler(contract.symbol, kwargs["barSizeSetting"])


def _daily(_symbol: str, _bar_size: str) -> list[_Bar]:
    return [_Bar(date(2025, 1, 2)), _Bar(date(2025, 1, 3))]


def _downloader(tmp_path: Path, jobs: list[Job]) -> BacktestDownloader:
    return BacktestDownloader(
        jobs, BacktestStore(tmp_path),
        pacing=PacingQueue(limit=1000), retry_wait_s=0.0, timeout_s=5.0,
    )


def _job_1d(symbol: str) -> Job:
    return Job(symbol, "1d", date(2025, 1, 1), date(2025, 1, 3), "1 Y")


def test_jobs_saved_with_progress(tmp_path: Path) -> None:
    """UT-BKT-001.006.M04.T01: Each job is saved and progress is emitted per job."""
    dl = _downloader(tmp_path, [_job_1d("AAPL"), _job_1d("MSFT")])
    seen: list[tuple[str, int, int, str]] = []
    dl.progress.connect(lambda *a: seen.append(a))

    ok, _msg = asyncio.run(dl.run_jobs(_FakeIB(_daily)))

    assert ok
    assert [(s[1], s[2]) for s in seen] == [(1, 2), (2, 2)]
    assert len(BacktestStore(tmp_path).read("AAPL", "1d")) == 2
    assert len(BacktestStore(tmp_path).read("MSFT", "1d")) == 2


def test_retry_then_mark_failed(tmp_path: Path) -> None:
    """UT-BKT-001.006.M04.T02: A stock that times out 3 times is marked failed; others run."""
    def handler(symbol: str, bar_size: str) -> list[_Bar]:
        if symbol == "AAPL":
            raise asyncio.TimeoutError
        return _daily(symbol, bar_size)

    jobs = [_job_1d("AAPL"), _job_1d("MSFT"),
            Job("AAPL", "3m", date(2024, 10, 3), date(2025, 1, 3), "3 M")]
    ib = _FakeIB(handler)

    asyncio.run(_downloader(tmp_path, jobs).run_jobs(ib))

    assert [c for c in ib.calls if c[0] == "AAPL"] == [("AAPL", "1 Y")] * 3
    assert DownloadState.load(tmp_path).failed == ["AAPL"]
    assert len(BacktestStore(tmp_path).read("MSFT", "1d")) == 2


def test_empty_window_sets_floor(tmp_path: Path) -> None:
    """UT-BKT-001.006.M04.T03: An empty 3m window older than saved data sets the floor."""
    store = BacktestStore(tmp_path)
    recent = [_Bar(datetime(2025, 1, 2, 15, 0, tzinfo=timezone.utc))]
    asyncio.run(_downloader(tmp_path, [
        Job("AAPL", "3m", date(2024, 10, 3), date(2025, 1, 3), "3 M"),
    ]).run_jobs(_FakeIB(lambda s, b: recent)))
    assert store.coverage("AAPL", "3m") is not None

    old = Job("AAPL", "3m", date(2024, 7, 3), date(2024, 10, 3), "3 M")
    asyncio.run(_downloader(tmp_path, [old]).run_jobs(_FakeIB(lambda s, b: [])))

    assert DownloadState.load(tmp_path).floors == {"AAPL": date(2024, 10, 3)}


def test_stop_ends_after_current_job(tmp_path: Path) -> None:
    """UT-BKT-001.007.M04.T01: A stop during job 1 saves it and skips the rest."""
    jobs = [_job_1d("AAPL"), _job_1d("MSFT"), _job_1d("NVDA")]
    dl = _downloader(tmp_path, jobs)

    def handler(symbol: str, bar_size: str) -> list[_Bar]:
        dl.request_stop()
        return _daily(symbol, bar_size)

    ib = _FakeIB(handler)
    asyncio.run(dl.run_jobs(ib))

    assert [c[0] for c in ib.calls] == ["AAPL"]
    assert len(BacktestStore(tmp_path).read("AAPL", "1d")) == 2
    assert BacktestStore(tmp_path).read("MSFT", "1d").empty


def test_stopped_run_not_reported_complete(tmp_path: Path) -> None:
    """UT-BKT-001.007.M04.T02: A stopped run returns ok False with message Stopped."""
    dl = _downloader(tmp_path, [_job_1d("AAPL"), _job_1d("MSFT"), _job_1d("NVDA")])

    def handler(symbol: str, bar_size: str) -> list[_Bar]:
        dl.request_stop()
        return _daily(symbol, bar_size)

    assert asyncio.run(dl.run_jobs(_FakeIB(handler))) == (False, "Stopped")
