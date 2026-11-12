"""Tests for MD-GUI-039.006.M02 (core/desk_books.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from us_swing.core.desk_books import BookAddError, add_book, safe_name


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
