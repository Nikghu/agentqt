# Issue Report — ISS-GUI-0007

**Tool:** GUI (right-panel Watchlist)
**Severity:** Medium (saved watchlist looks lost after a restart)
**Status:** Resolved
**Date Opened:** 2026-10-26
**Date Resolved:** 2026-10-26
**Reporter:** User (screenshot: Charts list shows AAPL, NVDA; right panel says "Watchlist is empty")
**Resolution:** RN-GUI-1.35.2-20261026
**Related:** ISS-GUI-0006, SRD-GUI-025.019

---

## Symptom

After a restart the Charts source list shows the saved watchlist, but the right-panel watchlist is empty.

## Root Cause

`_WatchlistTab.__init__` drew only the empty state and waited for `watchlist_updated`. That signal fires on add, remove or a price update (feed connected). The saved list loads before the widget exists and sends no signal, so the right panel stayed empty. The Market Watch tile worked only because the dashboard called `reload()` on it.

**SRD root cause: code diverged — SRD-GUI-025.019** (watchlist restored at start). No SRD change.

## Fix

| File | Change |
|---|---|
| `gui/dashboard_panel.py` | `_WatchlistTab.__init__` loads the current list once when built |

## Verification

`tests/gui/test_dashboard_tiles.py` — UT-GUI-025.019.M02.T01 (failed before the fix, passes after).
