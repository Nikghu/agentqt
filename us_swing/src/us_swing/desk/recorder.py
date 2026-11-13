"""
Module: MD-DSK-005.001.M14 — desk/recorder.py
Parent SRD: SRD-DSK-005.001
Also: SRD-DSK-011.030 (``message`` column), SRD-DSK-011.025 (message turns skip the rewake gap)
Also: SRD-DSK-005.002 (append-only), SRD-DSK-005.003 (briefs), SRD-DSK-003.009 (last wake),
SRD-DSK-005.006 (replay tries are marked), SRD-DSK-006.004 (shadow tries are marked),
SRD-DSK-004.008 (budget part, payer and ticket of each try)

Append-only records of every AI try (``activity``) and every AI feed brief (``briefs``)
in ``desk.db``. The database itself refuses updates and deletes on both tables.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from us_swing.core.desk_agents import FeedItem
from us_swing.core.desk_contract import DB_NAME

NY = ZoneInfo("America/New_York")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY, run_id INTEGER, employee TEXT, employee_name TEXT, version INTEGER,
    data_day TEXT,
    started TEXT, source TEXT, model TEXT, attempt INTEGER, prompt TEXT, answer TEXT,
    valid INTEGER, error TEXT, tokens_in INTEGER, tokens_out INTEGER, cost_usd REAL,
    seconds REAL
);
CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY, created TEXT, data_day TEXT, author TEXT, kind TEXT, text TEXT,
    employee_id TEXT
);
"""
# Columns added after the first P5a tables were created on real desks.
_ADDED = (("activity", "employee_name", "TEXT"), ("briefs", "employee_id", "TEXT"),
          ("activity", "replay", "INTEGER DEFAULT 0"), ("activity", "shadow", "INTEGER DEFAULT 0"),
          ("activity", "part", "TEXT"), ("activity", "payer", "TEXT"),
          ("activity", "ticket", "INTEGER"), ("activity", "message", "INTEGER"))
_GUARDS = [
    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} "
    f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
    for table in ("activity", "briefs") for op in ("UPDATE", "DELETE")
]


@dataclass(frozen=True)
class Attempt:
    """One gateway try; ``employee`` is the stable id, ``employee_name`` the name at the time.

    ``started`` is New York time (ISO); cost is 0 for Claude Code CLI.
    """

    run_id: int
    employee: str
    employee_name: str
    version: int
    data_day: str
    started: str
    source: str
    model: str
    attempt: int
    prompt: str
    answer: str
    valid: bool
    error: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    seconds: float
    replay: int = 0
    shadow: int = 0
    part: str = "plan"
    payer: str = ""
    ticket: int | None = None
    message: int | None = None


@dataclass(frozen=True)
class RecordedTry:
    """One stored try, as a replay reads it."""

    employee: str
    employee_name: str
    data_day: str
    source: str
    model: str
    attempt: int
    prompt: str
    answer: str
    valid: bool


def ny_now() -> datetime:
    """The current time in New York."""
    return datetime.now(NY)


