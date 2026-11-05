# Revision Note — RN-GUI-1.60.0-20261106

**Version:** 1.60.0
**Date:** 2026-11-06
**Tool:** GUI
**Artifact:** FO-GUI-034 / SRD-GUI-034.001–.010
**Type:** Feature

---

## Summary

Two new sidebar pages: Market Floor (5 tabs, foldable AI feed, 12-column adjustable panel grid with edit mode, catalog, panel settings, link groups A/B/C, named layouts) and AI Desk (Command home plus 10 other sections). A desk bar on both pages shows the desk state and drives Start / Pause / Resume / Stop off the UI thread. All panels and sections use sample data until the desk's data feed exists (P1).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-034.001.M01 | `gui/main_window.py` | Market Floor and AI Desk nav items and pages; poller shutdown |
| MD-GUI-034.002.M02 | `gui/desk_control.py` | Desk bar pill, Start / Pause / Resume / Stop, off-thread poller |
| MD-GUI-034.003.M09 | `core/desk_contract.py`, `desk/task.py` | Shared desk launch command; `FloorData` interface and `ProductDescriptor` |
| MD-GUI-034.004.M04 | `gui/market_floor.py`, `gui/floor_feed.py` | Five tabs, toolbar, foldable AI feed column |
| MD-GUI-034.005.M05 | `gui/floor_grid_model.py`, `gui/floor_grid.py` | 12-column grid rules and widget; edit mode drag, resize, remove |
| MD-GUI-034.006.M06 | `gui/floor_panel.py`, `gui/floor_dialogs.py` | Panel frame and bodies, link bus, catalog and panel settings dialogs |
| MD-GUI-034.008.M07 | `gui/floor_layouts.py` | Named layouts in `~/.usswing/floor_layouts.json`; default layout |
| MD-GUI-034.009.M08 | `gui/ai_desk.py`, `gui/ai_desk_sections.py`, `gui/ai_desk_sections2.py`, `gui/ai_desk_sections3.py`, `gui/ai_desk_sample.py` | AI Desk section list and 11 section frames |
| MD-GUI-034.010.M03 | `gui/floor_sample.py` | Sample products and rows behind `FloorData`; "Sample data" tag |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-034.001 | Sidebar shows Market Floor and AI Desk after Backtest, both as wide pages | Implemented |
| SRD-GUI-034.002 | Desk bar on both pages shows desk state as a pill, read every 2 seconds off the UI thread | Implemented |
| SRD-GUI-034.003 | Start launches the desk when Off, Stopped or Error; Pause, Resume and Stop send commands; buttons enabled only in allowed states | Implemented |
| SRD-GUI-034.004 | Market Floor has five tabs and a foldable AI feed column on the right; fold choice kept | Implemented |
| SRD-GUI-034.005 | Each tab is a 12-column grid; edit mode allows add, move, resize and remove, snapped with no overlap | Implemented |
| SRD-GUI-034.006 | Add panel opens a catalog of desk products; panel settings set view, filters and link group | Implemented |
| SRD-GUI-034.007 | Clicking a stock sends it to the other panels in the same link group (A, B or C) | Implemented |
| SRD-GUI-034.008 | Layouts saved by name in `~/.usswing/floor_layouts.json`; last one opens at start | Implemented |
| SRD-GUI-034.009 | AI Desk has a section list with Command as home and the ten other sections | Implemented |
| SRD-GUI-034.010 | Panels and sections fed by sample data show a "Sample data" tag; data comes through `FloorData` | Implemented |

---

## Design Decisions

- Start re-reads the desk status first, so it never launches a second desk. The desk is launched detached.
- A broken layouts file is renamed to `floor_layouts.json.bak` and the default layout is used, with a `[Floor]` warning.
- Chart view is a placeholder card in P0b.
- Approve, Reject and chat are shown but disabled until P5b.
- Known gap (not fixed): no undo for panel remove. The ✕ sits where ⚙ is outside edit mode.

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-034.* (37 rows) all Pass. 99 tests pass across the desk and GUI-034 test sets. Checked in the real app with real mouse clicks, drag and screenshots. Reviews: step a had 2 HIGH and 3 MED issues, fixed; step b had 2 HIGH and 4 MED issues plus 4 visual issues, fixed; step c approved.
