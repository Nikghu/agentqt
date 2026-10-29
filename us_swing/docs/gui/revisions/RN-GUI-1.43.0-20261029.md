# Revision Note — RN-GUI-1.43.0-20261029

**Version:** 1.43.0
**Date:** 2026-10-29
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.040–.045
**Type:** Feature

---

## Summary

Phase 4a of the backtest engine, GUI side: a Report tab in the Backtest workspace. It shows a KPI row, an equity chart against the equal-weight benchmark with a drawdown chart below, a monthly P&L heat map, a breakdown table with a "Group by" picker, a variant picker with a compare table, and CSV export. Reports are built on a worker thread, and the variant picker also drives the Trades, Day log and Money tabs.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.040.M04 | `gui/backtest_report_view.py` | New: `ReportView`, `ReportChart`, `fmt()`, `skips_text()` |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Report tab; `report_done` signal (reports built on worker thread); variant picker also drives Trades / Day log / Money; results cleared at a new run |

Backend side of SRD-BKT-002.040–.047 is in RN-BKT-1.6.0-20261029.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.040 | Report tab shows a KPI row: net P&L, return %, max drawdown, win rate, profit factor, trades | Implemented |
| SRD-GUI-031.041 | Equity curve with the benchmark line, and a drawdown chart below it | Implemented |
| SRD-GUI-031.042 | Monthly P&L heat map (year × month), green gain, red loss | Implemented |
| SRD-GUI-031.043 | Breakdown table with a "Group by" picker | Implemented |
| SRD-GUI-031.044 | Variant picker, plus a compare table when the run has more than one variant | Implemented |
| SRD-GUI-031.045 | Export trades and stats to CSV | Implemented |

---

## Design Decisions

- Reports are built on a worker thread; the Report tab waits for `report_done`.
- The variant picker is shared: picking a variant also changes the Trades, Day log and Money tabs.
- A new run clears the old results.

---

## Issues Resolved

None

---

## Test Coverage

- UT-GUI-031.040–.045: 12 tests (M04 × 10, M03 × 2), all Pass.
- `tests/gui/test_backtest_workspace.py` + `tests/gui/test_backtest_report_view.py` with `tests/backtest`: 153 passed. `ruff` and `mypy --strict` clean on changed files.
- pyqt-code-reviewer: APPROVE. Fixed: CSV export `OSError` now logged (MEDIUM); clear results on a new run and skip an empty report (LOW × 2).
