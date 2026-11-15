"""
Module: MD-DSK-006.012.M35 — core/desk_proposals.py
Parent SRD: SRD-DSK-006.012
Also: SRD-DSK-006.013 (costly need), .014 (empty need), .015 (candidates), .018 (proposal row),
.021 (the boss's view), .022 (approve), .023 (reject), .026 (reads and card text) — AI Desk v3 M7a

Hire proposals: three need rules over the desk's own records, the candidates the secretary may
pick from, the ``hire_proposals`` table in ``desk.db``, the boss's view and the Master user's
gate 1 decision. Evidence lines are written here, by code, never by the AI. Shared by the desk
(the secretary skill and the boss turn) and the GUI (cards, Hiring list, decisions).
Design: DD-DSK-006.011.D01.
"""
from __future__ import annotations

import importlib
import json
import logging
import re
import sqlite3
import statistics
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_hiring import (
    _APPROVALS,
    HIRE_LEVELS,
    Employee,
    default_level,
    employees,
    seat_counts,
    start_hire,
)
from us_swing.core.desk_registry import HIRE_PROPOSAL
from us_swing.core.desk_steps import SKILL_PATHS

log = logging.getLogger(__name__)

DAYS = 10
MIN_TRIES = 5
MIN_VALID_SHARE = 0.70
MIN_VALID_FOR_COST = 3
MIN_COSTED = 3
COSTLY_TIMES = 3.0
REJECT_DAYS = 30
LIST_LIMIT = 50

