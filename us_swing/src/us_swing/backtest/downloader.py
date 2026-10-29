"""
Module: MD-BKT-001.006.M04 — backtest/downloader.py
Parent SRD: SRD-BKT-001.006

Runs planned jobs against TWS in a background thread: retry, floors and stop. Requests go
one after another with no fixed limit, like the candle download; TWS slows them itself.
Uses its own client ID so it never disturbs the live feeds.
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import date, datetime, time, timedelta, timezone
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from us_swing.backtest.planner import Job
from us_swing.backtest.settings import DownloadState
from us_swing.backtest.store import BacktestStore
from us_swing.broker.pacing import PacingQueue

_log = logging.getLogger(__name__)

_ET = ZoneInfo("America/New_York")
_TRIES = 3
_MAX_CLIENT_ID_RETRIES = 3
_IPO_SLACK = timedelta(days=7)
_BAR_SIZE = {"1d": "1 day", "3m": "3 mins"}
_RETRYABLE = (asyncio.TimeoutError, ConnectionError, OSError)


class BacktestDownloader(QThread):
    """Download backtest candles from TWS for a planned job list.

    Signals:
        progress(tf, done, total, symbol): After each job.
        completed(ok, message): When the run ends; ``ok`` is False when stopped or not connected.
    """

    progress = pyqtSignal(str, int, int, str)
    completed = pyqtSignal(bool, str)

    def __init__(
        self,
        jobs: Sequence[Job] | Callable[[], list[Job]],
        store: BacktestStore,
        *,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 16,
        delta: bool = False,
        pacing: PacingQueue | None = None,
        retry_wait_s: float = 30.0,
        timeout_s: float = 90.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._jobs = jobs
        self._store = store
        self._host = host
        self._port = port
        self._client_id = client_id
        self._delta = delta
        self._pacing = pacing
        self._retry_wait_s = retry_wait_s
        self._timeout_s = timeout_s
        self._stop = False

    def request_stop(self) -> None:
        """Stop after the current request finishes."""
        self._stop = True

    def run(self) -> None:
        """QThread entry: connect, run the jobs, disconnect, emit ``completed``."""
        try:
            ok, message = asyncio.run(self._connect_and_run())
        except Exception:  # noqa: BLE001
            _log.exception("[Backtest] Download stopped by an unexpected error")
            ok, message = False, "Download failed — see log"
        self.completed.emit(ok, message)

    async def run_jobs(self, ib: Any) -> tuple[bool, str]:
        """Run every job on a connected ``ib``; return ``(ok, message)``."""
        jobs = self._resolve_jobs()
        state = DownloadState.load(self._store.root)
        state.failed = []
        totals = Counter(job.tf for job in jobs)
        done: Counter[str] = Counter()
        for job in jobs:
            if self._stop:
                _log.info("[Backtest] Download paused")
                state.save(self._store.root)
                return False, "Stopped"
            if job.symbol not in state.failed and not self._below_floor(job, state):
                await self._run_job(ib, job, state)
            done[job.tf] += 1
            self.progress.emit(job.tf, done[job.tf], totals[job.tf], job.symbol)
        if self._delta:
            state.last_delta = datetime.now(timezone.utc)
        state.save(self._store.root)
        if state.failed:
            _log.warning("[Backtest] Download finished — %d stock(s) failed", len(state.failed))
            return True, f"Done — {len(state.failed)} stock(s) failed"
        _log.info("[Backtest] Download finished")
        return True, "Done"

    def _resolve_jobs(self) -> list[Job]:
        if callable(self._jobs):
            self._jobs = self._jobs()
        return list(self._jobs)

    async def _connect_and_run(self) -> tuple[bool, str]:
        from ib_insync import IB

        jobs = self._resolve_jobs()
        if not jobs:
            _log.info("[Backtest] Backtest data is already up to date")
            return True, "Up to date"

        ib = IB()  # type: ignore[no-untyped-call]
        client_id = self._client_id
        for attempt in range(_MAX_CLIENT_ID_RETRIES + 1):
            in_use: list[bool] = [False]

            def on_error(_req_id: int, code: int, *_: Any) -> None:
                if code == 326:
                    in_use[0] = True

            ib.errorEvent += on_error
            try:
                await ib.connectAsync(self._host, self._port, clientId=client_id, timeout=10)
                break
            except Exception:  # noqa: BLE001
                if not (in_use[0] and attempt < _MAX_CLIENT_ID_RETRIES):
                    _log.warning("[Backtest] Could not connect to TWS at %s:%d",
                                 self._host, self._port)
                    return False, "Could not connect to TWS"
                client_id += 1
            finally:
                ib.errorEvent -= on_error
        _log.info("[Backtest] Downloading %d request(s) from TWS", len(jobs))
        try:
            return await self.run_jobs(ib)
        finally:
            ib.disconnect()  # type: ignore[no-untyped-call]

    async def _run_job(self, ib: Any, job: Job, state: DownloadState) -> None:
        for attempt in range(1, _TRIES + 1):
            try:
                bars = await self._request(ib, job)
                break
            except _RETRYABLE:
                if attempt == _TRIES:
                    _log.warning("[Backtest] %s failed after %d tries — skipping its other "
                                 "requests", job.symbol, _TRIES)
                    state.failed.append(job.symbol)
                    return
                await asyncio.sleep(self._retry_wait_s)
        if bars:
            self._store.save(
                job.symbol, job.tf, _to_frame(bars), datetime.now(timezone.utc), job.start
            )
        self._update_floor(job, state, bool(bars))

    async def _request(self, ib: Any, job: Job) -> list[Any]:
        from ib_insync import Stock

        if self._pacing is not None:
            await self._pacing.acquire()
        started = monotonic()
        result = await ib.reqHistoricalDataAsync(
            Stock(job.symbol, "SMART", "USD"),
            endDateTime=_end_time(job.end),
            durationStr=job.duration,
            barSizeSetting=_BAR_SIZE[job.tf],
            whatToShow="TRADES",
            useRTH=True,
            formatDate=2,
            timeout=self._timeout_s,
        )
        if not result and monotonic() - started >= self._timeout_s:
            # ib_insync cancels a timed-out request and returns an empty list, not an error.
            raise asyncio.TimeoutError
        return list(result)

    def _update_floor(self, job: Job, state: DownloadState, got_bars: bool) -> None:
        saved = self._store.coverage(job.symbol, job.tf)
        if job.tf == "1d":
            floor = saved[0] if saved and saved[0] > job.start + _IPO_SLACK else None
        else:
            floor = job.end if not got_bars and (saved is None or job.end <= saved[0]) else None
        if floor is not None:
            state.floors[job.symbol] = max(floor, state.floors.get(job.symbol, floor))

    @staticmethod
    def _below_floor(job: Job, state: DownloadState) -> bool:
        floor = state.floors.get(job.symbol)
        return job.tf == "3m" and floor is not None and job.end <= floor


def _end_time(end: date) -> datetime | str:
    end_dt = datetime.combine(end, time(23, 59, 59), _ET)
    return "" if end_dt >= datetime.now(_ET) else end_dt.astimezone(timezone.utc)


def _to_frame(bars: list[Any]) -> pd.DataFrame:
    return pd.DataFrame({
        "ts": [b.date for b in bars],
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
    })
