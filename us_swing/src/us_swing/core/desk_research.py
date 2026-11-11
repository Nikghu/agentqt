"""
Module: MD-DSK-010.001.M25 — core/desk_research.py
Parent SRD: SRD-DSK-010.001
Also: SRD-DSK-010.002–.007 (who raises, auto approval, Master edits, expiry, repeats, parked
topics), SRD-DSK-010.012 (pause on app close), SRD-DSK-010.014 (logs), SRD-DSK-007.010
(waiting alert), SRD-MKT-014.002–.004 (kinds, cap range, research block), SRD-DSK-010.015
(follow-up tickets in the raising lead's name)

The research queue in ``desk.db``. Lead skills raise tickets here, the Master user approves
or rejects waiting ones from the app through ``ticket_edits``, and the desk's research
runner works approved ones. Only lead-level employees may raise, found from their employee
files by skill, never by name.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Skill
from us_swing.core.desk_alerts import Sender, raise_alert
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_employee import JobSpec, employee_folders, read_employee

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
KINDS: tuple[str, ...] = ("setup_tuning", "post_mortem", "stock_study", "sentiment",
                          "book_to_strategy", "strategy_test")
BOOK = "book_to_strategy"
AUTO_CAP = 10_000
CAP_MIN, CAP_MAX = 1_000, 100_000
PER_DAY = 3
WAIT_DAYS = 3
REPEAT_DAYS = 30
PARK_AFTER = 3
PARK_DAYS = 30
SHOW_DAYS = 7
BLOCK_CHARS = 2_400
SHARES: dict[str, float] = {"plan": 0.5, "market": 0.2, "research": 0.3}
OPEN = ("waiting", "approved", "running", "paused")
_GAIN = {1: "yes", 0: "no"}
WORKED = ("done", "failed", "stuck")
Action = Literal["approve", "reject", "cap"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, topic TEXT, goal TEXT, done_test TEXT,
    token_cap INTEGER, step_cap INTEGER DEFAULT 8, time_cap_min INTEGER DEFAULT 60,
    raised_by TEXT, raised_by_name TEXT, status TEXT, made TEXT, approved_by TEXT,
    approved TEXT, started TEXT, ended TEXT, tokens INTEGER DEFAULT 0, steps INTEGER DEFAULT 0,
    biggest INTEGER DEFAULT 0, quiet_steps INTEGER DEFAULT 0, last_call TEXT DEFAULT '',
    state TEXT DEFAULT '{}', result TEXT DEFAULT '', end_reason TEXT DEFAULT '',
    gain INTEGER, updated TEXT
);
CREATE TABLE IF NOT EXISTS ticket_edits (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER, action TEXT, token_cap INTEGER,
    made TEXT, applied TEXT
);
"""


class TicketAsk(BaseModel):
    """A ticket as a lead writes it in its answer; the queue checks kind and cap."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(max_length=30, description="one of: " + ", ".join(KINDS))
    topic: str = Field(min_length=3, max_length=60)
    goal: str = Field(min_length=10, max_length=300)
    done_test: str = Field(min_length=10, max_length=300)
    token_cap: int = Field(description=f"{CAP_MIN} to {CAP_MAX} tokens")


@dataclass(frozen=True)
class Ticket:
    """One stored ticket; times are New York ISO text."""

    id: int
    kind: str
    topic: str
    goal: str
    done_test: str
    token_cap: int
    step_cap: int
    time_cap_min: int
    raised_by: str
    raised_by_name: str
    status: str
    made: str
    approved_by: str | None
    approved: str | None
    started: str | None
    ended: str | None
    tokens: int
    steps: int
    biggest: int
    quiet_steps: int
    last_call: str
    state: str
    result: str
    end_reason: str
    gain: int | None
    updated: str | None


_COLUMNS = ", ".join(f.name for f in fields(Ticket))


@dataclass(frozen=True)
class StepResult:
    """What one research step found; ``note`` empty means nothing new."""

    note: str
    call: str
    outcome: Literal["go", "done", "failed"]
    gain: bool | None = None
    state: dict[str, Any] = field(default_factory=dict)


class ResearchSkill(Skill, Protocol):
    """A skill that works research tickets of its ``kinds``, one AI call per step."""

    kinds: tuple[str, ...]
    step_tokens: int

    def step(self, ctx: AgentContext, ticket: Ticket) -> StepResult | None: ...


def connect(home: Path) -> sqlite3.Connection:
    """Open ``desk.db`` in ``home`` with the ticket tables ready."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    return con