FAILING, COSTLY, EMPTY = "failing", "costly", "empty"
PENDING, AGREE, DISAGREE, NO_VIEW = "pending", "agree", "disagree", "none"
WAITING, APPROVED, REJECTED = "waiting", "approved", "rejected"
DECISIONS = ("approve", "reject")
KIND = "proposal"
DECIDED = "this proposal is already decided"
NOT_SAVED = "the decision could not be saved; see the desk log"
NO_BOSS = "no boss to ask"
NO_ANSWER = "no answer from the boss"
OFF = "hire proposals are off"
_LABELS = {FAILING: "Failing employee.", COSTLY: "Costly employee.",
           EMPTY: "Empty needed skill."}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hire_proposals (
    id INTEGER PRIMARY KEY, made TEXT, author TEXT, need TEXT, skill TEXT, level TEXT,
    holder TEXT, evidence TEXT, why TEXT, source TEXT, model TEXT, view TEXT, view_by TEXT,
    view_note TEXT, state TEXT, hire TEXT, decided TEXT
);
"""
_COLS = ("id, made, author, need, skill, level, holder, evidence, why, source, model, view, "
         "view_by, view_note, state, hire, decided")


@dataclass(frozen=True)
class Need:
    """One hire need found by code (SRD-DSK-006.012–.014); ``holder`` is empty for an empty
    need."""

    kind: str
    skill: str
    level: str
    holder: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    """A need the secretary may pick, with its id ``C1``, ``C2``, … (SRD-DSK-006.015)."""

    id: str
    need: Need


@dataclass(frozen=True)
class Proposal:
    """One ``hire_proposals`` row."""

    id: int
    made: str
    author: str
    need: str
    skill: str
    level: str
    holder: str
    evidence: tuple[str, ...]
    why: str
    source: str
    model: str
    view: str
    view_by: str
    view_note: str
    state: str
    hire: str
    decided: str


def _words(skill: str) -> str:
    return skill.replace("_", " ")


def _over(days: int) -> str:
    return f"over the last {days} data day{'' if days == 1 else 's'}"


def _stamp(now: datetime) -> str:
    return now.isoformat(timespec="seconds")


# ── need rules (SRD-DSK-006.012–.014) ───────────────────────────────────────


def _read(home: Path, sql: str, params: tuple[Any, ...] = (),
          strict: bool = False) -> list[tuple[Any, ...]]:
    """Rows of a read-only query; empty when the database or the table is missing. Any other
    database error (such as a lock) is raised when ``strict``, else read as empty."""
    path = home / DB_NAME
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
        try:
            return [tuple(r) for r in con.execute(sql, params).fetchall()]
        finally:
            con.close()
    except sqlite3.Error as exc:
        if strict and "no such table" not in str(exc):
            raise
        return []


_LIVE = "COALESCE(replay, 0) = 0 AND COALESCE(shadow, 0) = 0"


def _stats(home: Path) -> tuple[int, dict[str, tuple[int, int, float]]]:
    """Data days in the window, and tries, valid answers and cost per employee in it."""
    days = [str(r[0]) for r in _read(
        home, f"SELECT DISTINCT data_day FROM activity WHERE {_LIVE} AND data_day IS NOT NULL "
              "ORDER BY data_day DESC LIMIT ?", (DAYS,))]
    if not days:
        return 0, {}
    marks = ", ".join("?" * len(days))
    rows = _read(home, "SELECT employee, COUNT(*), SUM(COALESCE(valid, 0)), "
                       f"SUM(COALESCE(cost_usd, 0)) FROM activity WHERE {_LIVE} "
                       f"AND data_day IN ({marks}) GROUP BY employee", tuple(days))
    return len(days), {str(e): (int(t), int(v), float(c)) for e, t, v, c in rows}


def _needs_of(skill: str) -> tuple[str, ...]:
    """The skills ``skill`` needs before it runs; empty when its class cannot be loaded."""
    path = SKILL_PATHS.get(skill)
    if path is None:
        return ()
    module, _, name = path.partition(":")
    try:
        found = getattr(getattr(importlib.import_module(module), name), "needs", ())
    except Exception:  # noqa: BLE001 — a broken skill only hides its own needs
        log.debug("[Hiring] Skill %s could not be loaded", skill, exc_info=True)
        return ()
    return tuple(str(s) for s in found)


def _failing(staff: list[Employee], days: int,
             stats: Mapping[str, tuple[int, int, float]]) -> list[Need]:
    out = []
    for e in staff:
        tries, valid, _ = stats.get(e.id, (0, 0, 0.0))
        if tries >= MIN_TRIES and valid / tries < MIN_VALID_SHARE:
            out.append(Need(FAILING, e.skill, e.level, e.id, (
                f"{e.name} ({_words(e.skill)}): {valid} valid answers in {tries} tries "
                f"{_over(days)} ({round(100 * valid / tries)}%).",)))
    return out


def _costly(staff: list[Employee], days: int,
            stats: Mapping[str, tuple[int, int, float]]) -> list[Need]:
    per = {e.id: stats[e.id][2] / stats[e.id][1] for e in staff
           if e.id in stats and stats[e.id][1] >= MIN_VALID_FOR_COST and stats[e.id][2] > 0}
    if len(per) < MIN_COSTED:
        return []
    middle = statistics.median(per.values())
    return [Need(COSTLY, e.skill, e.level, e.id, (
        f"{e.name} ({_words(e.skill)}): USD {per[e.id]:.2f} per valid answer {_over(days)}; "
        f"the desk middle is USD {middle:.2f}.",))
        for e in staff if e.id in per and per[e.id] > COSTLY_TIMES * middle]


def _empty(staff: list[Employee]) -> list[Need]:
    held = {e.skill for e in staff}
    wanted: dict[str, list[str]] = {}
    for e in staff:
        for skill in _needs_of(e.skill):
            if skill not in held:
                wanted.setdefault(skill, []).append(e.name)
    out = []
    for skill, names in sorted(wanted.items()):
        level = default_level(skill)
        if level is not None:
            verb = "needs" if len(names) == 1 else "need"
            out.append(Need(EMPTY, skill, level, "", (
                f"Nobody holds {_words(skill)}; {', '.join(names)} {verb} it.",)))
    return out


def find_needs(home: Path) -> list[Need]:
    """Failing, then costly, then empty needs, from the last 10 data days of live tries."""
    staff = [e for e in employees(home) if e.status == "active"]
    days, stats = _stats(home)
    return [*_failing(staff, days, stats), *_costly(staff, days, stats), *_empty(staff)]


# ── candidates (SRD-DSK-006.015) ─────────────────────────────────────────────


def _recent(stamp: str, now: datetime, days: int) -> bool:
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=now.tzinfo)
    return now - when < timedelta(days=days)


def _seat_line(home: Path, level: str) -> str:
    cap = load_settings(home).cap(level)
    used = seat_counts(home).get(level, 0)
    if cap is None or used < cap:
        return ""
    return (f"Seats: {used} of {cap} {level} seats are taken; raise the cap in Desk settings "
            "before you approve.")


def candidates(home: Path, now: datetime) -> list[Candidate]:
    """The needs the secretary may pick, numbered ``C1``, ``C2``, … in rule order.

    A need is left out when its level cannot be hired, its skill has a waiting proposal or a
    shadow hire, or the same skill and need were rejected in the last 30 days.

    Raises:
        sqlite3.Error: When the proposals cannot be read, so a lock never looks like none.
    """
    found = proposal_rows(home, None, strict=True)
    waiting = {p.skill for p in found if p.state == WAITING}
    blocked = {(p.skill, p.need) for p in found
               if p.state == REJECTED and _recent(p.decided, now, REJECT_DAYS)}
    shadows = {e.skill for e in employees(home) if e.status == "shadow"}
    out: list[Candidate] = []
    for need in find_needs(home):
        if (need.level not in HIRE_LEVELS or need.skill in waiting or need.skill in shadows
                or (need.skill, need.kind) in blocked):
            continue
        seats = _seat_line(home, need.level)
        if seats:
            need = replace(need, evidence=(*need.evidence, seats))
        out.append(Candidate(f"C{len(out) + 1}", need))
    return out


# ── store ────────────────────────────────────────────────────────────────────


def _open(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(_SCHEMA + _APPROVALS)
    return con


def _proposal(row: tuple[Any, ...]) -> Proposal:
    try:
        evidence = tuple(str(x) for x in json.loads(str(row[7] or "[]")))
    except ValueError:
        evidence = ()
    text = [str(x or "") for x in row]
    return Proposal(int(row[0]), text[1], text[2], text[3], text[4], text[5], text[6], evidence,
                    text[8], text[9], text[10], text[11], text[12], text[13], text[14],
                    text[15], text[16])


def save_proposal(home: Path, author: str, need: Need, why: str, source: str, model: str,
                  boss: str | None, now: datetime) -> int:
    """Save one waiting proposal (SRD-DSK-006.018); its view waits for ``boss``, or is ``none``
    when there is no boss to ask. Returns the proposal id."""
    view, note = (PENDING, "") if boss else (NO_VIEW, NO_BOSS)
    con = _open(home)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO hire_proposals (made, author, need, skill, level, holder, evidence, "
                "why, source, model, view, view_by, view_note, state, hire, decided) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '')",
                (_stamp(now), author, need.kind, need.skill, need.level, need.holder,
                 json.dumps(list(need.evidence)), why, source, model, view, boss or "", note,
                 WAITING))
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def proposal_inputs(proposal_id: int, need: Need, holder_name: str, why: str,
                    source: str, model: str) -> dict[str, Any]:
    """One ``hire_proposal.v1`` row as ask inputs, keyed by the format's columns."""
    values = [proposal_id, need.kind, need.skill, holder_name, " / ".join(need.evidence),
              f"{source}/{model}", why]
    return dict(zip((c.name for c in HIRE_PROPOSAL.columns), values, strict=True))


