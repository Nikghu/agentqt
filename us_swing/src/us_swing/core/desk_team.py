"""
Module: MD-GUI-035.002.M02 — core/desk_team.py
Parent SRD: SRD-GUI-035.002
Also: SRD-GUI-035.004–.009 (run view, events, scorecard and profile data)

Read-only facts for AI Desk → Team at work: the team from the employee job files, desk runs,
each run's LLM calls and employee states, the day's events with their calls, a 30-day
scorecard and a short history per employee. Never imports ``desk``.
"""
from __future__ import annotations

import importlib
import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from functools import cache
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml  # type: ignore[import-untyped]

from us_swing.core.desk_contract import DB_NAME, parse_utc

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
EVENING_KINDS = ("evening", "manual")
URGENT = 0
_CALL_COLS = ("run_id, employee, employee_name, started, source, model, attempt, valid, error, "
              "tokens_in, tokens_out, cost_usd, seconds, prompt, answer")
_REAL = "COALESCE(replay, 0) = 0 AND COALESCE(shadow, 0) = 0"
_EVENT_NAMES = {
    "after_run": "Evening run", "regime_change": "Regime change", "market_open": "Market open",
    "market_close": "Market close", "chat_question": "Chat question", "data_request": "Data ask",
}
_EVENT_WHY = {
    "after_run": "Desk run finished its data steps",
    "regime_change": "The rule regime changed",
    "market_open": "NYSE opened",
    "market_close": "NYSE closed",
    "chat_question": "You asked the lead a question",
    "data_request": "You asked the desk for new data",
}


@dataclass(frozen=True)
class Member:
    """One AI employee as its job file describes it; ``needs`` holds employee ids."""

    id: str
    name: str
    title: str
    level: str
    skill: str
    status: str
    triggers: tuple[str, ...]
    reports_to: str
    primary: str
    backup: str
    calls_per_day: int
    month_cap_usd: float
    kpis: tuple[str, ...]
    needs: tuple[str, ...] = ()

    @property
    def on_demand(self) -> bool:
        """True when the member does not wake on the evening run."""
        return "after_run" not in self.triggers


@dataclass(frozen=True)
class Call:
    """One recorded LLM try."""

    run_id: int
    employee: str
    employee_name: str
    started: datetime
    source: str
    model: str
    attempt: int
    valid: bool
    error: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    seconds: float
    prompt: str
    answer: str

    @property
    def ended(self) -> datetime:
        """When the try finished."""
        return self.started + timedelta(seconds=self.seconds)


@dataclass(frozen=True)
class Run:
    """One desk run from the ``runs`` table; times are New York time."""

    id: int
    kind: str
    started: datetime
    ended: datetime | None
    result: str


@dataclass(frozen=True)
class MemberState:
    """What one employee is doing in a run: key is asleep, waiting, working, done, failed or
    skipped."""

    key: str
    label: str
    calls: tuple[Call, ...] = ()


@dataclass(frozen=True)
class RunView:
    """A run with the moment its AI part began and each woken employee's state."""

    run: Run
    ai_started: datetime | None
    states: dict[str, MemberState]
    calls: tuple[Call, ...]


@dataclass(frozen=True)
class DeskEvent:
    """One stored event with the calls it caused."""

    id: int
    kind: str
    priority: int
    data_day: str
    created: datetime
    deadline: datetime | None
    handled: datetime | None
    state: str
    note: str
    calls: tuple[Call, ...] = ()

    @property
    def name(self) -> str:
        """Plain event name."""
        return _EVENT_NAMES.get(self.kind, self.kind.replace("_", " ").capitalize())

    @property
    def why(self) -> str:
        """Plain reason the event fired."""
        return _EVENT_WHY.get(self.kind, "")


