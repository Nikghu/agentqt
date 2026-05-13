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
    sa.Column("trade_id",    sa.Text,    primary_key=True),
    sa.Column("user_id",     sa.Integer, sa.ForeignKey("users.user_id"), nullable=False),
    sa.Column("symbol",      sa.Text,    nullable=False),
    sa.Column("side",        sa.Text),
    sa.Column("entry_time",  sa.Text),
    sa.Column("entry_price", sa.Float),
    sa.Column("exit_time",   sa.Text),
    sa.Column("exit_price",  sa.Float),
    sa.Column("quantity",    sa.Integer),
    sa.Column("pnl",         sa.Float),
    sa.Column("strategy_id", sa.Text),
    sa.Column("mode",        sa.Text,    nullable=False, server_default="paper"),
    sa.Column("status",      sa.Text,    server_default="SUBMITTED"),
)

positions = sa.Table(
    "positions",
    metadata,
    sa.Column("symbol",        sa.Text,    nullable=False),
    sa.Column("user_id",       sa.Integer, sa.ForeignKey("users.user_id"), nullable=False),
    sa.Column("quantity",      sa.Integer),
    sa.Column("average_price", sa.Float),
    sa.Column("stop_loss",     sa.Float),
    sa.Column("target_price",  sa.Float),
    sa.Column("trailing_stop", sa.Float),
    sa.Column("mode",          sa.Text,    nullable=False, server_default="paper"),
    sa.Column("state",         sa.Text,    nullable=False, server_default="NEW"),
    sa.PrimaryKeyConstraint("user_id", "symbol"),
)

# ── Indexes (compound) ────────────────────────────────────────────────────────
# Created separately so create_schema() can issue them after the tables.

_PRICE_INDEXES = [
    sa.Index("idx_price_1m_sym_dt",  price_1m.c.symbol,  price_1m.c.datetime),
    sa.Index("idx_price_3m_sym_dt",  price_3m.c.symbol,  price_3m.c.datetime),
    sa.Index("idx_price_15m_sym_dt", price_15m.c.symbol, price_15m.c.datetime),
    sa.Index("idx_price_1d_sym_dt",  price_1d.c.symbol,  price_1d.c.datetime),
    sa.Index("idx_price_1w_sym_dt",  price_1w.c.symbol,  price_1w.c.datetime),
    sa.Index("idx_trades_user_sym",  trades.c.user_id,   trades.c.symbol),
]

# Map canonical timeframe keys to the corresponding table object.
PRICE_TABLES: dict[str, sa.Table] = {
    "1m":  price_1m,
    "3m":  price_3m,
    "15m": price_15m,
    "1d":  price_1d,
    "1w":  price_1w,
}


# ── Schema lifecycle ──────────────────────────────────────────────────────────

def create_schema(engine: sa.Engine) -> None:
    """Create all tables and indexes if they do not already exist."""
    metadata.create_all(engine, checkfirst=True)


def drop_schema(engine: sa.Engine) -> None:
    """Drop all tables (test use only)."""
    metadata.drop_all(engine)
