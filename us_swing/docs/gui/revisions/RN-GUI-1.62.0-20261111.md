# Revision Note — RN-GUI-1.62.0-20261111

**Version:** 1.62.0
**Date:** 2026-11-11
**Tool:** GUI
**Artifact:** FO-GUI-037 / SRD-GUI-037.001–.004
**Type:** Feature

---

## Summary

AI Desk gets a Memory section after Results. It lists lessons, with a filter for active, candidate or retired ones, and lets the Master pin, unpin, edit text, retire or delete a lesson. Each action adds a row that the desk applies at its next tick. Choosing a lesson shows its proof picks.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-037.001.M01 | `src/us_swing/gui/ai_desk_memory.py` | New Memory section: filter, lessons table, Pin/Unpin/Edit/Retire/Delete, proof list |
| MD-GUI-037.001.M01 | `src/us_swing/gui/ai_desk.py` | Changed: Memory section wired after Results |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-037.001 | AI Desk has a Memory section after Results; reads `desk.db` only | Implemented |
| SRD-GUI-037.002 | Lessons table with status, pinned, text, tags, cases, average R, confidence and last confirmed | Implemented |
| SRD-GUI-037.003 | Pin, Unpin, Edit, Retire and Delete add a `lesson_edits` row; Delete asks first | Implemented |
| SRD-GUI-037.004 | Choosing a lesson shows its proof picks with date, side, stock and R | Implemented |

---

## Design Decisions

- The GUI writes only new `lesson_edits` rows; it never edits `lessons` directly.
- Delete uses the app's frameless confirm box.

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-037.* — 7 cases, all Pass. Full suite: 12 failed (same as TODO T112), plus the old collection error in `tests/screener/test_llm_claude_screener.py` (TODO T136).
