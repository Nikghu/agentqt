# Revision Note — RN-GUI-1.65.0-20261112

**Version:** 1.65.0
**Date:** 2026-11-12
**Tool:** GUI
**Artifact:** FO-GUI-034, FO-GUI-039 / SRD-GUI-034.065, SRD-GUI-039.006–.008
**Type:** Feature

---

## Summary

The AI Desk header tiles for Last run and Next run now show the day, date and time, in ET only. The AI Desk Research tab gets an Add book button that copies a chosen PDF, TXT, MD or HTML file into the desk books folder, and a Books list that shows each book's added date and the chapters already read. The book file-type list moved from the market package to core so both the GUI and the desk use one copy.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-034.065.M39 | `src/us_swing/gui/ai_desk_console.py` | Changed: header tiles show day and date in ET |
| MD-GUI-039.001.M01 | `src/us_swing/gui/ai_desk_research.py` | Changed: Add book button and Books list on the Research tab |
| MD-GUI-039.006.M02 | `src/us_swing/core/desk_books.py` | New: book types, safe file names, adding a book, listing books with chapters read |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-034.065 | Last run and Next run show day, date and time in ET only (wording updated) | Implemented |
| SRD-GUI-039.006 | Add book button copies a chosen PDF, TXT, MD or HTML file into the desk books folder | Implemented |
| SRD-GUI-039.007 | Each added or refused book is logged with the `[Books]` prefix | Implemented |
| SRD-GUI-039.008 | Books list shows the books with the date each was added and the chapters read | Implemented |

---

## Design Decisions

- Spaces and odd characters in a book's file name become `_`; a file with the same name is not replaced.
- `BOOK_TYPES` moved from the market package to `core` so the GUI and the desk share one list.
- Books list reads the books folder and `books_read` only; it skips the Gutenberg cache files.

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-039.006–.008 — 10 new cases, all Pass (`tests/gui/`). UT-GUI-034.060.M33.T01 and UT-GUI-034.065.M39.T01 updated for the header dates; both Pass. 109 AI Desk GUI tests pass. ruff clean; mypy clean for changed files.
