"""
Module: MD-DSK-009.010.M30 — core/desk_memory.py
Parent SRD: SRD-DSK-009.010
Also: SRD-DSK-009.012 (memory rows and FTS5 index), SRD-DSK-009.014 (3 a day),
SRD-DSK-009.015 (clean write), SRD-DSK-009.016 (core block), SRD-DSK-009.017 (recall),
SRD-DSK-009.018 (view scores notes), SRD-DSK-009.019 (weak and proven), SRD-DSK-009.020
(expiry; a view with no prices 30 days after its check day retires too), SRD-DSK-009.021 (clean-up actions), SRD-DSK-009.022 (the Master's edits),
SRD-DSK-009.024 (log lines)

Desk memory v2 (AI Desk v3 M3): the ``memory.db`` file next to ``desk.db``. Lead and expert
employees keep short notes and views here; code keeps them clean, shows a core block and a
few recalled notes at each wake, scores notes by how the views of the same day turned out
and retires notes nobody needs. Lessons live in the same file (``core/desk_lessons.py``).
Only prompt text: no risk, capital or approval code reads this module.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from us_swing.core.desk_contract import DB_NAME
from us_swing.data.market_calendar import get_exchange_status

if TYPE_CHECKING:
    from us_swing.core.desk_msg import Remember

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
MEMORY_DB = "memory.db"
TOP_LEVELS: tuple[str, ...] = ("lead", "expert")
KINDS: tuple[str, ...] = ("note", "view")
NOTE_STATUSES: tuple[str, ...] = ("active", "weak", "retired")
VIEW_STATUSES: tuple[str, ...] = ("open", "right", "wrong", "neutral", "retired")
EDIT_ACTIONS: tuple[str, ...] = ("pin", "unpin", "retire")
PER_DAY = 3
VIEW_DAYS = 10
MOVE_PCT = 1.0
SAME_WORDS = 0.8
MIN_CHECKS = 5
WEAK_BELOW = 0.4
PROVEN_RIGHT = 3
EXPIRE_DAYS = 30
MISS_DAYS = 10
CORE_CHARS = 1200
RECALL_CHARS = 4000
RECALL_MAX = 10
MAX_TERMS = 30
CORE_HEADER = "Your memory (notes you wrote; use them only as hints):"
RECALL_HEADER = "Notes you wrote before that may fit today:"

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, kind TEXT, text TEXT,
    symbol TEXT DEFAULT '', direction TEXT DEFAULT '', made TEXT, updated TEXT,
    due TEXT DEFAULT '', status TEXT, right INTEGER DEFAULT 0, wrong INTEGER DEFAULT 0,
    pinned INTEGER DEFAULT 0, result REAL, why TEXT DEFAULT ''
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    text, symbol, content='memories', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts (rowid, text, symbol) VALUES (new.id, new.text, new.symbol);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts (memories_fts, rowid, text, symbol)
    VALUES ('delete', old.id, old.text, old.symbol);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE OF text, symbol ON memories BEGIN
    INSERT INTO memories_fts (memories_fts, rowid, text, symbol)
    VALUES ('delete', old.id, old.text, old.symbol);
    INSERT INTO memories_fts (rowid, text, symbol) VALUES (new.id, new.text, new.symbol);
END;
CREATE TABLE IF NOT EXISTS memory_uses (
    day TEXT, owner TEXT, memory_id INTEGER, PRIMARY KEY (day, owner, memory_id)
);
CREATE TABLE IF NOT EXISTS memory_edits (
    id INTEGER PRIMARY KEY, memory_id INTEGER, action TEXT, created TEXT, applied TEXT,
    note TEXT
);
CREATE TABLE IF NOT EXISTS memory_state (key TEXT PRIMARY KEY, value TEXT);
"""
_COLUMNS = ("id, owner, kind, text, symbol, direction, made, updated, due, status, right, "
            "wrong, pinned, result, why")
_TICKER = re.compile(r"\b[A-Z]{1,5}\b")