def _stamp(now: datetime) -> str:
    return now.astimezone(NY).isoformat(timespec="seconds")


def _ago(now: datetime, days: float) -> str:
    return _stamp(now - timedelta(days=days))


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _ticket(row: Sequence[object]) -> Ticket:
    return Ticket(*row)  # type: ignore[arg-type]


def get_ticket(con: sqlite3.Connection, ticket_id: int) -> Ticket | None:
    """One ticket by id, or ``None``."""
    row = con.execute(f"SELECT {_COLUMNS} FROM tickets WHERE id = ?",  # noqa: S608
                      (ticket_id,)).fetchone()
    return _ticket(row) if row else None


def holder(home: Path, skill_key: str) -> JobSpec | None:
    """The active employee whose skill is ``skill_key``, from the employee files."""
    for folder in employee_folders(home):
        employee = read_employee(folder)
        if employee and employee.spec.skill == skill_key and employee.spec.status == "active":
            return employee.spec
    return None


def research_used(home: Path, payer: str, day: str) -> int:
    """Tokens ``payer`` spent from its research part on ``day`` (New York)."""
    if not (home / DB_NAME).exists():
        return 0
    con = sqlite3.connect(f"{(home / DB_NAME).as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        row = con.execute(
            "SELECT COALESCE(SUM(tokens_in + tokens_out), 0) FROM activity "
            "WHERE substr(started, 1, 10) = ? AND COALESCE(NULLIF(payer, ''), employee) = ? "
            "AND part = 'research' AND COALESCE(replay, 0) = 0", (day, payer)).fetchone()
        return int(row[0])
    except sqlite3.Error:
        return 0
    finally:
        con.close()


def research_cap(spec: JobSpec) -> int:
    """Tokens a day in the employee's research part."""
    return int(spec.tokens_per_day * SHARES["research"])


# ── raising ────────────────────────────────────────────────────────────────


def raise_tickets(home: Path, skill_key: str, asks: Sequence[TicketAsk], now: datetime,
                  send: Sender | None = None) -> list[str]:
    """Add the tickets a lead skill asked for; return one plain note per ticket.

    Args:
        home: Desk folder.
        skill_key: Key of the skill that raised them; its active lead is the raiser.
        asks: Tickets from the skill's answer.
        now: Time-zone aware time.
        send: Telegram sender for the waiting alert (``send_telegram`` when ``None``).
    """
    try:
        spec = holder(home, skill_key)
        if spec is None or spec.level != "lead":
            why = "no active lead holds this skill"
            for ask in asks:
                log.info("[Research] Ticket on %s refused: %s", ask.topic, why)
            return [f"refused: {why}" for _ in asks]
        con = connect(home)
        try:
            return [_raise_one(con, home, spec, ask, now, send) for ask in asks]
        finally:
            con.close()
    except Exception:  # noqa: BLE001 — a ticket problem must never lose the lead's answer
        log.exception("[Research] Could not add the lead's tickets")
        return ["refused: the queue could not be written" for _ in asks]


def _employee_by_id(home: Path, emp_id: str) -> JobSpec | None:
    for folder in employee_folders(home):
        employee = read_employee(folder)
        if employee and employee.spec.id == emp_id:
            return employee.spec
    return None


def raise_follow_ups(home: Path, lead_id: str, asks: Sequence[TicketAsk], now: datetime,
                     send: Sender | None = None) -> list[str]:
    """Add a research skill's follow-up tickets in the name of the lead that raised its ticket.

    The same rules as :func:`raise_tickets` apply to that lead; return one note per ticket.
    """
    if not asks:
        return []
    try:
        spec = _employee_by_id(home, lead_id)
        if spec is None or spec.level != "lead" or spec.status != "active":
            why = "the raising lead is no longer an active lead"
            for ask in asks:
                log.info("[Research] Follow-up ticket on %s refused: %s", ask.topic, why)
            return [f"refused: {why}" for _ in asks]
        con = connect(home)
        try:
            return [_raise_one(con, home, spec, ask, now, send) for ask in asks]
        finally:
            con.close()
    except Exception:  # noqa: BLE001 — a ticket problem must never lose the research result
        log.exception("[Research] Could not add the follow-up tickets")
        return ["refused: the queue could not be written" for _ in asks]


