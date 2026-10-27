# Revision Note — RN-GUI-1.37.3-20261027

**Version:** 1.37.3
**Date:** 2026-10-27
**Tool:** GUI
**Artifact:** FO-GUI-019 / SRD-GUI-019.009
**Type:** Bugfix

---

## Summary

Opening a right panel no longer pushes the maximized window past the screen. The sidebar now shrinks to mini at the moment of the click, on every screen, and stays mini while the panel is open.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-019.009.M03 | `us_swing/src/us_swing/gui/main_window.py` | Sidebar shrinks before the right panel reveal starts |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-019.009 | Sidebar stays mini while a right panel is open | Implemented |

---

## Issues Resolved

ISS-GUI-0010 — window grows past the screen when a right panel opens.

---

## Test Coverage

3 UT runs (UT-GUI-019.009.M03.T01 for Details and Watchlist, T02) in `tests/gui/test_side_panels_exit_drawer.py` — all Pass.
