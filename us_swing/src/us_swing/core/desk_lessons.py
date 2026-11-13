"""
Module: MD-DSK-009.001.M23 — core/desk_lessons.py
Parent SRD: SRD-DSK-009.001
Also: SRD-DSK-009.002 (active at 5 cases), SRD-DSK-009.003 (same lesson updated),
SRD-DSK-009.004 (lessons block for pick makers), SRD-DSK-009.005 (prompt text only),
SRD-DSK-009.006 (lessons shown are kept), SRD-DSK-009.007 (retire), SRD-DSK-009.008 (the
Master's edits), SRD-DSK-009.009 (log lines), SRD-DSK-009.011 (lessons live in ``memory.db``,
moved once from ``desk.db``)

Desk memory: short lessons learned from closed lead picks. A lesson starts as a candidate,
becomes active once enough closed picks back it, is shown to the pick-making skills as plain
prompt text and retires when later picks stop backing it. Only prompt text: no risk, capital
or approval code reads this module. Shared by the market skills, the desk loop and the GUI.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from us_swing.core import desk_memory
from us_swing.core.desk_contract import DB_NAME

log = logging.getLogger(__name__)

TAG_KEYS: tuple[str, ...] = ("side", "setup", "regime", "sector", "grade", "tone")
CLAIMS: tuple[str, ...] = ("better", "worse")
EDIT_ACTIONS: tuple[str, ...] = ("pin", "unpin", "edit", "retire", "delete")
MIN_CASES = 5
LATER_CASES = 10
MAX_SHOWN = 5
MAX_CHARS = 3200
CANDIDATE_DAYS = 30
CONFIRM_DAYS = 90
CLOSED = ("stop", "target", "time")
HEADER = ("Lessons from past picks (use them only to be stricter: lower a grade, add a veto "
          "or skip a pick; never loosen a rule):")

SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, tags TEXT, claim TEXT, proof TEXT,
    cases INTEGER,
    avg_r REAL, confidence REAL, status TEXT, made TEXT, active_on TEXT, last_confirmed TEXT,
    retired_on TEXT, pinned INTEGER DEFAULT 0, author TEXT, why TEXT
);
CREATE TABLE IF NOT EXISTS lesson_uses (
    day TEXT, skill TEXT, lesson_id INTEGER, PRIMARY KEY (day, skill, lesson_id)
);
CREATE TABLE IF NOT EXISTS lesson_edits (
    id INTEGER PRIMARY KEY, lesson_id INTEGER, action TEXT, text TEXT, created TEXT,
    applied TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS memory_state (key TEXT PRIMARY KEY, value TEXT);
"""

_CASES_SQL = """
SELECT p.date, p.side, p.symbol, p.r, i.setup, i.sector, g.regime, s.grade, n.tone
FROM pick_results p
LEFT JOIN ideas i ON i.date = p.date AND i.side = p.side AND i.symbol = p.symbol
LEFT JOIN regime_snapshot g ON g.date = p.date
LEFT JOIN setup_review s ON s.date = p.date AND s.side = p.side AND s.symbol = p.symbol
LEFT JOIN news_tags n ON n.date = p.date AND n.side = p.side AND n.symbol = p.symbol
WHERE p.status IN ('stop', 'target', 'time') AND p.r IS NOT NULL
ORDER BY p.date, p.side, p.symbol
"""
_LESSON_COLUMNS = ("id, text, tags, claim, proof, cases, avg_r, confidence, status, made, "
                   "active_on, last_confirmed, retired_on, pinned, author, why")


@dataclass(frozen=True)
class Case:
    """One closed lead pick: its key (``date|side|symbol``), day, tags and R."""

    key: str
    day: str
    tags: dict[str, str]
    r: float


@dataclass(frozen=True)
class Proof:
    """How the matching closed picks stand against a lesson's claim."""

    cases: int
    avg_r: float
    agree: bool
    confidence: float


@dataclass(frozen=True)
class Lesson:
    """One stored lesson."""

    id: int
    text: str
    tags: dict[str, str]
    claim: str
    proof: list[str]
    cases: int
    avg_r: float
    confidence: float
    status: str
    made: str
    active_on: str | None
    last_confirmed: str | None
    retired_on: str | None
    pinned: bool
    author: str
    why: str


@dataclass(frozen=True)
class ProofRow:
    """One proof pick for the Memory view."""

    day: str
    side: str
    symbol: str
    r: float | None


