"""
Module: MD-GUI-000.003 — scheduler_store.py
Parent SRD: SRD-GUI-006.005

Persistent JSON storage for the Windows Task Scheduler config.
Storage: ~/.usswing/scheduler.json  (atomic write, same pattern as system_store)

Two independent tasks are stored under top-level keys "usswing" and "ibkr".
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

_APP_DIR    = Path.home() / ".usswing"
_STORE_FILE = _APP_DIR / "scheduler.json"

_USSWING_EXE_DEFAULT = r"C:\Program Files (x86)\USSwing\USSwing.exe"


@dataclass
class USSwingConfig:
    task_name:   str = "USSwing_App"
    exe_path:    str = _USSWING_EXE_DEFAULT
    launch_time: str = "09:00"
    days:        str = "weekdays"   # "weekdays" | "daily"


@dataclass
class SchedulerConfig:
    """Trader Workstation scheduled task config."""
    task_name:     str  = "USSwing_IBKR"
    exe_path:      str  = ""
    launch_time:   str  = "09:00"
    days:          str  = "weekdays"   # "weekdays" | "daily"
    ibkr_username: str  = ""
    auto_login:    bool = False


@dataclass
class CloseConfig:
    """Shared auto-close config for both scheduled apps."""
    enabled:    bool = False
    close_time: str  = "16:30"


# ── Load ──────────────────────────────────────────────────────────────────────

def _load_raw() -> dict[str, object]:
    if not _STORE_FILE.exists():
        return {}
    try:
        data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def load_usswing_config() -> USSwingConfig | None:
    """Return saved USSwing config, or None if not yet configured."""
    raw = _load_raw()
    section = raw.get("usswing")
    if not isinstance(section, dict):
        return None
    cfg = USSwingConfig()
    cfg.task_name   = str(section.get("task_name",   cfg.task_name))
    cfg.exe_path    = str(section.get("exe_path",    cfg.exe_path))
    cfg.launch_time = str(section.get("launch_time", cfg.launch_time))
    cfg.days        = str(section.get("days",        cfg.days))
    return cfg


def load_scheduler_config() -> SchedulerConfig | None:
    """Return saved IBKR config, or None if not yet configured."""
    raw = _load_raw()
    section = raw.get("ibkr")

    # Backward-compat: old flat-key format (no "ibkr" sub-key)
    if not isinstance(section, dict) and "task_name" in raw:
        section = raw

    if not isinstance(section, dict):
        return None
    cfg = SchedulerConfig()
    cfg.task_name     = str(section.get("task_name",     cfg.task_name))
    cfg.exe_path      = str(section.get("exe_path",      cfg.exe_path))
    cfg.launch_time   = str(section.get("launch_time",   cfg.launch_time))
    cfg.days          = str(section.get("days",          cfg.days))
    cfg.ibkr_username = str(section.get("ibkr_username", cfg.ibkr_username))
    cfg.auto_login    = bool(section.get("auto_login",   cfg.auto_login))
    return cfg


def load_close_config() -> CloseConfig:
    """Return the saved shared auto-close config, or defaults if unset."""
    raw = _load_raw()
    section = raw.get("close")
    cfg = CloseConfig()
    if isinstance(section, dict):
        cfg.enabled    = bool(section.get("enabled",    cfg.enabled))
        cfg.close_time = str(section.get("close_time",  cfg.close_time))
    return cfg


# ── Save / Delete ─────────────────────────────────────────────────────────────

def _save_raw(data: dict[str, object]) -> None:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(_STORE_FILE)


def save_usswing_config(cfg: USSwingConfig) -> None:
    raw = _load_raw()
    raw.pop("task_name", None)   # remove old flat-key format if present
    raw["usswing"] = asdict(cfg)
    _save_raw(raw)


def save_scheduler_config(cfg: SchedulerConfig) -> None:
    raw = _load_raw()
    raw.pop("task_name", None)   # remove old flat-key format if present
    raw["ibkr"] = asdict(cfg)
    _save_raw(raw)


def save_close_config(cfg: CloseConfig) -> None:
    raw = _load_raw()
    raw["close"] = asdict(cfg)
    _save_raw(raw)


def delete_close_config() -> None:
    raw = _load_raw()
    raw.pop("close", None)
    _save_raw(raw)


def delete_usswing_config() -> None:
    raw = _load_raw()
    raw.pop("usswing", None)
    _save_raw(raw)


def delete_scheduler_config() -> None:
    raw = _load_raw()
    raw.pop("ibkr", None)
    raw.pop("task_name", None)   # old flat-key cleanup
    _save_raw(raw)
