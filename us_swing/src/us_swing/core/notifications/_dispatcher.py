"""
Module: MD-INF-010.001.M04 — core/notifications/_dispatcher.py
Parent SRD: SRD-INF-010.004, SRD-INF-010.007

Subscribes to the bus, renders each event, and fans it out to every channel.
The producer only ever enqueues (never blocks); a worker paces per chat, retries
with bounded backoff, and isolates each channel so one failure never affects
another channel or the caller.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, Iterable, Mapping

from us_swing.core.notifications._dto import NotificationMessage
from us_swing.core.notifications._formatters import FormatterRegistry
from us_swing.core.notifications._protocols import NotificationBus, NotificationChannel

log = logging.getLogger(__name__)


class NotificationDispatcher:
    """Renders events and delivers them to channels with isolation + retry."""

    def __init__(
        self,
        bus: NotificationBus,
        channels: Iterable[NotificationChannel],
        registry: FormatterRegistry,
        *,
        event_toggles: Mapping[str, bool] | None = None,
        max_retries: int = 2,
        min_interval_s: float = 1.0,
        backoff_base_s: float = 0.5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._channels = list(channels)
        self._registry = registry
        self._event_toggles = dict(event_toggles or {})
        self._queue: asyncio.Queue[NotificationMessage] = asyncio.Queue()
        self._max_retries = max_retries
        self._min_interval_s = min_interval_s
        self._backoff_base_s = backoff_base_s
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_sent: dict[str, float] = {}
        bus.subscribe(self.dispatch)

    @property
    def channels(self) -> tuple[NotificationChannel, ...]:
        return tuple(self._channels)

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    def dispatch(self, event: object) -> None:
        """Render an event and enqueue it. Never raises to the producer — a
        missing formatter or render error is logged and dropped. An event whose
        kind the user has toggled off is dropped before enqueue."""
        if not self._channels:
            return
        try:
            message = self._registry.render(event)  # type: ignore[arg-type]
        except Exception as exc:
            log.error("[Notify] Could not format %s: %r", type(event).__name__, exc)
            return
        if not self._event_toggles.get(message.event_kind, True):
            return
        self._queue.put_nowait(message)

    async def run(self) -> None:
        """Worker loop: drain the queue and deliver each message."""
        while True:
            message = await self._queue.get()
            try:
                await self.deliver(message)
            finally:
                self._queue.task_done()

    async def deliver(self, message: NotificationMessage) -> None:
        """Fan one message out to every channel, isolating each failure."""
        for channel in self._channels:
            try:
                await self._rate_limit(channel.name)
                await self._send_with_retry(channel, message)
            except Exception as exc:
                log.error("[Notify] Delivery to %s failed: %r", channel.name, exc)

    async def _rate_limit(self, channel_name: str) -> None:
        if self._min_interval_s <= 0:
            return
        last = self._last_sent.get(channel_name)
        if last is not None:
            wait = self._min_interval_s - (self._monotonic() - last)
            if wait > 0:
                await self._sleep(wait)
        self._last_sent[channel_name] = self._monotonic()

    async def _send_with_retry(
        self,
        channel: NotificationChannel,
        message: NotificationMessage,
    ) -> None:
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            try:
                await channel.send(message)
                return
            except Exception:
                if attempt + 1 >= attempts:
                    raise
                await self._sleep(self._backoff_base_s * (2**attempt))
