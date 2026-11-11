"""
Module: MD-DSK-003.021.M24 — core/desk_watch.py
Parent SRD: SRD-DSK-003.021
Also: SRD-DSK-003.022 (once per stock and kind an hour), SRD-DSK-003.024 (code feed note),
SRD-GUI-038.001 (desk live symbols), SRD-GUI-038.002 (open trades written by the app)

Watcher flags and the app's open trades in ``desk.db``. A flag is stored once per stock, kind
and New York hour; each new flag posts a ``watch_flag`` event and a short feed note made by
code. The open trades are written only by the app and read by the watchers. Shared by the
market watchers, the desk and the app.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_events import post_event

NY = ZoneInfo("America/New_York")
FLAG_LABELS: dict[str, str] = {
    "trigger_hit": "reached its trigger", "stop_touch": "touched its stop",
    "target_touch": "touched its target", "volume_spike": "volume spike", "gap": "gap",
    "regime_move": "large market move", "headline": "new headline",
}
FLAG_KINDS: tuple[str, ...] = tuple(FLAG_LABELS)
AUTHOR = "Watchers"
BENCHMARK = "SPY"

SCHEMA = """
CREATE TABLE IF NOT EXISTS watch_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT, hour INTEGER, kind TEXT, symbol TEXT,
    detail TEXT, price REAL, created TEXT, verdict TEXT, note TEXT, answered TEXT, tag TEXT,
    UNIQUE (day, hour, kind, symbol)
);
CREATE TABLE IF NOT EXISTS open_trades (
    symbol TEXT, side TEXT, entry REAL, stop REAL, target REAL, strategy TEXT, updated TEXT
);
CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY, created TEXT, data_day TEXT, author TEXT, kind TEXT, text TEXT,
    employee_id TEXT
);
"""
_FLAG_COLUMNS = "id, day, hour, kind, symbol, detail, price, created, verdict, note, answered"


@dataclass(frozen=True)
class Flag:
    """One watcher flag."""

    id: int
    day: str
    hour: int
    kind: str
    symbol: str
    detail: str
    price: float
    created: str
    verdict: str | None
    note: str | None
    answered: str | None


@dataclass(frozen=True)
class OpenTrade:
    """One open trade as the app last wrote it."""

    symbol: str
    side: str
    entry: float
    stop: float
    target: float | None
    strategy: str


def connect(home: Path) -> sqlite3.Connection:
    """Open ``desk.db`` in ``home`` with the watch tables ready."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    return con


def _flag(row: Sequence[object]) -> Flag:
    fid, day, hour, kind, symbol, detail, price, created, verdict, note, answered = row
    return Flag(int(str(fid)), str(day), int(str(hour)), str(kind), str(symbol), str(detail),
                float(str(price)), str(created), None if verdict is None else str(verdict),
                None if note is None else str(note), None if answered is None else str(answered))


def label(kind: str) -> str:
    """Plain words for a flag kind."""
    return FLAG_LABELS.get(kind, kind.replace("_", " "))


def add_flag(home: Path, kind: str, symbol: str, detail: str, price: float,
             now: datetime, tag: str = "") -> int | None:
    """Store a flag, post its event and its feed note; ``None`` when this hour has one.

    Raises:
        ValueError: When ``kind`` is not a flag kind.
    """
    if kind not in FLAG_KINDS:
        raise ValueError(f"unknown flag kind {kind}")
    ny = now.astimezone(NY)
    day = ny.date().isoformat()
    con = connect(home)
    try:
        with con:
            cur = con.execute(
                "INSERT OR IGNORE INTO watch_flags (day, hour, kind, symbol, detail, price, "
                "created, tag) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (day, ny.hour, kind, symbol, detail[:300], price, ny.isoformat(timespec="seconds"),
                 tag))
        if cur.rowcount != 1:
            return None
        fid = int(cur.lastrowid or 0)
        text = f"{symbol}: {label(kind)} at {price:.2f}" + (f" — {detail}" if detail else "")
        with con:
            con.execute("INSERT INTO briefs (created, data_day, author, kind, text, employee_id) "
                        "VALUES (?, ?, ?, 'info', ?, '')",
                        (ny.isoformat(timespec="seconds"), day, AUTHOR, text[:400]))
    finally:
        con.close()
    post_event(home, "watch_flag", day, now, fid)
    return fid


