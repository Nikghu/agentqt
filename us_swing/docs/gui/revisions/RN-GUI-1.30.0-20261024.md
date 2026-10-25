# Revision Note — RN-GUI-1.30.0-20261024

**Version:** 1.30.0
**Date:** 2026-10-24
**Tool:** GUI
**Artifact:** FO-GUI-026 (Phase 2 of 3) / SRD-GUI-026.008–.010
**Type:** Feature

---

## Summary

Phase 2 adds two Inspector sections and a Send to Execution button on the Charts screen. Patterns Found lists the price action patterns (from the shared 51-pattern catalogue) that showed on the last 5 bars and marks them on the chart with arrows. Key Levels lists the three nearest swing highs and lows above and below the last close, and can draw them as dotted lines. Send to Execution in Trade Plan adds the symbol as a manual pick and opens the Execution screen; if the pick is refused (for example it is already there) the reason is shown and the screen stays on Charts.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-026.005.M03 | `us_swing/src/us_swing/gui/chart_inspector.py` | `pattern_hits`, `key_levels`, `PatternsSection`, `KeyLevelsSection`, Send to Execution button and message; Inspector passes on section signals by name |
| MD-GUI-011.001.M01 | `us_swing/src/us_swing/gui/chart_panel.py` | `set_markers`, `set_levels`; JS markers (`createSeriesMarkers`) and dotted level lines |
| MD-GUI-026.001.M01 | `us_swing/src/us_swing/gui/chart_workspace.py` | Wires markers, levels and Send to Execution; `execution_requested` signal |
| MD-GUI-019.002.M03 | `us_swing/src/us_swing/gui/main_window.py` | `execution_requested` switches to the Execution screen |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-026.008 | Patterns Found on the last 5 bars, marked on the chart | Implemented |
| SRD-GUI-026.009 | Key Levels: three nearest swing highs and lows, optional lines | Implemented |
| SRD-GUI-026.010 | Send to Execution adds a manual pick and switches screens | Implemented |

---

## Design Decisions

- Bars become arrays once and are sliced per offset: 11 ms for 500 bars, 18 ms for 2000 bars, so it stays on the GUI thread.
- Each pattern keeps only its newest hit; a pattern that raises is skipped and logged at debug level.
- A section exposes `markers_changed` / `levels_changed` / `send_requested` and the Inspector passes them on, so new sections need no Inspector change.
- Key levels use pivots with 3 bars each side over the last 120 bars.

---

## Issues Resolved

None

---

## Test Coverage

7 UT cases (UT-GUI-026.008.M03.T01–T02, .008.M01.T03, .009.M03.T01–T02, .010.M01.T01–T02) — all Pass. GUI suite 415 passed. Markers and level lines checked in a real web view: no console errors.