def _raise_one(con: sqlite3.Connection, home: Path, spec: JobSpec, ask: TicketAsk,
               now: datetime, send: Sender | None) -> str:
    why = _refusal(con, spec, ask, now)
    if why:
        log.info("[Research] %s raised a ticket on %s: refused, %s", spec.name, ask.topic, why)
        return f"refused: {why}"
    auto = ask.token_cap <= AUTO_CAP and ask.kind != BOOK
    status, stamp = ("approved" if auto else "waiting"), _stamp(now)
    with con:
        cur = con.execute(
            "INSERT INTO tickets (kind, topic, goal, done_test, token_cap, raised_by, "
            "raised_by_name, status, made, approved_by, approved, updated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ask.kind, ask.topic.strip(), ask.goal.strip(), ask.done_test.strip(),
             ask.token_cap, spec.id, spec.name, status, stamp, "auto" if auto else None,
             stamp if auto else None, stamp))
    tid = int(cur.lastrowid or 0)
    log.info("[Research] %s raised ticket %d (%s, %s tokens): %s", spec.name, tid,
             ask.kind.replace("_", " "), f"{ask.token_cap:,}", status)
    if not auto:
        raise_alert(home, "ticket_waiting", str(tid), 0,
                    f"Ticket {tid}: {ask.goal.strip()} ({ask.token_cap:,} tokens)", now, send)
    return f"ticket {tid} {status}"


def _refusal(con: sqlite3.Connection, spec: JobSpec, ask: TicketAsk, now: datetime) -> str:
    if ask.kind not in KINDS:
        return "unknown kind"
    if not CAP_MIN <= ask.token_cap <= CAP_MAX:
        return "cap out of range"
    day = _stamp(now)[:10]
    made = con.execute("SELECT COUNT(*) FROM tickets WHERE raised_by = ? AND "
                       "substr(made, 1, 10) = ?", (spec.id, day)).fetchone()[0]
    if int(made) >= PER_DAY:
        return f"{PER_DAY} tickets a day"
    goal = _norm(ask.goal)
    marks = ",".join("?" * len(OPEN))
    rows = con.execute(
        f"SELECT goal FROM tickets WHERE kind = ? AND (status IN ({marks}) OR "  # noqa: S608
        "(status = 'done' AND ended >= ?))", (ask.kind, *OPEN, _ago(now, REPEAT_DAYS)))
    if any(_norm(str(g)) == goal for (g,) in rows):
        return "repeat of a recent ticket"
    if _parked(con, ask.topic, now):
        return "topic parked"
    return ""


def _parked(con: sqlite3.Connection, topic: str, now: datetime) -> bool:
    marks = ",".join("?" * len(WORKED))
    rows = con.execute(f"SELECT topic, ended FROM tickets WHERE status IN ({marks}) AND "  # noqa: S608
                       "gain = 0", WORKED).fetchall()
    ends = sorted(str(e) for t, e in rows if _norm(str(t)) == _norm(topic) and e)
    return len(ends) >= PARK_AFTER and ends[-1] >= _ago(now, PARK_DAYS)


# ── research block ─────────────────────────────────────────────────────────


def with_research(text: str, home: Path, skill_key: str, now: datetime) -> str:
    """``text`` with the lead's research block after it; unchanged without a lead or desk."""
    try:
        return _with_research(text, home, skill_key, now)
    except Exception:  # noqa: BLE001 — a research block problem must never stop the lead
        log.exception("[Research] Could not add the research block to the lead's facts")
        return text


