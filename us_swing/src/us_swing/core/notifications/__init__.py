"""
Module: MD-INF-010.001.M07 — core/notifications/__init__.py
Parent SRD: SRD-INF-010.008

Public surface of the notification package. Producers import the event classes
and publish through the ``NotificationBus`` returned by the factory; they never
import the dispatcher or any channel. Concrete classes (``_InProcessBus``,
``NotificationDispatcher``, ``TelegramChannel``) are deliberately not
re-exported — type against the Protocols and build via ``build_default_dispatcher``.
"""
from __future__ import annotations

import httpx

from us_swing.core.notifications._dispatcher import NotificationDispatcher
from us_swing.core.notifications._dto import (
    NotificationConfig,
    NotificationMessage,
    load_config,
)
from us_swing.core.notifications._events import (
    DayEndPnLEvent,
    NotificationEvent,
    ScreenerApprovedEvent,
    ToolStartedEvent,
    _InProcessBus,
)
from us_swing.core.notifications._formatters import FormatterRegistry, default_registry
from us_swing.core.notifications._inbound import CommandRouter, TelegramPoller
from us_swing.core.notifications._protocols import (
    CommandPort,
    NotificationBus,
    NotificationChannel,
)
from us_swing.core.notifications._telegram import TelegramChannel


def build_default_dispatcher(
    config: NotificationConfig,
    *,
    http: httpx.AsyncClient | None = None,
    registry: FormatterRegistry | None = None,
    bus: NotificationBus | None = None,
) -> tuple[NotificationDispatcher, NotificationBus]:
    """Wire a dispatcher and bus from a user's notification config.

    Only the channels the config enables are attached. When Telegram is
    disabled the dispatcher has no channels and publishing is a safe no-op.

    Args:
        config: Parsed per-user notification settings.
        http: An ``httpx.AsyncClient`` — required only when Telegram is enabled.
        registry: Formatter registry; defaults to the built-in one.
        bus: Event bus; defaults to a fresh in-process bus.

    Returns:
        ``(dispatcher, bus)`` — producers publish events on the bus; the caller
        runs ``dispatcher.run()`` as a background task to deliver them.
    """
    resolved_bus = bus if bus is not None else _InProcessBus()
    resolved_registry = registry if registry is not None else default_registry()

    channels: list[NotificationChannel] = []
    if config.telegram_enabled:
        if http is None:
            raise ValueError("An httpx.AsyncClient is required when Telegram is enabled")
        channels.append(TelegramChannel(config.bot_token, config.chat_id, http))

    dispatcher = NotificationDispatcher(
        resolved_bus, channels, resolved_registry, event_toggles=config.event_toggles
    )
    return dispatcher, resolved_bus


def build_command_poller(
    config: NotificationConfig,
    http: httpx.AsyncClient,
    port: CommandPort | None,
) -> TelegramPoller | None:
    """Build the inbound command poller, or ``None`` when it cannot run.

    Returns ``None`` if Telegram is disabled or no ``CommandPort`` is supplied —
    inbound commands simply stay off, exactly like a dispatcher with no channels.

    Args:
        config: Parsed per-user notification settings.
        http: The shared ``httpx.AsyncClient`` used for Telegram calls.
        port: The read-only query surface answering each command.

    Returns:
        A ready :class:`TelegramPoller`, or ``None``.
    """
    if not config.telegram_enabled or port is None:
        return None
    router = CommandRouter(port)
    return TelegramPoller(config.bot_token, config.chat_id, http, router)


__all__ = [
    # Protocols
    "NotificationChannel",
    "NotificationBus",
    "CommandPort",
    # Events
    "NotificationEvent",
    "ToolStartedEvent",
    "ScreenerApprovedEvent",
    "DayEndPnLEvent",
    # DTOs
    "NotificationMessage",
    "NotificationConfig",
    "load_config",
    # Formatters
    "FormatterRegistry",
    "default_registry",
    # Inbound commands
    "CommandRouter",
    "TelegramPoller",
    # Factory
    "build_default_dispatcher",
    "build_command_poller",
]
