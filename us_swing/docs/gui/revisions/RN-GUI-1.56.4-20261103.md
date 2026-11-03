# Revision Note — RN-GUI-1.56.4-20261103

**Tool:** GUI
**Version:** 1.56.4
**Date:** 2026-11-03
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Main window stays inside the screen (ISS-GUI-0015)

---

## Summary

With a right panel open, the maximized window grew to 1962 px on a 1920 px screen and the ✕
close button went off screen. The screens now sit in a resizable scroll area, so no screen's
content can widen the window; a screen that needs more room scrolls inside its own area.

## Changes

| File | Change |
|---|---|
| `gui/main_window.py` | New `MainWindow._fit_to_screen`: the screen stack is held in a resizable `QScrollArea` |
| `tests/gui/test_side_panels_exit_drawer.py` | UT-GUI-019.010.M03.T01–T02 |

## Requirements

SRD-GUI-019.010 (new, approved by user 2026-11-03, Implemented).

## Notes

- `QStackedWidget` takes the widest screen's minimum, so one wide screen widened every screen; a maximized frameless window grows to its minimum and never shrinks back (same mechanism as ISS-GUI-0010).
- The exact wide widget with live data was not found; if a screen shows a sideways scrollbar, its widest label is the next fix.

## Verification

- Sandbox (temp home, no feed): a screen forced to 2400 px with the right panel open keeps the window at 1920 px, icon strip at x = 1915; on main it grew to 2516 px
- `pytest tests/gui`: 629 passed; 22 `test_chart_workspace.py` errors pre-existing (same on main)
- `ruff` clean on `main_window.py`
- Real-app check pending (TODO T90)
