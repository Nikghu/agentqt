"""
Module: MD-DSK-006.009.M20 — desk/weekly_report.py
Parent SRD: SRD-DSK-006.009
Also: SRD-DSK-006.010 (log line); MD-MKT-009.007.M05 — pick results section (SRD-MKT-009.007)

Desk step "Weekly report": the first desk run on or after each Friday (New York) writes
one process and cost report by code, from the recorded tries and the hires. No AI call.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from pathlib import Path

from us_swing.core.desk_contract import DB_NAME, StepContext, desk_home
from us_swing.core.desk_hiring import SHADOW_DAYS, employees, list_hires
from us_swing.core.desk_results import results_lines, results_view
from us_swing.desk.recorder import NY, ny_now

log = logging.getLogger(__name__)

_SCHEMA = ("CREATE TABLE IF NOT EXISTS desk_reports (id INTEGER PRIMARY KEY, week TEXT UNIQUE, "
           "created TEXT, title TEXT, text TEXT)")


def report_friday(today: date) -> date:
    """The latest Friday on or before ``today``."""
    return today - timedelta(days=(today.weekday() - 4) % 7)


def _has_activity(con: sqlite3.Connection) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE name = 'activity'").fetchone() is not None


def build_report(home: Path, friday: date) -> tuple[str, int, float]:
    """Report text for the week Saturday..``friday``; also the employee count and cost."""
    first = friday - timedelta(days=6)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    try:
        rows = [] if not _has_activity(con) else con.execute(
            "SELECT employee, MAX(employee_name), COUNT(*), SUM(valid), "
            "SUM(tokens_in + tokens_out), SUM(cost_usd), MAX(COALESCE(shadow, 0)) "
            "FROM activity WHERE substr(started, 1, 10) BETWEEN ? AND ? "
            "AND COALESCE(replay, 0) = 0 GROUP BY employee ORDER BY employee",
            (first.isoformat(), friday.isoformat())).fetchall()
    finally:
        con.close()
    names = {e.id: e.name for e in employees(home)}
    lines = [f"Weekly report {first.isoformat()} to {friday.isoformat()}", "",
             "Employee | tries | valid | failed | tokens | cost USD"]
    total_cost = 0.0
    total_tokens = 0
    for emp, old_name, tries, valid, tokens, cost, shadow in rows:
        name = names.get(str(emp), str(old_name or emp)) + (" (shadow)" if shadow else "")
        good = int(valid or 0)
        total_cost += float(cost or 0.0)
        total_tokens += int(tokens or 0)
        lines.append(f"{name} | {tries} | {round(100 * good / tries)}% | {tries - good} | "
                     f"{int(tokens or 0):,} | {float(cost or 0.0):.4f}")
    if not rows:
        lines.append("(no AI work this week)")
    lines += ["", f"Total: {total_tokens:,} tokens, USD {total_cost:.4f}", "", "Shadow hires:"]
    shadows = [h for h in list_hires(home) if h.employee.status == "shadow"]
    lines += [f"{h.employee.name} ({h.employee.skill.replace('_', ' ')}): {h.days} of "
              f"{SHADOW_DAYS} days{' - ready for a decision' if h.ready else ''}"
              for h in shadows] or ["(none)"]
    week_end = datetime.combine(friday, time(23, 59), tzinfo=NY)
    lines += ["", "Pick results:", *results_lines(
        results_view(home, week_end, first.isoformat(), friday.isoformat()))]
    return "\n".join(lines), len(rows), total_cost


class WeeklyReportStep:
    """Writes one weekly report per week, by code only."""

    name = "Weekly report"

    def __init__(self, clock: Callable[[], datetime] = ny_now) -> None:
        """Use ``clock`` (New York time) to pick the week; injectable for tests."""
        self._clock = clock

    def __call__(self, ctx: StepContext) -> None:
        """Write the report for the latest Friday unless it exists already."""
        home = ctx.home or desk_home()
        friday = report_friday(self._clock().astimezone(NY).date())
        home.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(home / DB_NAME, timeout=5)
        try:
            with con:
                con.execute(_SCHEMA)
            if con.execute("SELECT 1 FROM desk_reports WHERE week = ?",
                           (friday.isoformat(),)).fetchone():
                return
        finally:
            con.close()
        text, count, cost = build_report(home, friday)
        con = sqlite3.connect(home / DB_NAME, timeout=5)
        try:
            with con:
                con.execute("INSERT OR IGNORE INTO desk_reports (week, created, title, text) "
                            "VALUES (?, ?, ?, ?)",
                            (friday.isoformat(), self._clock().isoformat(timespec="seconds"),
                             f"Weekly report {friday.isoformat()}", text))
        finally:
            con.close()
        log.info("[Report] Weekly report for %s written: %d employee(s), cost USD %.2f",
                 friday.isoformat(), count, cost)
