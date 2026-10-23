# Revision Note — RN-GUI-1.11.0-20261023

**Version:** 1.11.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-019 / SRD-GUI-019.001–.008
**Type:** Feature

---

## Summary

Phase 3 of the Carbon workspace. A right icon strip (Details, Watchlist, Log) opens a 300 px right panel and a 180 px bottom Live Log, both driven by RevealController. The Watchlist and the Dashboard log move out of the Dashboard. The modal Exit Position dialog is replaced by a non-modal Exit drawer, and Square Off All uses a list mode in the same drawer.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-019.001.M01 | `us_swing/src/us_swing/gui/side_panels.py` (new) | Right icon strip and Position Details panel |
| MD-GUI-019.006.M02 | `us_swing/src/us_swing/gui/dashboard_panel.py` | Exit drawer replaces modal dialog; Watchlist tab and embedded log removed |
| MD-GUI-019.002.M03 | `us_swing/src/us_swing/gui/main_window.py` | Panel layout, RevealController wiring, Settings scroll area |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-019.001 | Right icon strip with Details, Watchlist and Log toggles; Log badge counts warnings and errors while hidden | Implemented |
| SRD-GUI-019.002 | 280 px right panel and 180 px bottom panel, opened and closed through RevealController | Implemented |
| SRD-GUI-019.003 | Position Details shows the selected position with Exit, Stop / Trail and Open in Chart | Implemented |
| SRD-GUI-019.004 | Watchlist moves from a Dashboard tab to the right panel | Implemented |
| SRD-GUI-019.005 | Live Log moves from the Dashboard to the bottom panel | Implemented |
| SRD-GUI-019.006 | Non-modal Exit drawer replaces the Exit Position dialog | Implemented |
| SRD-GUI-019.007 | Square Off All opens the drawer in list mode, then Review and Confirm | Implemented |
| SRD-GUI-019.008 | Open in Chart switches to the Chart screen and loads the symbol | Implemented |

---

## Design Decisions

- Panels are plain QFrames, not QDockWidgets. Floating to a second monitor is not supported.
- The Exit drawer is non-modal (560 px). Confirm is one-shot, the live-mode block is re-checked at Confirm, and the drawer closes with an INFO log if its position closes or changes size.
- The Settings page is wrapped in a QScrollArea. It had forced a 939 px minimum height; the window minimum is now 395 px.

---

## Issues Resolved

None

---

## Test Coverage

10 new tests (UT-GUI-019.*) in `tests/gui/test_side_panels_exit_drawer.py`, all Pass. GUI suite: 285 passed.
