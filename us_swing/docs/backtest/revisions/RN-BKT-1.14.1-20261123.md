# Revision Note — RN-BKT-1.14.1-20261123

**Version:** 1.14.1
**Date:** 2026-11-23
**Tool:** BKT (+ GUI, see RN-GUI-2.8.1-20261123)
**Artifact:** FO-BKT-002 / SRD-BKT-002.088
**Type:** Bugfix

---

## Summary

The setup date range used the common span of all stocks. One newly listed stock (VYLR, from 2026-10-01) narrowed the calendar to a few months. The range now starts at the Backtest Data settings start date and ends at the latest saved data day, capped by the settings end date.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.008.M05 | `src/us_swing/backtest/service.py` | `_range_span` uses the settings start and the latest data day (capped by settings end), not the common span |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.088 | Data check returns the run range: Backtest Data start to the latest saved day (reopened 2026-11-22) | Implemented |

SRD row is not edited (status Implemented).

---

## Design Decisions

- A stock with later data does not narrow the range.
- The range end is the latest saved day, capped by the settings end date.

---

## Issues Resolved

None

---

## Test Coverage

- UT-BKT-002.088.M05.T01 (rewritten) and T02 (no saved data gives none): Pass.
- Backtest tests: 287 passed.
- App check: TODO T225 (GUI part).
