# Revision Note — RN-MKT-0.20.0-20261111

**Version:** 0.20.0
**Date:** 2026-11-11
**Tool:** MKT
**Artifact:** FO-MKT-018 / SRD-MKT-018.001–.012
**Type:** Feature

---

## Summary

Step F of the autonomous desk, skill 4: book to strategy research. A `book_to_strategy` ticket reads one chapter of a book (desk books folder or Project Gutenberg plain text) and writes one strategy card with entry, exit, stop and short quotes. Each chapter is read once; book tickets never auto-approve. This closes step F (4 of 4 skills).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-018.001.M01 | `src/us_swing/market/book_strategy.py` | New: read and card steps, quote check, result, gain, logs |
| MD-MKT-018.002.M02 | `src/us_swing/market/book_text.py` | New: topic form, books folder and Gutenberg source, readers, chapter split |
| MD-MKT-018.006.M03 | `src/us_swing/market/book_cards.py` | New: `strategy_cards` and `books_read` tables, read check, lead books block |
| MD-MKT-005.014.M08 | `src/us_swing/market/lead_brief.py` | Changed: lead plan facts show the books block |
| MD-MKT-018.001.M01 | `src/us_swing/market/employees/emp-016/` | New: default employee "Expert 13", skill `book_to_strategy`, trigger `research_done` |
| MD-MKT-018.001.M01 | `SKILL_PATHS`, `USSwing.spec`, `pyproject.toml` | Changed: skill path added; build includes new modules; new dependency `pypdf>=5.1` (installed as 5.1.0) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-018.001 | The book skill works `book_to_strategy` tickets in two steps: read (code) and card (one AI call) | Implemented |
| SRD-MKT-018.002 | Topic must be `upload:<file> ch <n>` or `gutenberg:<number> ch <n>`; any other topic ends `failed` | Implemented |
| SRD-MKT-018.003 | Book text comes only from the desk books folder or the Gutenberg plain-text file of that number; downloaded once and cached | Implemented |
| SRD-MKT-018.004 | The reader takes `.txt`, `.md`, `.html` and `.pdf`; other types end `failed` | Implemented |
| SRD-MKT-018.005 | Chapters split at headings, or into 5,000-word parts when none; text cut to 24,000 characters; missing chapter ends `failed` | Implemented |
| SRD-MKT-018.006 | A chapter already read is never read again; the ticket ends `failed` and names the earlier card | Implemented |
| SRD-MKT-018.007 | The card step makes one AI call returning name, idea, market, entry, exit, stop and 1 to 3 short quotes | Implemented |
| SRD-MKT-018.008 | Code keeps only quotes found in the chapter; card saved in `strategy_cards`; chapter marked read in `books_read` | Implemented |
| SRD-MKT-018.009 | Ticket ends `done` with the card; gain is yes only when entry, exit and stop are filled and at least one quote was found | Implemented |
| SRD-MKT-018.010 | Lead plan facts list uploaded books, the topic form for book tickets and chapters already read; at most 15 lines | Implemented |
| SRD-MKT-018.011 | Default employee `emp-016` ("Expert 13", skill `book_to_strategy`) ships; skill path in `SKILL_PATHS` and the app build | Implemented |
| SRD-MKT-018.012 | Each step logs the book, chapter, word count and quotes kept with the `[Research]` prefix | Implemented |

---

## Design Decisions

- Book tickets never auto-approve. Approval is the permission to read that one chapter (SRD-DSK-010.003).
- Text comes only from the desk books folder (`~/.usswing/desk/books`) or Project Gutenberg plain text. Gutenberg files are cached once.
- Output is one strategy card only. No trades, no changes to live setups.
- Gain = entry, exit and stop filled and at least one quote found in the chapter.
- Code review fixes: 20 MB file cap; 500-page PDF cap; Gutenberg download streamed with a 20 MB cap and refused if it leaves gutenberg.org; empty download refused; cache written atomically; safe heading regex; case-insensitive read-once key; first read record kept; chapter text dropped from state when done.
- Live check fixed a table-of-contents bug: book #11 split into 24 chapters instead of 12. Sections under 100 words are now skipped.

---

## Issues Resolved

None

---

## Test Coverage

UT-MKT-018.* — 23 cases, all Pass (`tests/market/test_book_strategy.py`).

Test runs by folder (`.venv`): market 509 pass; desk 347; core 276; AI Desk GUI files 194. `SKILL_PATHS` and the `test_p5b_defaults` skill list updated.

Commits on `feat/mkt-research-book` (stacked, unpushed): 6b31b2fe (FO/SRD), a49905aa (DD/MD/UTCD), e099584f (code).
