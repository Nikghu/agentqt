"""Module: MD-INF-007.001.M01 — data/providers/ibkr_provider.py
Parent SRD: SRD-INF-007.001, SRD-INF-007.002

IBKRProvider delegates every DataProvider call to IBKRClient.
Pacing is handled internally by IBKRClient; this class simply adapts the
interface — it adds no logic of its own.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from us_swing.data.models import OHLCVBar, RealtimeBar

if TYPE_CHECKING:
    # Imported for typing only — a runtime import here forms a circular import
    # (broker.client → data.models → data/__init__ → providers → broker.client)
    # that breaks importing the broker package first.
    from us_swing.broker.client import IBKRClient

_log = logging.getLogger(__name__)


class IBKRProvider:
    """Production DataProvider backed by a live IBKR connection.

    Args:
        client: A connected :class:`IBKRClient` instance.
    """

    def __init__(self, client: IBKRClient) -> None:
        self._client = client

    async def req_historical_data(
        self,
        symbol: str,
        end_datetime: datetime,
        duration: str,
        bar_size: str,
    ) -> list[OHLCVBar]:
        _log.debug("historical data request: %s duration=%s bar_size=%s", symbol, duration, bar_size)
        return await self._client.req_historical_data(
            symbol=symbol,
            end_datetime=end_datetime,
            duration=duration,
            bar_size=bar_size,
        )

    def subscribe_realtime_bars(self, symbol: str, bar_size: int = 5) -> None:
        self._client.subscribe_realtime_bars(symbol, bar_size)

    def unsubscribe_realtime_bars(self, symbol: str) -> None:
        self._client.unsubscribe_realtime_bars(symbol)

    def on_realtime_bar(self, callback: Callable[[RealtimeBar], None]) -> None:
        self._client.on_realtime_bar(callback)
