"""
Module: MD-EXE-008.001.M01 — execution/live_tick_worker.py
Parent SRD: SRD-EXE-008.001–006
"""
from __future__ import annotations

import asyncio
import logging
import math
import threading
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

log = logging.getLogger(__name__)

_SUB_BATCH: int = 10
_SUB_PAUSE: float = 0.20          # seconds — IBKR pacing limit
_CONNECT_TIMEOUT: int = 10
_FATAL_CODES: frozenset[int] = frozenset({200, 354, 420})


class LiveTickWorker(QThread):
    """Streams live last-price ticks for a set of IBKR contracts via reqMktData.

    Each tag (Yahoo-notation symbol or index string) maps to an ib_insync Contract.
    When IBKR delivers a price update, ``tick_price`` fires with the tag and price.
    Uses a dedicated clientId (configurable, default 14) isolated from other workers.

    Args:
        host:       IBKR TWS / Gateway hostname.
        port:       IBKR TWS / Gateway port.
        client_id:  Dedicated IBKR client ID for this connection.
        parent:     Optional Qt parent object.
    """

    tick_price          = pyqtSignal(str, float)  # (tag, price)
    subscription_failed = pyqtSignal(str, int)    # (tag, ibkr_error_code)

    def __init__(
        self,
        host: str,
        port: int,
        client_id: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._host       = host
        self._port       = port
        self._client_id  = client_id
        self._stop_event = threading.Event()
        self._lock       = threading.RLock()
        self._ib: Any    = None
        self._loop: asyncio.AbstractEventLoop | None = None
        # All four dicts guarded by _lock:
        self._active:       dict[str, Any] = {}  # tag → Contract
        self._tickers:      dict[str, Any] = {}  # tag → Ticker
        self._tag_by_conid: dict[int, str] = {}  # conId → tag
        self._reqid_to_tag: dict[int, str] = {}  # reqId → tag

    # ── QThread entry point ───────────────────────────────────────────────────

    def run(self) -> None:
        """QThread entry: run the async subscription loop in a fresh event loop."""
        try:
            asyncio.run(self._async_run())
        except Exception:
            log.exception("[Tick] Unexpected error in tick worker")

    def request_stop(self) -> None:
        """Signal the worker to stop; safe to call from any thread."""
        self._stop_event.set()

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_contracts(self, contracts: dict[str, Any]) -> None:
        """Update live reqMktData subscriptions.

        Thread-safe.  When called from the Qt main thread (after initial connect),
        schedules the diff+subscribe work on the asyncio event loop via
        run_coroutine_threadsafe so that ib.reqMktData() runs in the correct thread.

        Args:
            contracts: Complete desired set of {tag: Contract} pairs.
        """
        ib = self._ib
        if ib is None:
            # Not yet connected — queue for initial subscription after connect
            with self._lock:
                self._active = dict(contracts)
            return

        loop = self._loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._apply_contracts(ib, dict(contracts)), loop
            )

    # ── IBKR async path ───────────────────────────────────────────────────────

    async def _async_run(self) -> None:
        """Async main loop: connect, subscribe initial contracts, wait for ticks."""
        try:
            from ib_insync import IB  # noqa: PLC0415
        except ImportError:
            log.error("[Tick] ib_insync not installed — live tick streaming unavailable")
            return

        ib: Any = IB()  # type: ignore[no-untyped-call]
        connected = await self._connect_with_retry(ib)
        if not connected:
            return

        self._ib   = ib
        self._loop = asyncio.get_running_loop()
        log.info("[Tick] Connected to IBKR (clientId=%d)", self._client_id)
        ib.pendingTickersEvent += self._on_pending_tickers
        ib.errorEvent          += self._on_ibkr_error

        # Subscribe any contracts queued before the loop connected.
        with self._lock:
            initial = dict(self._active)
            self._active.clear()
        if initial:
            await self._apply_contracts(ib, initial)

        try:
            while not self._stop_event.is_set() and ib.isConnected():
                await asyncio.sleep(0.05)
        finally:
            with self._lock:
                tickers_snapshot = list(self._tickers.values())
            for ticker in tickers_snapshot:
                try:
                    ib.cancelMktData(ticker.contract)
                except Exception:
                    pass
            try:
                ib.disconnect()
            except Exception:
                pass
            self._ib = None

        if not self._stop_event.is_set():
            log.warning("[Tick] IBKR connection dropped — tick streaming ended")
        else:
            log.info("[Tick] Tick worker stopped")

    async def _apply_contracts(self, ib: Any, contracts: dict[str, Any]) -> None:
        """Diff subscriptions and apply changes; uses asyncio.sleep for pacing.

        Must run in the asyncio event loop so ib.reqMktData() executes in the
        correct thread context.
        """
        with self._lock:
            current_tags = set(self._active)
            new_tags     = set(contracts)
            to_remove    = current_tags - new_tags
            to_add       = new_tags    - current_tags

            for tag in to_remove:
                ticker = self._tickers.pop(tag, None)
                if ticker is not None:
                    try:
                        ib.cancelMktData(ticker.contract)
                    except Exception:
                        pass
                self._active.pop(tag, None)

        batch: list[tuple[str, Any]] = []
        for tag in to_add:
            batch.append((tag, contracts[tag]))
            if len(batch) == _SUB_BATCH:
                with self._lock:
                    self._subscribe_batch(ib, batch)
                await asyncio.sleep(_SUB_PAUSE)
                batch.clear()
        if batch:
            with self._lock:
                self._subscribe_batch(ib, batch)

        with self._lock:
            self._active = dict(contracts)

    async def _connect_with_retry(self, ib: Any) -> bool:
        """Attempt IBKR connect with clientId collision retry (SRD-EXE-008.006).

        Error 326 (clientId in use) arrives via errorEvent and causes isConnected()
        to return False after connectAsync() returns.  Retries up to 3 times with
        incremented clientId.

        Returns:
            True if connected, False if all attempts failed.
        """
        client_id = self._client_id
        for attempt in range(4):
            try:
                await ib.connectAsync(
                    self._host, self._port,
                    clientId=client_id,
                    timeout=_CONNECT_TIMEOUT,
                )
                if ib.isConnected():
                    return True
                # Not connected after return — error 326 (clientId in use)
                if attempt < 3:
                    log.warning(
                        "[Tick] ClientId %d in use — retrying with %d",
                        client_id, client_id + 1,
                    )
                    client_id += 1
            except ConnectionRefusedError:
                log.error("[Tick] Cannot reach IBKR at %s:%d", self._host, self._port)
                return False
            except Exception as exc:
                log.warning("[Tick] IBKR connection error: %s", exc)
                return False
        log.error("[Tick] Cannot connect — all clientId slots exhausted")
        return False

    def _subscribe_batch(self, ib: Any, batch: list[tuple[str, Any]]) -> None:
        """Subscribe a batch of (tag, contract) pairs via reqMktData.

        Must be called while holding _lock.
        """
        for tag, contract in batch:
            try:
                ticker = ib.reqMktData(contract, "", False, False)
                self._tickers[tag] = ticker
                con_id = getattr(ticker.contract, "conId", 0)
                if con_id:
                    self._tag_by_conid[con_id] = tag
                req_id = getattr(ticker, "reqId", None)
                if req_id is not None:
                    self._reqid_to_tag[req_id] = tag
            except Exception as exc:
                log.warning("[Tick] Failed to subscribe to %s: %s", tag, exc)

    def _on_pending_tickers(self, tickers: Any) -> None:
        """Handle ib_insync pendingTickersEvent — emit tick_price for valid prices."""
        with self._lock:
            reverse: dict[int, str] = {id(t): tag for tag, t in self._tickers.items()}

        for ticker in tickers:
            tag = reverse.get(id(ticker))
            if tag is None:
                continue

            # Backfill conId map lazily so _on_ibkr_error can clean up correctly
            con_id = getattr(ticker.contract, "conId", 0)
            if con_id:
                with self._lock:
                    self._tag_by_conid.setdefault(con_id, tag)

            # last → bid (IBKR reports index level as bid for IND contracts) → close
            price: float = getattr(ticker, "last", float("nan"))
            if math.isnan(price) or price <= 0:
                price = getattr(ticker, "bid", float("nan"))
            if math.isnan(price) or price <= 0:
                price = getattr(ticker, "close", float("nan"))
            if math.isnan(price) or price <= 0:
                continue

            self.tick_price.emit(tag, price)

    def _on_ibkr_error(self, req_id: int, code: int, msg: str, *_: Any) -> None:
        """Handle ib_insync errorEvent — manage fatal subscription errors."""
        if code not in _FATAL_CODES:
            if req_id > 0:
                with self._lock:
                    tag = self._reqid_to_tag.get(req_id)
                label = tag or f"req#{req_id}"
                log.warning("[Tick] IBKR warning %d for %s: %s", code, label, msg)
            return

        with self._lock:
            tag = self._reqid_to_tag.pop(req_id, None)
            if tag is None:
                # reqId not in our map (ib_insync doesn't expose Ticker.reqId) —
                # log so the user can see the rejection in the log panel
                log.warning("[Tick] IBKR error %d for req#%d: %s", code, req_id, msg)
                return
            self._tickers.pop(tag, None)
            self._active.pop(tag, None)
            self._tag_by_conid = {k: v for k, v in self._tag_by_conid.items() if v != tag}

        self.subscription_failed.emit(tag, code)
        log.warning("[Tick] Subscription failed for %s (code %d)", tag, code)
