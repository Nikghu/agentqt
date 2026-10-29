"""
Module: MD-BKT-002.007.M04 — backtest/results.py
Parent SRD: SRD-BKT-002.007

Results store (``results.db``): one row per run with its plan and status.
Variant, trade and log tables are added in Phase 3.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from us_swing.backtest import DEFAULT_ROOT
from us_swing.backtest.spec import RunPlan

DEFAULT_RESULTS_PATH: Path = DEFAULT_ROOT / "results.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id   TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    status   TEXT NOT NULL,
    started  TEXT NOT NULL,
    finished TEXT,
    message  TEXT NOT NULL DEFAULT ''
)
"""


@dataclass(frozen=True)
class RunRow:
    """One saved run."""

    run_id: str
    name: str
    plan_json: str
    status: str
    started: datetime
    finished: datetime | None
    message: str


class ResultsStore:
    """Repository for backtest run rows."""

    def __init__(self, path: Path = DEFAULT_RESULTS_PATH) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def start_run(self, plan: RunPlan, now: datetime) -> str:
        """Save a new run with status ``running`` and return its id."""
        run_id = uuid.uuid4().hex
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO runs (run_id, name, plan_json, status, started) "
                "VALUES (?, ?, ?, 'running', ?)",
                (run_id, plan.name, plan.to_json(), now.isoformat()),
            )
        return run_id

    def finish_run(self, run_id: str, status: str, now: datetime, message: str = "") -> None:
        """Set the final status (``done``, ``cancelled`` or ``failed``) and end time."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE runs SET status = ?, finished = ?, message = ? WHERE run_id = ?",
                (status, now.isoformat(), message, run_id),
            )

    def get_run(self, run_id: str) -> RunRow | None:
        """Return one run, or ``None`` when the id is unknown."""
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT run_id, name, plan_json, status, started, finished, message "
                "FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return _row(row) if row else None

    def list_runs(self, limit: int = 50) -> list[RunRow]:
        """Return the newest runs first."""
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                "SELECT run_id, name, plan_json, status, started, finished, message "
                "FROM runs ORDER BY started DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row(r) for r in rows]


def _row(r: tuple[str, str, str, str, str, str | None, str]) -> RunRow:
    return RunRow(
        run_id=r[0], name=r[1], plan_json=r[2], status=r[3],
        started=datetime.fromisoformat(r[4]),
        finished=datetime.fromisoformat(r[5]) if r[5] else None,
        message=r[6],
    )
