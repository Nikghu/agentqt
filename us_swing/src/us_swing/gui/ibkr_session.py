"""
Module: MD-GUI-012.001.M01 — IBKRSession
Parent SRD: SRD-GUI-012.001
"""
from __future__ import annotations

import asyncio
import logging
import random
import threading
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from us_swing.data.models import AccountState, OpenPosition

_log = logging.getLogger(__name__)

# ── Reconnect constants (DD-GUI-012.001.D03) ─────────────────────────────────
_RECONNECT_BASE: float = 2.0
_RECONNECT_MAX_DELAY: float = 30.0
_RECONNECT_MAX_ATTEMPTS: int = 10

# ── Debounce / coalesce windows ───────────────────────────────────────────────
_ACCOUNT_DEBOUNCE_S: float = 0.05   # 50 ms
_QUOTE_COALESCE_S: float = 0.25     # 250 ms


# ── Helper functions ──────────────────────────────────────────────────────────

def _last_or_close(ticker: Any) -> float:
    """Return the best available last-price from an ib_insync Ticker."""
    ltp: float = getattr(ticker, "last", float("nan"))
    if ltp != ltp or ltp <= 0:   # nan check
        ltp = getattr(ticker, "close", 0.0) or 0.0
    return ltp


def _change_pct(ticker: Any) -> float:
    """Return the daily change % from an ib_insync Ticker."""
    prev: float = getattr(ticker, "close", 0.0) or 0.0
    ltp = _last_or_close(ticker)
    if prev <= 0 or ltp <= 0:
        return 0.0
    return (ltp - prev) / prev * 100.0


# ── IBKRSession ───────────────────────────────────────────────────────────────

