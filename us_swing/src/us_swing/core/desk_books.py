"""
Module: MD-GUI-039.006.M02 — core/desk_books.py
Parent SRD: SRD-GUI-039.006

The desk books folder: the book types the desk can read and adding a book the user chose.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

BOOK_TYPES: tuple[str, ...] = (".txt", ".md", ".html", ".htm", ".pdf")
_ODD = re.compile(r"[^A-Za-z0-9._-]+")


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