def flagged_today(home: Path, kind: str, symbol: str, day: str, tag: str | None = None
                  ) -> bool:
    """True when ``symbol`` already has a ``kind`` flag on ``day`` (with ``tag`` if given)."""
    con = connect(home)
    try:
        sql = "SELECT 1 FROM watch_flags WHERE day = ? AND kind = ? AND symbol = ?"
        params: tuple[object, ...] = (day, kind, symbol)
        if tag is not None:
            sql, params = sql + " AND tag = ?", (*params, tag)
        return con.execute(sql + " LIMIT 1", params).fetchone() is not None
    finally:
        con.close()


def next_flag(home: Path, day: str, since: datetime | None = None) -> Flag | None:
    """The oldest flag of ``day`` (made after ``since`` when given) with no verdict yet."""
    con = connect(home)
    try:
        rows = con.execute(f"SELECT {_FLAG_COLUMNS} FROM watch_flags WHERE day = ? AND "
                           "verdict IS NULL ORDER BY id", (day,)).fetchall()
    finally:
        con.close()
    flags = [_flag(r) for r in rows]
    if since is not None:
        flags = [f for f in flags if datetime.fromisoformat(f.created) > since]
    return flags[0] if flags else None


def answer_flag(home: Path, flag_id: int, verdict: str, note: str, now: datetime) -> None:
    """Keep the AI's verdict and note on a flag."""
    con = connect(home)
    try:
        with con:
            con.execute("UPDATE watch_flags SET verdict = ?, note = ?, answered = ? WHERE id = ?",
                        (verdict, note, now.isoformat(timespec="seconds"), flag_id))
    finally:
        con.close()


def flags_since(home: Path, since: datetime) -> list[Flag]:
    """Flags made after ``since``, oldest first."""
    con = connect(home)
    try:
        rows = con.execute(f"SELECT {_FLAG_COLUMNS} FROM watch_flags ORDER BY id").fetchall()
    finally:
        con.close()
    return [f for f in (_flag(r) for r in rows) if datetime.fromisoformat(f.created) > since]


def write_open_trades(home: Path, trades: Sequence[OpenTrade], now: datetime) -> None:
    """Replace the open trades with the app's current list."""
    con = connect(home)
    try:
        with con:
            con.execute("DELETE FROM open_trades")
            con.executemany(
                "INSERT INTO open_trades VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(t.symbol, t.side, t.entry, t.stop, t.target, t.strategy,
                  now.isoformat(timespec="seconds")) for t in trades])
    finally:
        con.close()


def open_trades(home: Path) -> list[OpenTrade]:
    """The open trades the app last wrote; empty when there are none."""
    con = connect(home)
    try:
        rows = con.execute("SELECT symbol, side, entry, stop, target, strategy FROM open_trades "
                           "ORDER BY symbol").fetchall()
    finally:
        con.close()
    return [OpenTrade(str(s), str(d), float(e), float(p), None if t is None else float(t),
                      str(g or "")) for s, d, e, p, t, g in rows]


def _has(con: sqlite3.Connection, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                       (table,)).fetchone() is not None


def plan_day(con: sqlite3.Connection, day: str) -> str | None:
    """The newest ideas day on or before ``day``."""
    if not _has(con, "ideas"):
        return None
    row = con.execute("SELECT MAX(date) FROM ideas WHERE date <= ?", (day,)).fetchone()
    return str(row[0]) if row and row[0] else None


def desk_live_symbols(home: Path, day: str) -> list[str]:
    """Listed ideas and lead picks of the newest plan day, then SPY; read-only."""
    path = home / DB_NAME
    if not path.exists():
        return [BENCHMARK]
    try:
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    except sqlite3.Error:
        return [BENCHMARK]
    try:
        plan = plan_day(con, day)
        out: list[str] = []
        if plan is not None:
            out = [str(r[0]) for r in con.execute(
                "SELECT symbol FROM ideas WHERE date = ? AND status = 'list' ORDER BY rank",
                (plan,))]
            if _has(con, "lead_picks"):
                out += [str(r[0]) for r in con.execute(
                    "SELECT symbol FROM lead_picks WHERE date = ?", (plan,))]
    except sqlite3.Error:
        out = []
    finally:
        con.close()
    return list(dict.fromkeys([*out, BENCHMARK]))
