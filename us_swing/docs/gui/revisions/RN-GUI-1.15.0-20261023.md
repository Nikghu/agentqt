# Revision Note — RN-GUI-1.15.0-20261023

**Version:** 1.15.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-021 / SRD-GUI-021.004
**Type:** Feature

---

## Summary

The candle database moves out of Settings into a Data panel opened from a new Data icon on the right strip (option Data 2, chosen by the user). The panel shows download percent, stock count, the current stock and failed stocks, and ends each download as Complete or Partial. The Data icon carries a badge: percent while downloading, a tick when complete, ! when stocks failed. Long help texts became short labels and tooltips. Settings no longer scrolls sideways, which had hidden the section list when a side panel was open.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-021.001.M01 | `us_swing/src/us_swing/gui/settings_panel.py` | `_DatabaseTab` → `_DataPanel`; `data_panel` property; Database section removed; System Diagnostics → Orders; Risk checkbox text shortened |
| MD-GUI-019.001.M01 | `us_swing/src/us_swing/gui/side_panels.py` | `data` strip button and `set_data_state()` badge |
| MD-GUI-019.002.M03 | `us_swing/src/us_swing/gui/main_window.py` | Data panel in the right panel stack; badge wiring; no horizontal scroll on Settings |
| MD-GUI-017 | `us_swing/src/us_swing/gui/theme.py` | `data_pill`, `data_pct`, `data_bar`, `data_badge` state rules |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-021.004 | Data panel with percent and Complete / Partial result; strip badge | Implemented |

---

## Design Decisions

- Download, delta, resume, fix (now "Retry Failed") and reset logic is unchanged; only layout and state display are new.
- The Complete badge uses the check icon, not a text tick, so it stays readable at 14 px.

---

## Issues Resolved

- Settings section list scrolled out of view when a side panel opened (found from the user's screenshot).
- A partial download showed as Complete when the Data panel was closed (`isVisible()` check); found by UT-GUI-021.004.M01.T03 before release.

---

## Test Coverage

8 new tests in `tests/gui/test_data_panel.py` (UT-GUI-021.004.*), 2 updated in `tests/gui/test_settings_sections.py`, all Pass. GUI suite: 305 passed.
