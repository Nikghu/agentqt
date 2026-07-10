"""
Module: MD-INF-010.001.M06 — core/notifications/_dto.py
Parent SRD: SRD-INF-010.006

Frozen data containers for the notification service plus the per-user config
loader. Config lives in the existing user ``settings_json`` (FO-INF-006); this
module only parses it — it owns no separate store.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    """A rendered, channel-ready message. ``event_kind`` is the source event's
    type name, used for per-event routing and toggles."""

    text: str
    event_kind: str


@dataclass(frozen=True, slots=True)
class NotificationConfig:
    """Per-user notification settings parsed from ``settings_json``."""

    telegram_enabled: bool
    bot_token: str
    chat_id: str
    event_toggles: Mapping[str, bool]


def load_config(settings_json: Mapping[str, Any]) -> NotificationConfig:
    """Parse a user's ``settings_json`` into a :class:`NotificationConfig`.

    Telegram is treated as disabled unless it is explicitly enabled *and* both a
    non-blank bot token and chat id are present — a half-configured channel can
    never deliver, so it is reported as off rather than failing later.

    Args:
        settings_json: The user profile's raw settings mapping.

    Returns:
        A frozen :class:`NotificationConfig`.
    """
    notifications = settings_json.get("notifications") or {}
    telegram = notifications.get("telegram") or {}

    bot_token = str(telegram.get("bot_token") or "").strip()
    chat_id = str(telegram.get("chat_id") or "").strip()
    enabled = bool(telegram.get("enabled")) and bool(bot_token) and bool(chat_id)

    toggles = {str(k): bool(v) for k, v in (notifications.get("events") or {}).items()}

    return NotificationConfig(
        telegram_enabled=enabled,
        bot_token=bot_token,
        chat_id=chat_id,
        event_toggles=toggles,
    )
