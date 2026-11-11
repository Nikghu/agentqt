"""
Module: MD-MKT-017.006.M03 — market/sentiment_cards.py
Parent SRD: SRD-MKT-017.006
Also: SRD-MKT-017.007 (cards block in the lead's plan facts)

Sentiment cards in ``desk.db``: one short news tone per stock, judged for its idea's side
by a sentiment research ticket. The lead's plan prompt shows the newest card of the last
7 days for each idea it may pick. Cards are information only; no score reads them.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from us_swing.core.desk_contract import DB_NAME

log = logging.getLogger(__name__)

SHOW_DAYS = 7
MAX_LINES = 30
HEADER = ("News tone cards from research (last 7 days; information only, scores unchanged):")
SCHEMA = """
CREATE TABLE IF NOT EXISTS sentiment_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT, side TEXT, symbol TEXT, tone TEXT,
    reason TEXT, headlines INTEGER, ticket_id INTEGER, made TEXT
);
"""


@dataclass(frozen=True)
class CardRow:
    """One card to save."""

    side: str
    symbol: str
    tone: str
    reason: str
    headlines: int


def connect(home: Path) -> sqlite3.Connection:
    """Open ``desk.db`` in ``home`` with the cards table ready."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    return con


def save_cards(home: Path, day: str, ticket_id: int, cards: Iterable[CardRow],
               made: str) -> int:
    """Save the cards of one ticket; return how many were written."""
    rows = [(day, c.side, c.symbol, c.tone, c.reason, c.headlines, ticket_id, made)
            for c in cards]
    con = connect(home)
    try:
        with con:
            con.executemany("INSERT INTO sentiment_cards (day, side, symbol, tone, reason, "
                            "headlines, ticket_id, made) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    finally:
        con.close()
    return len(rows)


def _rows(path: Path, first: str) -> list[tuple[str, str, str, str, str, int]]:
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                           "name='sentiment_cards'").fetchone():
            return []
        return [(str(s), str(y), str(t), str(r), str(d), int(n or 0)) for s, y, t, r, d, n in con.execute(
            "SELECT side, symbol, tone, reason, day, headlines FROM sentiment_cards "
            "WHERE day >= ? ORDER BY day DESC, id DESC", (first,))]
    finally:
        con.close()


def cards_block(home: Path, keys: Iterable[tuple[str, str]], day: str) -> str:
    """The newest card from 7 days before ``day`` on, per ``(side, symbol)``; empty if none.

    Cards made after the ideas day (for example on a weekend) count too. Any read problem
    gives an empty block, so the lead's plan never fails on cards.
    """
    path = home / DB_NAME
    wanted = list(dict.fromkeys(keys))
    if not wanted or not path.exists():
        return ""
    try:
        first = (date.fromisoformat(day) - timedelta(days=SHOW_DAYS)).isoformat()
        rows = _rows(path, first)
    except (ValueError, sqlite3.Error):
        log.warning("[Research] Could not read the sentiment cards for the lead")
        return ""
    newest: dict[tuple[str, str], tuple[str, str, str, int]] = {}
    for side, symbol, tone, reason, when, count in rows:
        newest.setdefault((str(side), str(symbol)), (str(tone), str(reason), str(when),
                                                       int(count or 0)))
    lines = [f"{side} {symbol}: {tone}, {reason} ({when}, {count} headlines)"
             for (side, symbol) in wanted if (side, symbol) in newest
             for tone, reason, when, count in [newest[(side, symbol)]]]
    return "\n".join([HEADER, *lines[:MAX_LINES]]) if lines else ""
