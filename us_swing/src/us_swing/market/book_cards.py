"""
Module: MD-MKT-018.006.M03 — market/book_cards.py
Parent SRD: SRD-MKT-018.006
Also: SRD-MKT-018.008 (card and read rows), SRD-MKT-018.010 (books block for the lead)

Strategy cards and the list of book chapters already read, in ``desk.db``. A chapter is
read once: a second ticket for it is refused and points to the earlier card. The lead's
plan prompt lists the uploaded books and the chapters already read.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from us_swing.core.desk_books import BOOK_TYPES
from us_swing.core.desk_contract import DB_NAME

log = logging.getLogger(__name__)

MAX_LINES = 15
MAX_BOOKS = 12
MAX_READ = 10
HEADER = ("Books you may propose (kind book_to_strategy; topic upload:<file> ch <n> or "
          "gutenberg:<number> ch <n>; public-domain Gutenberg books only):")
SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, chapter INTEGER, ticket_id INTEGER,
    name TEXT, idea TEXT, market TEXT, entry TEXT, exit TEXT, stop TEXT, quotes TEXT,
    made TEXT
);
CREATE TABLE IF NOT EXISTS books_read (
    source TEXT, chapter INTEGER, card_id INTEGER, ticket_id INTEGER, made TEXT,
    PRIMARY KEY (source, chapter)
);
"""


@dataclass(frozen=True)
class CardText:
    """The card fields to save."""

    name: str
    idea: str
    market: str
    entry: str
    exit: str
    stop: str
    quotes: Sequence[str]


def connect(home: Path) -> sqlite3.Connection:
    """Open ``desk.db`` in ``home`` with the card tables ready."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    return con


def already_read(home: Path, source: str, chapter: int) -> tuple[int, int] | None:
    """The earlier ``(card id, ticket id)`` for this chapter, or ``None`` when not read."""
    con = connect(home)
    try:
        row = con.execute("SELECT card_id, ticket_id FROM books_read WHERE source = ? AND "
                          "chapter = ?", (source, chapter)).fetchone()
    finally:
        con.close()
    return (int(row[0]), int(row[1])) if row else None


def save_card(home: Path, source: str, chapter: int, ticket_id: int, card: CardText,
              made: str) -> int:
    """Save the card and mark the chapter read in one go; return the card id."""
    con = connect(home)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO strategy_cards (source, chapter, ticket_id, name, idea, market, "
                "entry, exit, stop, quotes, made) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (source, chapter, ticket_id, card.name, card.idea, card.market, card.entry,
                 card.exit, card.stop, json.dumps(list(card.quotes)), made))
            card_id = int(cur.lastrowid or 0)
            con.execute("INSERT OR IGNORE INTO books_read VALUES (?, ?, ?, ?, ?)",
                        (source, chapter, card_id, ticket_id, made))
    finally:
        con.close()
    return card_id


def _read_list(home: Path) -> list[str]:
    path = home / DB_NAME
    if not path.exists():
        return []
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                           "name='books_read'").fetchone():
            return []
        return [f"{s} ch {c} (card SC-{k})" for s, c, k in con.execute(
            "SELECT source, chapter, card_id FROM books_read ORDER BY made DESC LIMIT ?",
            (MAX_READ,))]
    finally:
        con.close()


def books_block(home: Path, folder: Path) -> str:
    """Uploaded books, the topic form and chapters already read, in at most 15 lines."""
    try:
        files = sorted(p.name for p in folder.iterdir()
                       if p.is_file() and p.suffix.lower() in BOOK_TYPES
                       and not p.name.startswith("gutenberg-")) if folder.is_dir() else []
        done = _read_list(home)
    except (OSError, sqlite3.Error):
        log.warning("[Research] Could not list the books for the lead")
        return ""
    lines = [HEADER, *(f"upload:{f}" for f in files[:MAX_BOOKS])] if files else [
        HEADER, "No uploaded books yet"]
    if done:
        lines.append("Already read: " + ", ".join(done))
    return "\n".join(lines[:MAX_LINES])
