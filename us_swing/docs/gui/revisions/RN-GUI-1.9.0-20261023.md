# Revision Note — RN-GUI-1.9.0-20261023

**Version:** 1.9.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-017 / SRD-GUI-017.001–005
**Type:** Feature

---

## Summary

Phase 1 of the Carbon Workspace redesign. A new default Carbon theme (graphite and amber) and a bundled icon set replace emoji on buttons, tabs and navigation. Risky buttons now use a red danger style in all three themes.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-017.001.M02 | `gui/theme.py` | Carbon theme tokens, danger role, 8-digit hex converted to rgba() |
| MD-GUI-017.003.M01 | `gui/icons.py` | New icon helper (cached QIcon, role colours, theme refresh) |
| — | `gui/main_window.py`, `gui/dashboard_panel.py`, `gui/screener_panel.py`, `gui/execution_panel.py`, `gui/settings_panel.py`, `gui/log_viewer_panel.py`, `gui/scheduler_dialog.py`, `gui/indicator_rules_dialog.py`, `gui/price_action_rules_dialog.py` | Emoji replaced by icons; danger role on risky buttons |
| — | `src/us_swing/__main__.py` | Registers bundled IBM Plex fonts at start |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-017.001 | Carbon theme is the default and is offered in Settings | Implemented |
| SRD-GUI-017.002 | IBM Plex Sans and Mono bundled and registered at start | Implemented |
| SRD-GUI-017.003 | Icons returned as cached QIcon coloured by role | Implemented |
| SRD-GUI-017.004 | Emoji on buttons, tabs and navigation replaced by icon plus label | Implemented |
| SRD-GUI-017.005 | Risky buttons use `role="danger"` in every theme | Implemented |

---

## Design Decisions

- Carbon theme generated from the Mocha QSS through a hex map.
- 8-digit hex converted to rgba() because Qt reads `#AARRGGBB` differently.
- Exit dialog confirm is danger for sell tabs; neutral with a shield icon for Stop and Trail.
- Added the missing INPUT token to Mocha (indicator dialogs referenced it).

---

## Issues Resolved

None

---

## Test Coverage

10 new tests in `tests/gui/test_carbon_theme_icons.py`. Full GUI suite: 266 passed.

---

## Notes

- Existing users keep their saved theme and must pick Carbon once in Settings.
- Fonts (IBM Plex, OFL) and icons (Lucide, ISC) are bundled under `us_swing/assets/`.
- Pre-existing ruff issues in panel files left untouched.
- Phases 2–4 (sidebar shell with Reveal, panels with Exit drawer, Charts MDI) pending.