@dataclass(frozen=True)
class Score:
    """30-day numbers for one employee (or the team when ``employee`` is empty)."""

    employee: str
    runs: int
    calls: int
    valid: int
    retries: int
    backup_calls: int
    avg_seconds: float
    max_seconds: float
    avg_tokens_in: float
    avg_tokens_out: float
    cost_usd: float
    last_problem: datetime | None
    last_error: str

    @property
    def valid_share(self) -> float | None:
        """Share of calls with a valid answer, or ``None`` without calls."""
        return self.valid / self.calls if self.calls else None

    @property
    def cost_per_answer(self) -> float | None:
        """Cost per valid answer, or ``None`` without one."""
        return self.cost_usd / self.valid if self.valid else None


@dataclass(frozen=True)
class DayWork:
    """One day of an employee's work."""

    day: str
    calls: int
    valid: bool
    seconds: float
    cost_usd: float


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
        log.debug("[AI Desk] Could not read %s", sql.split()[0:4])
        return []


def _ny(text: object) -> datetime | None:
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return stamp.astimezone(NY) if stamp.tzinfo is not None else stamp.replace(tzinfo=NY)


@cache
def skill_needs() -> dict[str, tuple[str, ...]]:
    """Skill key → the skill keys it needs, read from the skill classes once."""
    from us_swing.core.desk_steps import SKILL_PATHS  # noqa: PLC0415 — avoids a cycle

    needs: dict[str, tuple[str, ...]] = {}
    for key, path in SKILL_PATHS.items():
        module_name, _, class_name = path.partition(":")
        try:
            cls = getattr(importlib.import_module(module_name), class_name)
            needs[key] = tuple(getattr(cls, "needs", ()))
        except Exception:  # noqa: BLE001 — a bad skill must not stop the page
            log.warning("[AI Desk] Could not read what skill %s needs", key)
            needs[key] = ()
    return needs


def _model(data: dict[str, Any], which: str) -> str:
    spec = (data.get("models") or {}).get(which) or {}
    return f"{spec.get('source', '')} / {spec.get('model', '')}" if spec else ""


def _member(folder: Path) -> Member | None:
    try:
        data = yaml.safe_load((folder / "job.yaml").read_text(encoding="utf-8"))
        trig = data.get("trigger") or ()
        triggers = (trig,) if isinstance(trig, str) else tuple(str(t) for t in trig)
        return Member(
            str(data["id"]), str(data["name"]), str(data.get("title") or ""),
            str(data.get("level") or ""), str(data["skill"]), str(data.get("status") or "active"),
            triggers, str(data.get("reports_to") or ""), _model(data, "primary"),
            _model(data, "backup"), int(data.get("calls_per_day") or 0),
            float(data.get("monthly_cost_usd") or 0.0),
            tuple(str(k) for k in data.get("kpis") or ()))
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError, AttributeError):
        log.warning("[AI Desk] Could not read the job file in %s", folder.name)
        return None


def team(home: Path, needs: dict[str, tuple[str, ...]] | None = None) -> list[Member]:
    """Every readable employee, in run order, with ``needs`` resolved to employee ids.

    Args:
        home: Desk folder.
        needs: Skill key → needed skill keys; read from the skill classes when ``None``.
    """
    root = home / "employees"
    folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    members = [m for m in (_member(f) for f in folders) if m is not None]
    wants = skill_needs() if needs is None else needs
    by_skill: dict[str, list[str]] = {}
    for m in members:
        by_skill.setdefault(m.skill, []).append(m.id)
    linked = [
        replace(m, needs=tuple(i for key in wants.get(m.skill, ()) if key != m.skill
                               for i in by_skill.get(key, ())))
        for m in members
    ]
    return _ordered(linked)


def _ordered(members: Sequence[Member]) -> list[Member]:
    graph = {m.id: list(m.needs) for m in members}
    try:
        order = list(TopologicalSorter(graph).static_order())
    except CycleError:
        return list(members)
    rank = {mid: i for i, mid in enumerate(order)}
    return sorted(members, key=lambda m: (m.on_demand, rank.get(m.id, 0)))


def levels(members: Sequence[Member]) -> list[list[Member]]:
    """Group evening-run members into columns: each column needs only earlier columns."""
    depth: dict[str, int] = {}
    evening = [m for m in members if not m.on_demand]
    for m in evening:
        depth[m.id] = 1 + max((depth.get(n, 0) for n in m.needs), default=-1)
    cols: list[list[Member]] = [[] for _ in range(max(depth.values(), default=-1) + 1)]
    for m in evening:
        cols[depth[m.id]].append(m)
    return cols


