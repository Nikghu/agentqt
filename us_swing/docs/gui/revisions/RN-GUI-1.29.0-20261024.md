# Revision Note — RN-GUI-1.29.0-20261024

**Version:** 1.29.0
**Date:** 2026-10-24
**Tool:** GUI
**Artifact:** FO-GUI-026 (Phase 1 of 3) / SRD-GUI-026.001–.007
**Type:** Feature

---

## Summary

The Charts screen is now one large chart between a symbol source list and a collapsible Inspector (canvas Option 3, "Focus + Inspector"). It replaces the multi-window layout of FO-GUI-020. The source list has Watchlist, Screener and Trades tabs with a filter. The chart header shows price, change, 1D / 1W and SMA / EMA overlay chips. The chart has an RSI 14 pane and draws entry, stop and target lines with shaded zones. The Inspector has Trade Plan and Indicators sections; a new chart feature is one more section class in the registry.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-026.001.M01 | `us_swing/src/us_swing/gui/chart_workspace.py` | Rewritten: three cards, header, overlays, plan source, remembered settings; MDI removed |
| MD-GUI-026.002.M02 | `us_swing/src/us_swing/gui/chart_source_list.py` | New: Watchlist / Screener / Trades tabs, filter, rows |
| MD-GUI-026.005.M03 | `us_swing/src/us_swing/gui/chart_inspector.py` | New: section registry, Trade Plan (with Edit), Indicators, plan and indicator maths |
| MD-GUI-011.001.M01 | `us_swing/src/us_swing/gui/chart_panel.py` | `study_points`, `candles`, `set_overlays`, `set_plan`, `set_rsi_pane`; JS `applyStudies` |
| — | `us_swing/src/us_swing/data/models.py`, `us_swing/src/us_swing/gui/app_service.py` | `FilteredStockEntry` carries the saved AI plan (`plan_entry`, `plan_stop`, `plan_target`) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-026.001 | Source list, chart and Inspector cards; MDI removed | Implemented |
| SRD-GUI-026.002 | Watchlist / Screener / Trades tabs with filter | Implemented |
| SRD-GUI-026.003 | Chart header with price, change, 1D / 1W and overlay chips | Implemented |
| SRD-GUI-026.004 | Volume, RSI pane, plan lines and shaded zones | Implemented |
| SRD-GUI-026.005 | Inspector sections from one registry; open state remembered | Implemented |
| SRD-GUI-026.006 | Trade Plan with R:R, size at user risk and Edit | Implemented |
| SRD-GUI-026.007 | Indicators: RSI, ATR, ADX, relative volume | Implemented |

---

## Design Decisions

- Overlay and RSI values are computed in Python with TA-Lib (same as the screener rules), so the chart and the Inspector use one calculation.
- Studies are pushed with `runJavaScript` and sent again on `loadFinished`, so a change made while the page loads is not lost.
- Only a long-shaped plan (stop < entry < target) is drawn; any other plan clears the lines.
- Edited plans last for the session only.
- Timeframes are 1D and 1W, as the chart database holds daily and weekly bars.

---

## Issues Resolved

None

---

## Test Coverage

25 UT cases in `tests/gui/test_chart_workspace.py`, `test_chart_source_list.py` and `test_chart_inspector.py` — all Pass. GUI suite 407 passed. The JS was checked in a real web view: no console errors, plan lines, zones, overlays and RSI pane drawn. UT-GUI-020.001–.003 are Superseded (MDI removed).
