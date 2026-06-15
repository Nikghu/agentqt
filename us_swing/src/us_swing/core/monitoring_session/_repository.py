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

from us_swing.core.monitoring_session._dto import MonitoringSessionRow
from us_swing.db.schema import monitoring_session
from us_swing.execution import ExecutionEnums

log = logging.getLogger(__name__)

# Module-local handle for the canonical lifecycle enum (single source of truth
# is ExecutionEnums — SRD-EXE-009.012).
_LifecycleState = ExecutionEnums.LifecycleState

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
        lifecycle_state = _LifecycleState(row["lifecycle_state"]),
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
                "lifecycle_state": _LifecycleState.MONITORING.value,
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
                monitoring_session.c.lifecycle_state == _LifecycleState.MONITORING.value,
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
                    lifecycle_state=_LifecycleState.ENTERED.value,
                    entered_at=entered_at,
                    exited_at=None,
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
                    lifecycle_state=_LifecycleState.EXITED.value,
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
                    monitoring_session.c.lifecycle_state == _LifecycleState.MONITORING.value,
                )
                .values(lifecycle_state=_LifecycleState.SKIPPED.value)
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
                        (_LifecycleState.SKIPPED.value, _LifecycleState.MONITORING.value)
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
                            (_LifecycleState.SKIPPED.value, _LifecycleState.MONITORING.value)
                        ),
                    )
                    .values(
                        lifecycle_state=_LifecycleState.EVICTED.value,
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
            monitoring_session.c.lifecycle_state == _LifecycleState.ENTERED.value
        )
        with self._engine.connect() as conn:
            return frozenset(r[0] for r in conn.execute(stmt))

    def stale_lifecycle_symbols(self, today: date) -> frozenset[str]:
        """Symbols with at least one prior-day MONITORING or SKIPPED row —
        the candidate set for eviction."""
        stmt = sa.select(monitoring_session.c.symbol.distinct()).where(
            monitoring_session.c.session_date < today.isoformat(),
            monitoring_session.c.lifecycle_state.in_(
                (_LifecycleState.MONITORING.value, _LifecycleState.SKIPPED.value)
            ),
        )
        with self._engine.connect() as conn:
            return frozenset(r[0] for r in conn.execute(stmt))

    # ── Position queries (trade_cycles is the live surface, FO-EXE-016) ───────

    def open_system_position_symbols(self) -> frozenset[str]:
        """Symbols with a currently-open trade cycle.

        ``trade_cycles`` replaced the retired ``positions`` table as the live
        position surface. Queried by table name so ``core/`` need not import the
        execution-owned schema (same pattern as ``health.py``).
        """
        stmt = sa.text(
            "SELECT DISTINCT symbol FROM trade_cycles "
            "WHERE state NOT IN ('CLOSED', 'ABORTED')"
        )
        with self._engine.connect() as conn:
            return frozenset(r[0] for r in conn.execute(stmt))

    def fetch_entered_row(self, symbol: str) -> MonitoringSessionRow | None:
        """Most-recent ``ENTERED`` ledger row for *symbol*, if any."""
        stmt = (
            sa.select(monitoring_session)
            .where(
                monitoring_session.c.symbol          == symbol,
                monitoring_session.c.lifecycle_state == _LifecycleState.ENTERED.value,
            )
            .order_by(monitoring_session.c.session_date.desc())
            .limit(1)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _row_to_session(row) if row else None

    def fetch_latest_exited_row(self, symbol: str) -> MonitoringSessionRow | None:
        """Most-recent ``EXITED`` ledger row for *symbol*, if any.

        The re-arm target for a same-day re-entry: after a symbol is entered and
        exited in the same session its only ledger row is ``EXITED``, so a second
        entry has no open ``MONITORING`` row to advance (SRD-EXE-016.007).
        """
        stmt = (
            sa.select(monitoring_session)
            .where(
                monitoring_session.c.symbol          == symbol,
                monitoring_session.c.lifecycle_state == _LifecycleState.EXITED.value,
            )
            .order_by(monitoring_session.c.session_date.desc())
            .limit(1)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _row_to_session(row) if row else None