_MOVED = "lessons_moved"
_MOVE_TABLES = ("lessons", "lesson_uses", "lesson_edits", "memory_state")


def connect(home: Path) -> sqlite3.Connection:
    """Open ``memory.db`` in ``home`` (``desk.db`` attached) with the lesson tables ready."""
    con = desk_memory.connect(home)
    con.executescript(SCHEMA)
    _move(con)
    return con


def _move(con: sqlite3.Connection) -> None:
    """Copy the lesson tables from ``desk.db`` once; the old tables stay as a backup."""
    if get_state(con, _MOVED):
        return
    found = {str(r[0]) for r in con.execute(
        "SELECT name FROM desk.sqlite_master WHERE type = 'table'")}
    moved = 0
    with con:
        for table in _MOVE_TABLES:
            if table not in found:
                continue
            cols = ", ".join(str(r[1]) for r in con.execute(f"PRAGMA desk.table_info({table})"))
            cur = con.execute(f"INSERT OR IGNORE INTO main.{table} ({cols}) "  # noqa: S608
                              f"SELECT {cols} FROM desk.{table}")
            if table == "lessons":
                moved = cur.rowcount
        con.execute("INSERT OR REPLACE INTO memory_state (key, value) VALUES (?, ?)",
                    (_MOVED, datetime.now().isoformat(timespec="seconds")))
    if "lessons" in found:
        log.info("[Memory] Moved %d lesson(s) to the memory file", moved)


def _has(con: sqlite3.Connection, table: str) -> bool:
    return desk_memory.has_table(con, table)


def _stamp(now: datetime) -> str:
    return now.isoformat(timespec="seconds")


def check_tags(tags: dict[str, str]) -> dict[str, str]:
    """Return clean tags (1 to 3 known keys, text values) or raise ``ValueError``."""
    clean = {str(k): str(v).strip() for k, v in tags.items() if str(v).strip()}
    if not 1 <= len(clean) <= 3 or any(k not in TAG_KEYS for k in clean):
        raise ValueError(f"tags must be 1 to 3 of {', '.join(TAG_KEYS)}")
    return clean


def cases(con: sqlite3.Connection) -> list[Case]:
    """Every closed lead pick with its tags; empty before the market tables exist."""
    needed = ("pick_results", "ideas", "regime_snapshot", "setup_review", "news_tags")
    if not all(_has(con, t) for t in needed):
        return []
    out: list[Case] = []
    for day, side, symbol, r, setup, sector, regime, grade, tone in con.execute(_CASES_SQL):
        values = {"side": side, "setup": setup, "regime": regime, "sector": sector,
                  "grade": grade, "tone": tone}
        tags = {k: str(v) for k, v in values.items() if v not in (None, "")}
        out.append(Case(f"{day}|{side}|{symbol}", str(day), tags, float(r)))
    return out


def matches(tags: dict[str, str], case_tags: dict[str, str]) -> bool:
    """True when every lesson tag equals the pick's tag."""
    return all(case_tags.get(k) == v for k, v in tags.items())


def check(tags: dict[str, str], claim: str, all_cases: Sequence[Case],
          base_cases: Sequence[Case] | None = None) -> Proof:
    """Compare the matching cases with the average of ``base_cases`` (all cases by default)."""
    base_of = base_cases if base_cases is not None else all_cases
    hit = [c for c in all_cases if matches(tags, c.tags)]
    if not hit or not base_of:
        return Proof(len(hit), 0.0, False, 0.0)
    base = sum(c.r for c in base_of) / len(base_of)
    avg = sum(c.r for c in hit) / len(hit)
    side = [c for c in hit if (c.r < base if claim == "worse" else c.r > base)]
    agree = avg < base if claim == "worse" else avg > base
    return Proof(len(hit), round(avg, 4), agree, round(len(side) / len(hit), 4))


def _row(row: Sequence[object]) -> Lesson:
    (lid, text, tags, claim, proof, n, avg, conf, status, made, active_on, confirmed,
     retired_on, pinned, author, why) = row
    return Lesson(int(str(lid)), str(text), json.loads(str(tags)), str(claim),
                  json.loads(str(proof or "[]")), int(str(n or 0)), float(str(avg or 0.0)),
                  float(str(conf or 0.0)), str(status), str(made),
                  str(active_on) if active_on else None,
                  str(confirmed) if confirmed else None,
                  str(retired_on) if retired_on else None, bool(pinned), str(author),
                  str(why or ""))


