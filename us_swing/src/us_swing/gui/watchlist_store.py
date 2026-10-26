"""
Module: MD-GUI-025.019.M05 — gui/watchlist_store.py
Parent SRD: SRD-GUI-025.019

Persists each user's watchlist — stocks added to the Dashboard watchlist by hand.

Storage location : ~/.usswing/watchlist.json
Format           : {"version": 1, "users": {"<user_id>": ["TSLA", "AAPL"]}}
Write strategy   : atomic (write → tmp file → os.replace).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_STORE_FILE = Path.home() / ".usswing" / "watchlist.json"


def _load_all() -> dict[str, list[str]]:
    try:
        data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        log.warning("[Watchlist] Could not read your saved watchlist — starting with none")
        return {}
    users = data.get("users") if isinstance(data, dict) else None
    if not isinstance(users, dict):
        return {}
    return {
        str(uid): [str(s) for s in syms]
        for uid, syms in users.items()
        if isinstance(syms, list)
    }


def load_watchlist(user_id: str) -> list[str]:
    """Return the user's watchlist symbols in the order they were added."""
    return _load_all().get(user_id, [])


def save_watchlist(user_id: str, symbols: list[str]) -> None:
    """Replace the user's watchlist."""
    users = _load_all()
    users[user_id] = symbols
    try:
        _STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STORE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "users": users}, indent=2), encoding="utf-8")
        os.replace(tmp, _STORE_FILE)
    except OSError:
        log.warning("[Watchlist] Could not save your watchlist")
