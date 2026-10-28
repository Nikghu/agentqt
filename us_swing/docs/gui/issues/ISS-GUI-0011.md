# Issue Report — ISS-GUI-0011

**Tool:** GUI
**Severity:** Low (console errors; RSI and volume pane heights could be off for a moment)
**Status:** Resolved
**Date Opened:** 2026-10-28
**Date Resolved:** 2026-10-28
**Reporter:** User (app console log — repeated `js: Uncaught Error: Assertion failed: Invalid pane index`)
**Resolution:** RN-GUI-1.37.4-20261028

---

## Symptom

With the RSI pane on, the Charts page wrote `Assertion failed: Invalid pane index` to the console many times while charts loaded.

## Root Cause

Loading a chart sends overlays, plan, markers, levels and drawings one after another, and each call runs `applyStudies`. Each run removes and rebuilds the volume and RSI panes, then sets their heights over the next two animation frames. A height step from an older run then called `setHeight` on a pane that a newer run had already removed. Lightweight Charts 5.0.5 asserts that the pane index is valid.

## Fix

| File | Change |
|---|---|
| `gui/chart_panel.py` | `_sizeSubPanes` keeps a run counter; older pending frames are skipped and panes are looked up fresh before `setHeight` |

## Verification

`ruff` clean; 58 chart tests in `tests/gui` pass. No JS test exists for the chart page, and WebEngine cannot start from the agent shell, so the user checks it in the app: Charts with RSI on, switch stocks, no error in the console.

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| SRD-GUI-026.004 | No change — fix inside the existing RSI pane requirement | Implemented |
| Code | `gui/chart_panel.py` | Fixed |

## Notes

- Session docs (CONTEXT, DEVLOG, TODO, TRACE) are not edited on this branch, so it merges with `feat/backtest-data` without conflicts; add the session entries after both merge.
