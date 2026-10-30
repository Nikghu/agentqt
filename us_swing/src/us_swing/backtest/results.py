"""
Module: MD-BKT-002.007.M04 — backtest/results.py
Parent SRD: SRD-BKT-002.007, SRD-BKT-002.039, SRD-BKT-002.040

Results store (``results.db``): one row per run with its plan and status, and
per variant its trades, day log and money-by-day rows (Phase 3).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from us_swing.backtest import DEFAULT_ROOT
from us_swing.backtest.spec import RunPlan, Variant

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
_VARIANT_TABLES = ("trades", "day_log", "money_daily")


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
    note: str = ""


class ResultsStore:
    """Repository for backtest run rows."""

    def __init__(self, path: Path = DEFAULT_RESULTS_PATH) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)
            columns = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
            if "note" not in columns:
                conn.execute("ALTER TABLE runs ADD COLUMN note TEXT NOT NULL DEFAULT ''")

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
                f"SELECT {_RUN_COLUMNS} FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return _row(row) if row else None

    def save_variant(self, run_id: str, index: int, variant: Variant, trades: pd.DataFrame,
                     day_log: pd.DataFrame, money: pd.DataFrame) -> str:
        """Save one variant's Step 3 rows (SRD-BKT-002.039); returns the variant id."""
        variant_id = f"{run_id}-{index}"
        head = pd.DataFrame([{
            "variant_id": variant_id, "run_id": run_id, "capital": variant.capital,
            "strategies_json": json.dumps([list(s) for s in variant.strategies]),
        }])
        with closing(self._connect()) as conn, conn:
            for name, frame in (("variants", head), ("trades", trades),
                                ("day_log", day_log), ("money_daily", money)):
                _as_text(frame).assign(variant_id=variant_id).to_sql(
                    name, conn, if_exists="append", index=False)
        return variant_id

    def read_table(self, name: str, variant_id: str) -> pd.DataFrame:
        """Read one saved table for a variant (``trades``, ``day_log``, ``money_daily``)."""
        if name not in ("trades", "day_log", "money_daily"):
            raise ValueError(f"Unknown results table {name!r}")
        with closing(self._connect()) as conn:
            return pd.read_sql_query(f"SELECT * FROM {name} WHERE variant_id = ?", conn,
                                     params=(variant_id,))

    def list_variants(self, run_id: str) -> list[tuple[str, Variant]]:
        """Return (variant id, variant) for each saved variant of a run, in order."""
        with closing(self._connect()) as conn:
            if not conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                "AND name = 'variants'").fetchone():
                return []
            rows = conn.execute(
                "SELECT variant_id, capital, strategies_json FROM variants WHERE run_id = ? "
                "ORDER BY rowid", (run_id,),
            ).fetchall()
        return [(vid, Variant(float(cap), tuple((str(s[0]), float(s[1]), float(s[2]))
                                                for s in json.loads(text))))
                for vid, cap, text in rows]

    def list_runs(self, limit: int = 50) -> list[RunRow]:
        """Return the newest runs first."""
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                f"SELECT {_RUN_COLUMNS} FROM runs ORDER BY started DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row(r) for r in rows]

    def list_reports(self, limit: int = 200) -> list[RunRow]:
        """Newest runs that saved Step 3 results (one per Run press) (SRD-GUI-031.055)."""
        with closing(self._connect()) as conn:
            if not _has_table(conn, "variants"):
                return []
            rows = conn.execute(
                f"SELECT {_RUN_COLUMNS} FROM runs WHERE run_id IN "
                "(SELECT run_id FROM variants) ORDER BY started DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row(r) for r in rows]

    def rename_run(self, run_id: str, name: str) -> None:
        """Give a run a new name (SRD-BKT-002.060)."""
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE runs SET name = ? WHERE run_id = ?", (name, run_id))

    def set_note(self, run_id: str, note: str) -> None:
        """Keep a free-text note on a run (SRD-BKT-002.060)."""
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE runs SET note = ? WHERE run_id = ?", (note, run_id))

    def delete_run(self, run_id: str) -> None:
        """Delete a run with its variants, trades, day log and money rows (SRD-BKT-002.060)."""
        with closing(self._connect()) as conn, conn:
            if _has_table(conn, "variants"):
                ids = [r[0] for r in conn.execute(
                    "SELECT variant_id FROM variants WHERE run_id = ?", (run_id,))]
                for name in _VARIANT_TABLES:
                    if _has_table(conn, name):
                        conn.executemany(f"DELETE FROM {name} WHERE variant_id = ?",
                                         [(v,) for v in ids])
                conn.execute("DELETE FROM variants WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))


_RUN_COLUMNS = "run_id, name, plan_json, status, started, finished, message, note"


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def _as_text(frame: pd.DataFrame) -> pd.DataFrame:
    """Dates and timestamps as ISO text, so SQLite keeps them readable."""
    out = frame.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]) or out[col].dtype == object:
            out[col] = out[col].map(lambda v: v.isoformat() if hasattr(v, "isoformat") else v)
    return out


def _row(r: tuple[str, str, str, str, str, str | None, str, str]) -> RunRow:
    return RunRow(
        run_id=r[0], name=r[1], plan_json=r[2], status=r[3],
        started=datetime.fromisoformat(r[4]),
        finished=datetime.fromisoformat(r[5]) if r[5] else None,
        message=r[6],
        note=r[7],
    )