def proposal_of_ask(schema: object, inputs: object) -> int | None:
    """The proposal id an ask carries: its ``want`` names ``hire_proposal.v1`` and its inputs
    hold the row; ``None`` for any other ask."""
    if schema != HIRE_PROPOSAL.id or not isinstance(inputs, Mapping):
        return None
    value = inputs.get(HIRE_PROPOSAL.key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _names(home: Path) -> dict[str, str]:
    return {e.id: e.name for e in employees(home)}


def note_view(home: Path, proposal_id: int, view: str, by: str, note: str,
              now: datetime) -> bool:
    """Set the view of a proposal whose view is still pending (SRD-DSK-006.021).

    Returns:
        True when the view changed; a later reply never overwrites a view already set.
    """
    con = _open(home)
    try:
        with con:
            changed = con.execute(
                "UPDATE hire_proposals SET view = ?, view_by = ?, view_note = ? "
                "WHERE id = ? AND view = ?", (view, by, note[:200], proposal_id, PENDING)).rowcount
    finally:
        con.close()
    if changed:
        who = _names(home).get(by, by)
        text = {AGREE: f"{who} agrees with", DISAGREE: f"{who} does not agree with"}.get(
            view, "No view on")
        log.info("[Hiring] %s proposal #%d", text, proposal_id)
    return bool(changed)


# ── gate 1 (SRD-DSK-006.022, .023) ──────────────────────────────────────────


def next_name(home: Path, level: str) -> str:
    """The next free generic name of ``level``: its title and one more than the highest number
    in use, such as ``Expert 16``."""
    title = level.title()
    numbers = [int(m.group(1)) for e in employees(home)
               if (m := re.fullmatch(rf"{title} (\d+)", e.name.strip()))]
    return f"{title} {max(numbers, default=0) + 1}"


def _get(home: Path, proposal_id: int) -> Proposal | None:
    rows = _read(home, f"SELECT {_COLS} FROM hire_proposals WHERE id = ?", (proposal_id,),
                 strict=True)
    return _proposal(rows[0]) if rows else None


def _update(home: Path, sql: str, params: tuple[Any, ...]) -> int:
    con = _open(home)
    try:
        with con:
            return con.execute(sql, params).rowcount
    finally:
        con.close()


def _approval(con: sqlite3.Connection, proposal: Proposal, decision: str, detail: str,
              now: datetime) -> None:
    con.execute("INSERT INTO approvals (created, kind, subject, decision, detail) "
                "VALUES (?, ?, ?, ?, ?)", (_stamp(now), KIND, proposal.skill, decision, detail))


def _reject(home: Path, found: Proposal, now: datetime) -> str:
    con = _open(home)
    try:
        with con:
            if not con.execute("UPDATE hire_proposals SET state = ?, decided = ? "
                               "WHERE id = ? AND state = ?",
                               (REJECTED, _stamp(now), found.id, WAITING)).rowcount:
                return DECIDED
            _approval(con, found, "reject", f"proposal #{found.id}", now)
    finally:
        con.close()
    log.info("[Hiring] Proposal #%d rejected", found.id)
    return ""


def _approve(home: Path, found: Proposal, now: datetime) -> str:
    """Claim the proposal before the hire starts, so one proposal never starts two hires; a
    refused hire puts it back to waiting."""
    if not _update(home, "UPDATE hire_proposals SET state = ?, decided = ? "
                         "WHERE id = ? AND state = ?",
                   (APPROVED, _stamp(now), found.id, WAITING)):
        return DECIDED
    name = next_name(home, found.level)
    try:
        hire, why = start_hire(home, found.skill, found.level, name, found.source,
                               found.model, now.date())
    except OSError as exc:
        hire, why = None, f"the employee files could not be written: {exc}"
    if hire is None:
        _update(home, "UPDATE hire_proposals SET state = ?, decided = '' "
                      "WHERE id = ? AND state = ? AND hire = ''", (WAITING, found.id, APPROVED))
        return why
    con = _open(home)
    try:
        with con:
            con.execute("UPDATE hire_proposals SET hire = ? WHERE id = ?", (hire, found.id))
            _approval(con, found, "approve", f"proposal #{found.id}: {hire}", now)
    finally:
        con.close()
    log.info("[Hiring] Proposal #%d approved: trial hire %s started", found.id, name)
    return ""


def decide_proposal(home: Path, proposal_id: int, decision: str, now: datetime) -> str:
    """Record the Master user's gate 1 decision; an empty string means done.

    Approve starts the trial hire in shadow with the proposal's skill, level, source and model
    and the next free generic name. A refused hire (for example full seats) returns its reason
    and the proposal keeps waiting. A database error returns ``NOT_SAVED``.
    """
    if decision not in DECISIONS:
        return f"unknown decision {decision}"
    try:
        found = _get(home, proposal_id)
        if found is None or found.state != WAITING:
            return DECIDED
        return _approve(home, found, now) if decision == "approve" else _reject(home, found, now)
    except sqlite3.Error as exc:
        log.error("[Hiring] The decision on proposal #%d could not be saved: %s", proposal_id,
                  exc)
        return NOT_SAVED


# ── reads (SRD-DSK-006.026) ─────────────────────────────────────────────────


def proposal_rows(home: Path, limit: int | None = LIST_LIMIT,
                  strict: bool = False) -> list[Proposal]:
    """Proposals newest first, at most ``limit`` (all with ``None``); empty with no data. With
    ``strict`` a database error other than a missing table is raised."""
    sql = f"SELECT {_COLS} FROM hire_proposals ORDER BY id DESC"
    rows = (_read(home, sql + " LIMIT ?", (limit,), strict) if limit is not None
            else _read(home, sql, (), strict))
    return [_proposal(r) for r in rows]


def waiting_proposals(home: Path) -> list[Proposal]:
    """Proposals that wait for the Master user's decision, newest first."""
    return [p for p in proposal_rows(home, None) if p.state == WAITING]


def view_line(proposal: Proposal, names: Mapping[str, str]) -> str:
    """The boss's view in words, for the card and the Hiring list."""
    boss = names.get(proposal.view_by, proposal.view_by) or "the boss"
    note = f": {proposal.view_note}" if proposal.view_note else "."
    if proposal.view == PENDING:
        return f"Waiting for {boss}'s view."
    if proposal.view == AGREE:
        return f"{boss} agrees{note}"
    if proposal.view == DISAGREE:
        return f"{boss} does not agree{note}"
    return f"No view{note}"


def proposal_text(home: Path, proposal: Proposal) -> str:
    """Card text: the need with its evidence, the reason, the model and the boss's view."""
    first, *rest = proposal.evidence or ("",)
    return "\n".join([f"{_LABELS.get(proposal.need, '')} {first}".strip(), *rest,
                      f"Why: {proposal.why}", f"Model: {proposal.source}/{proposal.model}",
                      view_line(proposal, _names(home))])
