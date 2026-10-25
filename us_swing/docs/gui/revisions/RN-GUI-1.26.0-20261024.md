# Revision Note — RN-GUI-1.26.0-20261024

**Version:** 1.26.0
**Date:** 2026-10-24
**Tool:** GUI
**Artifact:** FO-GUI-025 / SRD-GUI-025.008–.012
**Type:** Feature

---

## Summary

The Dashboard tiles now have working buttons (FO-GUI-025, Phase 2 of 5). Open Positions gets a symbol filter and a Columns menu; Trade History gets range and state menus and CSV export; Market Watch rows get a ✕ to remove a symbol. Hidden columns and the menu choices are remembered across restarts.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-025.001.M02 | `us_swing/src/us_swing/gui/dashboard_panel.py` | Symbol filter, Columns menu (hidden columns by name), Trade History range and state menus, CSV export, Market Watch ✕ remove |
| MD-GUI-002.001.M01 | `us_swing/src/us_swing/gui/dashboard_panel.py` | Market Watch tile ✕ column calls `remove_from_watchlist`; Remove button hidden in the tile only |
| MD-GUI-025.003.M01 | `us_swing/src/us_swing/gui/dashboard_tiles.py` | `table_rows()` returns the shown rows and columns for CSV export |
| — | `us_swing/assets/icons/columns-3.svg` | New Lucide icon for the Columns button |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-025.008 | The Open Positions Filter button shows a symbol box; typing hides rows whose symbol does not contain the text. | Implemented |
| SRD-GUI-025.009 | The Open Positions Columns button opens a checkable list; unticked columns are hidden and remembered. Symbol cannot be hidden. | Implemented |
| SRD-GUI-025.010 | Trade History has a range menu (Today, 7 days, 30 days, All) and a state menu; the header count shows the range and row count. | Implemented |
| SRD-GUI-025.011 | The Trade History Export button saves the shown rows and columns to a CSV file the user picks. | Implemented |
| SRD-GUI-025.012 | Each Market Watch tile row ends with a ✕ that removes that symbol. | Implemented |

---

## Design Decisions

- Hidden columns are stored by name (`hidden_cols`), so they survive the User column shift.
- Trade History range uses the market time zone; range and state choices are remembered.
- Model reset re-applies the row filter and hidden columns (review HIGH fix: hidden state was lost on reset).

---

## Issues Resolved

None

---

## Test Coverage

12 UT cases (UT-GUI-025.008–.012) in `tests/gui/test_dashboard_tiles.py` — 12 Pass. GUI suite 373 passed. Code reviewed with pyqt-code-reviewer: 1 HIGH and 2 MEDIUM fixed, LOW items fixed.
