"""
Module: MD-EXE-012.001.M01 — execution/trade_cycle/_schema.py
Parent SRD: SRD-EXE-012.001

SQLAlchemy Core table definition for the ``trade_cycles`` ledger and its
composite indexes.  The table object is re-exported through
``db/schema.py`` so ``create_schema(checkfirst=True)`` picks it up on
startup; no separate migration is needed.
"""
from __future__ import annotations

import sqlalchemy as sa

from us_swing.db.schema import metadata

trade_cycles = sa.Table(
    "trade_cycles",
    metadata,
    sa.Column("cycle_id",                sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("strategy_id",             sa.Text,    nullable=False),
    sa.Column("symbol",                  sa.Text,    nullable=False),
    sa.Column("user_id",                 sa.Integer, nullable=False),
    sa.Column("monitoring_session_date", sa.Text,    nullable=False),
    sa.Column("entry_time",              sa.Text,    nullable=False),
    sa.Column("entry_price",             sa.Float,   nullable=False),
    sa.Column("entry_qty",               sa.Integer, nullable=False),
    sa.Column("entry_order_id",          sa.Text,    nullable=False, unique=True),
    sa.Column("hard_stop_loss",          sa.Float,   nullable=False),
    sa.Column("target_price",            sa.Float),
    sa.Column("target_type",             sa.Text,    nullable=False),
    sa.Column("stoploss_type",           sa.Text,    nullable=False),
    sa.Column("trailing_mode",           sa.Text),
    sa.Column("trailing_offset",         sa.Float),
    sa.Column("current_price",           sa.Float),
    sa.Column("current_pnl_usd",         sa.Float),
    sa.Column("current_pnl_pct",         sa.Float),
    sa.Column("highest_price_seen",      sa.Float),
    sa.Column("trailing_stop_level",     sa.Float),
    sa.Column("effective_stop",          sa.Float),
    sa.Column("last_updated_at",         sa.Text),
    sa.Column("exit_time",               sa.Text),
    sa.Column("exit_price",              sa.Float),
    sa.Column("exit_qty",                sa.Integer),
    sa.Column("exit_order_id",           sa.Text, unique=True),
    sa.Column("exit_reason",             sa.Text),
    sa.Column("realized_pnl_usd",        sa.Float),
    sa.Column("realized_pnl_pct",        sa.Float),
    sa.Column("state",                   sa.Text, nullable=False, server_default="OPENING"),
    sa.Column("opened_at",               sa.Text, nullable=False),
    sa.Column("closed_at",               sa.Text),
)

idx_trade_cycles_state_symbol = sa.Index(
    "idx_trade_cycles_state_symbol",
    trade_cycles.c.state,
    trade_cycles.c.symbol,
)

idx_trade_cycles_strategy_symbol_state = sa.Index(
    "idx_trade_cycles_strategy_symbol_state",
    trade_cycles.c.strategy_id,
    trade_cycles.c.symbol,
    trade_cycles.c.state,
)

__all__ = [
    "trade_cycles",
    "idx_trade_cycles_state_symbol",
    "idx_trade_cycles_strategy_symbol_state",
]