def runs(home: Path, limit: int = 30) -> list[Run]:
    """Recent evening and manual runs, newest first."""
    marks = ",".join("?" * len(EVENING_KINDS))
    rows = _rows(home, f"SELECT id, kind, started_at, ended_at, result FROM runs "
                       f"WHERE kind IN ({marks}) ORDER BY id DESC LIMIT ?",
                 (*EVENING_KINDS, limit))
    out: list[Run] = []
    for rid, kind, start, end, result in rows:
        started = parse_utc(start)
        if started is None:
            continue
        ended = parse_utc(end)
        out.append(Run(int(rid), str(kind), started.astimezone(NY),
                       ended.astimezone(NY) if ended else None, str(result)))
    return out


def _calls(home: Path, where: str, params: tuple[Any, ...]) -> list[Call]:
    rows = _rows(home, f"SELECT {_CALL_COLS} FROM activity WHERE {_REAL} AND {where} "
                       "ORDER BY started, id", params)
    out: list[Call] = []
    for r in rows:
        started = _ny(r[3])
        if started is None:
            continue
        out.append(Call(int(r[0] or 0), str(r[1]), str(r[2] or r[1]), started, str(r[4] or ""),
                        str(r[5] or ""), int(r[6] or 1), bool(r[7]), str(r[8] or ""),
                        int(r[9] or 0), int(r[10] or 0), float(r[11] or 0.0),
                        float(r[12] or 0.0), str(r[13] or ""), str(r[14] or "")))
    return out


def run_calls(home: Path, run_id: int) -> list[Call]:
    """Every real LLM try of one run, oldest first."""
    return _calls(home, "run_id = ?", (run_id,))


def _ai_start(home: Path, run_id: int) -> datetime | None:
    rows = _rows(home, "SELECT created FROM events WHERE kind = 'after_run' AND key LIKE ?",
                 (f"after_run|%|{run_id}",))
    return _ny(rows[0][0]) if rows else None


def _done_state(member: Member, mine: Sequence[Call]) -> MemberState:
    if not any(c.valid for c in mine):
        return MemberState("failed", "Failed", tuple(mine))
    main_source = member.primary.split(" / ")[0]
    if any(c.valid and c.source != main_source for c in mine):
        return MemberState("done", "Done · backup used", tuple(mine))
    retries = len(mine) - 1
    return MemberState("done", f"Done · {retries} retry" if retries else "Done", tuple(mine))


def run_view(home: Path, run: Run, members: Sequence[Member]) -> RunView:
    """Each evening-run employee's state in ``run``; on-demand employees are asleep."""
    calls = run_calls(home, run.id)
    ai_started = _ai_start(home, run.id)
    running = run.ended is None
    woken = [m for m in members if not m.on_demand and m.status == "active"]
    by_member: dict[str, list[Call]] = {}
    for c in calls:
        by_member.setdefault(c.employee, []).append(c)
    states: dict[str, MemberState] = {}
    for i, m in enumerate(woken):
        mine = by_member.get(m.id, [])
        later = any(by_member.get(n.id) for n in woken[i + 1:])
        valid = any(c.valid for c in mine)
        if running and ai_started is not None and not later and not valid and (
                mine or not any(s.key == "working" for s in states.values())):
            label = f"Working · try {len(mine) + 1}" if mine else "Working"
            states[m.id] = MemberState("working", label, tuple(mine))
        elif mine:
            states[m.id] = _done_state(m, mine)
        elif running:
            states[m.id] = MemberState("waiting", "Waiting for data" if ai_started is None
                                       else "Waiting")
        else:
            states[m.id] = MemberState("skipped", "No call")
    for m in members:
        states.setdefault(m.id, MemberState("asleep", "Asleep"))
    return RunView(run, ai_started, states, tuple(calls))


