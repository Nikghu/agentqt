"""Module: MD-INF-001.001.M01 — broker/client.py
Parent SRD: SRD-INF-001.001 – SRD-INF-001.005

IBKRClient wraps ``ib_insync.IB`` to provide a clean async interface for
connection management, historical/realtime data, and order operations.

``ib_insync`` is an optional dependency (not installed in dev/paper mode).
The module imports it lazily so the rest of the codebase can import this
module without crashing if the package is absent.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from us_swing.broker.pacing import PacingQueue
from us_swing.data.models import (
    AccountState,
    ConnectionStatus,
    IBKRPosition,
    OHLCVBar,
    RealtimeBar,
)
from us_swing.exceptions import BrokerConnectionError

if TYPE_CHECKING:
    pass   # ib_insync types for static-analysis only (not runtime)

log = logging.getLogger(__name__)

_BACKOFF_BASE = 2.0
_BACKOFF_CAP  = 60.0


def _backoff(attempt: int) -> float:
    """Exponential backoff capped at 60 s."""
    return min(_BACKOFF_BASE * (2 ** (attempt - 1)), _BACKOFF_CAP)


class IBKRClient:
    """Async wrapper around ``ib_insync.IB`` with reconnect and pacing.

    All public coroutines must be called from within a running asyncio
    event loop (the ib_insync loop, or any loop when mocked in tests).
    """

    def __init__(self, max_reconnect_attempts: int = 10) -> None:
        self._ib: Any = None          # ib_insync.IB instance
        self._connected = False
        self._max_reconnect = max_reconnect_attempts
        self._pacing = PacingQueue()
        self._status_callbacks: list[Callable[[ConnectionStatus], None]] = []
        self._realtime_callbacks: list[Callable[[RealtimeBar], None]] = []

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect(
        self,
        host: str,
        port: int,
        client_id: int,
        timeout: float = 5.0,
    ) -> None:
        """Connect to IBKR and validate with an account-summary probe.

        Raises:
            BrokerConnectionError: If the connection or validation fails.
        """
        try:
            from ib_insync import IB  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover
            raise BrokerConnectionError(
                "ib_insync is not installed. "
                "Run: pip install ib_insync  (or switch DATA_PROVIDER=dummy)"
            ) from exc

        self._ib = IB()
        self._ib.disconnectedEvent += self._on_disconnect

        try:
            await asyncio.wait_for(
                self._ib.connectAsync(host, port, clientId=client_id),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise BrokerConnectionError(
                f"Connection to IBKR at {host}:{port} timed out after {timeout}s."
            )
        except Exception as exc:
            raise BrokerConnectionError(f"IBKR connect error: {exc}") from exc

        # Validate (SRD-INF-001.002)
        try:
            await asyncio.wait_for(self._ib.reqAccountSummaryAsync(), timeout=timeout)
        except Exception as exc:
            await self.disconnect()
            raise BrokerConnectionError(f"IBKR account validation failed: {exc}") from exc

        self._connected = True
        log.info("IBKRClient connected to %s:%d client_id=%d", host, port, client_id)
        self._emit_status(ConnectionStatus.CONNECTED)

    async def disconnect(self) -> None:
        if self._ib:
            self._ib.disconnect()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._ib is not None and self._ib.isConnected()

    @property
    def ib(self) -> Any:
        """The underlying ``ib_insync.IB`` instance (None until connected).

        Exposed so the broker-execution layer (``broker/ibkr.py``) can place
        orders and subscribe to order-status events without duplicating the
        connection wrapper.
        """
        return self._ib

    # ── Status observable ─────────────────────────────────────────────────────

    def on_status_change(self, callback: Callable[[ConnectionStatus], None]) -> None:
        """Register a callback invoked on every connection state change."""
        self._status_callbacks.append(callback)

    # ── Historical data ───────────────────────────────────────────────────────

    async def req_historical_data(
        self,
        symbol: str,
        end_datetime: datetime,
        duration: str,
        bar_size: str,
    ) -> list[OHLCVBar]:
        """Fetch historical bars through the pacing queue.

        Args:
            symbol:       Ticker symbol (e.g. ``"AAPL"``).
            end_datetime: Inclusive end of the requested range.
            duration:     IBKR duration string (e.g. ``"1 Y"``, ``"5 D"``).
            bar_size:     IBKR bar-size string (e.g. ``"1 min"``, ``"1 day"``).

        Returns:
            List of :class:`OHLCVBar` objects ordered by datetime.
        """
        await self._pacing.acquire()

        from ib_insync import Stock  # type: ignore[import]

        contract = Stock(symbol, "SMART", "USD")
        raw_bars = await self._ib.reqHistoricalDataAsync(
            contract,
            endDateTime=end_datetime,
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
        )
        tf = self._bar_size_to_tf(bar_size)
        return [
            OHLCVBar(
                symbol=symbol,
                datetime=datetime.combine(b.date, datetime.min.time())
                if hasattr(b.date, "year") and not hasattr(b.date, "hour")
                else b.date,
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=int(b.volume),
                timeframe=tf,
            )
            for b in raw_bars
        ]

    # ── Realtime bars ─────────────────────────────────────────────────────────

    def subscribe_realtime_bars(self, symbol: str, bar_size: int = 5) -> None:
        from ib_insync import Stock  # type: ignore[import]
        contract = Stock(symbol, "SMART", "USD")
        bars = self._ib.reqRealTimeBars(contract, barSize=bar_size, whatToShow="TRADES", useRTH=False)
        bars.updateEvent += lambda bars, has_new: self._on_realtime_bar(symbol, bars[-1])

    def unsubscribe_realtime_bars(self, symbol: str) -> None:
        # ib_insync tracks by contract; simplified: cancel all RDB subscriptions
        self._ib.cancelRealTimeBars(self._ib.reqRealTimeBars)

    def on_realtime_bar(self, callback: Callable[[RealtimeBar], None]) -> None:
        self._realtime_callbacks.append(callback)

    # ── Orders ────────────────────────────────────────────────────────────────

    async def place_order(self, contract: Any, order: Any) -> int:
        trade = self._ib.placeOrder(contract, order)
        await asyncio.sleep(0)   # yield to let TWS process
        return trade.order.orderId

    async def cancel_order(self, order_id: int) -> None:
        for trade in self._ib.trades():
            if trade.order.orderId == order_id:
                self._ib.cancelOrder(trade.order)
                return

    async def cancel_all_orders(self) -> None:
        for trade in self._ib.trades():
            self._ib.cancelOrder(trade.order)
        log.warning("All pending orders cancelled.")

    async def close_all_positions(self) -> None:
        from ib_insync import MarketOrder, Stock  # type: ignore[import]
        for pos in self._ib.positions():
            qty = int(pos.position)
            if qty == 0:
                continue
            side = "SELL" if qty > 0 else "BUY"
            contract = Stock(pos.contract.symbol, "SMART", "USD")
            order = MarketOrder(side, abs(qty))
            self._ib.placeOrder(contract, order)
        log.warning("Emergency close-all positions submitted.")

    # ── Account ───────────────────────────────────────────────────────────────

    async def get_account_summary(self) -> AccountState:
        summary = await self._ib.reqAccountSummaryAsync()
        vals = {item.tag: item.value for item in summary}
        equity           = float(vals.get("NetLiquidation", 0))
        sod              = float(vals.get("PreviousDayEquityWithLoanValue", equity))
        pnl              = float(vals.get("RealizedPnL", 0))
        excess_liquidity = float(vals.get("ExcessLiquidity", 0))
        return AccountState(
            user_id=0,   # populated by caller who knows the active user
            equity=equity,
            start_of_day_equity=sod,
            open_position_value=0.0,
            daily_pnl=pnl,
            excess_liquidity=excess_liquidity,
        )

    async def get_open_positions(self) -> list[IBKRPosition]:
        positions = self._ib.positions()
        return [
            IBKRPosition(
                symbol=p.contract.symbol,
                quantity=int(p.position),
                average_price=float(p.avgCost),
                market_value=float(p.position) * float(p.avgCost),
            )
            for p in positions
        ]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _on_disconnect(self) -> None:
        if self._connected:
            self._connected = False
            log.warning("IBKRClient: disconnected — starting reconnect loop")
            self._emit_status(ConnectionStatus.DISCONNECTED)
            asyncio.ensure_future(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        for attempt in range(1, self._max_reconnect + 1):
            delay = _backoff(attempt)
            log.info("Reconnect attempt %d/%d in %.0fs", attempt, self._max_reconnect, delay)
            self._emit_status(ConnectionStatus.RECONNECTING)
            await asyncio.sleep(delay)
            try:
                if self._ib:
                    await asyncio.wait_for(self._ib.connectAsync(
                        self._ib.client.host,
                        self._ib.client.port,
                        clientId=self._ib.client.clientId,
                    ), timeout=5.0)
                    self._connected = True
                    self._emit_status(ConnectionStatus.CONNECTED)
                    log.info("Reconnected on attempt %d", attempt)
                    return
            except Exception as exc:
                log.warning("Reconnect attempt %d failed: %s", attempt, exc)
        log.critical("IBKRClient: max reconnect attempts reached — giving up")

    def _emit_status(self, status: ConnectionStatus) -> None:
        for cb in self._status_callbacks:
            try:
                cb(status)
            except Exception:
                log.exception("Status callback raised an exception")

    def _on_realtime_bar(self, symbol: str, bar: Any) -> None:
        rtb = RealtimeBar(
            symbol=symbol,
            datetime=bar.time,
            open=float(bar.open),
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            volume=int(bar.volume),
        )
        for cb in self._realtime_callbacks:
            try:
                cb(rtb)
            except Exception:
                log.exception("Realtime bar callback raised an exception")

    @staticmethod
    def _bar_size_to_tf(bar_size: str) -> str:
        mapping = {
            "1 min": "1m", "1 day": "1d", "1 week": "1w",
            "3 mins": "3m", "5 mins": "5m", "15 mins": "15m",
            "1 hour": "1h", "4 hours": "4h",
        }
        return mapping.get(bar_size, bar_size)
