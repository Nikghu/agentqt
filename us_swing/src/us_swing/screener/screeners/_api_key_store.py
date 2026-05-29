"""
Module: MD-SCR-002.003.M06b — Cloud AI API key keyring store.
Parent SRD: SRD-SCR-013.005

Stores the OpenRouter API key in the OS keychain (Windows Credential
Manager / macOS Keychain / Secret Service).  Never serialized to disk
alongside presets.
"""
from __future__ import annotations

import logging
import os
from typing import Final

from us_swing.screener.screeners._cloud_ai_models import ENV_API_KEY

_log = logging.getLogger(__name__)

_SERVICE: Final[str] = "usswing_cloud_ai"
_USER:    Final[str] = "openrouter"


def save(api_key: str) -> None:
    """Persist *api_key* to the OS keychain, or delete the entry if empty."""
    try:
        import keyring  # type: ignore[import-untyped]
    except ImportError:
        _log.warning("keyring not installed; API key not persisted.")
        return

    if api_key:
        keyring.set_password(_SERVICE, _USER, api_key)
    else:
        try:
            keyring.delete_password(_SERVICE, _USER)
        except Exception:
            pass


def load() -> str:
    """Return the stored key: env var takes priority, then keychain, then empty string."""
    if env_key := os.environ.get(ENV_API_KEY, ""):
        return env_key
    try:
        import keyring  # type: ignore[import-untyped]
        if (key := keyring.get_password(_SERVICE, _USER)):
            return key
    except Exception as exc:
        _log.debug("keyring backend unavailable: %s", exc)
    return ""


def has_key() -> bool:
    return bool(load())
