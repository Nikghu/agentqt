"""
Module: MD-INF-010.001.M09 — gui/notification_worker.py
Parent SRD: SRD-INF-010.004, SRD-INF-010.010

Hosts the async notification dispatcher on its own thread. The app has no
app-wide asyncio loop (it is Qt/QThread based), so the dispatcher — which uses
``asyncio`` and ``httpx`` — runs inside a dedicated ``QThread`` with its own
event loop. GUI-thread producers hand events in via ``publish_event``, which
marshals onto the loop thread (``asyncio.Queue`` is not thread-safe).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging

import httpx
from PyQt6.QtCore import QThread, pyqtSignal

from us_swing.core.notifications import (
    CommandPort,
    NotificationBus,
    NotificationConfig,
    build_command_poller,
    build_default_dispatcher,
)

_log = logging.getLogger(__name__)


class NotificationWorker(QThread):
    """Runs the notification dispatcher loop until :meth:`shutdown` is called."""

    ready = pyqtSignal()

    def __init__(self, config: NotificationConfig, command_port: CommandPort | None = None) -> None:
        super().__init__()
        self._config = config
        self._command_port = command_port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bus: NotificationBus | None = None
        self._stop: asyncio.Event | None = None

    def run(self) -> None:
        try:
            asyncio.run(self._serve())
        except Exception:
            _log.exception("[Notify] Notification worker stopped unexpectedly")

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        async with httpx.AsyncClient(timeout=10.0) as http:
            dispatcher, bus = build_default_dispatcher(self._config, http=http)
            self._bus = bus
            delivery = asyncio.create_task(dispatcher.run())
            tasks = [delivery]
            poller = build_command_poller(self._config, http, self._command_port)
            if poller is not None:
                tasks.append(asyncio.create_task(poller.run()))
            self.ready.emit()
            await self._stop.wait()
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    def publish_event(self, event: object) -> None:
        """Publish an event from any thread. No-op until the loop is running."""
        loop = self._loop
        bus = self._bus
        if loop is None or bus is None:
            return
        loop.call_soon_threadsafe(bus.publish, event)

    def shutdown(self) -> None:
        """Stop the loop and join the thread."""
        loop = self._loop
        stop = self._stop
        if loop is not None and stop is not None:
            loop.call_soon_threadsafe(stop.set)
        self.quit()
        self.wait(3000)
