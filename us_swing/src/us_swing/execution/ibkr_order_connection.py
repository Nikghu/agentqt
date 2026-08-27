"""Module: execution/ibkr_order_connection.py
Parent SRD: SRD-EXE-015.004

Note: no MD module ID yet — MD.md has no MD-EXE-015.003 section, so the sibling
broker_factory.py header is undocumented too.  Both need an MD row adding.

Dedicated IBKR connection for live order routing.

Every other IBKR consumer in the app (tick feed, intraday loader, account
poller) owns its own connection under its own client id; order routing follows
the same pattern so a slow download can never stall an order.

``ib_insync`` is bound to the event loop that opened its connection, so the
connection lives on a private daemon thread running that loop for the life of
the app.  ``IBKRClientGateway`` marshals every placement and cancellation back
onto it.
"""
from __future__ import annotations

import asyncio
import logging
import threading

from us_swing.broker.client import IBKRClient
from us_swing.exceptions import BrokerConnectionError

_log = logging.getLogger(__name__)

# How long shutdown waits for TWS to acknowledge the logout.
_DISCONNECT_TIMEOUT_S = 5.0


class IBKROrderConnection:
    """Owns the order-routing IBKR connection and the loop it runs on."""

    def __init__(self, host: str, port: int, client_id: int, timeout: float = 10.0) -> None:
        self._host = host
        self._port = port
        self._client_id = client_id
        self._timeout = timeout
        self._client = IBKRClient()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._thread: threading.Thread | None = None

    def is_live(self) -> bool:
        """Whether the order socket is currently up.

        Checked before every placement so a reconnect in progress refuses the
        order outright instead of dropping it into a dead socket.
        """
        return self._client.is_connected()

    def connect(self) -> IBKRClient:
        """Start the connection thread and block until IBKR accepts or refuses.

        Returns:
            The connected client, ready for order placement.

        Raises:
            BrokerConnectionError: If the connection failed or timed out.
        """
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._run, name="ibkr-orders", daemon=True
            )
            self._thread.start()

        # IBKRClient.connect spends up to `timeout` on the socket and another
        # `timeout` on the account probe, so wait for both before giving up —
        # a premature timeout would strand a connected session on this client id.
        if not self._ready.wait(timeout=2 * self._timeout + 5.0):
            raise BrokerConnectionError(
                f"IBKR order connection to {self._host}:{self._port} did not respond"
            )
        if self._error is not None:
            raise BrokerConnectionError(
                f"IBKR order connection failed: {self._error}"
            ) from self._error
        return self._client

    def close(self) -> None:
        """Disconnect and stop the loop.  Safe to call when never connected."""
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        # Wait for the logout to complete before stopping the loop, otherwise
        # TWS sees a dropped socket instead of a clean disconnect.
        future = asyncio.run_coroutine_threadsafe(self._client.disconnect(), loop)
        try:
            future.result(timeout=_DISCONNECT_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 - shutdown is best-effort
            _log.warning("[Orders] Live order connection did not close cleanly: %s", exc)
        loop.call_soon_threadsafe(loop.stop)

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect_once())
        except BaseException as exc:  # noqa: BLE001 - relayed to connect()
            self._error = exc
        finally:
            self._ready.set()
        if self._error is None:
            loop.run_forever()

    async def _connect_once(self) -> None:
        await self._client.connect(
            self._host, self._port, self._client_id, timeout=self._timeout
        )
        _log.info(
            "[Orders] Live order routing connected to IBKR at %s:%d",
            self._host,
            self._port,
        )


__all__ = ["IBKROrderConnection"]
