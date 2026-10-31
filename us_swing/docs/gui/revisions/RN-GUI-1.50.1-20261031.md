# Revision Note — RN-GUI-1.50.1-20261031

**Version:** 1.50.1
**Date:** 2026-10-31
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.075, SRD-GUI-031.055
**Type:** Fix

---

## Summary

Backtest header stepper now sits in a centred rounded capsule (3-column title row) with small step circles, solid green when done, and short thin connectors. Play / Cancel icons on Run and Open were drawn in the dark background colour; they now use the "go" colour. Saved Reports allows Ctrl / Shift multi-select; Delete removes all picked runs after one confirm. The bottom status bar is removed: Internet and market status were already in the sidebar Connections box, and backtest download progress now shows there as a "Backtest data" row while a download runs.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.075.M11 | `gui/backtest_header.py` | `StepStrip` is a capsule frame, 16 px circles, 16 px connectors |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Title row is a 3-column grid; Run / Cancel icons use "go" |
| MD-GUI-031.055.M09 | `gui/backtest_reports.py` | Extended selection, `selected_all()`, multi-delete, Open icon "go" |
| — | `gui/backtest_setup.py` | Run icon uses "go" |
| MD-GUI-030.007.M05 | `gui/sidebar.py` | "Backtest data" row in Connections, hidden 15 s after the end |
| — | `gui/main_window.py` | Status bar and its Internet / NYSE / NASDAQ / backtest items removed |
| — | `gui/theme.py` | Capsule and step circle QSS |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.075 | Header stepper and field grid | Implemented |
| SRD-GUI-031.055 | Saved runs table: open, rename, note, delete | Implemented |

---

## Design Decisions

- User picked the centred capsule from https://claude.ai/artifact/2Y3fKMNjRpjoKLETA5pqxF; done steps stay solid green.
- With several runs picked, only Delete stays on; it reads "Delete (N)" and the details say "N runs selected".

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-031.055.M09.T06 (Pass) added; UT-GUI-030.007.M05.T01 moved to the sidebar, T02 added (Pass); full GUI suite 582 passed, same 22 test-order errors as main; 38 backtest reports and workspace tests pass; ruff clean, no new mypy errors. Real-app check by user pending.
