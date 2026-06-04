"""
Module: MD-GUI-013.002.M01 — strategy_store.py (DB-backed strategy registry)
Parent SRD: pending (strategies.json → SQLite migration)

Single source of truth for strategy configuration.  Replaces the legacy
``~/.usswing/strategies.json`` file with a ``strategies`` table in the shared
``~/.usswing/candles.db`` SQLite database.

Per-trade runtime state is NOT stored here — it lives in ``trade_cycles``.
The only dynamic field kept on a strategy is ``run_state``.  List-valued
config (``days``, ``symbols_include``, ``symbols_exclude``) is JSON-encoded
in a single TEXT column each; promote to a child table only if a query like
"all strategies trading AAPL" is ever needed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Engine, create_engine

from us_swing.db.schema import metadata

_DB_PATH: Path = Path.home() / ".usswing" / "candles.db"


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class StrategyConfig:
    name: str
    mode: str
    capital_max: int
    start_time: str
    end_time: str
    start_date: str
    end_date: str
    days: list[str]
    entry_condition: str
    exit_condition: str
    strategy_type: str = ""
    symbol_mode: str = "all"
    symbols_include: list[str] = field(default_factory=list)
    symbols_exclude: list[str] = field(default_factory=list)
    target_enabled: bool = False
    target_type: str = "fixed"
    target_value: float = 2.0
    stoploss_enabled: bool = False
    stoploss_type: str = "fixed"
    stoploss_value: float = 1.0
    auto_trade: bool = False
    trade_type: str = "Intraday"
    minute_close: int = 1
    execution_rate_sec: int = 1
    rex_count: int = 0
    run_state: str = "STOPPED"


# ── Schema ────────────────────────────────────────────────────────────────────

strategies = sa.Table(
    "strategies",
    metadata,
    sa.Column("name",               sa.Text,    primary_key=True),
    sa.Column("mode",               sa.Text,    nullable=False, server_default="manual"),
    sa.Column("capital_max",        sa.Integer, nullable=False, server_default="0"),
    sa.Column("start_time",         sa.Text,    nullable=False),
    sa.Column("end_time",           sa.Text,    nullable=False),
    sa.Column("start_date",         sa.Text,    nullable=False),
    sa.Column("end_date",           sa.Text,    nullable=False),
    sa.Column("days",               sa.Text,    nullable=False, server_default="[]"),
    sa.Column("entry_condition",    sa.Text,    nullable=False, server_default=""),
    sa.Column("exit_condition",     sa.Text,    nullable=False, server_default=""),
    sa.Column("strategy_type",      sa.Text,    nullable=False, server_default=""),
    sa.Column("symbol_mode",        sa.Text,    nullable=False, server_default="all"),
    sa.Column("symbols_include",    sa.Text,    nullable=False, server_default="[]"),
    sa.Column("symbols_exclude",    sa.Text,    nullable=False, server_default="[]"),
    sa.Column("target_enabled",     sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("target_type",        sa.Text,    nullable=False, server_default="fixed"),
    sa.Column("target_value",       sa.Float,   nullable=False, server_default="2"),
    sa.Column("stoploss_enabled",   sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("stoploss_type",      sa.Text,    nullable=False, server_default="fixed"),
    sa.Column("stoploss_value",     sa.Float,   nullable=False, server_default="1"),
    sa.Column("auto_trade",         sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("trade_type",         sa.Text,    nullable=False, server_default="Intraday"),
    sa.Column("minute_close",       sa.Integer, nullable=False, server_default="1"),
    sa.Column("execution_rate_sec", sa.Integer, nullable=False, server_default="1"),
    sa.Column("rex_count",          sa.Integer, nullable=False, server_default="0"),
    sa.Column("run_state",          sa.Text,    nullable=False, server_default="STOPPED"),
    sa.Column("updated_at",         sa.Text,    nullable=False),
)

_LIST_FIELDS = ("days", "symbols_include", "symbols_exclude")


# ── Engine (module-level, lazily bound to the shared candles.db) ──────────────

_engine_cache: Engine | None = None


def _engine() -> Engine:
    global _engine_cache
    if _engine_cache is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine_cache = create_engine(f"sqlite:///{_DB_PATH}", future=True)
        strategies.create(_engine_cache, checkfirst=True)
    return _engine_cache


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# ── Row ↔ StrategyConfig mapping (single source) ──────────────────────────────

def _cfg_to_values(cfg: StrategyConfig) -> dict[str, object]:
    values: dict[str, object] = {f.name: getattr(cfg, f.name) for f in fields(cfg)}
    for key in _LIST_FIELDS:
        values[key] = json.dumps(values[key])
    values["updated_at"] = _utcnow_iso()
    return values


def _row_to_cfg(row: sa.Row[Any]) -> StrategyConfig:
    data = dict(row._mapping)
    data.pop("updated_at", None)
    for key in _LIST_FIELDS:
        data[key] = json.loads(data[key]) if data.get(key) else []
    valid = {f.name for f in fields(StrategyConfig)}
    return StrategyConfig(**{k: v for k, v in data.items() if k in valid})


# ── Public API (drop-in replacements for the old json functions) ──────────────

def load_strategies() -> list[StrategyConfig]:
    """Return all configured strategies from the database.

    Persisted ``run_state`` is trusted verbatim.
    """
    engine = _engine()
    with engine.begin() as conn:
        rows = conn.execute(sa.select(strategies)).all()
    return [_row_to_cfg(r) for r in rows]


def save_strategies(configs: list[StrategyConfig]) -> None:
    """Persist the full strategy set, replacing the table contents atomically."""
    engine = _engine()
    with engine.begin() as conn:
        conn.execute(sa.delete(strategies))
        if configs:
            conn.execute(
                sa.insert(strategies),
                [_cfg_to_values(c) for c in configs],
            )


def set_run_state(name: str, run_state: str) -> None:
    """Update only the ``run_state`` of one strategy (targeted, single-writer)."""
    engine = _engine()
    with engine.begin() as conn:
        conn.execute(
            sa.update(strategies)
            .where(strategies.c.name == name)
            .values(run_state=run_state, updated_at=_utcnow_iso())
        )


__all__ = [
    "StrategyConfig",
    "strategies",
    "load_strategies",
    "save_strategies",
    "set_run_state",
]
