# Revision Note — RN-GUI-1.39.0-20261029

**Version:** 1.39.0
**Date:** 2026-10-29
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.001–.004, .010–.012
**Type:** Feature

---

## Summary

New Backtest workspace (sidebar item after Charts). The left builder sets name, period, stocks (S&P 500, sectors or names, plus add and remove), screener preset and stocks per day. The right side shows the four-step strip, a data check line with Download, and Run Step 1, which runs in the background with progress and Cancel. The Step 1 view lists days with stock counts and the selected day's stocks with score and rank. Engine work is in RN-BKT-1.2.0.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.001.M01 | `gui/main_window.py` | Backtest nav item (index 4, wide page) and stack page |
| MD-GUI-031.002.M02 | `gui/backtest_builder.py` | New — `BacktestBuilder` |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | New — `BacktestWorkspace`, estimate and run workers |
| — | `tests/gui/test_sidebar_shell.py` | Screen list now includes Backtest |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.001 | Sidebar item | Implemented |
| SRD-GUI-031.002, .010 | Builder fields | Implemented |
| SRD-GUI-031.003 | Step strip | Implemented |
| SRD-GUI-031.004 | Data check line and Download | Implemented |
| SRD-GUI-031.011–.012 | Step 1 run and view | Implemented |

---

## Tests

- 9 new tests (UT-GUI-031.*), all pass. `ruff` and `mypy --strict` clean on the new files.

---

## Notes

- "Use AI ranking" is shown but disabled until a later phase.
- Download starts the normal backtest data download (range from Settings › Backtest data).
