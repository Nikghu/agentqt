"""Module: MD-INF-004.001.M02 — db/schema.py
Parent SRD: SRD-INF-004.001, SRD-INF-004.002

SQLAlchemy Core table definitions and schema helpers.
Supports SQLite (dev) and PostgreSQL (prod) identically.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import MetaData

metadata = MetaData()

# ── Tables ────────────────────────────────────────────────────────────────────

universe = sa.Table(
    "universe",
    metadata,
    sa.Column("symbol", sa.Text, primary_key=True),
    sa.Column("name",   sa.Text, nullable=False),
    sa.Column("sector", sa.Text, nullable=False),
)

price_1m = sa.Table(
    "price_1m",
    metadata,
    sa.Column("symbol",   sa.Text,    nullable=False),
    sa.Column("datetime", sa.Text,    nullable=False),   # ISO 8601 UTC string
    sa.Column("open",     sa.Float),
    sa.Column("high",     sa.Float),
    sa.Column("low",      sa.Float),
    sa.Column("close",    sa.Float),
    sa.Column("volume",   sa.Integer),
    sa.PrimaryKeyConstraint("symbol", "datetime"),
)

price_3m = sa.Table(
    "price_3m",
    metadata,
    sa.Column("symbol",   sa.Text,    nullable=False),
    sa.Column("datetime", sa.Text,    nullable=False),
    sa.Column("open",     sa.Float),
    sa.Column("high",     sa.Float),
    sa.Column("low",      sa.Float),
    sa.Column("close",    sa.Float),
    sa.Column("volume",   sa.Integer),
    sa.PrimaryKeyConstraint("symbol", "datetime"),
)

price_15m = sa.Table(
    "price_15m",
    metadata,
    sa.Column("symbol",   sa.Text,    nullable=False),
    sa.Column("datetime", sa.Text,    nullable=False),
    sa.Column("open",     sa.Float),
    sa.Column("high",     sa.Float),
    sa.Column("low",      sa.Float),
    sa.Column("close",    sa.Float),
    sa.Column("volume",   sa.Integer),
    sa.PrimaryKeyConstraint("symbol", "datetime"),
)

price_1d = sa.Table(
    "price_1d",
    metadata,
    sa.Column("symbol",   sa.Text,    nullable=False),
    sa.Column("datetime", sa.Text,    nullable=False),
    sa.Column("open",     sa.Float),
    sa.Column("high",     sa.Float),
    sa.Column("low",      sa.Float),
    sa.Column("close",    sa.Float),
    sa.Column("volume",   sa.Integer),
    sa.PrimaryKeyConstraint("symbol", "datetime"),
)

price_1w = sa.Table(
    "price_1w",
    metadata,
    sa.Column("symbol",   sa.Text,    nullable=False),
    sa.Column("datetime", sa.Text,    nullable=False),
    sa.Column("open",     sa.Float),
    sa.Column("high",     sa.Float),
    sa.Column("low",      sa.Float),
    sa.Column("close",    sa.Float),
    sa.Column("volume",   sa.Integer),
    sa.PrimaryKeyConstraint("symbol", "datetime"),
)

watchlist = sa.Table(
    "watchlist",
    metadata,
    sa.Column("date",   sa.Text, nullable=False),
    sa.Column("symbol", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("date", "symbol"),
)

users = sa.Table(
    "users",
    metadata,
    sa.Column("user_id",        sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("username",       sa.Text,    nullable=False, unique=True),
    sa.Column("display_name",   sa.Text,    nullable=False),
    sa.Column("ibkr_client_id", sa.Integer, nullable=False, unique=True),
    sa.Column("settings_json",  sa.Text,    nullable=False, server_default="{}"),
    sa.Column("mode",           sa.Text,    nullable=False, server_default="paper"),
)

trades = sa.Table(
    "trades",
    metadata,
    sa.Column("trade_id",                sa.Text,    primary_key=True),
    sa.Column("user_id",                 sa.Integer, sa.ForeignKey("users.user_id"), nullable=False),
    sa.Column("symbol",                  sa.Text,    nullable=False),
    sa.Column("side",                    sa.Text),
    sa.Column("entry_time",              sa.Text),
    sa.Column("entry_price",             sa.Float),
    sa.Column("exit_time",               sa.Text),
    sa.Column("exit_price",              sa.Float),
    sa.Column("quantity",                sa.Integer),
    sa.Column("pnl",                     sa.Float),
    sa.Column("strategy_id",             sa.Text),
    sa.Column("mode",                    sa.Text,    nullable=False, server_default="paper"),
    sa.Column("status",                  sa.Text,    server_default="SUBMITTED"),
    sa.Column("trade_origin",            sa.Text),                                       # SRD-EXE-009.002
    sa.Column("monitoring_session_date", sa.Text),                                       # SRD-EXE-009.002
)

positions = sa.Table(
    "positions",
    metadata,
    sa.Column("symbol",              sa.Text,    nullable=False),
    sa.Column("user_id",             sa.Integer, sa.ForeignKey("users.user_id"), nullable=False),
    sa.Column("quantity",            sa.Integer),
    sa.Column("average_price",       sa.Float),
    sa.Column("stop_loss",           sa.Float),
    sa.Column("target_price",        sa.Float),
    sa.Column("trailing_stop",       sa.Float),
    sa.Column("mode",                sa.Text,    nullable=False, server_default="paper"),
    sa.Column("state",               sa.Text,    nullable=False, server_default="NEW"),
    sa.Column("origin",              sa.Text),                                           # SRD-EXE-009.003
    sa.Column("anchor_session_date", sa.Text),                                           # SRD-EXE-009.003
    sa.PrimaryKeyConstraint("user_id", "symbol"),
)

# SRD-EXE-009.001 — Intraday monitoring session ledger.
monitoring_session = sa.Table(
    "monitoring_session",
    metadata,
    sa.Column("session_date",    sa.Text, nullable=False),  # YYYY-MM-DD trading date
    sa.Column("symbol",          sa.Text, nullable=False),
    sa.Column("preset_id",       sa.Text, nullable=False),
    sa.Column("run_timestamp",   sa.Text, nullable=False),  # ISO-8601 UTC
    sa.Column("added_at",        sa.Text, nullable=False),  # ISO-8601 UTC
    sa.Column("lifecycle_state", sa.Text, nullable=False, server_default="MONITORING"),
    sa.Column("entered_at",      sa.Text),
    sa.Column("exited_at",       sa.Text),
    sa.Column("evicted_at",      sa.Text),
    sa.Column("trade_id",        sa.Text),
    sa.PrimaryKeyConstraint("session_date", "symbol", name="pk_monitoring_session"),
)

# ── Indexes (compound) ────────────────────────────────────────────────────────
# Created separately so create_schema() can issue them after the tables.

_PRICE_INDEXES = [
    sa.Index("idx_price_1m_sym_dt",          price_1m.c.symbol,           price_1m.c.datetime),
    sa.Index("idx_price_3m_sym_dt",          price_3m.c.symbol,           price_3m.c.datetime),
    sa.Index("idx_price_15m_sym_dt",         price_15m.c.symbol,          price_15m.c.datetime),
    sa.Index("idx_price_1d_sym_dt",          price_1d.c.symbol,           price_1d.c.datetime),
    sa.Index("idx_price_1w_sym_dt",          price_1w.c.symbol,           price_1w.c.datetime),
    sa.Index("idx_trades_user_sym",          trades.c.user_id,            trades.c.symbol),
    sa.Index("idx_monitoring_session_state", monitoring_session.c.lifecycle_state),
    sa.Index("idx_monitoring_session_symbol", monitoring_session.c.symbol),
]

# SRD-EXE-012.001 — trade-cycle ledger; the Table object is defined in
# execution/trade_cycle/_schema.py but registered on this metadata.  We
# import it lazily inside create_schema() to avoid pulling the execution
# package's heavy transitive deps during db/schema import.


def _register_trade_cycle_schema() -> None:
    from us_swing.execution.trade_cycle import _schema as _trade_cycle_schema  # noqa: F401

# Map canonical timeframe keys to the corresponding table object.
PRICE_TABLES: dict[str, sa.Table] = {
    "1m":  price_1m,
    "3m":  price_3m,
    "15m": price_15m,
    "1d":  price_1d,
    "1w":  price_1w,
}


# ── Schema lifecycle ──────────────────────────────────────────────────────────

# SRD-EXE-009.002 / .003 — columns added by feature FO-EXE-009 to existing tables.
# Applied on app start via idempotent PRAGMA + ALTER TABLE; declared above so
# fresh DBs receive them through `create_schema()`.
_LIFECYCLE_COLUMN_ADDITIONS: tuple[tuple[str, str, str], ...] = (
    ("trades",    "trade_origin",            "TEXT"),
    ("trades",    "monitoring_session_date", "TEXT"),
    ("positions", "origin",                  "TEXT"),
    ("positions", "anchor_session_date",     "TEXT"),
)


def migrate_lifecycle_columns(engine: sa.Engine) -> None:
    """Add monitoring-session lifecycle columns to ``trades`` and ``positions``
    when they are missing.  Safe to run on every app start — a no-op once
    columns are present.
    """
    with engine.begin() as conn:
        for table_name, column_name, sql_type in _LIFECYCLE_COLUMN_ADDITIONS:
            rows = conn.execute(sa.text(f"PRAGMA table_info({table_name})")).mappings()
            existing = {row["name"] for row in rows}
            if column_name in existing:
                continue
            conn.execute(
                sa.text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}")
            )


def create_schema(engine: sa.Engine) -> None:
    """Create all tables and indexes if they do not already exist, then run
    additive lifecycle-column migrations for existing databases."""
    _register_trade_cycle_schema()
    metadata.create_all(engine, checkfirst=True)
    migrate_lifecycle_columns(engine)


def drop_schema(engine: sa.Engine) -> None:
    """Drop all tables (test use only)."""
    metadata.drop_all(engine)
