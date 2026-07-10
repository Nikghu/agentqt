"""
Module: MD-INF-010.001.M10 — core/notifications/_inbound.py
Parent SRD: SRD-INF-010.012, SRD-INF-010.013, SRD-INF-010.014

Inbound two-way Telegram commands. ``TelegramPoller`` long-polls the Bot API
``getUpdates`` and ``CommandRouter`` maps a slash-command to a read-only query on
the injected :class:`CommandPort`. The router never imports the GUI — the port is
the only seam to live app state.
"""
from __future__ import annotations

import asyncio
import html
import logging
from typing import Any, Callable

import httpx

from us_swing.core.notifications._protocols import CommandPort
from us_swing.core.notifications._telegram import _API_BASE

log = logging.getLogger(__name__)

# Single source of truth for the inbound commands: drives both the /help reply
# and the setMyCommands registration, so the in-app help and the Telegram command
# menu can never drift apart.
_COMMANDS: tuple[tuple[str, str], ...] = (
    ("status", "Feed and market session"),
    ("pnl", "Profit and loss summary"),
    ("positions", "Open positions"),
    ("signals", "Pending trade signals"),
    ("screener", "Latest screener results"),
    ("cycles", "Open and recently closed trades"),
    ("help", "Show this list of commands"),
)

_HELP_TEXT = "🤖 <b>USSwing Bot</b>\n\n" + "\n".join(
    f"/{name} — {desc.lower()}" for name, desc in _COMMANDS
)


def _parse_command(text: str) -> str | None:
    """Extract the normalized command name from a message.

    Returns the lowercased command without its leading ``/`` or trailing
    ``@botname``, or ``None`` when the text is not a slash-command.
    """
    text = text.strip()
    if not text.startswith("/"):
        return None
    token = text[1:].split()[0] if len(text) > 1 else ""
    token = token.split("@", 1)[0].lower()
    return token or None


class CommandRouter:
    """Maps a parsed command to a :class:`CommandPort` query and returns a reply."""

    __slots__ = ("_table",)

    def __init__(self, port: CommandPort) -> None:
        self._table: dict[str, Callable[[], str]] = {
            "status": port.status,
            "pnl": port.pnl,
            "positions": port.positions,
            "signals": port.signals,
            "screener": port.screener,
            "cycles": port.cycles,
        }

    def route(self, text: str) -> str | None:
        """Return the reply for a message, or ``None`` if it is not a command.

        An unknown command returns a help hint; a handler that raises is caught
        and answered with a plain apology so a stack trace never reaches the user.
        """
        command = _parse_command(text)
        if command is None:
            return None
        if command == "help":
            return _HELP_TEXT
        handler = self._table.get(command)
        if handler is None:
            safe = html.escape(command, quote=False)
            return f"Unknown command /{safe} — send /help for the list of commands"
        try:
            return handler()
        except Exception:
            log.exception("[Notify] Command /%s failed", command)
            return "Sorry, that command could not be completed right now"


class TelegramPoller:
    """Long-polls Telegram ``getUpdates`` and answers authorized commands."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        http: httpx.AsyncClient,
        router: CommandRouter,
        *,
        poll_timeout_s: int = 25,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._http = http
        self._router = router
        self._poll_timeout_s = poll_timeout_s

    async def run(self) -> None:
        """Poll forever, handling each batch of updates. Runs until cancelled."""
        await self._register_commands()
        offset = 0
        while True:
            try:
                updates = await self._get_updates(offset)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("[Notify] Inbound command polling failed; will retry")
                await asyncio.sleep(self._poll_timeout_s)
                continue
            offset = await self._process(updates, offset)

    async def _process(self, updates: list[dict[str, Any]], offset: int) -> int:
        """Handle a batch of updates and return the next offset to request."""
        loop = asyncio.get_running_loop()
        for update in updates:
            offset = int(update.get("update_id", offset - 1)) + 1
            message = update.get("message") or {}
            text = str(message.get("text") or "").strip()
            if not text:
                continue
            sender = str((message.get("chat") or {}).get("id", ""))
            if sender != self._chat_id:
                log.warning("[Notify] Ignoring an inbound command from an unauthorized chat")
                continue
            reply = await loop.run_in_executor(None, self._router.route, text)
            if reply:
                await self._send(reply)
        return offset

    async def _register_commands(self) -> None:
        """Publish the command list to Telegram so the chat shows a command menu.

        Best-effort: on failure the user only misses the tap-to-run menu and
        autocomplete, so it is logged and never stops the poll loop.
        """
        url = f"{_API_BASE}/bot{self._bot_token}/setMyCommands"
        commands = [{"command": name, "description": desc} for name, desc in _COMMANDS]
        try:
            response = await self._http.post(url, json={"commands": commands})
            response.raise_for_status()
            log.info("[Notify] Registered %d Telegram command(s)", len(commands))
        except Exception:
            log.warning("[Notify] Could not register the Telegram command menu")

    async def _get_updates(self, offset: int) -> list[dict[str, Any]]:
        url = f"{_API_BASE}/bot{self._bot_token}/getUpdates"
        response = await self._http.get(
            url,
            params={"offset": offset, "timeout": self._poll_timeout_s},
            timeout=self._poll_timeout_s + 10,
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") or []
        return list(result)

    async def _send(self, text: str) -> None:
        url = f"{_API_BASE}/bot{self._bot_token}/sendMessage"
        response = await self._http.post(
            url,
            json={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"},
        )
        response.raise_for_status()
