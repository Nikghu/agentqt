"""
Module: MD-INF-010.001.M08 — gui/telegram_token_store.py
Parent SRD: SRD-INF-010.011

Stores each user's Telegram bot token in the OS keychain (Windows Credential
Manager / macOS Keychain / Secret Service). The token is a secret and must never
be written to ``users.json`` — see the credential rule in ``gui/user_store.py``.
Mirrors the pattern in ``screener/screeners/_api_key_store.py``.
"""
from __future__ import annotations

import logging
from typing import Final

_log = logging.getLogger(__name__)

_SERVICE: Final[str] = "usswing_telegram"


def save(user_id: int, token: str) -> None:
    """Persist *token* for *user_id*, or delete the entry when *token* is blank."""
    try:
        import keyring
    except ImportError:
        _log.warning("[Notify] keyring not installed; Telegram token not persisted")
        return

    username = str(user_id)
    if token:
        keyring.set_password(_SERVICE, username, token)
    else:
        try:
            keyring.delete_password(_SERVICE, username)
        except Exception:
            pass


def load(user_id: int) -> str:
    """Return the stored token for *user_id*, or an empty string if none."""
    try:
        import keyring
        token = keyring.get_password(_SERVICE, str(user_id))
        if token:
            return str(token)
    except Exception as exc:
        _log.debug("[Notify] keyring backend unavailable: %s", exc)
    return ""
