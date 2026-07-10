"""
Module: MD-INF-010.001.M03 — core/notifications/_telegram.py
Parent SRD: SRD-INF-010.003

The first concrete :class:`NotificationChannel`. Delivers messages through the
Telegram Bot API over HTTP — no heavy Telegram SDK, just an injected
``httpx.AsyncClient`` so transport is swappable and testable.
"""
from __future__ import annotations

import httpx

from us_swing.core.notifications._dto import NotificationMessage

_API_BASE = "https://api.telegram.org"


class TelegramChannel:
    """Sends notifications to one Telegram chat via ``sendMessage``."""

    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str, http: httpx.AsyncClient) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._http = http

    async def send(self, message: NotificationMessage) -> None:
        """POST the message text to the configured chat.

        Raises ``httpx.HTTPStatusError`` on a non-2xx response so the dispatcher
        can isolate, log, and retry the failure.
        """
        url = f"{_API_BASE}/bot{self._bot_token}/sendMessage"
        response = await self._http.post(
            url,
            json={"chat_id": self._chat_id, "text": message.text},
        )
        response.raise_for_status()
