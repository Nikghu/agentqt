"""Tests for MD-GUI-039.006.M02 (core/desk_books.py)."""
from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from us_swing.core.desk_books import BookAddError, add_book, list_books, safe_name
from us_swing.core.desk_contract import DB_NAME


def test_add_book_safe_name(tmp_path: Path) -> None:
    """UT-GUI-039.006.M02.T01: A book is copied with a safe name."""
    source = tmp_path / "The Book (2nd ed).PDF"
    source.write_text("chapter 1 text")
    added = add_book(tmp_path / "desk", source)
    assert added == tmp_path / "desk" / "books" / "The_Book_2nd_ed.pdf"
    assert added.read_text() == "chapter 1 text"
    assert safe_name(".hidden.txt") == "hidden.txt"
    assert safe_name("!!!.md") == "book.md"


def test_add_book_wrong_type(tmp_path: Path) -> None:
    """UT-GUI-039.006.M02.T02: A file that is not a book type is refused."""
    source = tmp_path / "sheet.xlsx"
    source.write_text("x")
    with pytest.raises(BookAddError, match="not a PDF"):
        add_book(tmp_path / "desk", source)
    assert not (tmp_path / "desk" / "books").exists()


def test_add_book_same_name_kept(tmp_path: Path) -> None:
    """UT-GUI-039.006.M02.T03: A book with the same name is not replaced."""
    home = tmp_path / "desk"
    (home / "books").mkdir(parents=True)
    (home / "books" / "guide.txt").write_text("old")
    source = tmp_path / "guide.txt"
    source.write_text("new")
    with pytest.raises(BookAddError, match="already there"):
        add_book(home, source)
    assert (home / "books" / "guide.txt").read_text() == "old"


def test_add_book_missing_file(tmp_path: Path) -> None:
    """UT-GUI-039.006.M02.T04: A missing file is refused."""
    with pytest.raises(BookAddError, match="could not be found"):
        add_book(tmp_path / "desk", tmp_path / "gone.pdf")


def _read(home: Path, *rows: tuple[str, int]) -> None:
    con = sqlite3.connect(home / DB_NAME)
    con.execute("CREATE TABLE books_read (source TEXT, chapter INTEGER, card_id INTEGER, "
                "ticket_id INTEGER, made TEXT, PRIMARY KEY (source, chapter))")
    con.executemany("INSERT INTO books_read VALUES (?, ?, 1, 1, '2026-11-12')", rows)
    con.commit()
    con.close()


def test_list_books(tmp_path: Path) -> None:
    """UT-GUI-039.008.M02.T01: Books newest first, with added date and chapters read."""
    home = tmp_path / "desk"
    old = add_book(home, _src(tmp_path, "Old Book.pdf"))
    os.utime(old, (1_700_000_000, 1_700_000_000))
    add_book(home, _src(tmp_path, "new.txt"))
    (home / "books" / "gutenberg-12.txt").write_text("x")
    _read(home, ("upload:old_book.pdf", 3), ("upload:old_book.pdf", 1))
    books = list_books(home)
    assert [b.name for b in books] == ["new.txt", "Old_Book.pdf"]
    assert books[1].chapters == (1, 3) and books[0].chapters == ()
    assert books[1].added == date.fromtimestamp(1_700_000_000)


def test_list_books_none(tmp_path: Path) -> None:
    """UT-GUI-039.008.M02.T02: No books folder and no desk.db give an empty list."""
    assert list_books(tmp_path / "desk") == []


def _src(folder: Path, name: str) -> Path:
    path = folder / name
    path.write_text("text")
    return path
