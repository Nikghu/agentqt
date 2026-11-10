"""Shared desk.db fixtures for the Team at work tests (FO-GUI-035). Employee names are made up."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from us_swing.core.desk_events import post_event
from us_swing.desk.recorder import Attempt, Recorder
from us_swing.desk.store import DeskStore

NY = ZoneInfo("America/New_York")
DAY = "2026-11-09"
NOW = datetime(2026, 11, 9, 16, 27, 30, tzinfo=NY)
NEEDS = {"regime_view": (), "sector_flow_view": (),
         "risk_check": ("regime_view", "sector_flow_view"), "lead_chat": ()}
HIRES = (("emp-a", "Alpha", "regime_view", "after_run"),
         ("emp-b", "Beta", "sector_flow_view", "after_run"),
         ("emp-c", "Gamma", "risk_check", "after_run"),
         ("emp-d", "Delta", "lead_chat", "chat_question"))


def hire(home: Path, emp: str, name: str, skill: str, trigger: str) -> None:
    """Write one employee job file."""
    folder = home / "employees" / emp
    folder.mkdir(parents=True, exist_ok=True)
    job = {"id": emp, "name": name, "title": "Tester", "level": "expert", "reports_to": None,
           "skill": skill, "version": 1, "trigger": trigger,
           "models": {"primary": {"source": "claude", "model": "default"},
                      "backup": {"source": "openrouter", "model": "default"}},
           "calls_per_day": 3, "monthly_cost_usd": 3.0, "kpis": ["Share of valid answers"]}
    (folder / "job.yaml").write_text(yaml.safe_dump(job), encoding="utf-8")
    (folder / "soul.md").write_text("You are {name}.", encoding="utf-8")


def call(home: Path, run_id: int, emp: str, hhmmss: str, valid: bool, attempt: int = 1,
         source: str = "claude", cost: float = 0.01, seconds: float = 5.0,
         error: str = "") -> None:
    """Record one LLM try on ``DAY`` at ``hhmmss`` New York time."""
    rec = Recorder(home)
    try:
        rec.add(Attempt(run_id, emp, emp.upper(), 1, DAY, f"{DAY}T{hhmmss}-05:00", source, "m",
                        attempt, "the prompt", "the answer" if valid else "", valid, error,
                        1000, 200, cost, seconds))
    finally:
        rec.close()


def desk(home: Path, finished: bool) -> int:
    """Four employees, one evening run (running or finished) and one chat question.

    Alpha answers; Beta's first try is bad. When ``finished`` Beta's backup try is valid and
    the run ends; Gamma never calls.
    """
    for h in HIRES:
        hire(home, *h)
    store = DeskStore(home)
    run_id = store.start_run("evening", datetime(2026, 11, 9, 21, 25, tzinfo=UTC))
    post_event(home, "after_run", DAY, datetime(2026, 11, 9, 16, 27, tzinfo=NY), run_id)
    call(home, run_id, "emp-a", "16:27:05", True)
    call(home, run_id, "emp-b", "16:27:12", False, error="answer missing a field")
    if finished:
        call(home, run_id, "emp-b", "16:27:20", True, attempt=2, source="openrouter")
        store.end_run(run_id, "ok", datetime(2026, 11, 9, 21, 28, tzinfo=UTC))
    store.close()
    post_event(home, "chat_question", DAY, datetime(2026, 11, 9, 14, 0, tzinfo=NY), 7)
    call(home, 99, "emp-d", "14:00:02", True, cost=0.002)
    return run_id
