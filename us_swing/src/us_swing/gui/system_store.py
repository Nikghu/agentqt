"""
Module: system_store.py — persistent JSON storage for system/connection config.

Storage location : ~/.usswing/system.json
Write strategy   : atomic (write → tmp file → Path.replace)

Security note    : This file holds only connectivity config (host, port, log level,
                   scheduler times).  Broker credentials / API keys MUST be stored
                   via the OS keychain (keyring package) — NOT here.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

# ── Storage path ──────────────────────────────────────────────────────────────

_APP_DIR    = Path.home() / ".usswing"
_STORE_FILE = _APP_DIR / "system.json"


# ── Config dataclass ──────────────────────────────────────────────────────────

@dataclass
class SystemConfig:
    ibkr_host: str       = "127.0.0.1"
    ibkr_port: int       = 7497
    ibkr_system_client_id: int = 10
    ibkr_enabled: bool   = False
    ibkr_intraday_client_id: int = 12
    ibkr_live_client_id: int     = 13
    log_level: str       = "INFO"
    scheduler_enabled: bool = False
    market_open: str     = "09:35"
    market_close: str    = "15:55"
    market_timezone: str = "US/Eastern"
    benchmark_symbol: str = "SPY"


# ── Public API ────────────────────────────────────────────────────────────────

def load_system_config() -> SystemConfig:
    """Load config from disk.  Returns defaults if file is missing or corrupt."""
    if not _STORE_FILE.exists():
        return SystemConfig()
    try:
        data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return SystemConfig()
        cfg = SystemConfig()
        cfg.ibkr_host                = str(data.get("ibkr_host",                cfg.ibkr_host))
        cfg.ibkr_port                = int(data.get("ibkr_port",                cfg.ibkr_port))
        cfg.ibkr_system_client_id    = int(data.get("ibkr_system_client_id",    cfg.ibkr_system_client_id))
        cfg.ibkr_enabled             = bool(data.get("ibkr_enabled",            cfg.ibkr_enabled))
        cfg.ibkr_intraday_client_id  = int(data.get("ibkr_intraday_client_id",  cfg.ibkr_intraday_client_id))
        cfg.ibkr_live_client_id      = int(data.get("ibkr_live_client_id",      cfg.ibkr_live_client_id))
        cfg.log_level              = str(data.get("log_level",              cfg.log_level))
        cfg.scheduler_enabled = bool(data.get("scheduler_enabled", cfg.scheduler_enabled))
        cfg.market_open       = str(data.get("market_open",       cfg.market_open))
        cfg.market_close      = str(data.get("market_close",      cfg.market_close))
        cfg.market_timezone   = str(data.get("market_timezone",   cfg.market_timezone))
        cfg.benchmark_symbol  = str(data.get("benchmark_symbol",  cfg.benchmark_symbol)).upper().strip() or "SPY"
        return cfg
    except (json.JSONDecodeError, TypeError, ValueError):
        return SystemConfig()


def save_system_config(cfg: SystemConfig) -> None:
    """Persist config atomically."""
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(asdict(cfg), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(_STORE_FILE)


# ── Market Hours Helpers ──────────────────────────────────────────────────────

def is_market_open(cfg: SystemConfig) -> bool:
    """Check if the market is currently open based on market_open/close times and timezone.

    Compares current time in the specified timezone against market hours.
    Assumes market_open and market_close are in HH:MM format (24-hour).

    Args:
        cfg: SystemConfig with market_open, market_close, and market_timezone

    Returns:
        True if current time in market_timezone is within market hours, False otherwise.
    """
    try:
        from datetime import datetime
        import zoneinfo
    except ImportError:
        # Fallback for Python < 3.9 (shouldn't happen with Python 3.11+)
        return False

    try:
        tz = zoneinfo.ZoneInfo(cfg.market_timezone)
        now = datetime.now(tz)

        # Parse market hours
        open_h, open_m = map(int, cfg.market_open.split(":"))
        close_h, close_m = map(int, cfg.market_close.split(":"))

        now_mins = now.hour * 60 + now.minute
        open_mins = open_h * 60 + open_m
        close_mins = close_h * 60 + close_m

        # Check if within market hours (ignoring weekends; caller should handle that if needed)
        return open_mins <= now_mins < close_mins
    except (ValueError, zoneinfo.ZoneInfoNotFoundError):
        return False
