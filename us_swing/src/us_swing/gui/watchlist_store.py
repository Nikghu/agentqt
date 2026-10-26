"""
Module: MD-GUI-025.019.M05 — gui/watchlist_store.py
Parent SRD: SRD-GUI-025.019

Persists each user's saved stock lists — the watchlist and the Market Watch tile list.

Storage location : ~/.usswing/<list name>.json  (watchlist.json, market_watch.json)
Format           : {"version": 1, "users": {"<user_id>": ["TSLA", "AAPL"]}}
Write strategy   : atomic (write → tmp file → os.replace).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_STORE_DIR = Path.home() / ".usswing"

WATCHLIST = "watchlist"
MARKET_WATCH = "market_watch"


def _store_file(name: str) -> Path:
    return _STORE_DIR / f"{name}.json"


def _load_all(name: str) -> dict[str, list[str]]:
    try:
        data = json.loads(_store_file(name).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        log.warning("[Watchlist] Could not read your saved %s list — starting with none",
                    name.replace("_", " "))
        return {}
    users = data.get("users") if isinstance(data, dict) else None
    if not isinstance(users, dict):
        return {}
    return {
        str(uid): [str(s) for s in syms]
        for uid, syms in users.items()
        if isinstance(syms, list)
    }


def load_watchlist(user_id: str, name: str = WATCHLIST) -> list[str]:
    """Return the user's saved symbols for list ``name`` in the order they were added."""
    return _load_all(name).get(user_id, [])


def save_watchlist(user_id: str, symbols: list[str], name: str = WATCHLIST) -> None:
    """Replace the user's saved symbols for list ``name``."""
    users = _load_all(name)
    users[user_id] = symbols
    path = _store_file(name)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "users": users}, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        log.warning("[Watchlist] Could not save your %s list", name.replace("_", " "))