@dataclass(frozen=True)
class Memory:
    """One note or view of one employee."""

    id: int
    owner: str
    kind: str
    text: str
    symbol: str
    direction: str
    made: str
    updated: str
    due: str
    status: str
    right: int
    wrong: int
    pinned: bool
    result: float | None
    why: str

    @property
    def proven(self) -> bool:
        """True when 3 or more checks backed the note."""
        return self.right >= PROVEN_RIGHT


@dataclass(frozen=True)
class CleanupAction:
    """One clean-up step asked by an employee for one of its notes."""

    id: int
    do: str
    into: int | None = None
    text: str | None = None


def connect(home: Path) -> sqlite3.Connection:
    """Open ``memory.db`` in ``home`` (WAL) with ``desk.db`` attached as ``desk``."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / MEMORY_DB, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("ATTACH DATABASE ? AS desk", (str(home / DB_NAME),))
    con.executescript(SCHEMA)
    return con


def read_only(home: Path) -> sqlite3.Connection | None:
    """``memory.db`` opened read-only with ``desk.db`` attached; ``None`` with no file."""
    path = home / MEMORY_DB
    if not path.exists():
        return None
    try:
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    except sqlite3.Error:
        return None
    desk = home / DB_NAME
    try:
        if desk.exists():
            con.execute("ATTACH DATABASE ? AS desk", (f"{desk.as_uri()}?mode=ro",))
    except sqlite3.Error:
        con.close()
        return None
    return con


def has_table(con: sqlite3.Connection, table: str) -> bool:
    """True when ``table`` is in the memory file or an attached file."""
    return con.execute("SELECT 1 FROM pragma_table_info(?) LIMIT 1",
                       (table,)).fetchone() is not None


def get_state(con: sqlite3.Connection, key: str) -> str:
    """One memory state value, empty when unset."""
    row = con.execute("SELECT value FROM memory_state WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row else ""


def set_state(con: sqlite3.Connection, key: str, value: str) -> None:
    """Set one memory state value."""
    with con:
        con.execute("INSERT OR REPLACE INTO memory_state (key, value) VALUES (?, ?)",
                    (key, value))


def is_top(level: str) -> bool:
    """True for the levels that get memory v2: lead and expert."""
    return level in TOP_LEVELS


def add_trading_days(day: str, count: int) -> str:
    """The NYSE trading day ``count`` trading days after ``day`` (ISO dates)."""
    d = date.fromisoformat(day)
    left = count
    while left > 0:
        d += timedelta(days=1)
        if get_exchange_status(datetime.combine(d, time(12, 0), NY)) == "open":
            left -= 1
    return d.isoformat()


def _stamp(now: datetime) -> str:
    return now.isoformat(timespec="seconds")


def _row(row: Sequence[object]) -> Memory:
    (mid, owner, kind, text, symbol, direction, made, updated, due, status, right, wrong,
     pinned, result, why) = row
    return Memory(int(str(mid)), str(owner), str(kind), str(text), str(symbol or ""),
                  str(direction or ""), str(made), str(updated or made), str(due or ""),
                  str(status), int(str(right or 0)), int(str(wrong or 0)), bool(pinned),
                  None if result is None else float(str(result)), str(why or ""))


def _memories(con: sqlite3.Connection, where: str, params: tuple[object, ...] = ()
              ) -> list[Memory]:
    sql = f"SELECT {_COLUMNS} FROM memories {where}"  # noqa: S608 — fixed text, no input
    return [_row(r) for r in con.execute(sql, params).fetchall()]


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _same_words(a: str, b: str) -> bool:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= SAME_WORDS


# ── write (SRD-DSK-009.014, .015) ─────────────────────────────────────────


def write(home: Path, owner: str, drafts: Sequence[Remember], day: str,
          now: datetime) -> list[str]:
    """Store an employee's notes and views; return one result per draft.

    Results: ``added``, ``updated``, ``no change`` or ``dropped: ...``.
    """
    if not drafts:
        return []
    con = connect(home)
    try:
        out = [_write_one(con, owner, d, day, now) for d in drafts]
    finally:
        con.close()
    dropped = sum(1 for r in out if r.startswith("dropped"))
    if dropped:
        log.info("[Memory] %d note(s) of %s not kept: at most %d new a day", dropped, owner,
                 PER_DAY)
    return out


def _write_one(con: sqlite3.Connection, owner: str, draft: Remember, day: str,
               now: datetime) -> str:
    kind = draft.kind
    if kind not in KINDS:
        return "dropped: unknown kind"
    made_today = con.execute("SELECT COUNT(*) FROM memories WHERE owner = ? AND made = ?",
                             (owner, day)).fetchone()[0]
    text = draft.text.strip()[:200]
    if kind == "view":
        symbol = (draft.symbol or "").strip().upper()
        direction = draft.direction or ""
        open_views = _memories(con, "WHERE owner = ? AND kind = 'view' AND status = 'open' "
                               "AND symbol = ?", (owner, symbol))
        if any(v.direction == direction for v in open_views):
            return "no change"
        if made_today >= PER_DAY:
            return "dropped: 3 a day"
        with con:
            for old in open_views:
                con.execute("UPDATE memories SET status = 'retired', why = 'changed view', "
                            "updated = ? WHERE id = ?", (_stamp(now), old.id))
            con.execute("INSERT INTO memories (owner, kind, text, symbol, direction, made, "
                        "updated, due, status) VALUES (?, 'view', ?, ?, ?, ?, ?, ?, 'open')",
                        (owner, text, symbol, direction, day, _stamp(now),
                         add_trading_days(day, VIEW_DAYS)))
        return "added"
    for note in _memories(con, "WHERE owner = ? AND kind = 'note' AND status != 'retired'",
                          (owner,)):
        if _same_words(note.text, text):
            if note.pinned:
                return "no change"
            with con:
                con.execute("UPDATE memories SET text = ?, updated = ? WHERE id = ?",
                            (text, _stamp(now), note.id))
            return "updated"
    if made_today >= PER_DAY:
        return "dropped: 3 a day"
    with con:
        con.execute("INSERT INTO memories (owner, kind, text, symbol, made, updated, status) "
                    "VALUES (?, 'note', ?, ?, ?, ?, 'active')",
                    (owner, text, (draft.symbol or "").strip().upper(), day, _stamp(now)))
    return "added"


# ── prompt blocks (SRD-DSK-009.016, .017) ─────────────────────────────────


def _cut(lines: Sequence[str], limit: int) -> str:
    out: list[str] = []
    size = 0
    for line in lines:
        if size + len(line) + 1 > limit:
            break
        out.append(line)
        size += len(line) + 1
    return "\n".join(out)


def core_block(home: Path, owner: str, day: str) -> str:
    """Track record, pinned notes, open views and recent misses; empty with nothing kept."""
    con = read_only(home)
    if con is None:
        return ""
    try:
        if not has_table(con, "memories"):
            return ""
        rows = _memories(con, "WHERE owner = ? AND status != 'retired'", (owner,))
    except sqlite3.Error:
        return ""
    finally:
        con.close()
    return _core_text(rows, day)


def _core_text(rows: Sequence[Memory], day: str) -> str:
    checked = [m for m in rows if m.kind == "view" and m.status in ("right", "wrong", "neutral")]
    pinned = [m for m in rows if m.kind == "note" and m.pinned and m.status != "retired"]
    open_views = sorted((m for m in rows if m.kind == "view" and m.status == "open"),
                        key=lambda m: (m.made, m.id), reverse=True)[:5]
    since = (date.fromisoformat(day) - timedelta(days=MISS_DAYS)).isoformat()
    misses = sorted((m for m in checked if m.status == "wrong" and m.updated[:10] >= since),
                    key=lambda m: m.updated, reverse=True)[:3]
    if not (checked or pinned or open_views):
        return ""
    lines = [CORE_HEADER]
    if checked:
        right = sum(1 for m in checked if m.status == "right")
        wrong = sum(1 for m in checked if m.status == "wrong")
        neutral = len(checked) - right - wrong
        share = f" ({right * 100 // (right + wrong)}% right)" if right + wrong else ""
        lines.append(f"Track record: {len(checked)} views checked, {right} right, {wrong} "
                     f"wrong, {neutral} neutral{share}.")
    if pinned:
        lines.append("Pinned:")
        lines.extend(f"- {m.text}" for m in pinned)
    if open_views:
        lines.append("Open views:")
        lines.extend(f"- {m.symbol} {m.direction}, check {m.due}: {m.text}" for m in open_views)
    if misses:
        lines.append("Recent misses:")
        lines.extend(f"- {m.symbol} {m.direction} on {m.made}: moved {m.result or 0.0:+.1f}%"
                     for m in misses)
    return _cut(lines, CORE_CHARS)


def recall(home: Path, owner: str, facts_text: str, day: str) -> str:
    """Up to 10 active notes that fit the facts; the shown ones go to ``memory_uses``."""
    con = connect(home)
    try:
        known = {str(r[0]) for r in con.execute(
            "SELECT DISTINCT symbol FROM memories WHERE owner = ? AND kind = 'note' "
            "AND symbol != ''", (owner,))}
        terms = [t for t in dict.fromkeys(_TICKER.findall(facts_text)) if t in known]
        terms = terms[:MAX_TERMS]
        found: list[Memory] = []
        if terms:
            query = "symbol : (" + " OR ".join(f'"{t}"' for t in terms) + ")"
            found = [_row(r) for r in con.execute(
                f"SELECT {', '.join('m.' + c.strip() for c in _COLUMNS.split(','))} "  # noqa: S608
                "FROM memories_fts f JOIN memories m ON m.id = f.rowid "
                "WHERE memories_fts MATCH ? AND m.owner = ? AND m.kind = 'note' "
                "AND m.status = 'active' AND m.pinned = 0 "
                "ORDER BY bm25(memories_fts), m.right - m.wrong DESC, m.updated DESC",
                (query, owner)).fetchall()]
        seen = {m.id for m in found}
        found += [m for m in _memories(
            con, "WHERE owner = ? AND kind = 'note' AND status = 'active' AND pinned = 0 "
            "ORDER BY updated DESC", (owner,)) if m.id not in seen]
        lines = [RECALL_HEADER]
        size = len(RECALL_HEADER)
        shown: list[Memory] = []
        for m in found[:RECALL_MAX]:
            line = f"- N-{m.id}: {m.text} ({m.right} right, {m.wrong} wrong)"
            if size + len(line) + 1 > RECALL_CHARS:
                break
            lines.append(line)
            shown.append(m)
            size += len(line) + 1
        if not shown:
            return ""
        with con:
            con.executemany("INSERT OR IGNORE INTO memory_uses (day, owner, memory_id) "
                            "VALUES (?, ?, ?)", [(day, owner, m.id) for m in shown])
        return "\n".join(lines)
    finally:
        con.close()


def with_memory(text: str, home: Path, owner: str, day: str) -> str:
    """``text`` plus the core block and recall; on any memory error the plain text."""
    try:
        parts = [core_block(home, owner, day), recall(home, owner, text, day)]
    except Exception:  # noqa: BLE001 — a wake still runs without memory
        log.warning("[Memory] Could not read the memory of %s; the prompt goes without it",
                    owner)
        return text
    extra = "\n\n".join(p for p in parts if p)
    return f"{text}\n\n{extra}" if extra else text


# ── views and scores (SRD-DSK-009.018–.020) ───────────────────────────────


def open_views_due(home: Path, last_day: str) -> list[Memory]:
    """Open views whose check day has a close by ``last_day``."""
    con = connect(home)
    try:
        return _memories(con, "WHERE kind = 'view' AND status = 'open' AND due <= ? "
                         "ORDER BY id", (last_day,))
    finally:
        con.close()


def move_result(direction: str, move_pct: float) -> str:
    """``right``, ``wrong`` or ``neutral`` for a view that moved ``move_pct`` percent."""
    signed = move_pct if direction == "up" else -move_pct
    if signed >= MOVE_PCT:
        return "right"
    if signed <= -MOVE_PCT:
        return "wrong"
    return "neutral"


def score_view(home: Path, view_id: int, move_pct: float, checked: str) -> str:
    """Close a view and add its result to the notes its owner saw that day."""
    con = connect(home)
    try:
        found = _memories(con, "WHERE id = ? AND kind = 'view' AND status = 'open'",
                          (view_id,))
        if not found:
            return ""
        view = found[0]
        result = move_result(view.direction, move_pct)
        with con:
            con.execute("UPDATE memories SET status = ?, result = ?, updated = ? WHERE id = ?",
                        (result, round(move_pct, 2), checked, view.id))
            if result != "neutral":
                column = "right" if result == "right" else "wrong"
                con.execute(f"UPDATE memories SET {column} = {column} + 1 "  # noqa: S608
                            "WHERE kind = 'note' AND id IN (SELECT memory_id FROM memory_uses "
                            "WHERE day = ? AND owner = ?)", (view.made, view.owner))
        return result
    finally:
        con.close()


def review(home: Path, now: datetime) -> None:
    """Daily: weak notes leave recall, strong ones come back, old unproven notes retire."""
    cutoff = (now - timedelta(days=EXPIRE_DAYS)).date().isoformat()
    con = connect(home)
    try:
        with con:
            con.execute("UPDATE memories SET status = 'retired', why = 'no prices to check' "
                        "WHERE kind = 'view' AND status = 'open' AND due < ?", (cutoff,))
        for note in _memories(con, "WHERE kind = 'note' AND status IN ('active', 'weak')"):
            checks = note.right + note.wrong
            weak = checks >= MIN_CHECKS and note.right / checks < WEAK_BELOW
            if (not note.pinned and not note.proven
                    and max(note.made, note.updated[:10]) < cutoff):
                _set_status(con, note, "retired", "not proven in 30 days", now)
            elif weak and note.status == "active":
                _set_status(con, note, "weak", f"{note.right} of {checks} right", now)
            elif not weak and note.status == "weak":
                _set_status(con, note, "active", "", now)
    finally:
        con.close()


def _set_status(con: sqlite3.Connection, note: Memory, status: str, why: str,
                now: datetime) -> None:
    with con:
        con.execute("UPDATE memories SET status = ?, why = ? WHERE id = ?",
                    (status, why, note.id))
    if status == "retired":
        log.info("[Memory] Note N-%d retired: %s", note.id, why)
    elif status == "weak":
        log.info("[Memory] Note N-%d left out of recall: %s", note.id, why)
    else:
        log.info("[Memory] Note N-%d is back in recall", note.id)


# ── weekly clean-up (SRD-DSK-009.021) ─────────────────────────────────────


def cleanup_notes(home: Path, owner: str) -> list[Memory]:
    """The owner's notes a clean-up may change: active or weak and not pinned."""
    con = connect(home)
    try:
        return _memories(con, "WHERE owner = ? AND kind = 'note' AND status IN "
                         "('active', 'weak') AND pinned = 0 ORDER BY id", (owner,))
    finally:
        con.close()