def day_events(home: Path, day: date, members: Sequence[Member],
               now: datetime | None = None) -> list[DeskEvent]:
    """The events created on New York ``day``, newest first, each with the calls it caused.

    An evening run event takes its run's calls; other events take the calls of the employees
    that listen to them, made between the event and its handling.
    """
    rows = _rows(home, "SELECT id, key, kind, priority, data_day, created, deadline, handled, "
                       "state, note FROM events WHERE substr(created, 1, 10) = ? "
                       "ORDER BY created DESC, id DESC", (day.isoformat(),))
    out: list[DeskEvent] = []
    for eid, key, kind, prio, data_day, created, deadline, handled, state, note in rows:
        made = _ny(created)
        if made is None:
            continue
        done = _ny(handled)
        if kind == "after_run":
            run_id = str(key).rsplit("|", 1)[-1]
            calls = run_calls(home, int(run_id)) if run_id.lstrip("-").isdigit() else []
        else:
            ids = [m.id for m in members if kind in m.triggers]
            end = done or now or datetime.now(NY)
            calls = [c for c in _calls(home, "started >= ? AND started <= ?",
                                       (made.isoformat(timespec="seconds"),
                                        end.isoformat(timespec="seconds")))
                     if c.employee in ids] if ids else []
        out.append(DeskEvent(int(eid), str(kind), int(prio), str(data_day), made, _ny(deadline),
                             done, str(state), str(note or ""), tuple(calls)))
    return out


def scorecard(home: Path, members: Sequence[Member], now: datetime,
              days: int = 30) -> list[Score]:
    """30-day numbers per employee in ``members`` order, then a team total row."""
    since = (now - timedelta(days=days)).isoformat(timespec="seconds")
    calls = _calls(home, "started >= ?", (since,))
    main = {m.id: m.primary.split(" / ")[0] for m in members}
    out = [_score(m.id, [c for c in calls if c.employee == m.id], main) for m in members]
    out.append(_score("", calls, main))
    return out


def _score(employee: str, calls: Sequence[Call], main: dict[str, str]) -> Score:
    n = len(calls)
    bad = [c for c in calls if not c.valid]
    last_bad = max(bad, key=lambda c: c.started) if bad else None
    return Score(
        employee, len({(c.employee, c.run_id) for c in calls}), n,
        sum(1 for c in calls if c.valid), sum(1 for c in calls if c.attempt > 1),
        sum(1 for c in calls if c.source != main.get(c.employee, c.source)),
        sum(c.seconds for c in calls) / n if n else 0.0,
        max((c.seconds for c in calls), default=0.0),
        sum(c.tokens_in for c in calls) / n if n else 0.0,
        sum(c.tokens_out for c in calls) / n if n else 0.0,
        sum(c.cost_usd for c in calls),
        last_bad.started if last_bad else None,
        last_bad.error if last_bad else "")


def history(home: Path, employee: str, days: int = 4) -> list[DayWork]:
    """The employee's last ``days`` working days, newest first."""
    rows = _rows(home, "SELECT substr(started, 1, 10) AS d, COUNT(*), MAX(valid), "
                       f"SUM(seconds), SUM(cost_usd) FROM activity WHERE {_REAL} AND "
                       "employee = ? GROUP BY d ORDER BY d DESC LIMIT ?", (employee, days))
    return [DayWork(str(d), int(n), bool(v), float(s or 0.0), float(c or 0.0))
            for d, n, v, s, c in rows]


def month_cost(home: Path, employee: str, now: datetime) -> float:
    """The employee's AI cost in the New York month of ``now``."""
    rows = _rows(home, "SELECT COALESCE(SUM(cost_usd), 0) FROM activity WHERE "
                       "substr(started, 1, 7) = ? AND employee = ?",
                 (now.astimezone(NY).strftime("%Y-%m"), employee))
    return float(rows[0][0]) if rows else 0.0


def last_brief(home: Path, employee: str) -> str:
    """The employee's latest brief text, or an empty string."""
    rows = _rows(home, "SELECT text FROM briefs WHERE employee_id = ? ORDER BY id DESC LIMIT 1",
                 (employee,))
    return str(rows[0][0]) if rows else ""
