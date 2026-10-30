# Revision Note — RN-GUI-1.46.0-20261030

**Version:** 1.46.0
**Date:** 2026-10-30
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.055
**Type:** Feature

---

## Summary

Backtest redesign phase 3 (Reports). A third section tab, Reports, lists every saved run that has Step 3 results (name, saved time, period, return, max drawdown, trades, net P&L, status, stocks), loaded in a worker thread when the tab is shown. The details panel shows the run's plan and has Rename, a notes box with Save note, Delete (frameless confirm) and Open. Open (or double-click) reads the run back in a worker: Steps 1–2 from the step cache, Step 3 rows from `results.db`, with the saved Stocks per day; no new run is recorded. Panels now take a width share (`PanelSpec.stretch`).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.055.M09 | `gui/backtest_reports.py` | New: `ReportsView`, `plan_text()` |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Reports tab; `_OpenWorker`; shared `_start()`; saved Stocks per day for an opened run |
| MD-GUI-031.050.M05 | `gui/backtest_dock.py` | `PanelSpec.stretch` |

Backend side in RN-BKT-1.8.0-20261030.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.055 | Saved runs table; open, rename, note, delete | Implemented |
| SRD-GUI-031.050 | Three sections | Implemented (all three now present) |

---

## Tests

7 new GUI tests; backtest GUI + engine tests 184 passed. Real-window check (read-only): 24 saved runs listed in 3 ms tab click; opening the newest run took 3 s (11 s first time) and gave 103 trades, -$499.41, the same as the original run.
