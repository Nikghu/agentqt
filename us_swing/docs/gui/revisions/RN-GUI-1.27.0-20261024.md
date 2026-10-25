# Revision Note — RN-GUI-1.27.0-20261024

**Version:** 1.27.0
**Date:** 2026-10-24
**Tool:** GUI
**Artifact:** FO-GUI-025 (Phase 4 of 5) / SRD-GUI-025.013–.015
**Type:** Feature

---

## Summary

Phase 4 of the dashboard tiled workspace adds an Account Equity band above the tiles, with a range selector (1D, 1W, 1M, 3M, YTD) and a line-and-area chart. A "Performance" toggle in the KPI strip shows or hides the band. The Open Positions tile gets an "Exposure" tab with per-symbol bars and a $ Value / % Equity switch.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-025.013.M03 | `us_swing/src/us_swing/gui/performance_band.py` (new) | Equity band, equity chart, change text, exposure view and bars; groups more than 8 bars into "N others" |
| MD-GUI-025.001.M02 | `us_swing/src/us_swing/gui/dashboard_panel.py` | Account Equity band card, "Performance" toggle, remembered range and visibility (QSettings), Exposure tab on Open Positions tile |
| MD-GUI-025.003.M01 | `us_swing/src/us_swing/gui/dashboard_tiles.py` | `Tile.set_title_widget` so a tile can show tabs in its title |
| MD-GUI-025.001.M02 | `us_swing/assets/icons/chart-line.svg` (new) | Icon for the Performance toggle |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-025.013 | Performance band with Account Equity, range change, range buttons and equity chart | Implemented |
| SRD-GUI-025.014 | "Performance" button shows or hides the band; choice remembered | Implemented |
| SRD-GUI-025.015 | Open Positions "Exposure" tab with per-symbol bars, totals and $ / % switch | Implemented |

---

## Design Decisions

- Band and chart read `AppService.get_equity_curve(range)` (see RN-EXE-1.36.0-20261024).
- Header equity value comes from the last point of the curve, so it matches the chart.
- Exposure bars: largest first, long blue, short amber; more than 8 bars join one "N others" bar.

---

## Issues Resolved

None

---

## Test Coverage

10 UT cases (UT-GUI-025.013–.015) — all Pass. Suite: 1012 passed, 2 skipped (execution, GUI and core combined). pyqt-code-reviewer: no HIGH; 4 MEDIUM and LOW items fixed.

Known limits: paper equity is still Max Capital until Phase 5. Phase 5 KPI fixes are pending.
