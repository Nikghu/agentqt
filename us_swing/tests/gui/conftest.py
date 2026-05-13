"""
Shared test fixtures for GUI unit tests (FO-GUI-012).

Provides:
  - FakeIB          — duck-typed ib_insync.IB substitute
  - FakeContract    — minimal contract object returned by FakeStock(sym, ...)
  - FakeStock       — factory for FakeContract, replaces ib_insync.Stock
  - FakeTicker      — object stored in session._tickers; exposes .contract, .last, .close
  - fake_ib_module  — monkeypatches sys.modules["ib_insync"] with FakeIB/FakeStock
  - FakeIBKRSession — QObject with the same four signals as IBKRSession; all
                      public methods are no-ops that record calls
"""
from __future__ import annotations

import asyncio
import sys
import types
from typing import Any

import pytest
from PyQt6.QtCore import QObject, pyqtSignal


# ── Minimal Qt Application ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication for the full test session."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ── Event shim ───────────────────────────────────────────────────────────────

class _EventShim:
    """Minimal ib_insync-style event: supports += / -= and .emit(*args)."""

    def __init__(self) -> None:
        self._handlers: list[Any] = []

    def __iadd__(self, handler: Any) -> "_EventShim":
        if handler not in self._handlers:
            self._handlers.append(handler)
        return self

    def __isub__(self, handler: Any) -> "_EventShim":
        try:
            self._handlers.remove(handler)
        except ValueError:
            pass
        return self

    def emit(self, *args: Any) -> None:
        """Synchronously invoke all registered handlers."""
        for h in list(self._handlers):
            result = h(*args)
            # Support coroutine handlers — run them on the event loop if present
            if asyncio.iscoroutine(result):
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(result)
                else:
                    loop.run_until_complete(result)


# ── FakeContract / FakeStock / FakeTicker ────────────────────────────────────

class FakeContract:
    """Minimal ib_insync contract object."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol


class FakeStock:
    """Replacement for ib_insync.Stock — returns a FakeContract."""

    def __new__(cls, symbol: str, exchange: str = "SMART", currency: str = "USD") -> FakeContract:  # type: ignore[misc]
        return FakeContract(symbol)


class FakeTicker:
    """Minimal Ticker returned by reqMktData; holds last/close prices."""

    def __init__(self, contract: FakeContract, last: float = 100.0, close: float = 99.0) -> None:
        self.contract = contract
        self.last = last
        self.close = close


# ── FakeIB ───────────────────────────────────────────────────────────────────

class FakeIB:
    """Duck-typed ib_insync.IB substitute for unit tests.

    Setting ``fail_connect = True`` makes ``connectAsync`` raise
    ``ConnectionRefusedError`` — used to test reconnect failure paths.
    Setting ``fail_count`` makes it fail that many times before succeeding.
    """

    def __init__(self) -> None:
        self.connect_calls: list[tuple[str, int, int]] = []
        self.disconnect_called: bool = False
        self.req_calls: list[str] = []
        self.cancel_calls: list[str] = []
        self.reqAccountUpdates_calls: list[tuple[Any, ...]] = []

        self.fail_connect: bool = False
        self.fail_count: int = 0   # fail this many times then succeed
        self._connect_attempts: int = 0
        self._connected: bool = False

        # ib_insync-style events
        self.accountValueEvent    = _EventShim()
        self.updatePortfolioEvent = _EventShim()
        self.accountSummaryEvent  = _EventShim()
        self.pendingTickersEvent  = _EventShim()
        self.disconnectedEvent    = _EventShim()

    # ── Connection ────────────────────────────────────────────────────────────

    async def connectAsync(
        self,
        host: str,
        port: int,
        *,
        clientId: int,
        timeout: float = 5,
    ) -> None:
        self._connect_attempts += 1
        if self.fail_connect:
            raise ConnectionRefusedError("FakeIB: forced connect failure")
        if self.fail_count > 0:
            self.fail_count -= 1
            raise ConnectionRefusedError(f"FakeIB: forced failure #{self._connect_attempts}")
        self.connect_calls.append((host, port, clientId))
        self._connected = True

    def disconnect(self) -> None:
        self.disconnect_called = True
        self._connected = False

    def isConnected(self) -> bool:
        return self._connected

    # ── Account ───────────────────────────────────────────────────────────────

    def reqAccountUpdates(self, subscribe: bool, account: str) -> None:
        self.reqAccountUpdates_calls.append((subscribe, account))

    async def accountSummaryAsync(self) -> list[Any]:
        """Return a minimal summary list with NetLiquidation."""

        class _Item:
            def __init__(self, tag: str, currency: str, value: str) -> None:
                self.tag = tag
                self.currency = currency
                self.value = value

        return [_Item("NetLiquidation", "BASE", "100000.0")]

    def accountValues(self) -> list[Any]:
        return []

    def portfolio(self) -> list[Any]:
        return []

    # ── Market data ───────────────────────────────────────────────────────────

    def reqMktData(
        self,
        contract: Any,
        genericTickList: str = "",
        snapshot: bool = False,
        regulatorySnapshot: bool = False,
    ) -> FakeTicker:
        self.req_calls.append(contract.symbol)
        return FakeTicker(contract)

    def cancelMktData(self, contract: Any) -> None:
        self.cancel_calls.append(contract.symbol)


# ── fake_ib_module fixture ────────────────────────────────────────────────────

@pytest.fixture()
def fake_ib(qapp: Any) -> FakeIB:
    """Return a fresh FakeIB instance with ib_insync patched into sys.modules."""
    ib = FakeIB()
    mod = types.ModuleType("ib_insync")
    mod.IB = lambda: ib  # type: ignore[attr-defined]
    mod.Stock = FakeStock  # type: ignore[attr-defined]
    sys.modules["ib_insync"] = mod
    yield ib
    # Restore — remove the fake so the next test gets a clean slate
    sys.modules.pop("ib_insync", None)


# ── FakeIBKRSession ───────────────────────────────────────────────────────────

class FakeIBKRSession(QObject):
    """QObject with the same four signals as IBKRSession.

    All public methods record calls; none perform real I/O.
    Used to test AppService bridge slots in isolation.
    """

    account_ready      = pyqtSignal(object, list)
    quotes_updated     = pyqtSignal(list)
    connection_lost    = pyqtSignal(str)
    connection_restored = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.start_calls:  list[tuple[str, int, int]] = []
        self.stop_called:  bool = False
        self.set_mw_calls: list[list[str]] = []
        self.set_wl_calls: list[list[str]] = []

    def start(self, host: str, port: int, client_id: int) -> None:
        self.start_calls.append((host, port, client_id))

    def stop(self) -> None:
        self.stop_called = True

    def set_market_watch_symbols(self, symbols: list[str]) -> None:
        self.set_mw_calls.append(list(symbols))

    def set_watchlist_symbols(self, symbols: list[str]) -> None:
        self.set_wl_calls.append(list(symbols))
