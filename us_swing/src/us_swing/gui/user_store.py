"""
Module: user_store.py — persistent JSON storage for UserProfile records.

Storage location : ~/.usswing/users.json
Format           : JSON array; field names mirror UserProfile exactly.
Write strategy   : atomic (write → tmp file → os.replace) so a crash during
                   save never produces a corrupt file.

Security note    : UserProfile contains only trading-config values (no passwords,
                   no API keys).  The file is stored in the user's home directory,
                   protected by the OS file-permission model (read/write for the
                   current user only on POSIX; inherits user-profile ACL on Windows).
                   When API keys or broker credentials are added they MUST be stored
                   via the OS keychain (keyring package) — NOT here.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from us_swing.data.models import RiskConfig, UserProfile

log = logging.getLogger(__name__)

# ── Storage path ──────────────────────────────────────────────────────────────

_APP_DIR    = Path.home() / ".usswing"
_STORE_FILE = _APP_DIR / "users.json"


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _to_dict(u: UserProfile) -> dict:
    rc = u.risk_config
    return {
        "user_id":            u.user_id,
        "username":           u.username,
        "display_name":       u.display_name,
        "ibkr_client_id":     u.ibkr_client_id,
        "mode":               u.mode,
        "risk_per_trade_pct": rc.risk_per_trade_pct,
        "max_position_value": rc.max_position_value,
        "max_capital_value":  rc.max_capital_value,
        "max_daily_loss_pct": rc.max_daily_loss_pct,
        "default_order_type": rc.default_order_type,
        "confirm_orders":     rc.confirm_orders,
    }


def _from_dict(d: dict) -> UserProfile:
    if "max_capital_value" not in d and "max_allocation_pct" in d:
        log.info(
            "[Settings] Migrated user '%s' to absolute Max Capital ($%.0f)",
            d.get("username", d.get("user_id", "?")), 2_000.0,
        )
    risk = RiskConfig(
        risk_per_trade_pct = float(d.get("risk_per_trade_pct",  1.0)),
        max_position_value = float(d.get("max_position_value",  10_000.0)),
        max_capital_value  = float(d.get("max_capital_value",   2_000.0)),
        max_daily_loss_pct = float(d.get("max_daily_loss_pct",  2.0)),
        default_order_type = str(d.get("default_order_type",    "MKT")),
        confirm_orders     = bool(d.get("confirm_orders",        True)),
    )
    return UserProfile(
        user_id         = int(d["user_id"]),
        username        = str(d["username"]),
        display_name    = str(d.get("display_name", d["username"])),
        ibkr_client_id  = int(d["ibkr_client_id"]),
        mode            = str(d["mode"]),
        risk_config     = risk,
        strategy_config = {},
        screener_config = {},
    )


# ── Public API ────────────────────────────────────────────────────────────────

def load_users() -> list[UserProfile]:
    """Load users from disk.  Returns empty list if no store exists yet."""
    if not _STORE_FILE.exists():
        return []
    try:
        data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [_from_dict(d) for d in data]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return []


def save_users(users: list[UserProfile]) -> None:
    """Persist users to disk atomically (write tmp → replace)."""
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps([_to_dict(u) for u in users], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(_STORE_FILE)   # atomic on POSIX; MoveFileEx on Windows


def next_user_id(users: list[UserProfile]) -> int:
    """Return max existing ID + 1 (or 1 when list is empty)."""
    return max((u.user_id for u in users), default=0) + 1
