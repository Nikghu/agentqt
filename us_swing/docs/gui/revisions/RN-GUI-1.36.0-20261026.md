# Revision Note — RN-GUI-1.36.0-20261026

**Version:** 1.36.0
**Date:** 2026-10-26
**Tool:** GUI
**Artifact:** FO-GUI-025 / SRD-GUI-025.020
**Type:** Feature

---

## Summary

The Dashboard Market Watch tile now has its own saved list, separate from the watchlist. It accepts any stock and starts empty. The watchlist (right panel) stays S&P 500 only and still feeds the Charts list and Screener "Add to Watchlist".

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-025.019.M05 | `gui/watchlist_store.py` | One file per list: `watchlist.json`, `market_watch.json` |
| MD-GUI-004.001.M01 | `gui/app_service.py` | Market Watch tile list: load, save, add, remove, quotes, `market_list_updated`; ticks update both lists; tile stocks subscribed with no S&P 500 gate; quote fetches (both lists) stay alive until they finish |
| MD-GUI-025.001.M02 | `gui/dashboard_panel.py` | `_WatchlistTab(market_watch=True)` for the tile; no S&P 500 check there |

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-025.020 | Market Watch tile keeps its own saved list per user | Implemented (approved by user 2026-10-26) |

## Tests

UT-GUI-025.020.* (9 cases) in `tests/gui/test_watchlist_store.py` and `test_dashboard_tiles.py`. UT-GUI-025.012.M01.T01–T03 now use the tile list. GUI suite 489 passed.

## Known

SRD-GUI-025.007 and .012 (Implemented) still say the tile shows "the user's watchlist"; SRD-GUI-025.020 supersedes that wording. Title-bar index ETFs are unchanged. Tile and watchlist ticks are not trimmed by the 95-subscription cap (only positions are); a long tile list can go over it.
