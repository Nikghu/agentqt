# Revision Note — RN-MKT-0.16.0-20261111

**Version:** 0.16.0
**Date:** 2026-11-11
**Tool:** MKT
**Artifact:** FO-MKT-014 / SRD-MKT-014.001–.005
**Type:** Feature

---

## Summary

Step E of the autonomous desk, market side: the lead plan and the check-in note can now carry up to 3 research tickets. The lead's prompt shows its research tokens left, its open tickets and its recent results. Valid tickets of a kept answer are handed to the desk's research queue.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-014.001.M01 | `src/us_swing/market/lead_brief.py` | Changed: `tickets` field (up to 3) in the lead answer; research block in the facts; tickets handed to the queue |
| MD-MKT-014.001.M02 | `src/us_swing/market/checkin_note.py` | Changed: `tickets` field (up to 3) in the check-in answer; research block in the facts; tickets handed to the queue |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-014.001 | The lead plan and check-in answers may hold up to 3 tickets, each with kind, topic, goal, done test and token cap | Implemented |
| SRD-MKT-014.002 | Ticket kinds come from a fixed list of six; an unknown kind makes only that ticket invalid | Implemented |
| SRD-MKT-014.003 | A ticket's token cap is between 1,000 and 100,000 tokens | Implemented |
| SRD-MKT-014.004 | The lead's prompt shows its research tokens left today, its open tickets and its results from the last 30 days (at most 600 tokens) | Implemented |
| SRD-MKT-014.005 | Valid tickets of a kept answer are handed to the research queue; its rules decide approve, wait or refuse | Implemented |

---

## Design Decisions

- Tickets are added through the shared research rules in `core.desk_research`; the market code holds only the `tickets` field and the two calls.
- A queue error keeps the brief and the picks.

---

## Issues Resolved

None

---

## Test Coverage

UT-MKT-014.* — 12 cases, all Pass (`tests/market/test_lead_tickets.py`). Full suite: no new failures; the 12 failures are the old ones in TODO T112; `tests/screener/test_llm_claude_screener.py` ignored (old import error, TODO T136).
