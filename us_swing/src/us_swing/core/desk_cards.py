"""
Module: MD-MKT-019.009.M04 — core/desk_cards.py
Parent SRD: SRD-MKT-019.009
Also: SRD-MKT-019.011 (untested cards block for the lead plan), SRD-GUI-040.001 (read by the
Cards section)

Strategy cards and their tests in ``desk.db``. The strategy test skill saves one
``card_tests`` row per test; the lead plan and the AI Desk Cards section read cards, the
latest test of each and the cards that have an open test ticket.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from us_swing.core.desk_contract import DB_NAME

KIND = "strategy_test"
MAX_BLOCK_LINES = 8
OPEN = ("waiting", "approved", "running", "paused")
TOPIC = re.compile(r"^SC-(\d{1,6})$", re.IGNORECASE)
HEADER = ("Strategy cards not yet tested (kind strategy_test; topic SC-<n>; code tests the "
          "card on all Backtest Data):")
SCHEMA = """
CREATE TABLE IF NOT EXISTS card_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT, card_id INTEGER, ticket_id INTEGER, made TEXT,
    result TEXT, reason TEXT, recipe TEXT, first_day TEXT, last_day TEXT, trades INTEGER,
    win_rate REAL, avg_r REAL, worst_run INTEGER, base_trades INTEGER, base_r REAL,
    verdict TEXT
);
"""


@dataclass(frozen=True)
class CardRow:
    """One strategy card."""

    id: int
    source: str
    chapter: int
    name: str
    idea: str
    market: str
    entry: str
    exit: str
    stop: str
    quotes: tuple[str, ...]
    made: str


@dataclass(frozen=True)
class CardTest:
    """One test of a card; ``result`` is ``pass``, ``fail`` or ``cant_test``."""

    card_id: int
    ticket_id: int
    made: str
    result: str
    reason: str = ""
    recipe: str = ""
    first_day: str = ""
    last_day: str = ""
    trades: int = 0
    win_rate: float = 0.0
    avg_r: float = 0.0
    worst_run: int = 0
    base_trades: int = 0
    base_r: float = 0.0
    verdict: str = ""


def card_id_of(topic: str) -> int | None:
    """The card id in a ticket topic ``SC-<n>``, or ``None``."""
    found = TOPIC.match(topic.strip())
    return int(found.group(1)) if found else None


def _read(home: Path, sql: str, params: tuple[Any, ...] = (),
          tables: tuple[str, ...] = ()) -> list[tuple[Any, ...]]:
    path = home / DB_NAME
    if not path.exists():
        return []
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        for table in tables:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                               (table,)).fetchone():
                return []
        return [tuple(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def _card(row: tuple[Any, ...]) -> CardRow:
    cid, source, chapter, name, idea, market, entry, exit_, stop, quotes, made = row
    try:
        kept = tuple(str(q) for q in json.loads(quotes or "[]"))
    except ValueError:
        kept = ()
    return CardRow(int(cid), str(source), int(chapter or 0), str(name or ""), str(idea or ""),
                   str(market or ""), str(entry or ""), str(exit_ or ""), str(stop or ""),
                   kept, str(made or ""))


_CARD_SQL = ("SELECT id, source, chapter, name, idea, market, entry, exit, stop, quotes, made "
             "FROM strategy_cards")


def cards(home: Path) -> list[CardRow]:
    """Every strategy card, newest first; empty before any card exists."""
    return [_card(r) for r in _read(home, f"{_CARD_SQL} ORDER BY id DESC",
                                    tables=("strategy_cards",))]


def card(home: Path, card_id: int) -> CardRow | None:
    """One card by id, or ``None``."""
    rows = _read(home, f"{_CARD_SQL} WHERE id = ?", (card_id,), ("strategy_cards",))
    return _card(rows[0]) if rows else None


def save_test(home: Path, test: CardTest) -> int:
    """Save one test row; return its id."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    try:
        con.execute("PRAGMA busy_timeout=5000")
        con.executescript(SCHEMA)
        with con:
            cur = con.execute(
                "INSERT INTO card_tests (card_id, ticket_id, made, result, reason, recipe, "
                "first_day, last_day, trades, win_rate, avg_r, worst_run, base_trades, base_r, "
                "verdict) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (test.card_id, test.ticket_id, test.made, test.result, test.reason,
                 test.recipe, test.first_day, test.last_day, test.trades, test.win_rate,
                 test.avg_r, test.worst_run, test.base_trades, test.base_r, test.verdict))
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def latest_tests(home: Path) -> dict[int, CardTest]:
    """The latest test of each tested card, by card id."""
    rows = _read(home, "SELECT card_id, ticket_id, made, result, reason, recipe, first_day, "
                       "last_day, trades, win_rate, avg_r, worst_run, base_trades, base_r, "
                       "verdict FROM card_tests ORDER BY id", tables=("card_tests",))
    out: dict[int, CardTest] = {}
    for r in rows:
        out[int(r[0])] = CardTest(int(r[0]), int(r[1]), str(r[2]), str(r[3]), str(r[4] or ""),
                                 str(r[5] or ""), str(r[6] or ""), str(r[7] or ""),
                                 int(r[8] or 0), float(r[9] or 0), float(r[10] or 0),
                                 int(r[11] or 0), int(r[12] or 0), float(r[13] or 0),
                                 str(r[14] or ""))
    return out


def open_test_cards(home: Path) -> set[int]:
    """Ids of cards that have an open strategy test ticket."""
    marks = ",".join("?" * len(OPEN))
    rows = _read(home, f"SELECT topic FROM tickets WHERE kind = ? AND status IN ({marks})",  # noqa: S608
                 (KIND, *OPEN), ("tickets",))
    return {cid for (topic,) in rows if (cid := card_id_of(str(topic))) is not None}


def untested_block(home: Path) -> str:
    """Cards with no test and no open test, at most 8 lines; empty when there are none."""
    done = set(latest_tests(home)) | open_test_cards(home)
    todo = [c for c in cards(home) if c.id not in done]
    if not todo:
        return ""
    lines = [HEADER, *(f"SC-{c.id}: {c.name}" for c in todo)]
    return "\n".join(lines[:MAX_BLOCK_LINES])
