"""
Module: MD-EXE-011.001.M08 — execution/strategy_engine/_rex_counter.py
Parent SRD: SRD-EXE-011.016 — SRD-EXE-011.019

Per-symbol re-execution counter for each (strategy_id, symbol). Stores
``remaining`` as a small integer that initializes to ``cfg.rex_count`` on the
first entry, decrements by 1 after every confirmed entry fill, and blocks
further entries once the value drops below zero. Counters survive engine
restart because rows live in the shared ``candles.db`` SQLite file.
"""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Engine

from us_swing.db.schema import metadata

strategy_rex_counters = sa.Table(
    "strategy_rex_counters",
    metadata,
    sa.Column("strategy_id",  sa.Text,      nullable=False),
    sa.Column("symbol",       sa.Text,      nullable=False),
    sa.Column("remaining",    sa.Integer,   nullable=False),
    sa.Column("last_updated", sa.Text,      nullable=False),
    sa.PrimaryKeyConstraint("strategy_id", "symbol"),
)

idx_rex_strategy = sa.Index(
    "idx_rex_strategy",
    strategy_rex_counters.c.strategy_id,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


class RexCounterRepository:
    """CRUD over ``strategy_rex_counters`` keyed by (strategy_id, symbol)."""

    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        strategy_rex_counters.create(engine, checkfirst=True)
        idx_rex_strategy.create(engine, checkfirst=True)

    def get(self, strategy_id: str, symbol: str) -> int | None:
        """Return stored ``remaining``, or None when the row is absent."""
        stmt = sa.select(strategy_rex_counters.c.remaining).where(
            strategy_rex_counters.c.strategy_id == strategy_id,
            strategy_rex_counters.c.symbol == symbol,
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).first()
        return int(row[0]) if row is not None else None

    def decrement(
        self,
        strategy_id: str,
        symbol: str,
        *,
        init_value: int,
    ) -> int:
        """Insert with ``init_value - 1`` if missing, else ``remaining -= 1``.

        Returns the new ``remaining`` value.
        """
        now = _utcnow_iso()
        with self._engine.begin() as conn:
            existing = conn.execute(
                sa.select(strategy_rex_counters.c.remaining).where(
                    strategy_rex_counters.c.strategy_id == strategy_id,
                    strategy_rex_counters.c.symbol == symbol,
                )
            ).first()
            if existing is None:
                new_value = int(init_value) - 1
                conn.execute(
                    sa.insert(strategy_rex_counters).values(
                        strategy_id=strategy_id,
                        symbol=symbol,
                        remaining=new_value,
                        last_updated=now,
                    )
                )
            else:
                new_value = int(existing[0]) - 1
                conn.execute(
                    sa.update(strategy_rex_counters)
                    .where(
                        strategy_rex_counters.c.strategy_id == strategy_id,
                        strategy_rex_counters.c.symbol == symbol,
                    )
                    .values(remaining=new_value, last_updated=now)
                )
        return new_value

    def reset(self, strategy_id: str) -> int:
        """Delete every counter row for ``strategy_id``. Returns deleted count."""
        stmt = sa.delete(strategy_rex_counters).where(
            strategy_rex_counters.c.strategy_id == strategy_id,
        )
        with self._engine.begin() as conn:
            result = conn.execute(stmt)
        return int(result.rowcount or 0)


__all__ = [
    "RexCounterRepository",
    "strategy_rex_counters",
    "idx_rex_strategy",
]
