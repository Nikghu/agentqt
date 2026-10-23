# Revision Note — RN-GUI-1.12.0-20261023

**Version:** 1.12.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-020 / SRD-GUI-020.001–.005
**Type:** Feature

---

## Summary

Phase 4, the last phase of the Carbon workspace. The Chart screen is now "Charts", a `ChartWorkspace` MDI area holding up to six compact chart windows with Tile, Cascade and Tabs modes. The Screener's separate Quick Chart Viewer is removed; its chart button and Position Details "Open in Chart" both open the Charts screen.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-020.001.M01 | `us_swing/src/us_swing/gui/chart_workspace.py` (new) | MDI chart windows, arrange modes, open path, theme refresh |
| MD-GUI-011.001.M01 | `us_swing/src/us_swing/gui/chart_panel.py` | `chart_loaded` signal, `show_symbol()`, `set_compact()` |
| MD-GUI-003.001.M01 | `us_swing/src/us_swing/gui/screener_panel.py` | Quick Chart Viewer removed; chart button emits `chart_requested` |
| MD-GUI-019.002.M03 | `us_swing/src/us_swing/gui/main_window.py` | Charts screen uses `ChartWorkspace`; chart requests routed to it |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-020.001 | Charts screen is a `QMdiArea` of up to six chart windows | Implemented |
| SRD-GUI-020.002 | Tile, Cascade and Tabs modes; one checked at a time | Implemented |
| SRD-GUI-020.003 | `open_symbol()` focuses, fills an empty window, opens a new one, or reuses the active one | Implemented |
| SRD-GUI-020.004 | Open in Chart and Screener chart button switch to Charts; Quick Chart Viewer removed | Implemented |
| SRD-GUI-020.005 | A theme change refreshes every open chart | Implemented |

---

## Design Decisions

- The Quick Chart Viewer window is removed, not kept. The Charts screen is the one place for charts.
- Charts open in compact toolbar mode. Sub-windows use Fusion-styled frames in theme colours.

---

## Issues Resolved

None

---

## Test Coverage

6 new tests (UT-GUI-020.*) in `tests/gui/test_chart_workspace.py`, all Pass. GUI suite: 291 passed.