def apply_cleanup(home: Path, owner: str, actions: Sequence[CleanupAction],
                  now: datetime) -> tuple[int, int]:
    """Apply merges and retires to the owner's own unpinned notes; return (merged, retired)."""
    allowed = {m.id for m in cleanup_notes(home, owner)}
    merged = retired = 0
    con = connect(home)
    try:
        for act in actions:
            fresh = {m.id: m for m in _memories(
                con, "WHERE owner = ? AND kind = 'note' AND status IN ('active', 'weak') "
                "AND pinned = 0", (owner,)) if m.id in allowed}
            note = fresh.get(act.id)
            if note is None:
                continue
            if act.do == "retire":
                _set_status(con, note, "retired", "clean-up", now)
                retired += 1
            elif act.do == "merge" and act.into in fresh and act.into != act.id:
                target = fresh[act.into]
                with con:
                    con.execute("UPDATE memories SET text = ?, right = right + ?, "
                                "wrong = wrong + ?, updated = ? WHERE id = ?",
                                ((act.text or target.text).strip()[:200], note.right,
                                 note.wrong, _stamp(now), target.id))
                _set_status(con, note, "retired", f"merged into N-{target.id}", now)
                merged += 1
            else:
                continue
            allowed.discard(act.id)
    finally:
        con.close()
    log.info("[Memory] Clean-up for %s: %d merged, %d retired", owner, merged, retired)
    return merged, retired


