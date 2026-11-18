# Revision Note — RN-GUI-2.3.0-20261118

**Version:** 2.3.0
**Date:** 2026-11-18
**Tool:** GUI
**Artifact:** FO-GUI-042 / SRD-GUI-042.001–.006
**Type:** Feature

---

## Summary

The screener Edit Preset dialog now has a left side list with four sections: General, Screeners, AI Ranking and AI Context. Each list item shows a one-line summary and a dot (green when set, yellow when something is missing, grey when off). AI fields are greyed out, not hidden, while AI Ranking is off. A failed Save or Save As now shows its reason in a red footer line, so the error can no longer sit on a hidden page. Saved preset data is unchanged. The layout follows the design the user picked (Option B, Trade settings moved into General).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-042.001.M01 | `src/us_swing/gui/screener_panel.py` | Edit Preset side list, four section pages, per-item summaries and dots, AI fields disabled when off, red footer error line |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-042.001 | Side list of General, Screeners, AI Ranking and AI Context with one section page on the right | Implemented |
| SRD-GUI-042.002 | General holds name, description, timeframe, trading style and Assign Users | Implemented |
| SRD-GUI-042.003 | Each page holds its fields; AI fields disabled, not hidden, while AI Ranking is off | Implemented |
| SRD-GUI-042.004 | Each list item shows a one-line summary that follows its fields | Implemented |
| SRD-GUI-042.005 | Each list item shows a green, amber or grey dot | Implemented |
| SRD-GUI-042.006 | Saving gives the same preset as before for the same choices | Implemented |

---

## Design Decisions

- Side list reuses the `PresetItem` row style from the Backtest setup window.
- Trade settings moved from the old top area into the General page (Option B of the chosen design).
- AI fields are disabled, not hidden, while AI Ranking is off, so the user can see what turning AI on unlocks.
- Amber dot only warns. Save checks stay as they were.
- New FO-GUI-042 used; FO-GUI-034 was not reused because the removed AI Desk used it.

---

## Issues Resolved

None

---

## Test Coverage

9 UT cases added and Pass: UT-GUI-042.001.M01.T01, .002.M01.T01, .003.M01.T01–T02, .004.M01.T01, .005.M01.T01–T03, .006.M01.T01 (`tests/gui/test_preset_dialog_nav.py`). Two AI provider tests (`tests/gui/test_preset_ai_provider.py`) now tick Enable AI first. 53 tests pass across test_screener_views, test_preset_dialog_nav, test_preset_ai_provider and test_no_stray_windows.
