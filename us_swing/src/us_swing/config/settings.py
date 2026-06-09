"""Module: MD-INF-001.001.M03 — config/settings.py
Parent SRD: SRD-INF-001.001, SRD-INF-004.006, SRD-INF-005.001, SRD-INF-006.007

All application configuration dataclasses with environment-variable and
TOML-file loading.  Single entry-point: ``load_config() -> AppConfig``.

Load order (later sources win):
    1. Dataclass defaults
    2. ``us_swing.toml`` in the current working directory (if present)
    3. Environment variables (``USSWING_*`` prefix)
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


# ── Sub-configs ───────────────────────────────────────────────────────────────

@dataclass
class BrokerConfig:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1
    connect_timeout_s: float = 5.0
    max_reconnect_attempts: int = 10
    max_disconnect_minutes: int = 5


@dataclass
class DataConfig:
    provider: str = "dummy"          # "ibkr" | "dummy"
    intraday_retention_days: int = 5
    daily_retention_years: int = 1
    max_concurrent_bootstrap: int = 5


@dataclass
class UniverseConfig:
    refresh_interval_days: int = 7
    source_url: str = (
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    )


@dataclass
class RiskConfig:
    risk_per_trade_pct: float = 1.0
    max_position_value: float = 10_000.0
    max_capital_value:  float = 2_000.0
    max_daily_loss_pct: float = 2.0
    default_order_type: str = "MKT"


@dataclass
class LogConfig:
    level: str = "INFO"         # overridden by LOG_LEVEL env var
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    retention_days: int = 30
    alert_webhook_url: str = ""


@dataclass
class DatabaseConfig:
    url: str = "sqlite:///./data/us_swing.db"


@dataclass
class AppConfig:
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    data: DataConfig = field(default_factory=DataConfig)
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    log: LogConfig = field(default_factory=LogConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    # Phase 0: paper-only. Set to True only when IBKR live connectivity is
    # certified and tested. Guards UserManager.switch_mode() to 'live'.
    live_mode_enabled: bool = False


# ── Loaders ───────────────────────────────────────────────────────────────────

def _apply_toml(cfg: AppConfig, path: Path) -> None:
    """Overlay cfg in-place from a TOML file (best-effort; ignores unknown keys)."""
    with path.open("rb") as fh:
        raw: dict = tomllib.load(fh)

    b = raw.get("broker", {})
    cfg.broker.host = str(b.get("host", cfg.broker.host))
    cfg.broker.port = int(b.get("port", cfg.broker.port))
    cfg.broker.client_id = int(b.get("client_id", cfg.broker.client_id))
    cfg.broker.connect_timeout_s = float(b.get("connect_timeout_s", cfg.broker.connect_timeout_s))
    cfg.broker.max_reconnect_attempts = int(b.get("max_reconnect_attempts", cfg.broker.max_reconnect_attempts))
    cfg.broker.max_disconnect_minutes = int(b.get("max_disconnect_minutes", cfg.broker.max_disconnect_minutes))

    d = raw.get("data", {})
    cfg.data.provider = str(d.get("provider", cfg.data.provider))
    cfg.data.intraday_retention_days = int(d.get("intraday_retention_days", cfg.data.intraday_retention_days))
    cfg.data.daily_retention_years = int(d.get("daily_retention_years", cfg.data.daily_retention_years))
    cfg.data.max_concurrent_bootstrap = int(d.get("max_concurrent_bootstrap", cfg.data.max_concurrent_bootstrap))

    u = raw.get("universe", {})
    cfg.universe.refresh_interval_days = int(u.get("refresh_interval_days", cfg.universe.refresh_interval_days))
    cfg.universe.source_url = str(u.get("source_url", cfg.universe.source_url))

    r = raw.get("risk", {})
    cfg.risk.risk_per_trade_pct = float(r.get("risk_per_trade_pct", cfg.risk.risk_per_trade_pct))
    cfg.risk.max_position_value = float(r.get("max_position_value", cfg.risk.max_position_value))
    cfg.risk.max_capital_value = float(r.get("max_capital_value", cfg.risk.max_capital_value))
    cfg.risk.max_daily_loss_pct = float(r.get("max_daily_loss_pct", cfg.risk.max_daily_loss_pct))
    cfg.risk.default_order_type = str(r.get("default_order_type", cfg.risk.default_order_type))

    lo = raw.get("log", {})
    cfg.log.level = str(lo.get("level", cfg.log.level))
    if "log_dir" in lo:
        cfg.log.log_dir = Path(str(lo["log_dir"]))
    cfg.log.retention_days = int(lo.get("retention_days", cfg.log.retention_days))
    cfg.log.alert_webhook_url = str(lo.get("alert_webhook_url", cfg.log.alert_webhook_url))

    db = raw.get("database", {})
    cfg.database.url = str(db.get("url", cfg.database.url))

    cfg.live_mode_enabled = bool(raw.get("live_mode_enabled", cfg.live_mode_enabled))


def _apply_env(cfg: AppConfig) -> None:
    """Overlay cfg in-place from ``USSWING_*`` environment variables."""
    env = os.environ

    if v := env.get("USSWING_IBKR_HOST"):
        cfg.broker.host = v
    if v := env.get("USSWING_IBKR_PORT"):
        cfg.broker.port = int(v)
    if v := env.get("USSWING_CLIENT_ID"):
        cfg.broker.client_id = int(v)
    if v := env.get("USSWING_DATA_PROVIDER"):
        cfg.data.provider = v
    if v := env.get("DATABASE_URL"):
        cfg.database.url = v
    if v := env.get("LOG_LEVEL"):
        cfg.log.level = v
    if v := env.get("USSWING_LIVE_MODE"):
        cfg.live_mode_enabled = v.lower() in {"1", "true", "yes"}


def load_config(toml_path: Path | None = None) -> AppConfig:
    """Build ``AppConfig`` from defaults → TOML → environment variables.

    Args:
        toml_path: Explicit path to a TOML config file.  When ``None``,
            looks for ``us_swing.toml`` in the current working directory.

    Returns:
        Fully populated :class:`AppConfig`.
    """
    cfg = AppConfig()

    resolved = toml_path or Path("us_swing.toml")
    if resolved.exists():
        _apply_toml(cfg, resolved)

    _apply_env(cfg)
    return cfg