class Recorder:
    """Writes and sums the append-only AI records."""

    def __init__(self, home: Path) -> None:
        """Open ``desk.db`` in ``home`` and create the tables and guards when missing."""
        home.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(home / DB_NAME, timeout=5)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA busy_timeout=5000")
        with self._con:
            self._con.executescript(_SCHEMA)
            for table, column, kind in _ADDED:
                have = {r[1] for r in self._con.execute(f"PRAGMA table_info({table})")}
                if column not in have:
                    self._con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
            for sql in _GUARDS:
                self._con.execute(sql)

    def close(self) -> None:
        """Close the connection."""
        self._con.close()

    def add(self, attempt: Attempt) -> None:
        """Append one try."""
        names = [f.name for f in fields(Attempt)]
        with self._con:
            self._con.execute(
                f"INSERT INTO activity ({', '.join(names)}) "  # noqa: S608
                f"VALUES ({', '.join('?' * len(names))})", tuple(vars(attempt).values()))

    def add_briefs(self, items: list[FeedItem], employee_id: str, name: str,
                   created: datetime | None = None) -> None:
        """Append feed briefs from one employee (its id and its name at this time)."""
        when = (created or ny_now()).isoformat(timespec="seconds")
        with self._con:
            self._con.executemany(
                "INSERT INTO briefs (created, data_day, author, kind, text, employee_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(when, i.data_day, name, i.kind, i.text, employee_id) for i in items])

    def shadow_days(self, employee_id: str) -> set[str]:
        """Data days on which a shadow employee was asked (shadow tries only)."""
        rows = self._con.execute(
            "SELECT DISTINCT data_day FROM activity WHERE employee = ? AND shadow = 1",
            (employee_id,)).fetchall()
        return {str(r[0]) for r in rows}

    def done_on(self, employee_id: str, data_day: str) -> bool:
        """True when the employee already posted a brief for ``data_day``."""
        row = self._con.execute(
            "SELECT 1 FROM briefs WHERE employee_id = ? AND data_day = ? LIMIT 1",
            (employee_id, data_day)).fetchone()
        return row is not None

    def month_cost(self, month: str, employee: str | None = None) -> float:
        """API cost in ``month`` (``YYYY-MM``, New York time), for one employee or all."""
        row = self._con.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM activity WHERE substr(started, 1, 7) = ? "
            "AND (? IS NULL OR employee = ?)", (month, employee, employee)).fetchone()
        return float(row[0])

    def day_tries(self, day: str, employee: str) -> int:
        """Live tries by ``employee`` on ``day`` (New York time); replays use no live quota."""
        row = self._con.execute(
            "SELECT COUNT(*) FROM activity WHERE substr(started, 1, 10) = ? AND employee = ? "
            "AND COALESCE(replay, 0) = 0",
            (day, employee)).fetchone()
        return int(row[0])

    def last_wake(self, employee: str) -> datetime | None:
        """Start of the employee's latest try that was not a replay, or ``None``."""
        row = self._con.execute(
            "SELECT MAX(started) FROM activity WHERE employee = ? AND COALESCE(replay, 0) = 0 "
            "AND message IS NULL",
            (employee,)).fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

    def run_tries(self, run_id: int) -> list[RecordedTry]:
        """All tries of one desk run that were not replays, oldest first."""
        rows = self._con.execute(
            "SELECT employee, employee_name, data_day, source, model, attempt, prompt, answer, "
            "valid FROM activity WHERE run_id = ? AND COALESCE(replay, 0) = 0 ORDER BY id",
            (run_id,)).fetchall()
        return [RecordedTry(str(r[0]), str(r[1] or r[0]), str(r[2]), str(r[3]), str(r[4]),
                            int(r[5]), str(r[6]), str(r[7] or ""), bool(r[8])) for r in rows]

    def day_tokens(self, day: str, source: str) -> int:
        """Tokens in and out used by ``source`` on ``day`` (New York time)."""
        row = self._con.execute(
            "SELECT COALESCE(SUM(tokens_in + tokens_out), 0) FROM activity "
            "WHERE substr(started, 1, 10) = ? AND source = ?", (day, source)).fetchone()
        return int(row[0])

    def part_tokens(self, day: str, payer: str, part: str) -> int:
        """Tokens ``payer`` spent from one budget part on ``day``; old rows count as plan."""
        row = self._con.execute(
            "SELECT COALESCE(SUM(tokens_in + tokens_out), 0) FROM activity "
            "WHERE substr(started, 1, 10) = ? AND COALESCE(NULLIF(payer, ''), employee) = ? "
            "AND COALESCE(part, 'plan') = ? AND COALESCE(replay, 0) = 0",
            (day, payer, part)).fetchone()
        return int(row[0])

    def ticket_tokens(self, ticket: int) -> int:
        """Tokens spent on one research ticket so far."""
        row = self._con.execute(
            "SELECT COALESCE(SUM(tokens_in + tokens_out), 0) FROM activity WHERE ticket = ?",
            (ticket,)).fetchone()
        return int(row[0])

    def ticket_seconds(self, ticket: int) -> float:
        """Seconds of model calls spent on one research ticket so far."""
        row = self._con.execute(
            "SELECT COALESCE(SUM(seconds), 0) FROM activity WHERE ticket = ?",
            (ticket,)).fetchone()
        return float(row[0])
