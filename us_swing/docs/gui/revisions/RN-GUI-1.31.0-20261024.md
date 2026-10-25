# Revision Note — RN-GUI-1.31.0-20261024

**Version:** 1.31.0
**Date:** 2026-10-24
**Tool:** GUI
**Artifact:** FO-GUI-026 (Phase 3 of 3) / SRD-GUI-026.011–.012
**Type:** Feature

---

## Summary

Phase 3 adds drawing tools to the Charts screen. A thin bar on the left of the chart has Pointer, Horizontal line, Trend line and Rectangle, plus Delete all. A horizontal line takes one click; a trend line or rectangle takes two, with a preview after the first click (Esc cancels it). Drawings are saved per user, symbol and timeframe in `candles.db` and come back when that chart is opened again, also after a restart. The free TradingView library has no drawing tools, so each drawing is our own series primitive.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-026.012.M04 | `us_swing/src/us_swing/gui/chart_drawings.py` | New: `chart_drawings` table, `Drawing`, `DrawingStore`, `ChartBridge` |
| MD-GUI-011.001.M01 | `us_swing/src/us_swing/gui/chart_panel.py` | `enable_drawing` (QWebChannel), `set_drawings`, `set_draw_tool`; JS drawing primitives, click and preview handling |
| MD-GUI-026.001.M01 | `us_swing/src/us_swing/gui/chart_workspace.py` | Drawing tool bar; save, load and delete all |
| — | `us_swing/src/us_swing/gui/app_service.py` | `get_drawing_store()` on the existing `candles.db` engine |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-026.011 | Horizontal line, trend line, rectangle and delete all, drawn with chart primitives | Implemented |
| SRD-GUI-026.012 | Drawings saved per symbol and timeframe in SQLite and redrawn on load | Implemented |

---

## Design Decisions

- Python owns the saved list; the page only reports a finished drawing through the bridge and redraws what Python sends.
- Drawings are kept per user as well as per symbol and timeframe.
- The store creates its own table on first use (same pattern as the equity snapshot store), on its own metadata to avoid the `us_swing.db` circular import.
- A save failure logs `[Charts] Could not save drawing: …` and keeps the drawing on screen for the session.

---

## Issues Resolved

None

---

## Test Coverage

8 UT cases (UT-GUI-026.011.M04.T05, .011.M01.T01–T02, .012.M01.T05, .012.M04.T01–T04) on a real in-memory SQLite engine — all Pass. GUI suite 423 passed. Real web view check: real mouse clicks drew a trend line that reached Python; all three kinds render; no console errors.
