# Revision Note — RN-DSK-0.9.0-20261111

**Version:** 0.9.0
**Date:** 2026-11-11
**Tool:** DSK
**Artifact:** FO-DSK-009 / SRD-DSK-009.001–.009
**Type:** Feature

---

## Summary

Step C of the autonomous desk: the desk now keeps lessons from closed picks. A lesson is a short rule with proof picks, and it becomes active after 5 picks back it. Lessons are only prompt text, so risk, stop, capital and approval rules never read them. Master edits (pin, edit, retire, delete) reach the desk at its next tick.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-009.001.M23 | `src/us_swing/core/desk_lessons.py` | New: lesson table, checks, daily review, lessons block, edits, rows for the GUI |
| MD-DSK-001.010.M04 | `src/us_swing/desk/process.py` | Changed: each tick applies pending lesson edits |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-009.001 | Each lesson is a row with text, tags, claim, proof, numbers and status | Implemented |
| SRD-DSK-009.002 | A candidate becomes active at 5 backing picks; unproved for 30 days it retires | Implemented |
| SRD-DSK-009.003 | A new candidate like a kept lesson updates it instead of adding a row | Implemented |
| SRD-DSK-009.004 | Each pick maker gets at most 5 matching active lessons, pinned first | Implemented |
| SRD-DSK-009.005 | Lessons are prompt text only; risk, stop, capital and approval code never read them | Implemented |
| SRD-DSK-009.006 | Each lesson shown to a skill on a day is kept in `lesson_uses` | Implemented |
| SRD-DSK-009.007 | An active lesson retires after 10 later backing-test misses or 90 days unconfirmed; pinned never | Implemented |
| SRD-DSK-009.008 | Master pin, unpin, edit, retire and delete arrive as `lesson_edits` rows applied at the next tick | Implemented |
| SRD-DSK-009.009 | New, activated and retired lessons are logged with a `[Memory]` prefix | Implemented |

---

## Design Decisions

- Lesson rules live in `core/desk_lessons.py`, so the market skills, the desk loop and the GUI share one copy.
- A Master-edited or pinned text is never overwritten by a desk candidate.
- A candidate like a lesson retired in the last 90 days stays a candidate (no flapping).
- A memory error falls back to plain facts; the run does not fail.

---

## Issues Resolved

None

---

## Test Coverage

UT-DSK-009.* — 26 cases, all Pass. Full suite: 12 failed (same as TODO T112), plus the old collection error in `tests/screener/test_llm_claude_screener.py` (TODO T136).