# ── the Master's edits (SRD-DSK-009.022) ──────────────────────────────────


def add_edit(home: Path, memory_id: int, action: str, now: datetime) -> int:
    """Queue the Master's pin, unpin or retire of a note; return the edit id.

    Raises:
        ValueError: On an unknown action.
    """
    if action not in EDIT_ACTIONS:
        raise ValueError(f"action must be one of {', '.join(EDIT_ACTIONS)}")
    con = connect(home)
    try:
        with con:
            cur = con.execute("INSERT INTO memory_edits (memory_id, action, created) "
                              "VALUES (?, ?, ?)", (memory_id, action, _stamp(now)))
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def apply_edits(home: Path, now: datetime) -> int:
    """Apply the waiting edits in order; return how many were applied."""
    if not (home / MEMORY_DB).exists():
        return 0
    con = connect(home)
    try:
        waiting = con.execute("SELECT id, memory_id, action FROM memory_edits "
                              "WHERE applied IS NULL ORDER BY id").fetchall()
        for eid, mid, action in waiting:
            note = _apply_one(con, int(mid), str(action))
            with con:
                con.execute("UPDATE memory_edits SET applied = ?, note = ? WHERE id = ?",
                            (_stamp(now), note, eid))
        return len(waiting)
    finally:
        con.close()