class IBKRSession(QObject):
    """Manages a single persistent ib_insync connection on a dedicated QThread.

    All ib_insync calls execute on an asyncio event loop created inside
    ``_session_thread``.  Plain Python value objects cross back to the Qt main
    thread via queued pyqtSignal emissions.

    Usage::

        session = IBKRSession(parent=app_service)
        session.account_ready.connect(on_account_ready)
        session.quotes_updated.connect(on_quotes_updated)
        session.connection_lost.connect(on_connection_lost)
        session.connection_restored.connect(on_connection_restored)
        session.start("127.0.0.1", 7497, 10)
        session.set_market_watch_symbols(["AAPL", "MSFT"])
    """

    # ── Public signals ────────────────────────────────────────────────────────
    account_ready = pyqtSignal(object, list)
    """Emitted after the 50 ms account debounce completes.

    Arguments:
        AccountState: account equity / PnL snapshot.
        list[OpenPosition]: current open positions.
    """

    quotes_updated = pyqtSignal(list)
    """Emitted after the 250 ms tick-coalescing window closes.

    Arguments:
        list[dict]: one dict per symbol with keys
            ``symbol``, ``ltp``, ``change_pct``, ``previous_close``,
            ``source`` (always ``"ibkr"``).
    """

    connection_lost = pyqtSignal(str)
    """Emitted when the IBKR connection is lost or all reconnect attempts fail.

    Arguments:
        str: human-readable reason.
    """

    connection_restored = pyqtSignal()
    """Emitted after a successful reconnect completes."""

    # ── Constructor ───────────────────────────────────────────────────────────

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Connection parameters — set by start()
        self._host: str = ""
        self._port: int = 0
        self._client_id: int = 0

        # Threading
        self._session_thread: QThread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopping: bool = False

        # ib_insync handle — created inside _thread_main after IB import
        self._ib: Any = None  # ib_insync.IB

        # Symbol sets — guarded by _symbols_lock for cross-thread writes
        self._symbols_lock = threading.Lock()
        self._mw_symbols: set[str] = set()
        self._wl_symbols: set[str] = set()

        # Active tickers: symbol → ib_insync.Ticker
        self._tickers: dict[str, Any] = {}

        # Pending asyncio tasks
        self._debounce_account_task: asyncio.Task[None] | None = None
        self._coalesce_quotes_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._reconnect_attempt: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self, host: str, port: int, client_id: int) -> None:
        """Start the IBKR session thread.

        Idempotent: returns immediately if the session thread is already
        running.  The thread creates its own asyncio event loop, connects to
        IBKR, and then runs ``loop.run_forever()`` until ``stop()`` is called.

        Args:
            host: IBKR Gateway / TWS hostname or IP.
            port: Gateway port (7497 paper, 7496 live).
            client_id: Unique client ID for this persistent connection.
        """
        if self._session_thread is not None:
            return

        self._host = host
        self._port = port
        self._client_id = client_id
        self._stopping = False

        self._session_thread = QThread()
        # _session_thread.started → _thread_main
        self._session_thread.started.connect(self._thread_main)
        self._session_thread.start()

    def stop(self) -> None:
        """Stop the IBKR session and join the background thread.

        Schedules ``_shutdown()`` on the asyncio loop and waits up to 3 s for
        the thread to finish.  If the thread does not exit within the timeout
        it is forcibly terminated and a WARNING is logged.
        """
        if self._session_thread is None:
            return

        self._stopping = True

        loop = self._loop
        if loop is not None and loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(self._shutdown(), loop)
            try:
                fut.result(timeout=2.8)
            except Exception:
                pass

        if not self._session_thread.wait(500):
            _log.warning(
                "[Feed] Session thread did not stop within 3 s — forcing termination"
            )
            self._session_thread.terminate()
            self._session_thread.wait(1000)

        self._session_thread = None
        self._loop = None
        self._ib = None

    def set_market_watch_symbols(self, symbols: list[str]) -> None:
        """Update the Market Watch symbol set on the asyncio loop.

        The delta calculation (subscribe/cancel) runs inside
        ``_apply_symbol_delta``; ``^``-prefixed index symbols are filtered
        there and never passed to ``reqMktData``.

        Args:
            symbols: Full desired Market Watch symbol list (may include indices).
        """
        loop = self._loop
        if loop is None or not loop.is_running():
            with self._symbols_lock:
                self._mw_symbols = set(symbols)
            return
        asyncio.run_coroutine_threadsafe(
            self._apply_symbol_delta(new_mw=set(symbols)), loop
        )

    def set_watchlist_symbols(self, symbols: list[str]) -> None:
        """Update the Watchlist symbol set on the asyncio loop.

        Args:
            symbols: Full desired Watchlist symbol list.
        """
        loop = self._loop
        if loop is None or not loop.is_running():
            with self._symbols_lock:
                self._wl_symbols = set(symbols)
            return
        asyncio.run_coroutine_threadsafe(
            self._apply_symbol_delta(new_wl=set(symbols)), loop
        )

    # ── Thread entry point ────────────────────────────────────────────────────

    def _thread_main(self) -> None:
        """QThread entry point — creates asyncio loop and runs until stopped."""
        # Import ib_insync here so the main thread never touches the package
        try:
            from ib_insync import IB
        except ImportError:
            _log.error("[Feed] ib_insync is not installed — cannot connect to IBKR")
            self.connection_lost.emit("ib_insync not installed")
            return

        self._ib = IB()  # type: ignore[no-untyped-call]
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            # Run initial connect + subscribe, then hand off to run_forever
            self._loop.run_until_complete(self._connect_and_subscribe())
            if not self._stopping:
                self._loop.run_forever()
        except Exception as exc:
            _log.exception("[Feed] Session thread encountered a fatal error")
            self.connection_lost.emit(str(exc))
        finally:
            self._loop.close()

    # ── Core asyncio coroutines ───────────────────────────────────────────────

    async def _connect_and_subscribe(self) -> None:
        """Connect to IBKR and subscribe to account updates and market data.

        Called once from ``_thread_main`` on startup, and again after each
        successful reconnect.
        """
        if self._ib is None:
            raise RuntimeError("IB handle is not initialised")
        if self._loop is None:
            raise RuntimeError("Event loop is not initialised")

        try:
            from ib_insync import Stock
        except ImportError:
            _log.error("[Feed] ib_insync is not installed — cannot subscribe")
            return

        await self._ib.connectAsync(
            self._host, self._port, clientId=self._client_id, timeout=5
        )
        _log.info("[Feed] Connected to IBKR at %s:%d", self._host, self._port)

        # Idempotent event wiring — strip any prior subscriptions before re-adding
        try:
            self._ib.accountValueEvent    -= self._on_account_event
            self._ib.updatePortfolioEvent -= self._on_account_event
            self._ib.accountSummaryEvent  -= self._on_account_event
            self._ib.pendingTickersEvent  -= self._on_pending_tickers
            self._ib.disconnectedEvent    -= self._on_disconnected
        except Exception:
            pass   # first call — nothing to remove

        # ── Account subscription ──────────────────────────────────────────────
        self._ib.reqAccountUpdates(True, "")
        self._ib.accountValueEvent    += self._on_account_event
        self._ib.updatePortfolioEvent += self._on_account_event
        self._ib.accountSummaryEvent  += self._on_account_event

        # ── Market data subscription ──────────────────────────────────────────
        self._ib.pendingTickersEvent += self._on_pending_tickers

        # Wire disconnect event for the reconnect FSM
        self._ib.disconnectedEvent += self._on_disconnected

        # Re-subscribe any already-tracked symbols (handles reconnect path)
        with self._symbols_lock:
            union_active = {
                s
                for s in (self._mw_symbols | self._wl_symbols)
                if not s.startswith("^")
            }
        for sym in union_active:
            if sym not in self._tickers:
                contract = Stock(sym, "SMART", "USD")
                self._tickers[sym] = self._ib.reqMktData(contract, "", False, False)

    async def _apply_symbol_delta(
        self,
        new_mw: set[str] | None = None,
        new_wl: set[str] | None = None,
    ) -> None:
        """Compute the minimal subscribe/cancel diff and apply it.

        ``^``-prefixed index symbols are filtered here — they are never passed
        to ``reqMktData``.

        Args:
            new_mw: New Market Watch symbol set, or ``None`` to leave unchanged.
            new_wl: New Watchlist symbol set, or ``None`` to leave unchanged.
        """
        try:
            from ib_insync import Stock
        except ImportError:
            return

        if new_mw is not None:
            self._mw_symbols = new_mw
        if new_wl is not None:
            self._wl_symbols = new_wl

        union_new = {
            s
            for s in (self._mw_symbols | self._wl_symbols)
            if not s.startswith("^")
        }
        union_old = set(self._tickers.keys())

        # Cancel removed subscriptions
        for sym in union_old - union_new:
            ticker = self._tickers.pop(sym)
            if self._ib is not None and ticker.contract is not None:
                self._ib.cancelMktData(ticker.contract)

        # Add new subscriptions
        if self._ib is None:
            return
        for sym in union_new - union_old:
            contract = Stock(sym, "SMART", "USD")
            self._tickers[sym] = self._ib.reqMktData(contract, "", False, False)

    async def _shutdown(self) -> None:
        """Cancel all pending tasks, disconnect IB, and stop the event loop."""
        _log.info("[Feed] Shutting down IBKR session")

        # Gather all pending tasks — swallow exceptions so shutdown is clean
        tasks_to_cancel: list[asyncio.Task[None]] = []
        for task in (
            self._debounce_account_task,
            self._coalesce_quotes_task,
            self._reconnect_task,
        ):
            if task is not None and not task.done():
                task.cancel()
                tasks_to_cancel.append(task)

        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        if self._ib is not None and self._ib.isConnected():
            self._ib.disconnect()

        loop = self._loop
        if loop is not None:
            loop.stop()

    # ── Account event handlers ────────────────────────────────────────────────

    async def _on_account_event(self, *_args: object) -> None:
        """Schedule a debounced account snapshot — cancel any in-flight task and restart."""
        if self._debounce_account_task is not None and not self._debounce_account_task.done():
            self._debounce_account_task.cancel()
        self._debounce_account_task = asyncio.create_task(self._debounce_account())

    async def _debounce_account(self) -> None:
        """Wait for the 50 ms quiet window, then build and emit an account snapshot."""
        try:
            await asyncio.sleep(_ACCOUNT_DEBOUNCE_S)
            try:
                acct, positions = await self._build_account_snapshot()
            except Exception:
                _log.exception("[Feed] Failed to build account snapshot")
                return
            self.account_ready.emit(acct, positions)
        except asyncio.CancelledError:
            return

    async def _build_account_snapshot(
        self,
    ) -> tuple[AccountState, list[OpenPosition]]:
        """Build an AccountState + OpenPosition list from the live IB state.

        Mirrors the field extraction in ``_AccountDataWorker._async_run`` in
        ``app_service.py``: same ``accountSummaryAsync`` tag flatten, same
        ``ib.portfolio()`` iteration.

        Returns:
            A tuple of (AccountState, list[OpenPosition]).
        """
        if self._ib is None:
            raise RuntimeError("IB handle is not initialised")

        # ── Account summary ───────────────────────────────────────────────────
        summary_items = await self._ib.accountSummaryAsync()
        tag_vals: dict[str, dict[str, str]] = {}
        for item in summary_items:
            tag_vals.setdefault(item.tag, {})[item.currency] = item.value

        def _tag(name: str) -> float:
            vals = tag_vals.get(name, {})
            if not vals:
                return 0.0
            raw = vals.get("BASE") or next(iter(vals.values()), "0")
            try:
                return float(raw or 0)
            except (ValueError, TypeError):
                return 0.0

        equity = _tag("NetLiquidation")
        sod_equity_raw = _tag("PreviousEquityWithLoanValue")
        sod_equity = sod_equity_raw if sod_equity_raw > 0.0 else equity
        excess_liquidity = _tag("ExcessLiquidity")
        total_cash_value = _tag("TotalCashValue")
        gross_position_value = _tag("GrossPositionValue")

        # ── Portfolio ─────────────────────────────────────────────────────────
        portfolio = self._ib.portfolio()
        open_val: float = 0.0
        positions: list[OpenPosition] = []

        for pi in portfolio:
            qty = int(pi.position)
            if qty == 0:
                continue
            sym = pi.contract.symbol
            avg_cost: float = pi.averageCost
            mv: float = pi.marketValue
            ltp: float = abs(mv / qty) if qty else 0.0
            open_val += abs(mv)
            positions.append(
                OpenPosition(
                    symbol=sym,
                    user_id=1,
                    quantity=abs(qty),
                    average_price=avg_cost,
                    stop_loss=0.0,
                    target_price=0.0,
                    mode="live",
                    state="OPEN",
                    current_price=ltp,
                    strategy_id="IBKR",
                    filled_quantity=abs(qty),
                    total_quantity=abs(qty),
                )
            )

        acct = AccountState(
            user_id=1,
            equity=equity,
            start_of_day_equity=sod_equity,
            open_position_value=open_val,
            daily_pnl=sum(p.unrealised_pnl for p in positions),
            excess_liquidity=excess_liquidity,
            total_cash_value=total_cash_value,
            gross_position_value=gross_position_value,
        )
        return acct, positions

    # ── Market data event handlers ────────────────────────────────────────────

    async def _on_pending_tickers(self, _tickers: object) -> None:
        """Schedule a coalesced quote batch — cancel any in-flight task and restart."""
        if self._coalesce_quotes_task is not None and not self._coalesce_quotes_task.done():
            self._coalesce_quotes_task.cancel()
        self._coalesce_quotes_task = asyncio.create_task(self._coalesce_quotes())

    async def _coalesce_quotes(self) -> None:
        """Wait for the 250 ms coalescing window, then build and emit quote rows."""
        try:
            await asyncio.sleep(_QUOTE_COALESCE_S)
            rows: list[dict[str, object]] = []
            for sym, ticker in self._tickers.items():
                ltp = _last_or_close(ticker)
                rows.append(
                    {
                        "symbol": sym,
                        "ltp": ltp,
                        "change_pct": _change_pct(ticker),
                        "previous_close": getattr(ticker, "close", 0.0) or 0.0,
                        "source": "ibkr",
                    }
                )
            self.quotes_updated.emit(rows)
        except asyncio.CancelledError:
            return

    # ── Reconnect state machine ───────────────────────────────────────────────

    async def _on_disconnected(self) -> None:
        """ib.disconnectedEvent handler — spawns the reconnect loop unless stopping."""
        if self._stopping:
            return
        _log.warning("[Feed] Disconnected from IBKR — starting reconnect loop")
        self.connection_lost.emit("Disconnected from IBKR")

        # Only one reconnect loop at a time
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Exponential-backoff reconnect loop with ±20 % jitter.

        Attempts up to ``_RECONNECT_MAX_ATTEMPTS`` reconnects, then emits
        ``connection_lost("Max reconnect attempts reached")`` and stops the
        event loop.
        """
        self._reconnect_attempt = 0

        while not self._stopping and self._reconnect_attempt < _RECONNECT_MAX_ATTEMPTS:
            delay = min(
                _RECONNECT_BASE * (2 ** self._reconnect_attempt),
                _RECONNECT_MAX_DELAY,
            )
            delay *= random.uniform(0.8, 1.2)
            await asyncio.sleep(delay)
            self._reconnect_attempt += 1

            try:
                if self._ib is None:
                    raise RuntimeError("IB handle is not initialised")
                self._tickers.clear()
                await self._connect_and_subscribe()   # owns connectAsync internally
                self._reconnect_attempt = 0
                self.connection_restored.emit()
                _log.info("[Feed] Reconnected to IBKR successfully")
                return
            except Exception as exc:
                _log.warning(
                    "[Feed] Reconnect attempt %d failed: %s",
                    self._reconnect_attempt,
                    exc,
                )

        if not self._stopping:
            _log.error(
                "[Feed] All %d reconnect attempts exhausted — giving up",
                _RECONNECT_MAX_ATTEMPTS,
            )
            self.connection_lost.emit("Max reconnect attempts reached")
            self._stopping = True
            loop = self._loop
            if loop is not None:
                loop.stop()
