# Revision Note — RN-BKT-1.8.0-20261030

**Version:** 1.8.0
**Date:** 2026-10-30
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.060
**Type:** Feature

---

## Summary

Saved runs can be renamed, carry a note and be deleted with all their rows. The `runs` table gets a `note` column (added to old files at start). The service lists saved reports (runs with Step 3 rows) with the first variant's trades, net P&L, return and max drawdown, and opens a saved run without recording new runs.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.007.M04 | `backtest/results.py` | `note` column; `list_reports()`, `rename_run()`, `set_note()`, `delete_run()` |
| MD-BKT-002.008.M05 | `backtest/service.py` | `SavedReport`, `OpenedRun`, `stocks_text()`, `saved_results()`, `saved_reports()`, `open_run()`, rename / note / delete; `record` flag on Steps 1–2 |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.060 | Rename a run, keep a note, delete it with all its rows | Implemented |

---

## Tests

4 new tests (UT-BKT-002.060.M04.T01–T02, M05.T01–T02), Pass.
