# Revision Note — RN-DSK-0.12.0-20261111

**Version:** 0.12.0
**Date:** 2026-11-11
**Tool:** DSK
**Artifact:** FO-DSK-010 / SRD-DSK-010.015
**Type:** Feature

---

## Summary

Step F of the autonomous desk, skill 2 support: a research skill can now hand follow-up tickets to the research queue. Each follow-up is raised in the name of the lead that raised the skill's own ticket, and the lead's limits apply. The pick post-mortem skill (FO-MKT-016) is the first user.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-010.001.M25 | `src/us_swing/core/desk_research.py` | Changed: `raise_follow_ups()` added; raises asks in the lead's name using the usual ticket rules |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-010.015 | A research skill may hand follow-up tickets to the queue in the name of the lead that raised its own ticket; rules .002–.007 apply to that lead | Implemented |

---

## Design Decisions

- Follow-ups are never raised in the doer's name.
- Follow-ups use the lead's own limits: 3 tickets a day, auto-approval up to 10,000 tokens, repeat and parked-topic checks.
- A retired lead, or an id that is not a lead, refuses every ask; no rows are written.

---

## Issues Resolved

None

---

## Test Coverage

UT-DSK-010.015.M25.T01–T03 (3 cases), all Pass (`tests/desk/test_follow_ups.py`). Desk folder: 347 pass.