def _with_research(text: str, home: Path, skill_key: str, now: datetime) -> str:
    spec = holder(home, skill_key)
    if spec is None or spec.level != "lead" or not (home / DB_NAME).exists():
        return text
    day = _stamp(now)[:10]
    cap = research_cap(spec)
    used = research_used(home, spec.id, day)
    con = connect(home)
    try:
        marks = ",".join("?" * len(OPEN))
        open_rows = con.execute(
            f"SELECT id, kind, goal, status FROM tickets WHERE raised_by = ? AND "  # noqa: S608
            f"status IN ({marks}) ORDER BY id", (spec.id, *OPEN)).fetchall()
        worked = ",".join("?" * len(WORKED))
        ended = con.execute(
            f"SELECT goal, status, gain, result FROM tickets WHERE raised_by = ? AND "  # noqa: S608
            f"status IN ({worked}) AND ended >= ? ORDER BY ended DESC",
            (spec.id, *WORKED, _ago(now, REPEAT_DAYS))).fetchall()
    finally:
        con.close()
    lines = ["Research tickets:",
             f"Research tokens today: {used:,} used, {max(cap - used, 0):,} left of {cap:,}."]
    lines += ["Open tickets:"] + ([f"- {i} {k}: {g} ({s})" for i, k, g, s in open_rows]
                                  or ["- none"])
    lines += ["Results of the last 30 days:"] + (
        [f"- {g} ({s}, gain {_GAIN.get(n, 'not known')}): {str(r)[:150]}"
         for g, s, n, r in ended] or ["- none"])
    rules = (f"Rules: you may add at most {PER_DAY} tickets in `tickets`; kinds "
             f"{', '.join(KINDS)}; token cap {CAP_MIN:,} to {CAP_MAX:,}; tickets up to "
             f"{AUTO_CAP:,} tokens start by themselves, bigger and book tickets wait for the "
             "user; do not repeat an open ticket or a recent result.")
    block = "\n".join(lines)
    room = BLOCK_CHARS - len(rules) - 1
    if len(block) > room:
        block = block[:room].rsplit("\n", 1)[0]
    return f"{text}\n\n{block}\n{rules}"


# ── Master edits, expiry and pause ─────────────────────────────────────────


def add_ticket_edit(home: Path, ticket_id: int, action: Action, now: datetime,
                    token_cap: int | None = None) -> int:
    """Store one Master edit for the desk to apply at its next tick.

    Raises:
        ValueError: When the action is unknown or the cap is out of range.
    """
    if action not in ("approve", "reject", "cap"):
        raise ValueError(f"unknown ticket action {action}")
    if (action == "cap" and token_cap is None) or (
            token_cap is not None and not CAP_MIN <= token_cap <= CAP_MAX):
        raise ValueError(f"the cap must be {CAP_MIN:,} to {CAP_MAX:,} tokens")
    con = connect(home)
    try:
        with con:
            cur = con.execute("INSERT INTO ticket_edits (ticket_id, action, token_cap, made) "
                              "VALUES (?, ?, ?, ?)", (ticket_id, action, token_cap, _stamp(now)))
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def apply_ticket_edits(home: Path, now: datetime) -> int:
    """Apply the Master's waiting edits in order; return how many changed a ticket."""
    if not (home / DB_NAME).exists():
        return 0
    con = connect(home)
    changed = 0
    try:
        edits = con.execute("SELECT id, ticket_id, action, token_cap FROM ticket_edits "
                            "WHERE applied IS NULL ORDER BY id").fetchall()
        for eid, tid, action, cap in edits:
            with con:
                changed += _apply_edit(con, int(tid), str(action), cap, now)
                con.execute("UPDATE ticket_edits SET applied = ? WHERE id = ?",
                            (_stamp(now), eid))
    finally:
        con.close()
    return changed


def _apply_edit(con: sqlite3.Connection, tid: int, action: str, cap: object,
                now: datetime) -> int:
    ticket = get_ticket(con, tid)
    if ticket is None or ticket.status != "waiting":
        return 0
    stamp = _stamp(now)
    new_cap = int(str(cap)) if cap is not None else ticket.token_cap
    if action == "approve":
        con.execute("UPDATE tickets SET status = 'approved', approved_by = 'master', "
                    "approved = ?, token_cap = ?, updated = ? WHERE id = ?",
                    (stamp, new_cap, stamp, tid))
        log.info("[Research] Ticket %d approved by the Master user (%s tokens)", tid,
                 f"{new_cap:,}")
    elif action == "reject":
        con.execute("UPDATE tickets SET status = 'rejected', ended = ?, end_reason = "
                    "'rejected by the Master user', updated = ? WHERE id = ?",
                    (stamp, stamp, tid))
        log.info("[Research] Ticket %d rejected by the Master user", tid)
    else:
        con.execute("UPDATE tickets SET token_cap = ?, updated = ? WHERE id = ?",
                    (new_cap, stamp, tid))
        log.info("[Research] Ticket %d cap set to %s tokens; it still waits", tid,
                 f"{new_cap:,}")
    return 1


