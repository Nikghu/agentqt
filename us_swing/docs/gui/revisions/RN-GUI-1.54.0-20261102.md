# Revision Note — RN-GUI-1.54.0-20261102

**Version:** 1.54.0
**Date:** 2026-11-02
**Tool:** GUI
**Artifact:** FO-GUI-013, FO-GUI-031 / SRD-GUI-013.023, SRD-GUI-031.082–.084
**Type:** Feature

---

## Summary

Adds 30m across the strategy and backtest screens. The strategy builder uses one shared TIMEFRAMES list with 30m in all 9 dropdowns, and the Backtest Inspector offers a 30m choice. Saved runs can be downloaded as an HTML report, and Backtest screens plus the HTML report show dates as DD-MM-YYYY. Also fixes the Strategies table row fit and tick, the Step 3 status text, and adds a chart trade dropdown.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| — | `gui/theme.py` | Strategies table fits its rows; visible tick (QSS). MD ID not given in session input |
| MD-GUI-013.001.M01 | `gui/strategy_builder_dialog.py` | One shared `TIMEFRAMES` list with 30m in all 9 dropdowns |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Inspector 30m choice; chart trade dropdown (UT-GUI-031.052.M03.T02) |
| MD-GUI-031.055.M09 | `gui/backtest_reports.py` | Download HTML button in Saved runs; save runs in a worker |
| MD-GUI-031.083.M14 | `core/dates.py` | Shared DD-MM-YYYY date text; sessions keep the ISO date in UserRole |
| — | — | Step 3 status shows "Reading…", "Candles n/N", "Day n/N". File and MD ID not given in session input |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-013.023 | Every Timeframe dropdown offers 3m, 15m, 30m, 1d, 1w | Implemented |
| SRD-GUI-031.082 | Download button in Saved runs saves the run as an HTML report | Implemented |
| SRD-GUI-031.083 | Backtest screens and HTML report show DD-MM-YYYY dates | Implemented |
| SRD-GUI-031.084 | Backtest Inspector chart offers a 30m choice | Implemented |
| (none given) | Chart trade dropdown (UT-GUI-031.052.M03.T02) | Done — no SRD ID in session input |
| (none given) | Strategies table row fit and tick; Step 3 status text | Done — no SRD ID in session input |

---

## Design Decisions

- One shared TIMEFRAMES list for all strategy-builder forms (SRD-GUI-013.023).
- Dates change only in shown text. Stored data, cache keys and file names stay ISO (SRD-GUI-031.083).

---

## Issues Resolved

None.

---

## Test Coverage

5 UT cases, all Pass: UT-GUI-013.023.M01.T01, UT-GUI-031.052.M03.T02, UT-GUI-031.082.M09.T01, UT-GUI-031.083.M14.T01, UT-GUI-031.084.M03.T01.

Known flaky test: `test_backtest_item_after_charts` passes when run alone; it can fail in a full run.
