# Revision Note — RN-GUI-1.14.0-20261023

**Version:** 1.14.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-021 / SRD-GUI-021.003
**Type:** Feature

---

## Summary

Theme, Updates and Diagnostics each filled a whole Settings page with one or two buttons. They now sit together in a System panel opened from a new System icon on the right strip, like Details and Watchlist, on any screen. The Settings list drops to 7 sections. Layout option A from the "Settings Layout Options" design canvas, chosen by the user.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-021.001.M01 | `us_swing/src/us_swing/gui/settings_panel.py` | `_SystemSections.panel`; `SettingsPanel.system_panel`; Theme, Updates, Diagnostics pages removed |
| MD-GUI-019.001.M01 | `us_swing/src/us_swing/gui/side_panels.py` | `system` strip button |
| MD-GUI-019.002.M03 | `us_swing/src/us_swing/gui/main_window.py` | System panel added to the right panel stack |
| MD-GUI-017 | `us_swing/src/us_swing/gui/theme.py` | `panel_group` QSS rule |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-021.003 | System panel in the right panel stack, toggled from the strip | Implemented |

---

## Design Decisions

- Reuses the existing right panel and reveal path; no new animation code.
- Theme buttons share the panel width; "VS Code Dark" is shortened to "VS Code" so all three fit.

---

## Issues Resolved

None

---

## Test Coverage

2 new tests (UT-GUI-021.003.*) and 2 updated in `tests/gui/test_settings_sections.py`, all Pass. GUI suite: 297 passed.
