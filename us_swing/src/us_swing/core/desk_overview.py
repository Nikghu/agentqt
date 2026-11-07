"""
Module: MD-GUI-034.060.M34 — core/desk_overview.py
Parent SRD: SRD-GUI-034.060
Also: SRD-GUI-034.063 (today's runs), SRD-GUI-034.064 (team counts)

AI Desk header and Command facts read from ``desk.db`` read-only: today's runs, the last run,
AI spend against the month budget and employee counts. Never imports ``desk``.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_hiring import employees

NY = ZoneInfo("America/New_York")
_NAMES = {"evening": "Evening run", "manual": "Manual run", "event": "Event runs"}
_WORST = {"failed": 3, "error": 3, "running": 2, "ok": 1}


@dataclass(frozen=True)
class RunRow:
    """One line of Today's runs; ``count`` is above 1 only for the summed event row."""

    when: datetime
    name: str
    result: str
    count: int = 1


@dataclass(frozen=True)
class Spend:
    """AI spend today and this month, and the month budget, in USD."""

    today_usd: float
    month_usd: float
    budget_usd: float

    @property
    def month_share(self) -> float:
        """Share of the month budget used, 0 to 1 (capped)."""
        return min(self.month_usd / self.budget_usd, 1.0) if self.budget_usd > 0 else 0.0


def run_name(kind: str) -> str:
    """Plain name of a run kind."""
    return _NAMES.get(kind, kind.replace("_", " ").title())


def _rows(home: Path, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    path = home / DB_NAME
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
        try:
            return [tuple(r) for r in con.execute(sql, params).fetchall()]
        finally:
            con.close()
    except sqlite3.Error:
        return []


def _when(text: object) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return stamp.astimezone(NY) if stamp.tzinfo is not None else None


def todays_runs(home: Path, now: datetime) -> list[RunRow]:
    """Runs started on the New York day of ``now``, oldest first; event runs make one row."""
    today = now.astimezone(NY).date()
    out: list[RunRow] = []
    events: list[tuple[datetime, str]] = []
    for started, kind, result in _rows(
            home, "SELECT started_at, kind, result FROM runs ORDER BY id"):
        when = _when(started)
        if when is None or when.date() != today:
            continue
        if kind == "event":
            events.append((when, str(result)))
        else:
            out.append(RunRow(when, run_name(str(kind)), str(result)))
    if events:
        worst = max((r for _w, r in events), key=lambda r: _WORST.get(r, 0))
        out.append(RunRow(events[-1][0], run_name("event"), worst, len(events)))
    return sorted(out, key=lambda r: r.when)


def last_run(home: Path) -> RunRow | None:
    """The latest finished run that is not an event run, or ``None``."""
    rows = _rows(home, "SELECT ended_at, kind, result FROM runs WHERE kind <> 'event' "
                       "AND ended_at IS NOT NULL ORDER BY id DESC LIMIT 1")
    if not rows:
        return None
    ended, kind, result = rows[0]
    when = _when(ended)
    return RunRow(when, run_name(str(kind)), str(result)) if when else None


def spend(home: Path, now: datetime) -> Spend | None:
    """Today's and this month's AI spend (New York dates), or ``None`` before any AI call."""
    et = now.astimezone(NY)
    rows = _rows(home, "SELECT COALESCE(SUM(CASE WHEN substr(started, 1, 10) = ? THEN cost_usd "
                       "END), 0), COALESCE(SUM(cost_usd), 0), COUNT(*) FROM activity "
                       "WHERE substr(started, 1, 7) = ?",
                 (et.strftime("%Y-%m-%d"), et.strftime("%Y-%m")))
    if not rows or not rows[0][2]:
        return None
    today, month, _count = rows[0]
    return Spend(float(today), float(month), load_settings(home).monthly_budget_usd)


def team_counts(home: Path) -> dict[str, int]:
    """Employee count by status, most common first."""
    return dict(Counter(e.status for e in employees(home)).most_common())
