"""
Module: MD-GUI-004.001.M02 — gui/manual_picks_store.py
Parent SRD: SRD-GUI-004.010

Persists each user's manual picks — stocks added to Trade Execution by hand.

Storage location : ~/.usswing/manual_picks.json
Format           : {"version": 1, "users": {"<user_id>": ["TSLA", "AAPL"]}}
Write strategy   : atomic (write → tmp file → os.replace).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_STORE_FILE = Path.home() / ".usswing" / "manual_picks.json"


def _load_all() -> dict[str, list[str]]:
    try:
        data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        log.warning("[Execution] Could not read your manual picks — starting with none")
        return {}
    users = data.get("users") if isinstance(data, dict) else None
    if not isinstance(users, dict):
        return {}
    return {
        str(uid): [str(s) for s in syms]
        for uid, syms in users.items()
        if isinstance(syms, list)
    }


def load_manual_picks(user_id: str) -> list[str]:
    """Return the user's manual picks in the order they were added."""
    return _load_all().get(user_id, [])


def save_manual_picks(user_id: str, symbols: list[str]) -> None:
    """Replace the user's manual picks."""
    users = _load_all()
    users[user_id] = symbols
    _STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "users": users}, indent=2), encoding="utf-8")
    os.replace(tmp, _STORE_FILE)