def _lessons(con: sqlite3.Connection, where: str = "", params: tuple[object, ...] = ()
             ) -> list[Lesson]:
    sql = f"SELECT {_LESSON_COLUMNS} FROM lessons {where}"
    return [_row(r) for r in con.execute(sql, params).fetchall()]


def add_candidate(home: Path, text: str, tags: dict[str, str], claim: str,
                  proof: Sequence[str], now: datetime) -> int:
    """Store a candidate (or update a kept lesson with the same tags and claim); return its id.

    Raises:
        ValueError: On empty text, bad tags or an unknown claim.
    """
    clean = check_tags(tags)
    text = text.strip()[:200]
    if not text or claim not in CLAIMS:
        raise ValueError("a lesson needs text and a claim of better or worse")
    key = json.dumps(clean, sort_keys=True)
    con = connect(home)
    try:
        same = _lessons(con, "WHERE tags = ? AND claim = ? AND status != 'retired'",
                        (key, claim))
        with con:
            if same:
                lid = same[0].id
                keep = same[0].author == "master" or same[0].pinned
                con.execute("UPDATE lessons SET text = ?, proof = ? WHERE id = ?",
                            (same[0].text if keep else text, json.dumps(list(proof)), lid))
            else:
                cur = con.execute(
                    "INSERT INTO lessons (text, tags, claim, proof, cases, avg_r, confidence, "
                    "status, made, pinned, author, why) VALUES (?, ?, ?, ?, 0, 0, 0, "
                    "'candidate', ?, 0, 'desk', '')",
                    (text, key, claim, json.dumps(list(proof)), _stamp(now)))
                lid = int(cur.lastrowid or 0)
                log.info("[Memory] New candidate lesson L-%d: %s", lid, text)
        _refresh(con, lid, cases(con), now)
        return lid
    finally:
        con.close()


def _refresh(con: sqlite3.Connection, lid: int, all_cases: Sequence[Case],
             now: datetime) -> None:
    """Update a lesson's numbers and make a backed candidate active."""
    found = _lessons(con, "WHERE id = ?", (lid,))
    if not found:
        return
    lesson = found[0]
    proof = check(lesson.tags, lesson.claim, all_cases)
    with con:
        con.execute("UPDATE lessons SET cases = ?, avg_r = ?, confidence = ? WHERE id = ?",
                    (proof.cases, proof.avg_r, proof.confidence, lid))
        if (lesson.status == "candidate" and proof.cases >= MIN_CASES and proof.agree
                and not _recently_retired(con, lesson, now)):
            con.execute("UPDATE lessons SET status = 'active', active_on = ?, "
                        "last_confirmed = ? WHERE id = ?", (_stamp(now), _stamp(now), lid))
            log.info("[Memory] Lesson L-%d is active (%d cases)", lid, proof.cases)


def _recently_retired(con: sqlite3.Connection, lesson: Lesson, now: datetime) -> bool:
    """True when a lesson with the same tags and claim retired in the last 90 days."""
    since = _stamp(now - timedelta(days=CONFIRM_DAYS))
    return con.execute("SELECT 1 FROM lessons WHERE tags = ? AND claim = ? AND id != ? AND "
                       "status = 'retired' AND retired_on >= ? LIMIT 1",
                       (json.dumps(lesson.tags, sort_keys=True), lesson.claim, lesson.id,
                        since)).fetchone() is not None


def _retire(con: sqlite3.Connection, lesson: Lesson, why: str, now: datetime) -> None:
    with con:
        con.execute("UPDATE lessons SET status = 'retired', retired_on = ?, why = ? "
                    "WHERE id = ?", (_stamp(now), why, lesson.id))
    log.info("[Memory] Lesson L-%d retired: %s", lesson.id, why)


def review_lessons(home: Path, now: datetime) -> None:
    """Daily check: promote backed candidates, confirm or retire active lessons."""
    con = connect(home)
    try:
        all_cases = cases(con)
        for lesson in _lessons(con, "WHERE status != 'retired'"):
            _refresh(con, lesson.id, all_cases, now)
        for lesson in _lessons(con, "WHERE status != 'retired'"):
            _review_one(con, lesson, all_cases, now)
    finally:
        con.close()


