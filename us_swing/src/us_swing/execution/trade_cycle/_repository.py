"""
Module: MD-EXE-012.002.M01 — execution/trade_cycle/_repository.py
Parent SRD: SRD-EXE-012.003, SRD-EXE-012.007, SRD-EXE-012.008,
            SRD-EXE-012.009, SRD-EXE-012.010, SRD-EXE-012.013

The only file under ``execution/trade_cycle/`` permitted to import
SQLAlchemy.  Wraps every ``trade_cycles`` DB access used by the service,
including the duplicate-open guard and the compare-and-swap state move.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.engine import RowMapping

from us_swing.execution.trade_cycle._dto import (
    NON_TERMINAL_STATES,
    CycleSnapshot,
    DuplicateOpenCycleError,
    InvalidStateTransitionError,
    validate_exit_reason,
    validate_state,
)
from us_swing.execution.trade_cycle._schema import trade_cycles

log = logging.getLogger(__name__)


_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "OPENING": frozenset({"OPEN", "ABORTED"}),
    "OPEN":    frozenset({"CLOSING"}),
    "CLOSING": frozenset({"CLOSED", "OPEN"}),
    "CLOSED":  frozenset(),
    "ABORTED": frozenset(),
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _row_to_snapshot(row: RowMapping) -> CycleSnapshot:
    return CycleSnapshot(
        cycle_id                = int(row["cycle_id"]),
        strategy_id             = row["strategy_id"],
        symbol                  = row["symbol"],
        user_id                 = int(row["user_id"]),
        monitoring_session_date = row["monitoring_session_date"],
        state                   = row["state"],
        entry_time              = row["entry_time"],
        entry_price             = float(row["entry_price"]),
        entry_qty               = int(row["entry_qty"]),
        entry_order_id          = row["entry_order_id"],
        hard_stop_loss          = float(row["hard_stop_loss"]),
        target_price            = row["target_price"],
        target_type             = row["target_type"],
        stoploss_type           = row["stoploss_type"],
        trailing_mode           = row["trailing_mode"],
        trailing_offset         = row["trailing_offset"],
        current_price           = row["current_price"],
        current_pnl_usd         = row["current_pnl_usd"],
        current_pnl_pct         = row["current_pnl_pct"],
        highest_price_seen      = row["highest_price_seen"],
        trailing_stop_level     = row["trailing_stop_level"],
        effective_stop          = row["effective_stop"],
        last_updated_at         = row["last_updated_at"],
        exit_time               = row["exit_time"],
        exit_price              = row["exit_price"],
        exit_qty                = row["exit_qty"],
        exit_order_id           = row["exit_order_id"],
        exit_reason             = row["exit_reason"],
        realized_pnl_usd        = row["realized_pnl_usd"],
        realized_pnl_pct        = row["realized_pnl_pct"],
        opened_at               = row["opened_at"],
        closed_at               = row["closed_at"],
    )


class TradeCycleRepository:
    """SQLAlchemy-backed repository for the ``trade_cycles`` ledger."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ── Queries ──────────────────────────────────────────────────────────────

    def open_cycles(self) -> tuple[CycleSnapshot, ...]:
        stmt = (
            sa.select(trade_cycles)
            .where(trade_cycles.c.state.in_(tuple(NON_TERMINAL_STATES)))
            .order_by(trade_cycles.c.cycle_id.asc())
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return tuple(_row_to_snapshot(r) for r in rows)

    def cycle(self, cycle_id: int) -> CycleSnapshot | None:
        stmt = sa.select(trade_cycles).where(trade_cycles.c.cycle_id == cycle_id)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _row_to_snapshot(row) if row else None

    def history(
        self,
        *,
        symbol: str | None      = None,
        strategy_id: str | None = None,
        days: int               = 30,
    ) -> tuple[CycleSnapshot, ...]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
        conds: list[Any] = [trade_cycles.c.opened_at >= cutoff]
        if symbol is not None:
            conds.append(trade_cycles.c.symbol == symbol)
        if strategy_id is not None:
            conds.append(trade_cycles.c.strategy_id == strategy_id)
        stmt = (
            sa.select(trade_cycles)
            .where(sa.and_(*conds))
            .order_by(trade_cycles.c.cycle_id.desc())
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return tuple(_row_to_snapshot(r) for r in rows)

    def find_open(self, strategy_id: str, symbol: str) -> CycleSnapshot | None:
        stmt = (
            sa.select(trade_cycles)
            .where(
                trade_cycles.c.strategy_id == strategy_id,
                trade_cycles.c.symbol      == symbol,
                trade_cycles.c.state.in_(tuple(NON_TERMINAL_STATES)),
            )
            .limit(1)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _row_to_snapshot(row) if row else None

    def find_by_entry_order(self, entry_order_id: str) -> CycleSnapshot | None:
        stmt = sa.select(trade_cycles).where(
            trade_cycles.c.entry_order_id == entry_order_id
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _row_to_snapshot(row) if row else None

    def find_by_exit_order(self, exit_order_id: str) -> CycleSnapshot | None:
        stmt = sa.select(trade_cycles).where(
            trade_cycles.c.exit_order_id == exit_order_id
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _row_to_snapshot(row) if row else None

    # ── Mutations ────────────────────────────────────────────────────────────

    def insert_open(self, *, row: dict[str, Any]) -> CycleSnapshot:
        """Insert a new cycle row.

        Inside a single transaction, asserts there is no existing
        non-terminal cycle for the same ``(strategy_id, symbol)``; raises
        :class:`DuplicateOpenCycleError` and rolls back if there is.
        """
        validate_state(row["state"])
        opened_at = row.setdefault("opened_at", _utcnow_iso())
        row.setdefault("last_updated_at", opened_at)

        strategy_id = row["strategy_id"]
        symbol      = row["symbol"]

        with self._engine.begin() as conn:
            dup_q = sa.select(trade_cycles.c.cycle_id).where(
                trade_cycles.c.strategy_id == strategy_id,
                trade_cycles.c.symbol      == symbol,
                trade_cycles.c.state.in_(tuple(NON_TERMINAL_STATES)),
            )
            if conn.execute(dup_q).first() is not None:
                raise DuplicateOpenCycleError(
                    f"open cycle already exists for ({strategy_id}, {symbol})"
                )
            result = conn.execute(trade_cycles.insert().values(**row))
            new_id = int(result.inserted_primary_key[0])  # type: ignore[index]
            fresh  = conn.execute(
                sa.select(trade_cycles).where(trade_cycles.c.cycle_id == new_id)
            ).mappings().first()
        assert fresh is not None
        return _row_to_snapshot(fresh)

    def update_live(self, cycle_id: int, *, fields: dict[str, Any]) -> None:
        """Persist live tick-driven fields without emitting an event."""
        if not fields:
            return
        with self._engine.begin() as conn:
            conn.execute(
                trade_cycles.update()
                .where(trade_cycles.c.cycle_id == cycle_id)
                .values(**fields)
            )

    def update_state(self, cycle_id: int, new_state: str) -> CycleSnapshot:
        """Atomic compare-and-swap state transition.

        Raises :class:`InvalidStateTransitionError` if the current state
        does not permit moving to ``new_state``.
        """
        validate_state(new_state)
        with self._engine.begin() as conn:
            current = conn.execute(
                sa.select(trade_cycles.c.state).where(trade_cycles.c.cycle_id == cycle_id)
            ).scalar()
            if current is None:
                raise InvalidStateTransitionError(f"cycle {cycle_id} not found")
            if new_state not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise InvalidStateTransitionError(
                    f"illegal transition {current!r} -> {new_state!r} for cycle {cycle_id}"
                )
            result = conn.execute(
                trade_cycles.update()
                .where(
                    trade_cycles.c.cycle_id == cycle_id,
                    trade_cycles.c.state    == current,
                )
                .values(state=new_state)
            )
            if (result.rowcount or 0) == 0:
                raise InvalidStateTransitionError(
                    f"concurrent state change on cycle {cycle_id}"
                )
            fresh = conn.execute(
                sa.select(trade_cycles).where(trade_cycles.c.cycle_id == cycle_id)
            ).mappings().first()
        assert fresh is not None
        return _row_to_snapshot(fresh)

    def update_risk(
        self,
        cycle_id: int,
        *,
        fields: dict[str, Any],
    ) -> CycleSnapshot:
        if not fields:
            snap = self.cycle(cycle_id)
            if snap is None:
                raise InvalidStateTransitionError(f"cycle {cycle_id} not found")
            return snap
        with self._engine.begin() as conn:
            conn.execute(
                trade_cycles.update()
                .where(trade_cycles.c.cycle_id == cycle_id)
                .values(**fields)
            )
            fresh = conn.execute(
                sa.select(trade_cycles).where(trade_cycles.c.cycle_id == cycle_id)
            ).mappings().first()
        if fresh is None:
            raise InvalidStateTransitionError(f"cycle {cycle_id} not found")
        return _row_to_snapshot(fresh)

    def close(
        self,
        cycle_id: int,
        *,
        exit_fields: dict[str, Any],
    ) -> CycleSnapshot:
        """Finalise a CLOSING cycle into CLOSED.

        ``exit_fields`` must include exit_time/price/qty/reason and the
        frozen realized PnL columns.
        """
        validate_exit_reason(exit_fields["exit_reason"])
        exit_fields.setdefault("closed_at", _utcnow_iso())
        exit_fields["state"] = "CLOSED"
        with self._engine.begin() as conn:
            current = conn.execute(
                sa.select(trade_cycles.c.state).where(trade_cycles.c.cycle_id == cycle_id)
            ).scalar()
            if current is None:
                raise InvalidStateTransitionError(f"cycle {cycle_id} not found")
            if current not in ("CLOSING", "OPEN"):
                raise InvalidStateTransitionError(
                    f"cannot close cycle {cycle_id} from state {current!r}"
                )
            conn.execute(
                trade_cycles.update()
                .where(trade_cycles.c.cycle_id == cycle_id)
                .values(**exit_fields)
            )
            fresh = conn.execute(
                sa.select(trade_cycles).where(trade_cycles.c.cycle_id == cycle_id)
            ).mappings().first()
        assert fresh is not None
        return _row_to_snapshot(fresh)

    def abort(self, cycle_id: int, reason: str) -> CycleSnapshot:
        with self._engine.begin() as conn:
            current = conn.execute(
                sa.select(trade_cycles.c.state).where(trade_cycles.c.cycle_id == cycle_id)
            ).scalar()
            if current is None:
                raise InvalidStateTransitionError(f"cycle {cycle_id} not found")
            if current != "OPENING":
                raise InvalidStateTransitionError(
                    f"cannot abort cycle {cycle_id} from state {current!r}"
                )
            conn.execute(
                trade_cycles.update()
                .where(trade_cycles.c.cycle_id == cycle_id)
                .values(
                    state       = "ABORTED",
                    exit_reason = reason,
                    closed_at   = _utcnow_iso(),
                )
            )
            fresh = conn.execute(
                sa.select(trade_cycles).where(trade_cycles.c.cycle_id == cycle_id)
            ).mappings().first()
        assert fresh is not None
        return _row_to_snapshot(fresh)


__all__ = [
    "TradeCycleRepository",
]