def _apply_one(con: sqlite3.Connection, mid: int, action: str) -> str:
    found = _memories(con, "WHERE id = ? AND kind = 'note'", (mid,))
    if not found:
        return "no such note"
    if found[0].status == "retired":
        return "note is retired"
    with con:
        if action == "retire":
            con.execute("UPDATE memories SET status = 'retired', why = 'retired by the Master' "
                        "WHERE id = ?", (mid,))
        else:
            con.execute("UPDATE memories SET pinned = ? WHERE id = ?",
                        (1 if action == "pin" else 0, mid))
    return "done"


# ── reads for the GUI ─────────────────────────────────────────────────────


def memory_rows(home: Path, kind: str, status: str, owner: str | None = None
                ) -> list[Memory]:
    """Notes or views of one status (and one owner), pinned first then newest."""
    con = read_only(home)
    if con is None:
        return []
    try:
        if not has_table(con, "memories"):
            return []
        where = "WHERE kind = ? AND status = ?" + (" AND owner = ?" if owner else "")
        params: tuple[object, ...] = (kind, status, owner) if owner else (kind, status)
        rows = _memories(con, where, params)
    except sqlite3.Error:
        return []
    finally:
        con.close()
    return sorted(rows, key=lambda m: (not m.pinned, -m.id))


def pending_edits(home: Path) -> set[int]:
    """Ids of notes with an edit the desk has not applied yet."""
    con = read_only(home)
    if con is None:
        return set()
    try:
        if not has_table(con, "memory_edits"):
            return set()
        return {int(r[0]) for r in con.execute(
            "SELECT memory_id FROM memory_edits WHERE applied IS NULL")}
    except sqlite3.Error:
        return set()
    finally:
        con.close()
