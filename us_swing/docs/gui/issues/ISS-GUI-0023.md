# Issue Report — ISS-GUI-0023

**Tool:** GUI
**Severity:** Low (layout and missing total)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-21
**Date Resolved:** 2026-11-21
**Resolution:** SRD-GUI-002.005 (Reopen) — row text updated
**Reporter:** User — "column size can't extend, can you fix this. also I am not able to see the total position based on quantity"

---

## Symptom

Trade History columns cannot be dragged wider. There is no total amount for each order.

## Root Cause

| Point | Detail |
|---|---|
| Stretch columns | `dashboard_panel.py::_resize_columns()` set every column after Qty to Stretch, and Qt does not let the user drag a Stretch column. |
| No total | `TradeHistoryModel` showed only the average price, not shares × price. |

## Fix

| File | Change |
|---|---|
| `gui/position_table_model.py` | New Value column after Avg Price = Filled × Avg Price; `—` when nothing filled |
| `gui/dashboard_panel.py` | `_size_hist_columns()` gives start widths, every column Interactive, last column (Mode) fills the rest |
| `tests/gui/test_dashboard_tiles.py` | UT-GUI-002.005.M01.T06–T07 |

## User step

Restart the app; drag any Trade History column edge; Value shows e.g. EW SELL 3 at $102.98 → $308.94 (T220).
