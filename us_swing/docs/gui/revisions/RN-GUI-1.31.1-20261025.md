# Revision Note — RN-GUI-1.31.1-20261025

**Version:** 1.31.1
**Date:** 2026-10-25
**Tool:** GUI
**Artifact:** FO-GUI-026 / SRD-GUI-026.008, SRD-GUI-026.011
**Type:** Bugfix

---

## Summary

User reported the chart drawing tools "not working" (screenshot, 2026-10-25). Three faults:

1. The four tool buttons were blank: their text glyphs were clipped by the button padding at 32 px width.
2. A trend line or rectangle often never finished: the chart library's click event drops a second click that comes within 500 ms of the first (it waits for a double click), so a quick second point was lost.
3. Pattern arrows carried their full names on the chart, which piled up into unreadable text near the last bars.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-026.001.M01 | `us_swing/src/us_swing/gui/chart_workspace.py` | `tool_icon()` paints pointer, line, trend and rectangle icons; icons refresh with the theme |
| MD-GUI-011.001.M01 | `us_swing/src/us_swing/gui/chart_panel.py` | Drawing clicks read from `mousedown` / `mouseup` on the chart element; RSI pane clicks ignored by pane height |
| MD-GUI-026.005.M03 | `us_swing/src/us_swing/gui/chart_inspector.py` | Pattern markers have no text (name kept as marker `id`) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-026.011 | Drawing tools work at any click speed and show clear icons | Implemented |
| SRD-GUI-026.008 | Pattern markers stay readable | Implemented |

---

## Design Decisions

- A press that moves more than 5 px is a pan, not a point.
- The icon set has no line shapes, so the four tool icons are painted with `QPainter`.

---

## Issues Resolved

User report 2026-10-25 (drawing tools not working).

---

## Test Coverage

UT-GUI-026.008.M03.T01 updated (marker text empty). GUI suite 423 passed. Checked in a real window with the whole Charts workspace: tool button → two real mouse clicks 300 ms apart → trend line saved, tool back to Pointer; icons visible.
