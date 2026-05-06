"""
Module: MD-EXE-006.001.M01 — execution/intraday_candle_loader.py
Parent SRD: SRD-EXE-006.001 — SRD-EXE-006.006
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from us_swing.broker.pacing import PacingQueue
from us_swing.data.engine import DerivedTimeframe, HistoricalDataEngine
from us_swing.data.models import OHLCVBar
from us_swing.db.manager import DatabaseManager

log = logging.getLogger(__name__)

_MIN_CANDLES: int = 390
_IBKR_MAX_CAL_DAYS_PER_PAGE: int = 30
_FULL_FETCH_CAL_DAYS: int = 91  # 65 trading days ≈ 91 calendar days (65 × 7/5)
_REQUIRED_TIMEFRAMES: tuple[DerivedTimeframe, ...] = ("3m", "5m", "1h")
_SYMBOL_PAUSE_S: float = 0.3


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
    candles_5m: int
    candles_1h: int
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
            log.exception("IntradayCandleLoader: unexpected error in run()")
            results: list[CandleLoadResult] = [
                CandleLoadResult(s, False, repr(exc)) for s in self._symbols
            ]
            self.load_complete.emit(results)

    # ── Async implementation ───────────────────────────────────────────────────

    async def _async_run(self) -> None:
        try:
            from ib_insync import IB
        except ImportError:
            log.error("IntradayCandleLoader: ib_insync not installed")
            self.load_complete.emit(
                [CandleLoadResult(s, False, "ib_insync_not_installed") for s in self._symbols]
            )
            return

        ib = IB()  # type: ignore[no-untyped-call]
        try:
            await ib.connectAsync(
                self._ibkr_host,
                self._ibkr_port,
                clientId=self._ibkr_client_id,
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("IntradayCandleLoader: IBKR connect failed: %s", exc)
            self.load_complete.emit(
                [CandleLoadResult(s, False, f"ibkr_connect_error:{exc}") for s in self._symbols]
            )
            return

        pacing = PacingQueue()
        results: list[CandleLoadResult] = []
        total = len(self._symbols)

        try:
            for i, symbol in enumerate(self._symbols):
                try:
                    await self._fetch_symbol_async(ib, pacing, symbol)
                    result = self._validate_candle_counts(symbol)
                except Exception as exc:  # noqa: BLE001
                    result = CandleLoadResult(symbol=symbol, ok=False, reason=repr(exc))
                    log.warning("IntradayCandleLoader: error for %s: %s", symbol, exc)
                results.append(result)
                self.load_progress.emit(symbol, i + 1, total)
                await asyncio.sleep(_SYMBOL_PAUSE_S)
            # Emit before disconnect so load_complete always fires exactly once.
            self.load_complete.emit(results)
        finally:
            try:
                ib.disconnect()  # type: ignore[no-untyped-call]
            except Exception:  # noqa: BLE001
                log.warning("IntradayCandleLoader: error during IBKR disconnect (ignored)")

    async def _fetch_symbol_async(
        self, ib: Any, pacing: PacingQueue, symbol: str
    ) -> None:
        """Delta-fetch 1 m bars for *symbol*. Pages when the window > 30 calendar days."""
        now = datetime.now(tz=timezone.utc)
        last = self._db.get_last_timestamp(symbol, "1m")

        if last is None:
            await self._fetch_paged_async(ib, pacing, symbol, now, self._full_fetch_cal_days)
        else:
            gap_days = max(1, (now - last).days + 1)
            if gap_days <= _IBKR_MAX_CAL_DAYS_PER_PAGE:
                bars = await self._request_1m_bars(ib, pacing, symbol, now, gap_days)
                new_bars = [b for b in bars if b.datetime > last]
                inserted = self._db.insert_bars(symbol, "1m", new_bars)
                log.debug("Delta fetch %s: +%d bars", symbol, inserted)
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

    def _validate_candle_counts(self, symbol: str) -> CandleLoadResult:
        """Aggregate 3 m/5 m/1 h and verify each has ≥ min_candles bars.

        Fetches stored 1 m bars for the symbol and passes them to
        ``HistoricalDataEngine.aggregate_timeframe`` (pure, no I/O).
        """
        now = datetime.now(tz=timezone.utc)
        window_start = now - timedelta(days=self._full_fetch_cal_days)
        bars_1m = self._db.fetch_bars(symbol, "1m", window_start, now)

        for tf in _REQUIRED_TIMEFRAMES:
            agg = self._hist_engine.aggregate_timeframe(symbol, tf, bars_1m)
            count = len(agg)
            if count < self._min_candles:
                reason = f"insufficient_candles:{tf}:{count}"
                log.warning("Candle validation failed for %s: %s", symbol, reason)
                return CandleLoadResult(symbol=symbol, ok=False, reason=reason)

        return CandleLoadResult(symbol=symbol, ok=True)

    def get_readiness_report(
        self,
        symbols: list[str],
        min_candles: int = _MIN_CANDLES,
    ) -> dict[str, SymbolReadiness]:
        """Return a per-symbol readiness dict without triggering any fetches.

        Safe to call from the main thread at any time; reads the DB only.
        For large lists consider calling this off the main thread — each symbol
        requires 3 aggregations over up to 91 days of 1 m bars.

        Args:
            symbols:     Symbols to check (max 500).
            min_candles: Minimum candle count threshold (default 390).

        Returns:
            Mapping from symbol to :class:`SymbolReadiness`.

        Raises:
            ValueError: If ``len(symbols) > 500``.
        """
        if len(symbols) > 500:
            raise ValueError(
                f"get_readiness_report: max 500 symbols, got {len(symbols)}"
            )
        now = datetime.now(tz=timezone.utc)
        window_start = now - timedelta(days=self._full_fetch_cal_days)
        report: dict[str, SymbolReadiness] = {}

        for symbol in symbols:
            last = self._db.get_last_timestamp(symbol, "1m")
            bars_1m = self._db.fetch_bars(symbol, "1m", window_start, now)

            counts: dict[str, int] = {}
            for tf in _REQUIRED_TIMEFRAMES:
                agg = self._hist_engine.aggregate_timeframe(symbol, tf, bars_1m)
                counts[tf] = len(agg)

            ready = all(v >= min_candles for v in counts.values())
            report[symbol] = SymbolReadiness(
                symbol=symbol,
                candles_3m=counts["3m"],
                candles_5m=counts["5m"],
                candles_1h=counts["1h"],
                last_1m_bar=last,
                ready=ready,
            )

        return report


# ── Module-level helpers ───────────────────────────────────────────────────────

def _raw_bar_to_ohlcv(symbol: str, b: Any) -> OHLCVBar:
    """Convert an ib_insync BarData object to :class:`OHLCVBar`."""
    raw_dt: Any = b.date
    if hasattr(raw_dt, "hour"):
        # datetime — normalise to UTC regardless of source timezone.
        dt: datetime = (
            raw_dt.astimezone(timezone.utc)
            if raw_dt.tzinfo is not None
            else raw_dt.replace(tzinfo=timezone.utc)
        )
    else:
        # date object — should not occur for 1m bars; map to midnight UTC.
        log.warning(
            "_raw_bar_to_ohlcv: %s returned a date (not datetime) — mapping to midnight UTC", symbol
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
