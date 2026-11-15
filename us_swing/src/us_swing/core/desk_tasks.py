"""
Module: MD-DSK-012.016.M32 — core/desk_tasks.py
Parent SRD: SRD-DSK-012.016
Also: SRD-DSK-012.017 (task cards), .020 (unmade columns), .021 (tool group names), .027 (fail
count and retire), .030 (reads for the lead chat and the Tools view)
Also: SRD-DSK-013.017, .018 (make or drop the plan of one format) — AI Desk v3 M7b

Saved table plans and task cards in ``desk.db`` (AI Desk v3 M6). A plan says which tool group
fills which columns of a table format, in two waves; it is made from the tools the format's
columns name. A task card is the record of one table ask the planner worked: its parts and
how each ended. Shared by the desk and the GUI; this module imports neither ``desk``,
``market`` nor ``gui``. Design: DD-DSK-012.012.D01.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_registry import TableFormat, Tool, list_formats, list_tools

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
RETIRE_AFTER = 3
ACTIVE = "active"
RETIRED = "retired"
STOPPED = "the desk stopped before the card ended"
PartStatus = Literal["ok", "failed", "skipped"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS task_plans (
    format TEXT PRIMARY KEY, parts TEXT, unmade TEXT, status TEXT, fails INTEGER, why TEXT,
    updated TEXT
);
CREATE TABLE IF NOT EXISTS task_cards (
    id INTEGER PRIMARY KEY, message INTEGER, asker TEXT, planner TEXT, format TEXT, cols TEXT,
    keys TEXT, status TEXT, parts TEXT, rows INTEGER, reason TEXT, made TEXT, ended TEXT,
    secs REAL
);
"""
_PLAN_COLS = "format, parts, unmade, status, fails, why"
_CARD_COLS = ("id, message, asker, planner, format, cols, keys, status, parts, rows, reason, "
              "made, ended, secs")


