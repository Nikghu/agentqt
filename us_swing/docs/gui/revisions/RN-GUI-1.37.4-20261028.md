# Revision Note — RN-GUI-1.37.4-20261028

**Version:** 1.37.4
**Date:** 2026-10-28
**Tool:** GUI
**Artifact:** FO-GUI-026 / SRD-GUI-026.004
**Type:** Bugfix

---

## Summary

The Charts page no longer logs `Invalid pane index` when a chart with the RSI pane loads. Only the latest study update sets the volume and RSI pane heights.

---

## Modified Files

| File | Change |
|---|---|
| `us_swing/src/us_swing/gui/chart_panel.py` | Pane sizing skips frames from older study updates and reads panes fresh |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-026.004 | RSI pane under the price pane (no requirement change) | Implemented |

---

## Issues Resolved

ISS-GUI-0011 — `Invalid pane index` errors while charts load.

---

## Test Coverage

No new UT case (chart page JS has no test harness). 58 existing chart tests pass; user check in the app pending.
