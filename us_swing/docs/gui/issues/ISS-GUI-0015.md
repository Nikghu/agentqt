# Issue Report — ISS-GUI-0015

**Tool:** GUI
**Severity:** Medium (close button and right icon strip go off screen; window must be restored to reach them)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-03
**Date Resolved:** 2026-11-03
**Resolution:** RN-GUI-1.56.4-20261103
**Reporter:** User — "the tool is overfitted on the right side when I click on a right panel button; I cannot see the cross"

---

## Symptom

With the main window maximized, clicking a right panel button left the window wider than the 1920 px screen; the ✕ close button was off screen. Measured on the running app: window 1962 px, Windows minimum track size 1962 px.

## Root Cause

| Point | Detail |
|---|---|
| `QStackedWidget` minimum = widest of all screens | One wide screen raises the floor for every screen |
| Several labels size to their full text | With live data the widest screen plus the right panel passed 1920 px |
| A maximized frameless window grows to its minimum and never shrinks back | Same mechanism as ISS-GUI-0010, now from screen content, not the sidebar |

**SRD root cause:** no requirement capped the window at the screen width for screen content. SRD-GUI-019.010 added (approved by user, Implemented).

## Fix

| File | Change |
|---|---|
| `gui/main_window.py` | `_fit_to_screen` holds the screen stack in a resizable `QScrollArea`; a screen that needs more room scrolls inside its own area |

## Verification

UT-GUI-019.010.M03.T01–T02 pass; tests/gui 629 passed (22 old test_chart_workspace order errors, same on main). Sandbox (temp home, no feed): a screen forced to 2400 px with the right panel open keeps the window at 1920 px with the icon strip at x = 1915; on main the window grew to 2516 px.

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| SRD-GUI-019.010 | New | Implemented |
| MD-GUI-019.010.M03 | New row | Implemented |
| UTCD (GUI) | UT-GUI-019.010.M03.T01–T02 | Pass |
| TRACE (GUI) | SRD-GUI-019.010 row | Updated |

## Notes

- The exact wide widget in the live app was not found (live data needed); the scroll area makes the window safe whatever widget is wide. If a screen shows a sideways scrollbar in the app, that screen's widest label is the next thing to fix.
