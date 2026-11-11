# Revision Note — RN-GUI-1.64.0-20261111

**Version:** 1.64.0
**Date:** 2026-11-11
**Tool:** GUI
**Artifact:** FO-GUI-039 / SRD-GUI-039.001–.005
**Type:** Feature

---

## Summary

The AI Desk has a new live "Research" section in the TEAM group, after Team at work. It lists research tickets, shows each lead's research tokens used and left today, and lets the Master user approve, reject or change the token cap of a waiting ticket. Each edit is written as a `ticket_edits` row for the desk to apply.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-039.001.M01 | `src/us_swing/gui/ai_desk_research.py` | New: Research section with lead research line, ticket table, Approve / Reject / Change cap, detail label and logs |
| MD-GUI-034.009.M08 | `src/us_swing/gui/ai_desk.py` | Changed: Research section added to the TEAM group with live refresh |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-039.001 | The AI Desk has a Research tab that lists tickets with kind, goal, token cap, tokens spent, raised by and status | Implemented |
| SRD-GUI-039.002 | Approve, Reject and Change cap on a waiting ticket write one new `ticket_edits` row | Implemented |
| SRD-GUI-039.003 | Selecting an ended ticket shows its result and end reason | Implemented |
| SRD-GUI-039.004 | The Research tab shows each lead's research tokens used and left today | Implemented |
| SRD-GUI-039.005 | Each approve, reject and cap change is logged with the `[Research]` prefix | Implemented |

---

## Design Decisions

- The section reads `desk.db` only; the desk applies the edits on its next tick.
- Review fixes: reads are guarded against SQLite errors; no second edit is sent while one is pending.

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-039.* — 9 cases, all Pass (`tests/gui/test_ai_desk_research.py`). `test_ai_desk.py` and `test_ai_desk_design.py` now expect 11 sections. Full suite: no new failures; the 12 failures are the old ones in TODO T112; `tests/screener/test_llm_claude_screener.py` ignored (old import error, TODO T136).
