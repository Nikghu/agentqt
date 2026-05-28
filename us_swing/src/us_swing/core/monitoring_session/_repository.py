"""
Module: MD-EXE-009.002.M01 — core/monitoring_session/_repository.py
Parent SRD: SRD-EXE-009.001, SRD-EXE-009.005, SRD-EXE-009.006, SRD-EXE-009.007,
            SRD-EXE-009.009, SRD-EXE-010.002

The only file under ``core/monitoring_session/`` permitted to import SQLAlchemy.
Wraps every ledger / trades / positions DB access used by the lifecycle
service, including the per-symbol atomic eviction transaction.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

import sqlalchemy as sa
from sqlalchemy import Engine

from us_swing.core.monitoring_session._dto import (
    MonitoringSessionRow,
    PositionSnapshot,
)
from us_swing.core.monitoring_session._enums import LifecycleState, Side, TradeOrigin
from us_swing.db.schema import monitoring_session, positions, trades

log = logging.getLogger(__name__)

_PRICE_TABLES_FOR_EVICTION: tuple[str, ...] = ("price_1m", "price_3m", "price_15m")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _row_to_session(row: sa.engine.RowMapping) -> MonitoringSessionRow:
    return MonitoringSessionRow(
        session_date    = row["session_date"],
        symbol          = row["symbol"],
        preset_id       = row["preset_id"],
        run_timestamp   = row["run_timestamp"],
        added_at        = row["added_at"],
        lifecycle_state = LifecycleState(row["lifecycle_state"]),
        entered_at      = row["entered_at"],
        exited_at       = row["exited_at"],
        evicted_at      = row["evicted_at"],
        trade_id        = row["trade_id"],
    )


class MonitoringRepository:
    """SQLAlchemy-backed repository for the monitoring-session ledger and the
    lifecycle-related columns on ``trades`` and ``positions``."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ── Ledger writes ────────────────────────────────────────────────────────

    def insert_monitoring_rows(
        self,
        session_date: date,
        preset_id: str,
        run_timestamp: str,
        symbols: Sequence[str],
    ) -> tuple[str, ...]:
        """Insert one MONITORING row per symbol for *session_date*.

        Idempotent via ``ON CONFLICT DO NOTHING``; returns the symbols actually
        inserted (i.e., not already present for that session_date).
        """
        if not symbols:
            return ()

        added_at = _utcnow_iso()
        session_date_s = session_date.isoformat()
        rows = [
            {
                "session_date":    session_date_s,
                "symbol":          s,
                "preset_id":       preset_id,
                "run_timestamp":   run_timestamp,
                "added_at":        added_at,
                "lifecycle_state": LifecycleState.MONITORING.value,
            }
            for s in symbols
        ]

        with self._engine.begin() as conn:
            existing_q = sa.select(monitoring_session.c.symbol).where(
                monitoring_session.c.session_date == session_date_s,
                monitoring_session.c.symbol.in_(list(symbols)),
            )
            already = {r[0] for r in conn.execute(existing_q)}
            new_rows = [r for r in rows if r["symbol"] not in already]
            if not new_rows:
                return ()
            stmt = sa.dialects.sqlite.insert(monitoring_session).values(new_rows)  # type: ignore[attr-defined]
            stmt = stmt.on_conflict_do_nothing(index_elements=["session_date", "symbol"])
            conn.execute(stmt)

        return tuple(r["symbol"] for r in new_rows)

    def fetch_earliest_open_monitoring_row(
        self,
        symbol: str,
    ) -> MonitoringSessionRow | None:
        """Earliest ``MONITORING`` row for *symbol* across all session_dates."""
        stmt = (
            sa.select(monitoring_session)
            .where(
                monitoring_session.c.symbol          == symbol,
                monitoring_session.c.lifecycle_state == LifecycleState.MONITORING.value,
            )
            .order_by(monitoring_session.c.session_date.asc())
            .limit(1)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _row_to_session(row) if row else None

    def transition_to_entered(
        self,
        session_date: str,
        symbol: str,
        entered_at: str,
        trade_id: str,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                monitoring_session.update()
                .where(
                    monitoring_session.c.session_date == session_date,
                    monitoring_session.c.symbol       == symbol,
                )
                .values(
                    lifecycle_state=LifecycleState.ENTERED.value,
                    entered_at=entered_at,
                    trade_id=trade_id,
                )
            )

    def transition_to_exited(
        self,
        session_date: str,
        symbol: str,
        exited_at: str,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                monitoring_session.update()
                .where(
                    monitoring_session.c.session_date == session_date,
                    monitoring_session.c.symbol       == symbol,
                )
                .values(
                    lifecycle_state=LifecycleState.EXITED.value,
                    exited_at=exited_at,
                )
            )

    def bulk_skip_stale_monitoring(self, today: date) -> int:
        """Flip prior-day MONITORING rows to SKIPPED.  Returns row count."""
        today_s = today.isoformat()
        with self._engine.begin() as conn:
            result = conn.execute(
                monitoring_session.update()
                .where(
                    monitoring_session.c.session_date    < today_s,
                    monitoring_session.c.lifecycle_state == LifecycleState.MONITORING.value,
                )
                .values(lifecycle_state=LifecycleState.SKIPPED.value)
            )
        return int(result.rowcount or 0)

    def evict_symbol_atomic(
        self,
        symbol: str,
        today: date,
        evicted_at: str,
    ) -> tuple[str, ...]:
        """Single transaction: DELETE from every price_* table for *symbol*
        and mark matching stale ledger rows ``EVICTED``.

        Returns the ``session_date`` values that were flipped to ``EVICTED``.
        Any exception rolls the whole transaction back.
        """
        today_s = today.isoformat()
        with self._engine.begin() as conn:
            for table_name in _PRICE_TABLES_FOR_EVICTION:
                conn.execute(
                    sa.text(f"DELETE FROM {table_name} WHERE symbol = :sym"),
                    {"sym": symbol},
                )
            affected = conn.execute(
                sa.select(monitoring_session.c.session_date)
                .where(
                    monitoring_session.c.symbol == symbol,
                    monitoring_session.c.session_date < today_s,
                    monitoring_session.c.lifecycle_state.in_(
                        (LifecycleState.SKIPPED.value, LifecycleState.MONITORING.value)
                    ),
                )
            ).all()
            evicted_dates = tuple(r[0] for r in affected)
            if evicted_dates:
                conn.execute(
                    monitoring_session.update()
                    .where(
                        monitoring_session.c.symbol == symbol,
                        monitoring_session.c.session_date < today_s,
                        monitoring_session.c.lifecycle_state.in_(
                            (LifecycleState.SKIPPED.value, LifecycleState.MONITORING.value)
                        ),
                    )
                    .values(
                        lifecycle_state=LifecycleState.EVICTED.value,
                        evicted_at=evicted_at,
                    )
                )
        return evicted_dates

    # ── Ledger reads ─────────────────────────────────────────────────────────

    def fetch_history(
        self,
        symbol: str,
        days: int = 30,
    ) -> tuple[MonitoringSessionRow, ...]:
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
        stmt = (
            sa.select(monitoring_session)
            .where(
                monitoring_session.c.symbol       == symbol,
                monitoring_session.c.session_date >= cutoff,
            )
            .order_by(monitoring_session.c.session_date.desc())
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return tuple(_row_to_session(r) for r in rows)

    def fetch_session(
        self,
        session_date: date,
        symbol: str,
    ) -> MonitoringSessionRow | None:
        stmt = sa.select(monitoring_session).where(
            monitoring_session.c.session_date == session_date.isoformat(),
            monitoring_session.c.symbol       == symbol,
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _row_to_session(row) if row else None

    def entered_symbols(self) -> frozenset[str]:
        stmt = sa.select(monitoring_session.c.symbol).where(
            monitoring_session.c.lifecycle_state == LifecycleState.ENTERED.value
        )
        with self._engine.connect() as conn:
            return frozenset(r[0] for r in conn.execute(stmt))

    def stale_lifecycle_symbols(self, today: date) -> frozenset[str]:
        """Symbols with at least one prior-day MONITORING or SKIPPED row —
        the candidate set for eviction."""
        stmt = sa.select(monitoring_session.c.symbol.distinct()).where(
            monitoring_session.c.session_date < today.isoformat(),
            monitoring_session.c.lifecycle_state.in_(
                (LifecycleState.MONITORING.value, LifecycleState.SKIPPED.value)
            ),
        )
        with self._engine.connect() as conn:
            return frozenset(r[0] for r in conn.execute(stmt))

    # ── Position queries ─────────────────────────────────────────────────────

    def open_system_position_symbols(self) -> frozenset[str]:
        """Symbols of all currently-open system positions across users.

        SRD-EXE-005.001 — "open" derived from quantity > 0.
        """
        stmt = sa.select(positions.c.symbol).where(
            positions.c.quantity > 0,
            positions.c.origin   == TradeOrigin.SYSTEM.value,
        )
        with self._engine.connect() as conn:
            return frozenset(r[0] for r in conn.execute(stmt))

    def has_open_system_position(self, symbol: str) -> bool:
        stmt = sa.select(sa.func.count()).select_from(positions).where(
            positions.c.symbol   == symbol,
            positions.c.quantity > 0,
            positions.c.origin   == TradeOrigin.SYSTEM.value,
        )
        with self._engine.connect() as conn:
            return (conn.execute(stmt).scalar() or 0) > 0

    def position_anchor(self, symbol: str) -> str | None:
        """Anchor session date for the open system position, if any."""
        stmt = sa.select(positions.c.anchor_session_date).where(
            positions.c.symbol   == symbol,
            positions.c.quantity > 0,
            positions.c.origin   == TradeOrigin.SYSTEM.value,
        )
        with self._engine.connect() as conn:
            return conn.execute(stmt).scalar()

    # ── Trade + position writes ──────────────────────────────────────────────

    def insert_trade_with_anchor(
        self,
        trade_id: str,
        user_id: int,
        symbol: str,
        side: Side,
        qty: int,
        price: float,
        fill_time: str,
        origin: TradeOrigin,
        anchor_session_date: str | None,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                trades.insert().values(
                    trade_id                = trade_id,
                    user_id                 = user_id,
                    symbol                  = symbol,
                    side                    = side.value,
                    entry_time              = fill_time if side is Side.BUY else None,
                    entry_price             = price     if side is Side.BUY else None,
                    exit_time               = fill_time if side is Side.SELL else None,
                    exit_price              = price     if side is Side.SELL else None,
                    quantity                = qty,
                    strategy_id             = None,
                    mode                    = "paper",
                    order_state             = "FILLED",
                    filled_quantity         = qty,
                    trade_origin            = origin.value,
                    monitoring_session_date = anchor_session_date,
                )
            )

    def upsert_position_with_anchor(
        self,
        user_id: int,
        symbol: str,
        side: Side,
        fill_qty: int,
        fill_price: float,
        origin: TradeOrigin,
        anchor_session_date: str | None,
    ) -> PositionSnapshot:
        """Apply a fill to the ``positions`` row for (user_id, symbol).

        Computes the post-fill snapshot inside the same transaction so the
        caller can detect a closing fill (``state == 'CLOSED'``).
        """
        with self._engine.begin() as conn:
            existing = conn.execute(
                sa.select(positions).where(
                    positions.c.user_id == user_id,
                    positions.c.symbol  == symbol,
                )
            ).mappings().first()

            if existing is None:
                # Fresh position — must be a BUY for system fills.
                new_qty   = fill_qty if side is Side.BUY else -fill_qty
                avg_price = fill_price
                conn.execute(
                    positions.insert().values(
                        symbol              = symbol,
                        user_id             = user_id,
                        quantity            = new_qty,
                        average_price       = avg_price,
                        stop_loss           = None,
                        target_price        = None,
                        trailing_stop       = None,
                        mode                = "paper",
                        origin              = origin.value,
                        anchor_session_date = anchor_session_date,
                    )
                )
                return PositionSnapshot(
                    symbol              = symbol,
                    quantity            = new_qty,
                    average_price       = avg_price,
                    state               = "OPEN" if new_qty > 0 else "CLOSED",
                    origin              = origin,
                    anchor_session_date = anchor_session_date,
                )

            prev_qty   = int(existing["quantity"] or 0)
            prev_price = float(existing["average_price"] or 0.0)

            if side is Side.BUY:
                new_qty = prev_qty + fill_qty
                # Weighted-average entry price across BUY fills.
                if new_qty > 0:
                    avg_price = (
                        (prev_qty * prev_price + fill_qty * fill_price) / new_qty
                    )
                else:
                    avg_price = fill_price
            else:
                new_qty   = prev_qty - fill_qty
                avg_price = prev_price
                if new_qty < 0:
                    log.warning(
                        "[Lifecycle] Over-sell for %s: prev=%d sold=%d",
                        symbol, prev_qty, fill_qty,
                    )

            anchor = (
                existing["anchor_session_date"]
                if existing["anchor_session_date"] is not None
                else anchor_session_date
            )
            origin_value = existing["origin"] or origin.value

            conn.execute(
                positions.update()
                .where(
                    positions.c.user_id == user_id,
                    positions.c.symbol  == symbol,
                )
                .values(
                    quantity            = new_qty,
                    average_price       = avg_price,
                    origin              = origin_value,
                    anchor_session_date = anchor,
                )
            )

            realised_pnl = 0.0
            if side is Side.SELL and prev_qty > 0:
                realised_pnl = (fill_price - prev_price) * fill_qty

            return PositionSnapshot(
                symbol              = symbol,
                quantity            = new_qty,
                average_price       = avg_price,
                state               = "OPEN" if new_qty > 0 else "CLOSED",
                origin              = TradeOrigin(origin_value),
                anchor_session_date = anchor,
                realised_pnl        = realised_pnl,
            )