def _review_one(con: sqlite3.Connection, lesson: Lesson, all_cases: Sequence[Case],
                now: datetime) -> None:
    if lesson.status == "candidate":
        if not lesson.pinned and (now - datetime.fromisoformat(lesson.made)
                                  > timedelta(days=CANDIDATE_DAYS)):
            _retire(con, lesson, "not proved in 30 days", now)
        return
    if lesson.pinned or lesson.active_on is None:
        return
    shown = {str(d) for (d,) in con.execute(
        "SELECT DISTINCT day FROM lesson_uses WHERE lesson_id = ?", (lesson.id,))}
    active_day = lesson.active_on[:10]
    later = [c for c in all_cases
             if c.day > active_day and c.day in shown and matches(lesson.tags, c.tags)]
    if len(later) >= LATER_CASES and not check(lesson.tags, lesson.claim, later,
                                               all_cases).agree:
        _retire(con, lesson, "later picks do not back it", now)
        return
    base = sum(c.r for c in all_cases) / len(all_cases) if all_cases else 0.0
    backing = [c.day for c in later if (c.r < base if lesson.claim == "worse" else c.r > base)]
    confirmed = lesson.last_confirmed or lesson.active_on
    if backing and max(backing) > confirmed[:10]:
        with con:
            con.execute("UPDATE lessons SET last_confirmed = ? WHERE id = ?",
                        (_stamp(now), lesson.id))
        return
    if now - datetime.fromisoformat(confirmed) > timedelta(days=CONFIRM_DAYS):
        _retire(con, lesson, "not confirmed in 90 days", now)


def _day_tags(con: sqlite3.Connection, day: str) -> list[dict[str, str]]:
    if not _has(con, "ideas"):
        return []
    regime = ""
    if _has(con, "regime_snapshot"):
        row = con.execute("SELECT regime FROM regime_snapshot WHERE date = ?",
                          (day,)).fetchone()
        regime = str(row[0]) if row and row[0] else ""
    out: list[dict[str, str]] = []
    for side, setup, sector in con.execute(
            "SELECT side, setup, sector FROM ideas WHERE date = ?", (day,)):
        values = {"side": side, "setup": setup, "sector": sector, "regime": regime}
        out.append({k: str(v) for k, v in values.items() if v not in (None, "")})
    return out


def _fits_day(tags: dict[str, str], ideas: Sequence[dict[str, str]]) -> bool:
    """True when some idea of the day can match: tags it cannot know yet are not checked."""
    known = {k: v for k, v in tags.items() if k in ("side", "setup", "sector", "regime")}
    return any(matches(known, idea) for idea in ideas)


def lessons_block(home: Path, skill: str, day: str) -> str:
    """Prompt text with at most 5 matching active lessons; records what was shown."""
    con = connect(home)
    try:
        ideas = _day_tags(con, day)
        chosen = [x for x in _lessons(con, "WHERE status = 'active'")
                  if _fits_day(x.tags, ideas)]
        chosen.sort(key=lambda x: (not x.pinned, -x.confidence, x.id))
        lines: list[str] = []
        size = len(HEADER)
        for lesson in chosen[:MAX_SHOWN]:
            line = (f"- L-{lesson.id}: {lesson.text} ({lesson.cases} cases, average "
                    f"{lesson.avg_r:+.2f}R).")
            if size + len(line) + 1 > MAX_CHARS:
                break
            lines.append(line)
            size += len(line) + 1
        if not lines:
            return ""
        shown = chosen[:len(lines)]
        with con:
            con.executemany("INSERT OR IGNORE INTO lesson_uses (day, skill, lesson_id) "
                            "VALUES (?, ?, ?)", [(day, skill, x.id) for x in shown])
        return "\n".join([HEADER, *lines])
    finally:
        con.close()


def with_lessons(text: str, home: Path, skill: str, day: str) -> str:
    """``text`` followed by the lessons block, when there is one; a memory problem never
    stops a pick maker, so on any error the plain text comes back."""
    try:
        block = lessons_block(home, skill, day)
    except Exception:  # noqa: BLE001 — the pick still runs without lessons
        log.warning("[Memory] Could not read the lessons; the prompt goes without them")
        return text
    return f"{text}\n\n{block}" if block else text