class PlanPart(BaseModel):
    """One part of a plan: a tool group in one wave, and the columns each of its tools fills."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    wave: int = Field(ge=1)
    group: str = Field(min_length=1)
    tools: dict[str, list[str]]


class CardPart(BaseModel):
    """How one part of a task card ended."""

    model_config = ConfigDict(extra="forbid")

    id: str
    wave: int
    group: str
    tools: list[str]
    cols: list[str]
    rows: int = 0
    status: PartStatus
    secs: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class Plan:
    """The saved plan of one table format."""

    format: str
    parts: tuple[PlanPart, ...]
    unmade: tuple[str, ...] = ()
    status: str = ACTIVE
    fails: int = 0
    why: str = ""


@dataclass(frozen=True)
class Card:
    """One table ask the planner worked; times are New York ISO text."""

    id: int
    message: int
    asker: str
    planner: str
    format: str
    cols: tuple[str, ...]
    keys: tuple[str, ...]
    status: str
    parts: tuple[CardPart, ...]
    rows: int
    reason: str
    made: str
    ended: str | None
    secs: float | None


def group_of(tool: str) -> str:
    """The tool group of a tool: the part of its name before the dot (SRD-DSK-012.021)."""
    return tool.split(".", 1)[0]


def group_label(group: str) -> str:
    """The group as shown to the user, such as ``Calendar tools``."""
    return f"{group.capitalize()} tools"


def make_plan(fmt: TableFormat, tools: Sequence[Tool]) -> Plan | None:
    """The plan of ``fmt`` from the tools its columns name; ``None`` with no active key tool.

    Wave 1 is the key tool's group with the key tool's columns. Wave 2 has one part per tool
    group of the other columns. A column with no tool, or whose tool is missing or off, is
    listed as unmade (SRD-DSK-012.016, .020).
    """
    active = {t.name for t in tools if t.status == ACTIVE}
    key_tool = fmt.columns[0].by
    if key_tool is None or key_tool not in active:
        return None
    first = {key_tool: [c.name for c in fmt.columns if c.by == key_tool]}
    groups: dict[str, dict[str, list[str]]] = {}
    unmade: list[str] = []
    for col in fmt.columns:
        if col.by == key_tool:
            continue
        if col.by is None or col.by not in active:
            unmade.append(col.name)
            continue
        groups.setdefault(group_of(col.by), {}).setdefault(col.by, []).append(col.name)
    parts = [PlanPart(id="A", wave=1, group=group_of(key_tool), tools=first)]
    for number, group in enumerate(sorted(groups)):
        parts.append(PlanPart(id=chr(ord("B") + number), wave=2, group=group,
                              tools=dict(sorted(groups[group].items()))))
    return Plan(fmt.id, tuple(parts), tuple(unmade))


# ── store ────────────────────────────────────────────────────────────────────


def _connect(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    return con


def _stamp(moment: datetime) -> str:
    return moment.astimezone(NY).isoformat(timespec="seconds")


def _read(home: Path, sql: str, args: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
    path = home / DB_NAME
    if not path.exists():
        return []
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        return con.execute(sql, args).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            log.warning("[Task cards] Could not read the task cards: %s", exc)
        return []
    finally:
        con.close()


def _plan(row: Sequence[Any]) -> Plan:
    return Plan(str(row[0]), tuple(PlanPart.model_validate(p) for p in json.loads(row[1])),
                tuple(json.loads(row[2])), str(row[3]), int(row[4]), str(row[5] or ""))


def _card(row: Sequence[Any]) -> Card:
    return Card(int(row[0]), int(row[1]), str(row[2]), str(row[3]), str(row[4]),
                tuple(json.loads(row[5])), tuple(json.loads(row[6])), str(row[7]),
                tuple(CardPart.model_validate(p) for p in json.loads(row[8] or "[]")),
                int(row[9] or 0), str(row[10] or ""), str(row[11]), row[12], row[13])


def _put_plan(con: sqlite3.Connection, plan: Plan, stamp: str) -> None:
    con.execute(
        "INSERT INTO task_plans VALUES (?, ?, ?, ?, 0, '', ?) ON CONFLICT(format) DO "
        "UPDATE SET parts = excluded.parts, unmade = excluded.unmade, "
        "status = excluded.status, fails = 0, why = '', updated = excluded.updated",
        (plan.format, json.dumps([p.model_dump() for p in plan.parts]),
         json.dumps(list(plan.unmade)), ACTIVE, stamp))


def fill_plans(home: Path, now: datetime) -> int:
    """Make the plan of every table format again; each starts active with no fails.

    A format that has no plan any more loses its row (SRD-DSK-012.016).

    Returns:
        Number of plans kept.
    """
    tools = list_tools(home, ACTIVE)
    plans = [plan for fmt in list_formats(home) if (plan := make_plan(fmt, tools)) is not None]
    stamp = _stamp(now)
    con = _connect(home)
    try:
        with con:
            for plan in plans:
                _put_plan(con, plan, stamp)
            marks = ",".join("?" * len(plans))
            con.execute(f"DELETE FROM task_plans WHERE format NOT IN ({marks})",  # noqa: S608
                        [p.format for p in plans])
    finally:
        con.close()
    log.info("[Task cards] %d table plan(s) ready", len(plans))
    return len(plans)


def save_plan(home: Path, fmt: TableFormat, now: datetime) -> bool:
    """Make and keep the plan of one format from the active tools, leaving every other plan as
    it is; ``False`` when the format has no plan (SRD-DSK-013.017)."""
    plan = make_plan(fmt, list_tools(home, ACTIVE))
    if plan is None:
        return False
    con = _connect(home)
    try:
        with con:
            _put_plan(con, plan, _stamp(now))
    finally:
        con.close()
    return True


def drop_plan(home: Path, format_id: str) -> None:
    """Remove the plan of one format (SRD-DSK-013.018)."""
    con = _connect(home)
    try:
        with con:
            con.execute("DELETE FROM task_plans WHERE format = ?", (format_id,))
    finally:
        con.close()


def get_plan(home: Path, format_id: str) -> Plan | None:
    """The saved plan of one format, active or retired; ``None`` when it has none."""
    rows = _read(home, f"SELECT {_PLAN_COLS} FROM task_plans WHERE format = ?",  # noqa: S608
                 (format_id,))
    return _plan(rows[0]) if rows else None


def note_result(home: Path, format_id: str, failed_part: bool, why: str,
                now: datetime) -> bool:
    """Count one card of a plan; retire the plan at 3 cards in a row with a failed part.

    Args:
        home: Desk folder.
        format_id: The plan's format.
        failed_part: True when a part of the card failed (error or time limit).
        why: The failed part's reason, kept on a retired plan.
        now: Time-zone aware time.

    Returns:
        True only when this call retired the plan (SRD-DSK-012.027).
    """
    con = _connect(home)
    try:
        with con:
            row = con.execute("SELECT fails, status FROM task_plans WHERE format = ?",
                              (format_id,)).fetchone()
            if row is None or row[1] != ACTIVE:
                return False
            fails = int(row[0]) + 1 if failed_part else 0
            retired = fails >= RETIRE_AFTER
            con.execute("UPDATE task_plans SET fails = ?, status = ?, why = ?, updated = ? "
                        "WHERE format = ?",
                        (fails, RETIRED if retired else ACTIVE, why[:200] if retired else "",
                         _stamp(now), format_id))
            return retired
    finally:
        con.close()


def open_card(home: Path, message: int, asker: str, planner: str, format_id: str,
              cols: Sequence[str], keys: Sequence[str], now: datetime) -> int:
    """Store a working card for one ask and return its id (SRD-DSK-012.017)."""
    con = _connect(home)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO task_cards (message, asker, planner, format, cols, keys, status, "
                "parts, rows, reason, made) VALUES (?, ?, ?, ?, ?, ?, 'working', '[]', 0, '', ?)",
                (message, asker, planner, format_id, json.dumps(list(cols)),
                 json.dumps(list(keys)), _stamp(now)))
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def close_card(home: Path, card_id: int, status: str, parts: Sequence[CardPart], rows: int,
               reason: str, now: datetime, secs: float) -> bool:
    """Write how a card ended; ``False`` when there is no such card."""
    con = _connect(home)
    try:
        with con:
            cur = con.execute(
                "UPDATE task_cards SET status = ?, parts = ?, rows = ?, reason = ?, ended = ?, "
                "secs = ? WHERE id = ?",
                (status, json.dumps([p.model_dump() for p in parts]), rows, reason, _stamp(now),
                 round(secs, 2), card_id))
        return cur.rowcount == 1
    finally:
        con.close()


def close_open_cards(home: Path, now: datetime) -> int:
    """Mark the cards a stopped desk left working as failed; return how many."""
    con = _connect(home)
    try:
        with con:
            cur = con.execute("UPDATE task_cards SET status = 'failed', reason = ?, ended = ? "
                              "WHERE status = 'working'", (STOPPED, _stamp(now)))
        return cur.rowcount
    finally:
        con.close()


# ── reads (SRD-DSK-012.030) ──────────────────────────────────────────────────


def plan_rows(home: Path) -> list[Plan]:
    """Every saved plan, by format."""
    return [_plan(r) for r in _read(
        home, f"SELECT {_PLAN_COLS} FROM task_plans ORDER BY format")]  # noqa: S608


def card_rows(home: Path, limit: int = 50) -> list[Card]:
    """The latest ``limit`` task cards, newest first."""
    return [_card(r) for r in _read(
        home, f"SELECT {_CARD_COLS} FROM task_cards ORDER BY id DESC LIMIT ?",  # noqa: S608
        (limit,))]


def ready_formats(home: Path) -> list[TableFormat]:
    """The table formats that have an active plan, by name."""
    active = {p.format for p in plan_rows(home) if p.status == ACTIVE}
    return [f for f in list_formats(home) if f.id in active]
