"""
Module: MD-EXE-020.001.M01 — execution/equity_snapshot.py
Parent SRD: SRD-EXE-020.001 — SRD-EXE-020.003, SRD-EXE-020.005, SRD-EXE-020.007

Account equity saved every 5 minutes per user, so the dashboard can draw an
intraday equity curve. Rows live in the shared ``candles.db`` SQLite file.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

import sqlalchemy as sa
from sqlalchemy import Engine

from us_swing.db.schema import metadata

SLOT_MINUTES = 5
KEEP_DAYS = 30

equity_snapshots = sa.Table(
    "equity_snapshots",
    metadata,
    sa.Column("user_id",        sa.Integer, nullable=False),
    sa.Column("taken_at",       sa.Text,    nullable=False),
    sa.Column("equity",         sa.Float,   nullable=False),
    sa.Column("cash",           sa.Float,   nullable=False),
    sa.Column("unrealised_pnl", sa.Float,   nullable=False),
    sa.PrimaryKeyConstraint("user_id", "taken_at"),
)

idx_equity_taken_at = sa.Index("idx_equity_taken_at", equity_snapshots.c.taken_at)


@dataclass(frozen=True, slots=True)
class EquitySnapshot:
    """One 5-minute point; for "all users" the values are summed over users."""

    taken_at: str
    equity: float
    cash: float
    unrealised_pnl: float


@dataclass(frozen=True, slots=True)
class CurvePoint:
    """One point of the equity curve drawn on the dashboard."""

    at: str
    value: float


class _ClosedCycle(Protocol):
    @property
    def closed_at(self) -> str | None: ...
    @property
    def realized_pnl_usd(self) -> float | None: ...


def curve_from_closed(cycles: Iterable[_ClosedCycle], end_equity: float, start_iso: str,
                      end_iso: str) -> tuple[CurvePoint, ...]:
    """Equity curve that ends at ``end_equity`` and steps at each close (SRD-EXE-020.007).

    The start value is ``end_equity`` minus the realised P&L of the closes in the range.
    """
    closes = sorted(
        (c for c in cycles if c.realized_pnl_usd is not None and c.closed_at),
        key=lambda c: str(c.closed_at),
    )
    value = end_equity - sum(float(c.realized_pnl_usd or 0.0) for c in closes)
    points = [CurvePoint(start_iso, value)]
    for cycle in closes:
        value += float(cycle.realized_pnl_usd or 0.0)
        points.append(CurvePoint(str(cycle.closed_at), value))
    points.append(CurvePoint(end_iso, end_equity))
    return tuple(points)


def slot_iso(moment: datetime) -> str:
    """UTC ISO text of ``moment`` floored to its 5-minute slot; a naive time is taken as UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    utc = moment.astimezone(timezone.utc)
    floored = utc.replace(minute=utc.minute - utc.minute % SLOT_MINUTES, second=0, microsecond=0)
    return floored.strftime("%Y-%m-%dT%H:%M:%S")


class EquitySnapshotRepository:
    """Save and read ``equity_snapshots`` rows keyed by (user_id, taken_at)."""

    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        equity_snapshots.create(engine, checkfirst=True)
        idx_equity_taken_at.create(engine, checkfirst=True)

    def record(self, user_id: int, equity: float, cash: float, unrealised_pnl: float,
               taken_at: datetime) -> None:
        """Save one row for the slot of ``taken_at``, replacing a row already in that slot."""
        self.record_many([(user_id, equity, cash, unrealised_pnl)], taken_at)

    def record_many(self, rows: list[tuple[int, float, float, float]],
                    taken_at: datetime) -> None:
        """Save ``(user_id, equity, cash, unrealised_pnl)`` rows for one slot in one transaction.

        Either every user's row of the slot is saved or none is, so "all users" sums
        never mix a full slot with a partial one.
        """
        slot = slot_iso(taken_at)
        values = [
            {"user_id": uid, "taken_at": slot, "equity": float(equity), "cash": float(cash),
             "unrealised_pnl": float(unreal)}
            for uid, equity, cash, unreal in rows
        ]
        if not values:
            return
        with self._engine.begin() as conn:
            conn.execute(sa.delete(equity_snapshots).where(
                equity_snapshots.c.taken_at == slot,
                equity_snapshots.c.user_id.in_([v["user_id"] for v in values]),
            ))
            conn.execute(sa.insert(equity_snapshots), values)

    def between(self, start_iso: str, end_iso: str | None = None,
                user_id: int | None = None) -> tuple[EquitySnapshot, ...]:
        """Points from ``start_iso`` (inclusive) in time order; no user sums every user."""
        t = equity_snapshots.c
        stmt = (
            sa.select(t.taken_at, sa.func.sum(t.equity), sa.func.sum(t.cash),
                      sa.func.sum(t.unrealised_pnl))
            .where(t.taken_at >= start_iso)
            .group_by(t.taken_at)
            .order_by(t.taken_at)
        )
        if end_iso is not None:
            stmt = stmt.where(t.taken_at <= end_iso)
        if user_id is not None:
            stmt = stmt.where(t.user_id == user_id)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).all()
        return tuple(EquitySnapshot(str(r[0]), float(r[1]), float(r[2]), float(r[3]))
                     for r in rows)

    def prune(self, now: datetime, keep_days: int = KEEP_DAYS) -> int:
        """Delete rows older than ``keep_days``; returns the deleted count."""
        cutoff = slot_iso(now - timedelta(days=keep_days))
        with self._engine.begin() as conn:
            result = conn.execute(
                sa.delete(equity_snapshots).where(equity_snapshots.c.taken_at < cutoff))
        return int(result.rowcount or 0)


__all__ = [
    "CurvePoint",
    "curve_from_closed",
    "EquitySnapshot",
    "EquitySnapshotRepository",
    "equity_snapshots",
    "idx_equity_taken_at",
    "slot_iso",
]
