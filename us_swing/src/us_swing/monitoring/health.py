"""Module: MD-INF-005.001.M03 — monitoring/health.py
Parent SRD: SRD-INF-005.004

HealthCheck aggregates system state into a JSON-serialisable dict
suitable for the ``python -m us_swing health`` CLI subcommand.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


class HealthCheck:
    """Aggregates broker / DB / universe status into a health report.

    All dependencies are optional at construction time so that the health
    check can run even when a subsystem has not started yet.

    Args:
        broker:    An ``IBKRClient``-like object (duck-typed).
        db:        A ``DatabaseManager``-like object (duck-typed).
        start_time: When the application started (used for uptime).
    """

    def __init__(
        self,
        broker: Any = None,
        db: Any = None,
        start_time: datetime | None = None,
    ) -> None:
        self._broker     = broker
        self._db         = db
        self._start_time = start_time or datetime.now(tz=timezone.utc)

    def report(self) -> dict[str, Any]:
        """Return a health-check snapshot.

        Returns:
            Dict with keys: ``broker_connected``, ``last_update``,
            ``universe_count``, ``open_positions``, ``db_reachable``,
            ``uptime_seconds``.
        """
        broker_ok    = self._check_broker()
        db_ok, stats = self._check_db()
        uptime = (datetime.now(tz=timezone.utc) - self._start_time).total_seconds()

        return {
            "broker_connected": broker_ok,
            "last_update":      stats.get("last_update"),
            "universe_count":   stats.get("universe_count", 0),
            "open_positions":   stats.get("open_positions", 0),
            "db_reachable":     db_ok,
            "uptime_seconds":   int(uptime),
        }

    # ── Sub-checks ────────────────────────────────────────────────────────────

    def _check_broker(self) -> bool:
        if self._broker is None:
            return False
        try:
            return bool(self._broker.is_connected())
        except Exception:
            log.warning("HealthCheck: broker check failed")
            return False

    def _check_db(self) -> tuple[bool, dict[str, Any]]:
        if self._db is None:
            return False, {}
        try:
            universe = self._db.fetch_universe()
            open_pos = self._count_open_cycles()
            last_update = self._db.get_last_timestamp("SPY", "1d")  # proxy metric
            return True, {
                "universe_count": len(universe),
                "open_positions": open_pos,
                "last_update": last_update.isoformat() if last_update else None,
            }
        except Exception:
            log.warning("HealthCheck: DB check failed")
            return False, {}

    def _count_open_cycles(self) -> int:
        """Count non-terminal trade_cycles — the live open-position surface."""
        from sqlalchemy import text

        with self._db.engine.connect() as conn:
            count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM trade_cycles "
                    "WHERE state NOT IN ('CLOSED', 'ABORTED')"
                )
            ).scalar()
        return int(count or 0)