def add_edit(home: Path, lesson_id: int, action: str, now: datetime, text: str = "") -> int:
    """Add one Master edit for the desk to apply; return the edit id.

    Raises:
        ValueError: On an unknown action, or an edit with empty text.
    """
    if action not in EDIT_ACTIONS or (action == "edit" and not text.strip()):
        raise ValueError(f"unknown lesson edit {action}")
    con = connect(home)
    try:
        with con:
            cur = con.execute("INSERT INTO lesson_edits (lesson_id, action, text, created) "
                              "VALUES (?, ?, ?, ?)",
                              (lesson_id, action, text.strip()[:200], _stamp(now)))
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def apply_edits(home: Path, now: datetime) -> int:
    """Apply the Master's pending edits, oldest first; return how many were applied."""
    if not ((home / DB_NAME).exists() or (home / desk_memory.MEMORY_DB).exists()):
        return 0
    con = connect(home)
    try:
        pending = con.execute("SELECT id, lesson_id, action, text FROM lesson_edits "
                              "WHERE applied IS NULL ORDER BY id").fetchall()
        for eid, lid, action, text in pending:
            note = _apply_one(con, int(lid), str(action), str(text or ""), now)
            with con:
                con.execute("UPDATE lesson_edits SET applied = ?, note = ? WHERE id = ?",
                            (_stamp(now), note, eid))
        return len(pending)
    finally:
        con.close()


def _apply_one(con: sqlite3.Connection, lid: int, action: str, text: str,
               now: datetime) -> str:
    found = _lessons(con, "WHERE id = ?", (lid,))
    if not found:
        return "lesson not found"
    with con:
        if action in ("pin", "unpin"):
            con.execute("UPDATE lessons SET pinned = ? WHERE id = ?", (action == "pin", lid))
        elif action == "edit":
            con.execute("UPDATE lessons SET text = ?, author = 'master' WHERE id = ?",
                        (text, lid))
        elif action == "delete":
            con.execute("DELETE FROM lessons WHERE id = ?", (lid,))
            con.execute("DELETE FROM lesson_uses WHERE lesson_id = ?", (lid,))
    if action == "retire":
        _retire(con, found[0], "retired by the Master", now)
    return "done"


def _read_only(home: Path) -> sqlite3.Connection | None:
    con = desk_memory.read_only(home) or _old_file(home)
    if con is None:
        return None
    if not _has(con, "lessons"):
        con.close()
        return None
    return con


def _old_file(home: Path) -> sqlite3.Connection | None:
    """``desk.db`` read-only, for a GUI that opens before the desk has moved the lessons."""
    path = home / DB_NAME
    if not path.exists():
        return None
    try:
        return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    except sqlite3.Error:
        return None


def lesson_rows(home: Path, status: str = "active") -> list[Lesson]:
    """Lessons of one status for the Memory view, pinned first; empty with no data."""
    con = _read_only(home)
    if con is None:
        return []
    try:
        found = _lessons(con, "WHERE status = ?", (status,))
    except sqlite3.Error:
        return []
    finally:
        con.close()
    return sorted(found, key=lambda x: (not x.pinned, -x.confidence, x.id))


def pending_edits(home: Path) -> set[int]:
    """Ids of lessons with an edit the desk has not applied yet."""
    con = _read_only(home)
    if con is None:
        return set()
    try:
        return {int(r[0]) for r in con.execute(
            "SELECT lesson_id FROM lesson_edits WHERE applied IS NULL")}
    except sqlite3.Error:
        return set()
    finally:
        con.close()


def proof_rows(home: Path, lesson_id: int) -> list[ProofRow]:
    """The proof picks of one lesson with their R; empty when unknown."""
    con = _read_only(home)
    if con is None:
        return []
    try:
        found = _lessons(con, "WHERE id = ?", (lesson_id,))
        if not found:
            return []
        rs = {c.key: c.r for c in cases(con)}
    except sqlite3.Error:
        return []
    finally:
        con.close()
    out: list[ProofRow] = []
    for key in found[0].proof:
        parts = key.split("|")
        if len(parts) == 3:
            out.append(ProofRow(parts[0], parts[1], parts[2], rs.get(key)))
    return out


def get_state(con: sqlite3.Connection, key: str) -> str:
    """One memory state value, empty when unset."""
    row = con.execute("SELECT value FROM memory_state WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row else ""


def set_state(con: sqlite3.Connection, key: str, value: str) -> None:
    """Set one memory state value."""
    with con:
        con.execute("INSERT OR REPLACE INTO memory_state (key, value) VALUES (?, ?)",
                    (key, value))
