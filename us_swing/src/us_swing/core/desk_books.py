"""
Module: MD-GUI-039.006.M02 — core/desk_books.py
Parent SRD: SRD-GUI-039.006
Also: SRD-GUI-039.008 (books list with added date and chapters read)

The desk books folder: the book types the desk can read, adding a book the user chose and
listing the books with the chapters the desk has read.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from us_swing.core.desk_contract import DB_NAME

BOOK_TYPES: tuple[str, ...] = (".txt", ".md", ".html", ".htm", ".pdf")
_ODD = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class BookRow:
    """One book in the books folder."""

    name: str
    added: date
    chapters: tuple[int, ...]


class BookAddError(Exception):
    """Why a book could not be added, in plain words."""


def books_folder(home: Path) -> Path:
    """The books folder in the desk folder ``home``."""
    return home / "books"


def safe_name(name: str) -> str:
    """``name`` with spaces and odd characters as ``_`` and no leading dot."""
    path = Path(name)
    stem = _ODD.sub("_", path.stem).strip("._") or "book"
    return f"{stem}{path.suffix.lower()}"


def add_book(home: Path, source: Path) -> Path:
    """Copy ``source`` into the books folder and return the new file.

    Raises:
        BookAddError: The type is not a book type, the file is missing, or a book with
            the same name is already there.
    """
    if source.suffix.lower() not in BOOK_TYPES:
        raise BookAddError(f"{source.name} is not a PDF, TXT, MD or HTML file")
    if not source.is_file():
        raise BookAddError(f"{source.name} could not be found")
    folder = books_folder(home)
    target = folder / safe_name(source.name)
    if target.exists():
        raise BookAddError(f"A book named {target.name} is already there")
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def _chapters_read(home: Path) -> dict[str, list[int]]:
    path = home / DB_NAME
    if not path.exists():
        return {}
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                           "name='books_read'").fetchone():
            return {}
        read: dict[str, list[int]] = {}
        for source, chapter in con.execute("SELECT source, chapter FROM books_read "
                                           "ORDER BY chapter"):
            read.setdefault(str(source).lower(), []).append(int(chapter))
        return read
    finally:
        con.close()


def list_books(home: Path) -> list[BookRow]:
    """The books in the books folder, newest first, with the chapters already read.

    Raises:
        OSError: The folder could not be listed.
        sqlite3.Error: ``desk.db`` could not be read.
    """
    folder = books_folder(home)
    if not folder.is_dir():
        return []
    read = _chapters_read(home)
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in BOOK_TYPES
             and not p.name.startswith("gutenberg-")]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [BookRow(p.name, datetime.fromtimestamp(p.stat().st_mtime).date(),
                    tuple(read.get(f"upload:{p.name}".lower(), ()))) for p in files]