def expire_waiting(home: Path, now: datetime) -> int:
    """Expire tickets that waited for approval longer than 3 days."""
    if not (home / DB_NAME).exists():
        return 0
    con = connect(home)
    try:
        stamp = _stamp(now)
        old = [int(r[0]) for r in con.execute(
            "SELECT id FROM tickets WHERE status = 'waiting' AND made < ?",
            (_ago(now, WAIT_DAYS),))]
        with con:
            for tid in old:
                con.execute("UPDATE tickets SET status = 'expired', ended = ?, end_reason = "
                            "'not approved in 3 days', updated = ? WHERE id = ?",
                            (stamp, stamp, tid))
                log.info("[Research] Ticket %d expired: not approved in 3 days", tid)
        return len(old)
    finally:
        con.close()


def pause_running(home: Path, why: str, now: datetime, ticket_id: int | None = None) -> int:
    """Pause the running tickets (or only ``ticket_id``); they resume at the next quiet gap."""
    if not (home / DB_NAME).exists():
        return 0
    con = connect(home)
    try:
        ids = [int(r[0]) for r in con.execute(
            "SELECT id FROM tickets WHERE status = 'running' AND (? IS NULL OR id = ?)",
            (ticket_id, ticket_id))]
        with con:
            for tid in ids:
                con.execute("UPDATE tickets SET status = 'paused', end_reason = ?, "
                            "updated = ? WHERE id = ?", (why, _stamp(now), tid))
                log.info("[Research] Ticket %d paused: %s", tid, why)
        return len(ids)
    finally:
        con.close()


def save_step(con: sqlite3.Connection, ticket: Ticket, **changes: object) -> None:
    """Write changed ticket fields (``state`` as a dict is stored as JSON)."""
    if "state" in changes and isinstance(changes["state"], dict):
        changes["state"] = json.dumps(changes["state"])
    names = [n for n in changes if n in _COLUMNS.split(", ") and n != "id"]
    with con:
        con.execute(f"UPDATE tickets SET {', '.join(f'{n} = ?' for n in names)} "  # noqa: S608
                    "WHERE id = ?", (*(changes[n] for n in names), ticket.id))


# ── reads for the runner and the GUI ───────────────────────────────────────


def runnable(con: sqlite3.Connection) -> list[Ticket]:
    """Tickets to work, in order: running, then paused, then approved, oldest first."""
    rows = con.execute(
        f"SELECT {_COLUMNS} FROM tickets WHERE status IN ('running', 'paused', 'approved') "  # noqa: S608
        "ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'paused' THEN 1 ELSE 2 END, "
        "COALESCE(approved, made), id").fetchall()
    return [_ticket(r) for r in rows]


def _read_only(home: Path) -> sqlite3.Connection | None:
    path = home / DB_NAME
    if not path.exists():
        return None
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    has = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'tickets'").fetchone()
    if has is None:
        con.close()
        return None
    return con


def ticket_rows(home: Path, now: datetime) -> list[Ticket]:
    """Tickets for the AI Desk: waiting, running or paused, approved, then ended in 7 days."""
    con = _read_only(home)
    if con is None:
        return []
    try:
        rows = con.execute(
            f"SELECT {_COLUMNS} FROM tickets WHERE status IN ('waiting', 'running', "  # noqa: S608
            "'paused', 'approved') OR ended >= ? ORDER BY CASE status WHEN 'waiting' THEN 0 "
            "WHEN 'running' THEN 1 WHEN 'paused' THEN 1 WHEN 'approved' THEN 2 ELSE 3 END, "
            "COALESCE(ended, made) DESC, id DESC", (_ago(now, SHOW_DAYS),)).fetchall()
        return [_ticket(r) for r in rows]
    finally:
        con.close()


def pending_ticket_edits(home: Path) -> set[int]:
    """Ids of tickets with an edit the desk has not applied yet."""
    con = _read_only(home)
    if con is None:
        return set()
    try:
        has = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'ticket_edits'").fetchone()
        if has is None:
            return set()
        return {int(r[0]) for r in con.execute(
            "SELECT ticket_id FROM ticket_edits WHERE applied IS NULL")}
    finally:
        con.close()


def lead_research(home: Path, day: str) -> list[tuple[str, int, int]]:
    """Each active lead's name, research tokens used and left on ``day``."""
    out: list[tuple[str, int, int]] = []
    for folder in employee_folders(home):
        employee = read_employee(folder)
        if employee is None:
            continue
        spec = employee.spec
        if spec.level == "lead" and spec.status == "active":
            used = research_used(home, spec.id, day)
            out.append((spec.name, used, max(research_cap(spec) - used, 0)))
    return out
