"""
Module: MD-EXE-007.001.M01 — execution/live_bar_worker.py
Parent SRD: SRD-EXE-007.003
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, time as _dtime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from us_swing.core.candle_builder import CandleBuilder
from us_swing.data.models import OHLCVBar, RealtimeBar

log = logging.getLogger(__name__)

_YFINANCE_POLL_SECS: int = 60
_CONNECT_TIMEOUT: int = 10
_ET = ZoneInfo("America/New_York")
_LIVE_TIMEFRAMES: tuple[str, ...] = ("3m", "15m")
_RTH_OPEN  = _dtime(9, 30)
_RTH_CLOSE = _dtime(16, 0)
_SUB_BATCH_SIZE: int = 10        # pause after every N subscriptions
_SUB_BATCH_PAUSE: float = 0.20   # seconds — keeps rate below IBKR's ~50 req/s limit
_FALLBACK_THRESHOLD: float = 0.90  # fall back to yfinance if ≥ 90 % of subs fail

# IBKR error codes that indicate a missing market-data subscription.
_NO_PERM_CODES: frozenset[int] = frozenset({162, 200, 354, 420, 10089, 10189})


def _ensure_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _is_rth(dt: datetime) -> bool:
    """Return True iff *dt* falls inside US Regular Trading Hours (weekdays 09:30–16:00 ET)."""
    dt_et = dt.astimezone(_ET)
    if dt_et.weekday() >= 5:
        return False
    t = dt_et.time()
    return _RTH_OPEN <= t < _RTH_CLOSE


class LiveBarWorker(QThread):
    """Subscribes to IBKR 5-second real-time bars and builds 3m + 15m candles.

    Uses ``reqRealTimeBars(barSize=5, whatToShow='TRADES', useRTH=True)`` — capped
    by market-data lines (~100), not by the strict 5-concurrent tick-by-tick limit.
    Each 5s bar is forwarded to ``CandleBuilder``, which aggregates into 3m/15m
    candles on time-window boundaries.

    On each completed 3m or 15m bar, writes to the matching ``price_<tf>`` table
    asynchronously (off the event loop) and emits ``candle_closed`` so the GUI
    can refresh charts.  Falls back to yfinance batch polling (60 s interval)
    when IBKR is unavailable.

    Args:
        symbols:          Filtered stock list (max 100 — IBKR L1 streaming cap).
        ibkr_host:        IBKR TWS / Gateway hostname.
        ibkr_port:        IBKR TWS / Gateway port.
        ibkr_client_id:   Dedicated client ID for this subscription connection.
        db_path:          Absolute path to ``candles.db`` (price_3m / price_15m tables).
        parent:           Optional Qt parent object.
    """

    candle_closed = pyqtSignal(str)  # symbol — one completed 3m or 15m bar written to DB

    def __init__(
        self,
        symbols: list[str],
        ibkr_host: str,
        ibkr_port: int,
        ibkr_client_id: int,
        db_path: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._symbols = list(symbols)
        self._ibkr_host = ibkr_host
        self._ibkr_port = ibkr_port
        self._ibkr_client_id = ibkr_client_id
        self._db_path = db_path
        self._stop_flag = False
        self._stop_event: asyncio.Event | None = None
        self._worker_loop: asyncio.AbstractEventLoop | None = None
        self._ib: Any = None
        self._builder: CandleBuilder | None = None
        self._subscribed: set[str] = set()
        self._tick_subs: dict[str, Any] = {}
        self._reqid_to_symbol: dict[int, str] = {}

    # ── QThread entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """QThread entry: run the async subscription loop in a fresh event loop."""
        try:
            asyncio.run(self._async_run())
        except Exception:
            log.exception("[Live] Unexpected error in live bar worker")

    def request_stop(self) -> None:
        """Signal the worker to stop; safe to call from any thread."""
        self._stop_flag = True
        ib = self._ib
        if ib is not None:
            try:
                ib.disconnect()
            except Exception:
                pass
        loop = self._worker_loop
        stop_event = self._stop_event
        if loop is not None and stop_event is not None:
            try:
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError:
                pass

    def set_symbols(self, symbols: list[str]) -> None:
        """Update live real-time bar subscriptions without restarting the worker.

        Schedules IB subscribe/cancel calls on the worker's own event loop so
        all IB calls remain on the correct thread.  Safe to call from any thread.

        Args:
            symbols: New complete symbol list.
        """
        self._symbols = list(symbols)
        loop = self._worker_loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._apply_symbol_update(set(symbols)), loop
            )

    # ── IBKR path ──────────────────────────────────────────────────────────────

    async def _apply_symbol_update(self, new_set: set[str]) -> None:
        """Add/remove real-time bar subscriptions — must run on the worker event loop."""
        ib = self._ib
        builder = self._builder
        if ib is None or builder is None or not ib.isConnected():
            return

        from ib_insync import Stock  # noqa: PLC0415

        to_remove = self._subscribed - new_set
        to_add    = new_set - self._subscribed

        for symbol in to_remove:
            try:
                bars = self._tick_subs.pop(symbol, None)
                if bars is not None:
                    ib.cancelRealTimeBars(bars)
                    _rid: int | None = getattr(bars, "reqId", None)
                    if _rid is not None:
                        self._reqid_to_symbol.pop(_rid, None)
                self._subscribed.discard(symbol)
                builder.reset(symbol)
            except Exception as exc:
                log.warning("[Live] Could not cancel subscription for %s: %s", symbol, exc)

        for i, symbol in enumerate(sorted(to_add)):
            try:
                contract = Stock(symbol.replace(".", " "), "SMART", "USD")
                bars = ib.reqRealTimeBars(
                    contract, barSize=5, whatToShow="TRADES", useRTH=True
                )
                bars.updateEvent += self._make_bar_handler(symbol, builder)
                self._tick_subs[symbol] = bars
                self._subscribed.add(symbol)
                req_id: int | None = getattr(bars, "reqId", None)
                if req_id is not None:
                    self._reqid_to_symbol[req_id] = symbol
            except Exception as exc:
                log.warning("[Live] Could not subscribe to %s: %s", symbol, exc)
            if i % _SUB_BATCH_SIZE == _SUB_BATCH_SIZE - 1:
                await asyncio.sleep(_SUB_BATCH_PAUSE)

    async def _async_run(self) -> None:
        self._stop_event = asyncio.Event()
        self._worker_loop = asyncio.get_running_loop()
        try:
            from ib_insync import IB  # noqa: PLC0415
        except ImportError:
            log.warning("[Live] IBKR library not available — using Yahoo Finance instead")
            await self._run_yfinance()
            return

        ib = IB()  # type: ignore[no-untyped-call]
        self._ib = ib
        log.info("[Live] Connecting to IBKR at %s:%d …", self._ibkr_host, self._ibkr_port)
        try:
            await ib.connectAsync(
                self._ibkr_host,
                self._ibkr_port,
                clientId=self._ibkr_client_id,
                timeout=_CONNECT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning("[Live] IBKR connection timed out — switching to Yahoo Finance")
            await self._run_yfinance()
            return
        except Exception as exc:
            log.warning("[Live] IBKR connection failed (%s) — switching to Yahoo Finance", exc)
            await self._run_yfinance()
            return

        log.info(
            "[Live] Connected — subscribing to 5-second real-time bars for %d stock(s)",
            len(self._symbols),
        )
        builder = CandleBuilder(list(_LIVE_TIMEFRAMES), on_candle_closed=self._on_candle_closed)
        self._builder = builder

        failed_symbols: set[str] = set()
        _all_failed = asyncio.Event()
        total_symbols = len(self._symbols)

        def _on_ibkr_error(req_id: int, error_code: int, error_str: str, *_: Any) -> None:
            if error_code not in _NO_PERM_CODES or req_id <= 0:
                return
            symbol = self._reqid_to_symbol.get(req_id)
            if symbol is None or symbol in failed_symbols:
                return
            failed_symbols.add(symbol)
            log.warning("[Live] No market data permission for %s", symbol)
            if total_symbols > 0 and len(failed_symbols) / total_symbols >= _FALLBACK_THRESHOLD:
                log.warning(
                    "[Live] %d of %d stocks lack market data permission — falling back to Yahoo Finance",
                    len(failed_symbols), total_symbols,
                )
                _all_failed.set()

        ib.errorEvent += _on_ibkr_error

        from ib_insync import Stock  # noqa: PLC0415
        for i, symbol in enumerate(self._symbols):
            try:
                contract = Stock(symbol.replace(".", " "), "SMART", "USD")  # BRK.B → BRK B
                bars = ib.reqRealTimeBars(
                    contract, barSize=5, whatToShow="TRADES", useRTH=True
                )
                bars.updateEvent += self._make_bar_handler(symbol, builder)
                self._tick_subs[symbol] = bars
                self._subscribed.add(symbol)
                req_id = getattr(bars, "reqId", None)
                if req_id is not None:
                    self._reqid_to_symbol[req_id] = symbol
            except Exception as exc:
                log.warning("[Live] Could not subscribe to %s: %s", symbol, exc)
            if i % _SUB_BATCH_SIZE == _SUB_BATCH_SIZE - 1:
                await asyncio.sleep(_SUB_BATCH_PAUSE)

        try:
            while not self._stop_flag and ib.isConnected() and not _all_failed.is_set():
                await asyncio.sleep(1.0)
        finally:
            try:
                ib.disconnect()  # type: ignore[no-untyped-call]
            except Exception:
                pass
            for sym in list(self._subscribed):
                builder.reset(sym)
            self._subscribed.clear()
            self._tick_subs.clear()
            self._reqid_to_symbol.clear()
            self._builder = None

        if _all_failed.is_set() and not self._stop_flag:
            log.info("[Live] Switched to Yahoo Finance — IBKR market data unavailable")
            await self._run_yfinance()
            return

        log.info("[Live] IBKR real-time bar subscription ended")

    def _make_bar_handler(self, symbol: str, builder: CandleBuilder) -> Any:
        """Return an ib_insync updateEvent closure for ``reqRealTimeBars`` on *symbol*.

        ib_insync's ``RealTimeBarList.updateEvent`` fires on the asyncio loop thread
        with ``(bars, has_new_bar)`` where *bars* is the full accumulated list and
        ``has_new_bar`` flags that a new 5-second bar has just closed.  Only the most
        recently closed bar is fed to the builder.
        """
        def _handler(bars: Any, has_new_bar: bool) -> None:
            if not has_new_bar or not bars:
                return
            try:
                bar = bars[-1]
                dt = _ensure_utc(bar.time)
                if not _is_rth(dt):
                    return
                volume = int(bar.volume) if bar.volume is not None else 0
                if volume <= 0:
                    return
                builder.add_bar(RealtimeBar(
                    symbol=symbol,
                    datetime=dt,
                    open=float(bar.open_),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=volume,
                ))
            except Exception:
                log.debug("[Live] Real-time bar parse error for %s", symbol, exc_info=True)
        return _handler

    def _on_candle_closed(self, symbol: str, tf: str, bar: OHLCVBar) -> None:
        loop = self._worker_loop
        if loop is not None:
            async def _write_async() -> None:
                try:
                    await asyncio.to_thread(self._write_bar, symbol, tf, bar)
                except Exception:
                    log.warning("[Live] Failed to write %s bar for %s to database", tf, symbol)
            loop.create_task(_write_async())
        log.debug("[Live] %s — %s candle closed @ %s", symbol, tf, bar.datetime)
        self.candle_closed.emit(symbol)

    def _write_rows(
        self, tf: str, rows: list[tuple[str, str, float, float, float, float, int]]
    ) -> int:
        """Bulk-insert pre-filtered rows into price_<tf>. Returns attempted row count."""
        if not rows:
            return 0
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executemany(
                f"INSERT OR IGNORE INTO price_{tf} "
                "(symbol, datetime, open, high, low, close, volume) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
        finally:
            conn.close()
        return len(rows)

    def _write_bar(self, symbol: str, tf: str, bar: OHLCVBar) -> None:
        if tf not in _LIVE_TIMEFRAMES:
            raise ValueError(f"Unsupported live timeframe: {tf!r}")
        self._write_rows(tf, [(
            symbol,
            bar.datetime.strftime("%Y-%m-%dT%H:%M:%S"),
            bar.open, bar.high, bar.low, bar.close, bar.volume,
        )])

    # ── yfinance fallback ──────────────────────────────────────────────────────

    async def _run_yfinance(self) -> None:
        try:
            import yfinance  # type: ignore[import-untyped]  # noqa: F401
        except ImportError:
            log.error(
                "[Live] Yahoo Finance library not installed — live candle updates unavailable"
                " (run: pip install yfinance)"
            )
            return

        log.info(
            "[Live] Polling Yahoo Finance every %ds for %d stock(s)",
            _YFINANCE_POLL_SECS, len(self._symbols),
        )
        stop_event = self._stop_event or asyncio.Event()
        while not self._stop_flag:
            await asyncio.to_thread(self._poll_yfinance_once)
            try:
                await asyncio.wait_for(
                    asyncio.shield(stop_event.wait()), timeout=_YFINANCE_POLL_SECS
                )
                break
            except asyncio.TimeoutError:
                pass

    def _poll_yfinance_once(self) -> None:
        """Batch-download all symbols for both timeframes in two HTTP calls."""
        import yfinance as yf  # noqa: PLC0415
        symbols = list(self._symbols)
        if not symbols:
            return

        # Two batch downloads replace 2×N per-symbol requests.
        for interval, tf, period, group_minutes in [
            ("1m",  "3m",  "1d", 3),
            ("15m", "15m", "5d", None),
        ]:
            try:
                df_all = yf.download(
                    symbols, period=period, interval=interval,
                    group_by="ticker", auto_adjust=True,
                    progress=False, threads=True,
                )
            except Exception:
                log.debug("[Live] Yahoo Finance download failed for %s bars", tf, exc_info=True)
                continue

            multi = len(symbols) > 1
            for symbol in symbols:
                if self._stop_flag:
                    return
                try:
                    if multi:
                        top = df_all.columns.get_level_values(0)
                        if symbol not in top:
                            continue
                        df = df_all[symbol].dropna(how="all")
                    else:
                        df = df_all.dropna(how="all")
                    if df.empty:
                        continue

                    if group_minutes is not None:
                        wrote = self._write_yfinance_aggregated(symbol, df, tf, group_minutes)
                    else:
                        wrote = self._write_yfinance_direct(symbol, df, tf)

                    if wrote:
                        log.debug("[Live] %s — %d new %s bar(s) from Yahoo Finance", symbol, wrote, tf)
                        self.candle_closed.emit(symbol)
                except Exception:
                    log.debug("[Live] Yahoo Finance processing failed for %s", symbol, exc_info=True)

    def _write_yfinance_direct(self, symbol: str, df: Any, tf: str) -> int:
        """Insert each row of *df* as a candle in price_<tf>. Returns row count."""
        last_in_db = self._get_last_ts(symbol, tf)
        rows: list[tuple[str, str, float, float, float, float, int]] = []
        for ts, row in df.iterrows():
            dt = _ensure_utc(ts.to_pydatetime())
            if last_in_db is not None and dt <= last_in_db:
                continue
            rows.append((
                symbol,
                dt.strftime("%Y-%m-%dT%H:%M:%S"),
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                float(row["Close"]),
                int(row["Volume"]),
            ))
        return self._write_rows(tf, rows)

    def _write_yfinance_aggregated(
        self, symbol: str, df_1m: Any, tf: str, group_minutes: int
    ) -> int:
        """Aggregate 1m rows into *group_minutes* buckets, write completed buckets."""
        last_in_db = self._get_last_ts(symbol, tf)
        buckets: dict[datetime, dict[str, float]] = {}
        for ts, row in df_1m.iterrows():
            dt = _ensure_utc(ts.to_pydatetime())
            bucket_min = (dt.minute // group_minutes) * group_minutes
            bucket_dt = dt.replace(minute=bucket_min, second=0, microsecond=0)
            agg = buckets.get(bucket_dt)
            if agg is None:
                buckets[bucket_dt] = {
                    "open":   float(row["Open"]),
                    "high":   float(row["High"]),
                    "low":    float(row["Low"]),
                    "close":  float(row["Close"]),
                    "volume": float(row["Volume"]),
                }
            else:
                agg["high"]   = max(agg["high"], float(row["High"]))
                agg["low"]    = min(agg["low"],  float(row["Low"]))
                agg["close"]  = float(row["Close"])
                agg["volume"] = agg["volume"] + float(row["Volume"])

        if not buckets:
            return 0
        completed = sorted(buckets.keys())[:-1]  # skip the last (in-progress) bucket

        rows: list[tuple[str, str, float, float, float, float, int]] = []
        for bucket_dt in completed:
            if last_in_db is not None and bucket_dt <= last_in_db:
                continue
            agg = buckets[bucket_dt]
            rows.append((
                symbol,
                bucket_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                agg["open"], agg["high"], agg["low"], agg["close"],
                int(agg["volume"]),
            ))
        return self._write_rows(tf, rows)

    def _get_last_ts(self, symbol: str, tf: str) -> datetime | None:
        try:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    f"SELECT MAX(datetime) FROM price_{tf} WHERE symbol = ?", (symbol,)
                ).fetchone()
            finally:
                conn.close()
            if row and row[0]:
                return datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            pass
        return None
