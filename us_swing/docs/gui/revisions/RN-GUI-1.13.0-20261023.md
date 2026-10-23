# Revision Note — RN-GUI-1.13.0-20261023

**Version:** 1.13.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-021 / SRD-GUI-021.001–.002
**Type:** Feature

---

## Summary

Settings now follows the Carbon workspace mockup. The old tab bar is replaced by a section list on the left and one section card on the right. The crowded System tab is split into Connection, Scheduler, Telegram, Theme, Updates and Diagnostics. The Risk section (not shown before, and its Save only showed a demo note) is now listed and saves to the active user.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-021.001.M01 | `us_swing/src/us_swing/gui/settings_panel.py` | Section list + `QStackedWidget`; `_SystemTab` → `_SystemSections`; real Risk save |
| MD-GUI-017 | `us_swing/src/us_swing/gui/theme.py` | `settings_nav`, `settings_card`, `settings_head` QSS rules |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-021.001 | Section list shows one section at a time; System split into six sections | Implemented |
| SRD-GUI-021.002 | Save Risk Settings writes to the active user | Implemented |

---

## Design Decisions

- All ten sections kept (mockup's seven plus Connection, Universe and Database) — user choice.
- Theme section shows only the theme picker; the mockup's Animations and Sidebar mode options are left for later — user choice.
- No global Save button; each section keeps its own Save as before.

---

## Issues Resolved

None

---

## Test Coverage

4 new tests (UT-GUI-021.*) in `tests/gui/test_settings_sections.py`, all Pass. GUI suite: 295 passed.
