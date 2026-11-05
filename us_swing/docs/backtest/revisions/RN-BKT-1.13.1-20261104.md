# Revision Note — RN-BKT-1.13.1-20261104

**Version:** 1.13.1
**Date:** 2026-11-04
**Tool:** BKT
**Artifact:** FO-BKT-001 / SRD-BKT-001.005
**Type:** Enhancement

---

## Summary

The download now finishes one stock before it starts the next: its daily request, then all its 3m pieces, newest first. Before this, all daily requests ran first, then 3m pieces of all stocks took turns by date.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-001.005.M03 | `backtest/planner.py` | `plan()` builds jobs per stock (1d, then 3m sorted by end, newest first); no global 3m sort |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-001.005 | Plan finishes one stock before the next | Implemented (reopened by user 2026-11-04 in chat) |

---

## Design Decisions

- User's choice. Trade-off told to the user: a stop halfway leaves some stocks complete and others empty, instead of every stock having the same recent months.
- Stock order unchanged (S&P 500 list order); SPY daily stays last. Downloader and progress bars need no change (they count per timeframe).

---

## Test Coverage

UT-BKT-001.005.M03.T01 (changed), UT-BKT-001.005.M03.T05 (new), both Pass. tests/backtest + test_app_service_backtest.py: 176 passed.
