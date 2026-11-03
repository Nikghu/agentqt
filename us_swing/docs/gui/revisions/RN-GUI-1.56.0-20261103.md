# Revision Note — RN-GUI-1.56.0-20261103

**Version:** 1.56.0
**Date:** 2026-11-03
**Tool:** GUI
**Artifact:** FO-GUI-032 / SRD-GUI-032.001–.008
**Type:** Feature

---

## Summary

The Execution screen now opens on a Strategies tab. It has a grouped view (Running, Stopped, Disabled) and a table view with one row per strategy, a bulk bar and an inline detail. The picked strategy and the last view are kept.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-032.001.M01 | `gui/execution_panel.py` | Tab order Strategies, Active trades, Closed today; Strategies tools in the tab bar row |
| MD-GUI-032.002.M02 | `gui/strategies_views.py` (new) | Row data, grouped list, table with inline detail row, bulk bar |
| MD-GUI-032.003.M03 | `gui/strategies_pane.py` | Header tools, view switch kept in QSettings, detail placement, bulk Start / Stop / Reset count |
| — | `gui/theme.py` | `_sidebar_qss` gets `detail_bg`; new `strategy_groups`, `strategy_table`, `inline_detail`, `strategy_bulk` rules |
| — | `assets/icons/table.svg` | New Lucide table icon for the Table view button |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-032.001 | Execution tabs read Strategies, Active trades, Closed today; Strategies opens first | Implemented |
| SRD-GUI-032.002 | Tab bar right side: "N of M running", Find strategy, + Add, Grouped / Table buttons | Implemented |
| SRD-GUI-032.003 | Grouped view with Running / Stopped / Disabled headers, counts and a row per strategy | Implemented |
| SRD-GUI-032.004 | Table view: one row per strategy with status, mode, P&L and Start / Stop / Enable button | Implemented |
| SRD-GUI-032.005 | Table row click opens the detail inline under the row; click again closes it | Implemented |
| SRD-GUI-032.006 | Checkboxes and a "N selected" bar with Start / Stop / Reset count | Implemented |
| SRD-GUI-032.007 | Picked strategy kept on view switch; last view restored on start | Implemented |
| SRD-GUI-032.008 | Status pill shows the status word only, no dot | Implemented |

---

## Design Decisions

- Grouped view: "Disabled" means the strategy mode is Disabled.
- Table view: detail opens inline on a warm background (#17150f in Carbon) with an accent left stripe; one row open at a time.
- View choice stored in QSettings("USSwing","ExecutionPanel") key `strategies_view`.
- Row Start / Stop no longer changes the strategy shown in the open detail (pyqt-code-reviewer HIGH, fixed with a test).
- Design chosen: Option E (https://claude.ai/artifact/4ZoepH1m7GLTUqD1t1eXhE).

---

## Issues Resolved

None

---

## Test Coverage

- 12 test cases Pass: UT-GUI-032.001.M01.T01, .003.M02.T01, .004.M02.T01, .008.M02.T01, .002.M03.T01–T02, .003.M03.T01, .005.M03.T01–T02, .006.M03.T01–T02, .007.M03.T01 (`tests/gui/test_strategies_views.py`).
- `tests/gui/test_strategies_pane.py` UT-GUI-024.004.M04.T01 updated to the new API.
- `tests/gui`: 624 passed. 22 errors in `test_chart_workspace.py` are pre-existing (same on main, WebEngine stub issue).
- `ruff` clean; `mypy --strict` clean on new files.
- Pending: user check in the real app window.
