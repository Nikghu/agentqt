"""Module: MD-INF-003.001.M01 — data/engine.py
Parent SRD: SRD-INF-003.001 – SRD-INF-003.005, SRD-INF-007.004

HistoricalDataEngine orchestrates data bootstrap and incremental updates
using a DataProvider (IBKR or Dummy) injected at construction time.

Timeframe aggregation (3m/5m/15m/1h/4h) is always computed in-process
from stored 1m bars — the IBKR API is never called for derived timeframes.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from us_swing.config.settings import DataConfig
from us_swing.data.models import OHLCVBar, UniverseRecord
from us_swing.data.providers.protocol import DataProvider
from us_swing.db.manager import DatabaseManager
from us_swing.exceptions import CandleConsistencyError

log = logging.getLogger(__name__)

# IBKR bar-size strings for each canonical timeframe key.
_TF_TO_BAR_SIZE: dict[str, str] = {
    "1m": "1 min",
    "1d": "1 day",
    "1w": "1 week",
}

# [minutes] window for each derived (aggregated) timeframe.
_TF_MINUTES: dict[str, int] = {
    "3m":  3,
    "5m":  5,
    "15m": 15,
    "30m": 30,
    "1h":  60,
    "4h":  240,
}

DerivedTimeframe = Literal["3m", "5m", "15m", "30m", "1h", "4h"]


@dataclass
class BootstrapResult:
    symbol:      str
    bars_1m:     int
    bars_1d:     int
    bars_1w:     int


@dataclass
class UpdateResult:
    symbol:    str
    timeframe: str
    inserted:  int


class HistoricalDataEngine:
    """Orchestrates OHLCV data download, storage, and in-process aggregation.

    Args:
        provider: Any :class:`DataProvider` (IBKR or Dummy).
        db:       Initialised :class:`DatabaseManager`.
        cfg:      :class:`DataConfig` (retention, concurrency).
    """

    def __init__(
        self,
        provider: DataProvider,
        db: DatabaseManager,
        cfg: DataConfig,
    ) -> None:
        self._provider = provider
        self._db       = db
        self._cfg      = cfg

    # ── Bootstrap ─────────────────────────────────────────────────────────────

    async def bootstrap_symbol(self, symbol: str) -> BootstrapResult:
        """Fetch one year of 1m / 1d / 1w bars from the provider and store them.

        Safe to call repeatedly — duplicates are silently ignored by the DB.
        """
        now = datetime.now(tz=timezone.utc)

        async def _fetch_and_store(tf: str) -> int:
            bar_size = _TF_TO_BAR_SIZE[tf]
            bars = await self._provider.req_historical_data(
                symbol, end_datetime=now, duration="1 Y", bar_size=bar_size
            )
            return self._db.insert_bars(symbol, tf, bars)

        bars_1m = await _fetch_and_store("1m")
        bars_1d = await _fetch_and_store("1d")
        bars_1w = await _fetch_and_store("1w")

        log.info(
            "Bootstrap %s: 1m=%d 1d=%d 1w=%d bars stored",
            symbol, bars_1m, bars_1d, bars_1w,
        )
        return BootstrapResult(symbol=symbol, bars_1m=bars_1m, bars_1d=bars_1d, bars_1w=bars_1w)

    async def bootstrap_all(
        self,
        universe: list[UniverseRecord],
        max_concurrent: int | None = None,
    ) -> None:
        """Bootstrap all symbols with bounded concurrency.

        Symbol failures are logged and do not halt other symbols.
        """
        concurrency = max_concurrent or self._cfg.max_concurrent_bootstrap
        sem = asyncio.Semaphore(concurrency)

        async def _guarded(rec: UniverseRecord) -> None:
            async with sem:
                try:
                    await self.bootstrap_symbol(rec.symbol)
                except Exception:
                    log.exception("bootstrap_all: failed for %s", rec.symbol)

        await asyncio.gather(*(_guarded(r) for r in universe))

    # ── Incremental update ────────────────────────────────────────────────────

    async def update_missing_data(self, symbol: str) -> list[UpdateResult]:
        """Fetch only bars newer than the last stored timestamp for each TF.

        Falls back to ``bootstrap_symbol()`` when no data exists for a TF.
        """
        now = datetime.now(tz=timezone.utc)
        results: list[UpdateResult] = []

        for tf, bar_size in _TF_TO_BAR_SIZE.items():
            last = self._db.get_last_timestamp(symbol, tf)
            if last is None:
                log.info("update_missing_data: no data for %s %s — running bootstrap", symbol, tf)
                await self.bootstrap_symbol(symbol)
                return [UpdateResult(symbol=symbol, timeframe=tf, inserted=-1)]

            # Build IBKR duration string from the gap.
            gap_days = (now - last).days + 1
            duration = f"{max(1, gap_days)} D"
            bars = await self._provider.req_historical_data(
                symbol, end_datetime=now, duration=duration, bar_size=bar_size
            )
            # Keep only bars strictly after the last stored timestamp.
            new_bars = [b for b in bars if b.datetime > last]
            inserted = self._db.insert_bars(symbol, tf, new_bars)
            log.debug("update_missing_data: %s %s +%d bars", symbol, tf, inserted)
            results.append(UpdateResult(symbol=symbol, timeframe=tf, inserted=inserted))

        return results

    # ── Timeframe aggregation ─────────────────────────────────────────────────

    def aggregate_timeframe(
        self,
        symbol: str,
        target_tf: DerivedTimeframe,
        bars_1m: list[OHLCVBar],
    ) -> list[OHLCVBar]:
        """Synthesise a higher-timeframe bar series from 1m bars.

        Uses open=first, high=max, low=min, close=last, volume=sum.
        Incomplete trailing groups (bar count < target minutes) are excluded.

        Args:
            symbol:    Ticker symbol (attached to each output bar).
            target_tf: One of ``'3m'``, ``'5m'``, ``'15m'``, ``'30m'``, ``'1h'``, ``'4h'``.
            bars_1m:   Source 1-minute bars, sorted ascending by datetime.

        Returns:
            List of aggregated :class:`OHLCVBar` objects.
        """
        minutes = _TF_MINUTES[target_tf]
        groups: dict[int, list[OHLCVBar]] = {}

        for bar in bars_1m:
            # Bucket key = floor(epoch_minutes / target_minutes)
            epoch_min = int(bar.datetime.timestamp()) // 60
            bucket    = epoch_min // minutes
            groups.setdefault(bucket, []).append(bar)

        result: list[OHLCVBar] = []
        for bucket in sorted(groups):
            group = groups[bucket]
            if len(group) < minutes:
                continue   # incomplete — skip trailing partial bar
            result.append(
                OHLCVBar(
                    symbol    = symbol,
                    datetime  = group[0].datetime,
                    open      = group[0].open,
                    high      = max(b.high   for b in group),
                    low       = min(b.low    for b in group),
                    close     = group[-1].close,
                    volume    = sum(b.volume for b in group),
                    timeframe = target_tf,
                )
            )

        return result

    # ── Candle consistency check ──────────────────────────────────────────────

    def assert_candle_consistency(
        self,
        live_bar: OHLCVBar,
        historical_bar: OHLCVBar,
    ) -> None:
        """Assert that a live-built bar equals its stored historical counterpart.

        Raises:
            CandleConsistencyError: If any OHLCV field differs.
        """
        for field in ("open", "high", "low", "close", "volume"):
            lv = getattr(live_bar, field)
            hv = getattr(historical_bar, field)
            if lv != hv:
                raise CandleConsistencyError(
                    f"Candle mismatch for {live_bar.symbol} @ {live_bar.datetime}: "
                    f"{field} live={lv} != historical={hv}"
                )


def create_provider(cfg: DataConfig) -> DataProvider:
    """Factory: return the correct DataProvider based on config.

    Args:
        cfg: :class:`DataConfig` (``provider`` key is ``'ibkr'`` or ``'dummy'``).

    Returns:
        A :class:`DataProvider` instance ready to use.
    """
    from us_swing.data.providers.dummy_provider import DummyProvider

    if cfg.provider == "dummy":
        return DummyProvider()

    if cfg.provider == "ibkr":
        from us_swing.broker.client import IBKRClient
        from us_swing.data.providers.ibkr_provider import IBKRProvider
        # IBKRClient must be connected by the caller before use.
        return IBKRProvider(IBKRClient())

    raise ValueError(f"Unknown DATA_PROVIDER '{cfg.provider}'. Choose 'ibkr' or 'dummy'.")
