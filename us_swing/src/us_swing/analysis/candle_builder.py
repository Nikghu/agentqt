"""
Module: MD-ANA-001.001.M01 — analysis/candle_builder.py
Parent SRD: SRD-ANA-001.002–005

CandleBuilder aggregates RealtimeBars into multi-timeframe OHLCV candles using
time-based windows aligned to Unix-timestamp boundaries.  Input may be individual
trade ticks (open == high == low == close == price) or pre-aggregated bars.

Fires an on_candle_closed callback on each completed window.

Supported timeframes: 1m, 3m, 5m, 15m, 1h.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from us_swing.data.models import OHLCVBar, RealtimeBar

log = logging.getLogger(__name__)

_TF_SECONDS: dict[str, int] = {
    "1m":  60,
    "3m":  180,
    "5m":  300,
    "15m": 900,
    "1h":  3600,
}


def _floor_to_tf(dt: datetime, tf_secs: int) -> datetime:
    """Floor *dt* to the nearest *tf_secs* boundary (Unix-timestamp aligned)."""
    ts = int(dt.timestamp())
    return datetime.fromtimestamp((ts // tf_secs) * tf_secs, tz=timezone.utc)


class CandleBuilder:
    """Aggregates RealtimeBars into multi-timeframe OHLCV candles.

    Uses time-based windows: a candle closes when the next incoming bar's
    timestamp crosses the window boundary, regardless of how many bars
    accumulated inside it.  Windows with no bars are silently skipped — no
    synthetic flat candles are emitted.

    Backwards-compatible: accepts both tick-level bars (open==high==low==close)
    and pre-aggregated 5-second bars.

    Args:
        timeframes:       Timeframes to maintain (e.g. ["3m", "15m"]).
        on_candle_closed: Optional callback(symbol, tf, bar) invoked on each
                          completed candle.  Can also be set later via
                          :meth:`register_callback`.
    """

    def __init__(
        self,
        timeframes: list[str],
        on_candle_closed: Callable[[str, str, OHLCVBar], None] | None = None,
    ) -> None:
        for tf in timeframes:
            if tf not in _TF_SECONDS:
                raise ValueError(f"Unsupported timeframe: {tf!r}")
        self._tfs = timeframes
        self._callback: Callable[[str, str, OHLCVBar], None] = (
            on_candle_closed if on_candle_closed is not None else self._noop
        )
        # _window_start[symbol][tf] = UTC start of the current open window (None = not started)
        self._window_start: dict[str, dict[str, datetime | None]] = {}
        # _buffers[symbol][tf]      = bars accumulated in the current window
        self._buffers:      dict[str, dict[str, list[RealtimeBar]]] = {}
        # _completed[symbol][tf]    = list of finished OHLCVBar candles
        self._completed:    dict[str, dict[str, list[OHLCVBar]]] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def register_callback(
        self, on_candle_closed: Callable[[str, str, OHLCVBar], None]
    ) -> None:
        """Replace the candle-closed callback (e.g. wired in by LiveEngine)."""
        self._callback = on_candle_closed

    def add_bar(self, bar: RealtimeBar) -> None:
        """Process one bar and close any completed time windows."""
        symbol = bar.symbol
        self._ensure_symbol(symbol)
        self._process_bar(bar)

    def get_buffer(self, symbol: str, tf: str) -> list[OHLCVBar]:
        """Return a copy of the completed candle list for (symbol, tf)."""
        return list(self._completed.get(symbol, {}).get(tf, []))

    def reset(self, symbol: str) -> None:
        """Clear all in-progress and completed state for *symbol*."""
        self._window_start.pop(symbol, None)
        self._buffers.pop(symbol, None)
        self._completed.pop(symbol, None)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _ensure_symbol(self, symbol: str) -> None:
        if symbol not in self._buffers:
            self._window_start[symbol] = {tf: None for tf in self._tfs}
            self._buffers[symbol]      = {tf: [] for tf in self._tfs}
            self._completed[symbol]    = {tf: [] for tf in self._tfs}

    def _process_bar(self, bar: RealtimeBar) -> None:
        symbol = bar.symbol
        for tf in self._tfs:
            tf_secs = _TF_SECONDS[tf]
            win = self._window_start[symbol][tf]

            if win is None:
                self._window_start[symbol][tf] = _floor_to_tf(bar.datetime, tf_secs)
                self._buffers[symbol][tf].append(bar)
                continue

            # Advance through any completed windows (handles multi-window gaps too).
            while bar.datetime >= win + timedelta(seconds=tf_secs):
                buf = self._buffers[symbol][tf]
                if buf:
                    candle = self._aggregate(symbol, tf, buf, win)
                    self._completed[symbol][tf].append(candle)
                    log.debug("Candle closed: %s %s @ %s", symbol, tf, candle.datetime)
                    self._callback(symbol, tf, candle)
                self._buffers[symbol][tf] = []
                win = win + timedelta(seconds=tf_secs)
                self._window_start[symbol][tf] = win

            self._buffers[symbol][tf].append(bar)

    @staticmethod
    def _aggregate(
        symbol: str, tf: str, bars: list[RealtimeBar], window_start: datetime
    ) -> OHLCVBar:
        return OHLCVBar(
            symbol=symbol,
            datetime=window_start,
            open=bars[0].open,
            high=max(b.high for b in bars),
            low=min(b.low for b in bars),
            close=bars[-1].close,
            volume=sum(b.volume for b in bars),
            timeframe=tf,
        )

    @staticmethod
    def _noop(symbol: str, tf: str, bar: OHLCVBar) -> None:
        pass
