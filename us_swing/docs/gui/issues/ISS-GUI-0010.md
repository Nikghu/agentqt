# Issue Report — ISS-GUI-0010

**Tool:** GUI
**Severity:** Medium (close button and icon strip go off screen; window must be restored to reach them)
**Status:** Resolved
**Date Opened:** 2026-10-27
**Date Resolved:** 2026-10-27
**Reporter:** User (screenshots — Watchlist fits, Position Details pushes the window past the right edge)
**Resolution:** RN-GUI-1.37.3-20261027

---

## Symptom

With the main window maximized, clicking a right icon strip button (Details or Watchlist) made the window wider than the 1920 px screen. The ✕ close button, the icon strip and part of the status bar went off screen and stayed there.

## Root Cause

The sidebar switched to mini only after the right panel finished sliding in. For about 200 ms the full sidebar (200 px) and the right panel (304 px) were both shown, so the window's minimum width went past the screen. A maximized frameless window grows to its minimum and does not shrink back.

## Fix

| File | Change |
|---|---|
| `gui/main_window.py` | `_on_panel_toggled` sets `panel_open` and shrinks the sidebar before asking for the right panel reveal |

## Verification

UT-GUI-019.009.M03.T01–T02 pass. Sandbox maximized measure: peak minimum width with real KPI values fell from 1911 to 1838 px. User confirmed in the app that the window now stays on screen.

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| SRD-GUI-019.009 | New — sidebar mini while a right panel is open (user-stated rule) | Implemented |
| MD-GUI-019.009.M03 | New row | Implemented |
| UTCD (GUI) | UT-GUI-019.009.* | Pass |
| TRACE (GUI) | SRD-GUI-019.009 row | Updated |

## Notes

- The KPI strip's minimum width is its full text width. With very long values it could still push the window wider; not seen by the user after this fix.
