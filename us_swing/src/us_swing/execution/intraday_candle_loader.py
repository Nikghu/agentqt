"""
Module: MD-EXE-006.001.M01 — execution/intraday_candle_loader.py
Parent SRD: SRD-EXE-006.001  # covers SRD-EXE-006.001–006.006, SRD-EXE-006.010
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from us_swing.broker.pacing import PacingQueue
from us_swing.data.engine import DerivedTimeframe, HistoricalDataEngine
from us_swing.data.models import OHLCVBar
from us_swing.db.manager import DatabaseManager

log = logging.getLogger(__name__)

_MIN_CANDLES: int = 390
_IBKR_MAX_CAL_DAYS_PER_PAGE: int = 30
_FULL_FETCH_CAL_DAYS: int = 30  # 21 trading days ≈ 30 calendar days; fits one IBKR page
_REQUIRED_TIMEFRAMES: tuple[DerivedTimeframe, ...] = ("3m", "15m")
_SYMBOL_PAUSE_S: float = 0.3
_MAX_CLIENT_ID_RETRIES: int = 5  # SRD-EXE-006.011


def _ensure_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _build_tf_counts(
    symbol: str,
    bars_1m: list[OHLCVBar],
    timeframes: tuple[DerivedTimeframe, ...],
    hist_engine: HistoricalDataEngine,
) -> dict[str, int]:
    return {tf: len(hist_engine.aggregate_timeframe(symbol, tf, bars_1m)) for tf in timeframes}


def _merge_bars(derived: list[OHLCVBar], live: list[OHLCVBar]) -> list[OHLCVBar]:
    """Union two bar lists by timestamp; live bars win on conflict, sorted ascending."""
    by_dt: dict[datetime, OHLCVBar] = {b.datetime: b for b in derived}
    for bar in live:
        by_dt[bar.datetime] = bar
    return [by_dt[dt] for dt in sorted(by_dt)]


def _bars_to_frame(bars: list[OHLCVBar]) -> pd.DataFrame:
    """Build the OHLCV frame consumed by ``ConditionEvaluator`` (SRD-EXE-011.006)."""
    return pd.DataFrame(
        {
            "datetime": [b.datetime for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )


def assemble_execution_bars(
    db: DatabaseManager,
    hist_engine: HistoricalDataEngine,
    symbol: str,
    tf: DerivedTimeframe,
    lookback_days: int = _FULL_FETCH_CAL_DAYS,
) -> list[OHLCVBar]:
    """Assemble a derived-timeframe bar series for strategy evaluation (SRD-EXE-006.010).

    Aggregates stored 1m bars (the source of truth for historical depth) and
    merges any live ``price_{tf}`` bars already materialised by the live feed.

    Args:
        db: Candle database handle.
        hist_engine: Provides the pure ``aggregate_timeframe`` helper.
        symbol: Ticker symbol.
        tf: Target derived timeframe (e.g. ``'3m'`` or ``'15m'``).
        lookback_days: Calendar-day window of 1m history to aggregate.

    Returns:
        Merged bars sorted ascending by datetime; empty when no source has data.
    """
    now = datetime.now(tz=timezone.utc)
    window_start = now - timedelta(days=lookback_days)
    bars_1m = db.fetch_bars(symbol, "1m", window_start, now)
    derived = hist_engine.aggregate_timeframe(symbol, tf, bars_1m) if bars_1m else []
    live = db.fetch_bars(symbol, tf, window_start, now)
    return _merge_bars(derived, live)


def load_execution_frames(
    db: DatabaseManager,
    hist_engine: HistoricalDataEngine,
    symbol: str,
    timeframes: tuple[DerivedTimeframe, ...] = _REQUIRED_TIMEFRAMES,
    lookback_days: int = _FULL_FETCH_CAL_DAYS,
) -> dict[str, pd.DataFrame]:
    """Return ``{timeframe: frame}`` for strategy evaluation (SRD-EXE-006.010).

    A timeframe is omitted when neither aggregated 1m history nor live bars
    exist for it.
    """
    frames: dict[str, pd.DataFrame] = {}
    for tf in timeframes:
        bars = assemble_execution_bars(db, hist_engine, symbol, tf, lookback_days)
        if bars:
            frames[tf] = _bars_to_frame(bars)
    return frames


def load_latest_execution_bar(
    db: DatabaseManager,
    hist_engine: HistoricalDataEngine,
    symbol: str,
    tf: str,
    lookback_days: int = _FULL_FETCH_CAL_DAYS,
) -> OHLCVBar | None:
    """Return the most recent merged bar for ``(symbol, tf)`` or ``None`` (SRD-EXE-006.010).

    ``None`` when *tf* is not a supported derived timeframe or no bars exist.
    """
    for derived_tf in _REQUIRED_TIMEFRAMES:
        if derived_tf == tf:
            bars = assemble_execution_bars(db, hist_engine, symbol, derived_tf, lookback_days)
            return bars[-1] if bars else None
    return None


@dataclass
class CandleLoadResult:
    """Outcome for a single symbol in the load job."""

    symbol: str
    ok: bool
    reason: str = ""


@dataclass
class SymbolReadiness:
    """Per-symbol intraday candle readiness report."""

    symbol: str
    candles_3m: int
    candles_15m: int
    last_1m_bar: datetime | None
    ready: bool  # True iff all counts ≥ min_candles


class IntradayCandleLoader(QThread):
    """Delta-fetches intraday 1 m bars for a stock list and validates candle counts.

    Emits ``load_progress`` after each symbol and ``load_complete`` when all
    symbols finish (or fail). Idempotent: re-running on an up-to-date symbol
    inserts 0 rows.

    Args:
        symbols:             Screened stock list to process.
        ibkr_host:           IBKR TWS / Gateway hostname.
        ibkr_port:           IBKR TWS / Gateway port.
        ibkr_client_id:      Unique client ID for this dedicated connection.
        db:                  Initialised :class:`DatabaseManager`.
        hist_engine:         Used only for ``aggregate_timeframe`` (pure, no I/O).
        min_candles:         Minimum candle count per timeframe (default 390).
        full_fetch_cal_days: Calendar-day window used for a first-time symbol fetch.
        parent:              Optional Qt parent object.
    """

    load_progress = pyqtSignal(str, int, int)   # symbol, done, total
    load_complete = pyqtSignal(list)             # list[CandleLoadResult]

    def __init__(
        self,
        symbols: list[str],
        ibkr_host: str,
        ibkr_port: int,
        ibkr_client_id: int,
        db: DatabaseManager,
        hist_engine: HistoricalDataEngine,
        min_candles: int = _MIN_CANDLES,
        full_fetch_cal_days: int = _FULL_FETCH_CAL_DAYS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._symbols = list(symbols)
        self._ibkr_host = ibkr_host
        self._ibkr_port = ibkr_port
        self._ibkr_client_id = ibkr_client_id
        self._db = db
        self._hist_engine = hist_engine
        self._min_candles = min_candles
        self._full_fetch_cal_days = full_fetch_cal_days

    # ── QThread entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """QThread entry: run the async fetch loop in a fresh event loop."""
        try:
            asyncio.run(self._async_run())
        except Exception as exc:  # noqa: BLE001
            log.exception("[Candles] Unexpected error during candle download")
            results: list[CandleLoadResult] = [
                CandleLoadResult(s, False, repr(exc)) for s in self._symbols
            ]
            self.load_complete.emit(results)

    # ── Async implementation ───────────────────────────────────────────────────

    async def _async_run(self) -> None:
        try:
            from ib_insync import IB
        except ImportError:
            log.warning(
                "[Candles] IBKR library not available — using Yahoo Finance instead"
            )
            await self._run_yfinance_fallback()
            return

        ib = IB()  # type: ignore[no-untyped-call]
        log.info(
            "[Candles] Connecting to IBKR at %s:%d …",
            self._ibkr_host, self._ibkr_port,
        )

        client_id = self._ibkr_client_id
        _connect_exc: Exception | None = None
        for attempt in range(_MAX_CLIENT_ID_RETRIES + 1):
            _saw_326: list[bool] = [False]

            def _on_connect_error(req_id: int, error_code: int, *_: Any) -> None:
                if error_code == 326:
                    _saw_326[0] = True

            ib.errorEvent += _on_connect_error  # type: ignore[operator]
            try:
                await ib.connectAsync(
                    self._ibkr_host,
                    self._ibkr_port,
                    clientId=client_id,
                    timeout=10,
                )
                _connect_exc = None
                break
            except Exception as exc:  # noqa: BLE001
                _connect_exc = exc
                if _saw_326[0] and attempt < _MAX_CLIENT_ID_RETRIES:
                    log.info(
                        "[Candles] Client ID %d already in use — trying ID %d",
                        client_id, client_id + 1,
                    )
                    client_id += 1
                else:
                    break
            finally:
                ib.errorEvent -= _on_connect_error  # type: ignore[operator]

        if _connect_exc is not None:
            log.warning(
                "[Candles] IBKR connection failed (%s) — switching to Yahoo Finance",
                _connect_exc,
            )
            await self._run_yfinance_fallback()
            return

        log.info(
            "[Candles] Connected to IBKR — downloading %d stock(s)", len(self._symbols),
        )
        pacing = PacingQueue()
        results: list[CandleLoadResult] = []
        total = len(self._symbols)

        # Capture IBKR error codes per symbol (symbols are processed sequentially).
        # errorEvent fires asynchronously within the await; the list is checked after
        # each reqHistoricalDataAsync call returns to detect Error 200 before validation.
        _ibkr_errors: list[int] = []

        def _on_ib_error(req_id: int, error_code: int, *_: Any) -> None:
            _ibkr_errors.append(error_code)

        ib.errorEvent += _on_ib_error  # type: ignore[operator]
        try:
            for i, symbol in enumerate(self._symbols):
                del _ibkr_errors[:]
                try:
                    await self._fetch_symbol_async(ib, pacing, symbol)
                    if 200 in _ibkr_errors:
                        log.info(
                            "[Candles] %s is not available on US exchanges — skipped", symbol,
                        )
                        result = CandleLoadResult(
                            symbol=symbol, ok=False, reason="EXCHANGE_UNAVAILABLE"
                        )
                    else:
                        result = self._validate_candle_counts(symbol)
                except Exception as exc:  # noqa: BLE001
                    result = CandleLoadResult(symbol=symbol, ok=False, reason=repr(exc))
                    log.warning("[Candles] Failed to fetch %s: %s", symbol, exc)
                results.append(result)
                self.load_progress.emit(symbol, i + 1, total)
                await asyncio.sleep(_SYMBOL_PAUSE_S)
            ok_n = sum(1 for r in results if r.ok)
            log.info(
                "[Candles] IBKR download complete — %d of %d stock(s) ready", ok_n, total,
            )
            # Emit before disconnect so load_complete always fires exactly once.
            self.load_complete.emit(results)
        finally:
            ib.errorEvent -= _on_ib_error  # type: ignore[operator]
            try:
                ib.disconnect()  # type: ignore[no-untyped-call]
            except Exception:  # noqa: BLE001
                log.warning("[Candles] IBKR disconnect warning (ignored)")

    async def _run_yfinance_fallback(self) -> None:
        """Fetch 1m bars via yfinance when IBKR is unavailable (dev / offline mode).

        yfinance caps 1m data at 7 calendar days (~1950 bars), which is enough
        to validate 3m (≥390 bars) but not 15m (needs ~15 trading days).
        Only 3m is validated in this mode.
        """
        try:
            import yfinance  # type: ignore[import-untyped]  # noqa: F401
        except ImportError:
            log.error(
                "[Candles] Yahoo Finance library not installed — candle download unavailable"
                " (run: pip install yfinance)"
            )
            self.load_complete.emit(
                [CandleLoadResult(s, False, "yfinance_not_installed") for s in self._symbols]
            )
            return

        log.info(
            "[Candles] Downloading %d stock(s) via Yahoo Finance"
            " (7-day 1m data; only 3m timeframe validated — 15m requires more history)",
            len(self._symbols),
        )
        results: list[CandleLoadResult] = []
        total = len(self._symbols)

        for i, symbol in enumerate(self._symbols):
            try:
                await asyncio.to_thread(self._fetch_symbol_yfinance, symbol)
                result = self._validate_candle_counts(symbol, timeframes=("3m",))
            except Exception as exc:  # noqa: BLE001
                result = CandleLoadResult(symbol=symbol, ok=False, reason=repr(exc))
                log.warning("[Candles] Failed to fetch %s: %s", symbol, exc)
            results.append(result)
            self.load_progress.emit(symbol, i + 1, total)

        ok_n = sum(1 for r in results if r.ok)
        log.info(
            "[Candles] Yahoo Finance download complete — %d of %d stock(s) ready (3m validated)",
            ok_n, total,
        )
        self.load_complete.emit(results)

    async def _fetch_symbol_async(
        self, ib: Any, pacing: PacingQueue, symbol: str
    ) -> None:
        """Delta-fetch 1 m bars for *symbol*. Pages when the window > 30 calendar days.

        If existing data doesn't reach back to the full validation window (e.g. the DB
        was seeded by yfinance's 7-day cap), a full backfill is performed so that 15m
        aggregation can meet the minimum candle threshold.
        """
        now = datetime.now(tz=timezone.utc)
        last = self._db.get_last_timestamp(symbol, "1m")
        first = self._db.get_first_timestamp(symbol, "1m")
        window_start = now - timedelta(days=self._full_fetch_cal_days)

        if last is None or (first is not None and first > window_start):
            if last is None:
                log.info("[Candles] %s — no local data, fetching %d days of history", symbol, self._full_fetch_cal_days)
            else:
                shallow_days = (now - first).days
                log.info(
                    "[Candles] %s — local history too short (%d days), backfilling to %d days",
                    symbol, shallow_days, self._full_fetch_cal_days,
                )
            await self._fetch_paged_async(ib, pacing, symbol, now, self._full_fetch_cal_days)
        else:
            gap_days = max(1, (now - last).days + 1)
            log.info("[Candles] %s — updating %d day(s) of 1m bars (last saved: %s)", symbol, gap_days, last.date())
            if gap_days <= _IBKR_MAX_CAL_DAYS_PER_PAGE:
                bars = await self._request_1m_bars(ib, pacing, symbol, now, gap_days)
                new_bars = [b for b in bars if b.datetime > last]
                inserted = self._db.insert_bars(symbol, "1m", new_bars)
                log.debug("[Candles] %s — saved %d bar(s) to local database", symbol, inserted)
            else:
                await self._fetch_paged_async(ib, pacing, symbol, now, gap_days)

    async def _fetch_paged_async(
        self,
        ib: Any,
        pacing: PacingQueue,
        symbol: str,
        end: datetime,
        total_cal_days: int,
    ) -> None:
        """Fetch 1 m bars in ≤ 30-calendar-day pages (IBKR limit), newest-first.

        Duplicate bars are handled by ``insert_bars`` (INSERT OR IGNORE / ON CONFLICT
        DO NOTHING), so overlapping pages on incremental fetches are safe and idempotent.
        """
        pages = (total_cal_days + _IBKR_MAX_CAL_DAYS_PER_PAGE - 1) // _IBKR_MAX_CAL_DAYS_PER_PAGE
        for page in range(pages):
            page_end = end - timedelta(days=page * _IBKR_MAX_CAL_DAYS_PER_PAGE)
            remaining = total_cal_days - page * _IBKR_MAX_CAL_DAYS_PER_PAGE
            days = min(remaining, _IBKR_MAX_CAL_DAYS_PER_PAGE)
            bars = await self._request_1m_bars(ib, pacing, symbol, page_end, days)
            inserted = self._db.insert_bars(symbol, "1m", bars)
            log.debug(
                "Page fetch %s page %d/%d: %d bars inserted", symbol, page + 1, pages, inserted
            )

    async def _request_1m_bars(
        self,
        ib: Any,
        pacing: PacingQueue,
        symbol: str,
        end_dt: datetime,
        duration_days: int,
    ) -> list[OHLCVBar]:
        """Issue one IBKR 1 m-bar request through the pacing queue."""
        from ib_insync import Stock

        await pacing.acquire()
        ibkr_symbol = symbol.replace(".", " ")  # BRK.B → BRK B
        contract = Stock(ibkr_symbol, "SMART", "USD")
        raw: list[Any] = await ib.reqHistoricalDataAsync(
            contract,
            endDateTime=end_dt,
            durationStr=f"{duration_days} D",
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=True,
        )
        return [_raw_bar_to_ohlcv(symbol, b) for b in raw]

    # ── Synchronous helpers ────────────────────────────────────────────────────

    def _fetch_symbol_yfinance(self, symbol: str) -> None:
        """Delta-fetch 1 m bars from yfinance (max 7 calendar days lookback).

        Converts America/New_York timestamps to UTC before inserting.
        Duplicate rows are silently ignored by ``DatabaseManager.insert_bars``.
        """
        import yfinance as yf

        last = self._db.get_last_timestamp(symbol, "1m")
        ticker = yf.Ticker(symbol)

        if last is None:
            log.info("[Candles] %s — fresh download (7 days of 1m bars)", symbol)
            df = ticker.history(period="7d", interval="1m")
        else:
            now = datetime.now(tz=timezone.utc)
            gap_days = max(1, min((now - last).days + 1, 7))
            log.info(
                "[Candles] %s — updating %d day(s) of 1m bars (last saved: %s)",
                symbol, gap_days, last.date(),
            )
            df = ticker.history(period=f"{gap_days}d", interval="1m")

        if df.empty:
            log.warning("[Candles] %s — no data returned by Yahoo Finance", symbol)
            return

        bars: list[OHLCVBar] = []
        for ts, row in df.iterrows():  # iterrows yields untyped index/Series
            dt = _ensure_utc(ts.to_pydatetime())
            if last is not None and dt <= last:
                continue
            bars.append(OHLCVBar(
                symbol=symbol,
                datetime=dt,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
                timeframe="1m",
            ))

        inserted = self._db.insert_bars(symbol, "1m", bars)
        log.info("[Candles] %s — saved %d bar(s) to local database", symbol, inserted)

    def _validate_candle_counts(
        self,
        symbol: str,
        timeframes: tuple[DerivedTimeframe, ...] = _REQUIRED_TIMEFRAMES,
    ) -> CandleLoadResult:
        """Aggregate timeframes (default: 3m, 15m) and verify each has ≥ min_candles bars.

        Fetches stored 1 m bars for the symbol and passes them to
        ``HistoricalDataEngine.aggregate_timeframe`` (pure, no I/O).
        """
        now = datetime.now(tz=timezone.utc)
        window_start = now - timedelta(days=self._full_fetch_cal_days)
        bars_1m = self._db.fetch_bars(symbol, "1m", window_start, now)
        counts = _build_tf_counts(symbol, bars_1m, timeframes, self._hist_engine)

        for tf in timeframes:
            n = counts[tf]
            if n < self._min_candles:
                log.warning(
                    "[Candles] %s — not enough history for strategy indicators"
                    " (%s bars in %s)", symbol, n, tf,
                )
                return CandleLoadResult(symbol=symbol, ok=False, reason=f"insufficient_candles:{tf}:{n}")

        counts_str = ", ".join(f"{v} bars {tf}" for tf, v in counts.items())
        log.info("[Candles] %s — ready (%s)", symbol, counts_str)
        return CandleLoadResult(symbol=symbol, ok=True)

    def get_readiness_report(
        self,
        symbols: list[str],
        min_candles: int = _MIN_CANDLES,
    ) -> dict[str, SymbolReadiness]:
        """Return a per-symbol readiness dict without triggering any fetches.

        Delegates to :func:`check_candle_readiness` (module-level, thread-safe).
        """
        return check_candle_readiness(
            symbols, self._db, self._hist_engine, min_candles, self._full_fetch_cal_days
        )


# ── Module-level helpers ───────────────────────────────────────────────────────


def check_candle_readiness(
    symbols: list[str],
    db: DatabaseManager,
    hist_engine: HistoricalDataEngine,
    min_candles: int = _MIN_CANDLES,
    full_fetch_cal_days: int = _FULL_FETCH_CAL_DAYS,
) -> dict[str, SymbolReadiness]:
    """Pure DB-read readiness check — safe to call from any thread.

    Does not construct any Qt objects. Intended for use by background workers
    that need readiness data without instantiating :class:`IntradayCandleLoader`.

    Args:
        symbols:              Symbols to check (max 500).
        db:                   Initialised :class:`DatabaseManager`.
        hist_engine:          Used for ``aggregate_timeframe`` (pure, no I/O).
        min_candles:          Minimum candle count per timeframe (default 390).
        full_fetch_cal_days:  Look-back window in calendar days (default 30).

    Returns:
        Mapping from symbol to :class:`SymbolReadiness`.

    Raises:
        ValueError: If ``len(symbols) > 500``.
    """
    if len(symbols) > 500:
        raise ValueError(f"check_candle_readiness: max 500 symbols, got {len(symbols)}")
    now = datetime.now(tz=timezone.utc)
    window_start = now - timedelta(days=full_fetch_cal_days)
    report: dict[str, SymbolReadiness] = {}
    for symbol in symbols:
        last = db.get_last_timestamp(symbol, "1m")
        bars_1m = db.fetch_bars(symbol, "1m", window_start, now)
        counts = _build_tf_counts(symbol, bars_1m, _REQUIRED_TIMEFRAMES, hist_engine)
        ready = all(v >= min_candles for v in counts.values())
        report[symbol] = SymbolReadiness(
            symbol=symbol,
            candles_3m=counts["3m"],
            candles_15m=counts["15m"],
            last_1m_bar=last,
            ready=ready,
        )
    return report


def _raw_bar_to_ohlcv(symbol: str, b: Any) -> OHLCVBar:
    """Convert an ib_insync BarData object to :class:`OHLCVBar`."""
    raw_dt: Any = b.date
    if hasattr(raw_dt, "hour"):
        dt: datetime = _ensure_utc(raw_dt)
    else:
        # date object — should not occur for 1m bars; map to midnight UTC.
        log.warning(
            "[Candles] %s — unexpected date format in bar data, treating as midnight UTC",
            symbol,
        )
        dt = datetime.combine(raw_dt, datetime.min.time(), tzinfo=timezone.utc)

    return OHLCVBar(
        symbol=symbol,
        datetime=dt,
        open=float(b.open),
        high=float(b.high),
        low=float(b.low),
        close=float(b.close),
        volume=int(b.volume),
        timeframe="1m",
    )
