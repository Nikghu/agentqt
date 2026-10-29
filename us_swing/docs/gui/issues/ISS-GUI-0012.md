# Issue Report — ISS-GUI-0012

**Tool:** GUI
**Severity:** Medium (app shows "Not responding" for 2–3 s, again and again)
**Status:** Resolved
**Date Opened:** 2026-10-29
**Date Resolved:** 2026-10-29
**Reporter:** User (Backtest screen, no TWS connection)
**Resolution:** RN-GUI-1.42.1-20261029

---

## Problem

With no TWS connection, the app froze for 2–3 seconds every few minutes, on any screen.

## Cause

Found with `py-spy record` on the running app: 706 of 850 busy main-thread samples were in the
watchlist last-price refresh. Each "candle closed" signal made `get_latest_close` rebuild 30 days
of 3m bars from 1m rows (about 287 ms per stock) on the GUI thread, just to read one close.
Many stocks close a candle at the same time, so the calls added up to 2–3 s.

## Fix

`get_latest_close` now reads only the newest stored 1m or 3m row (`load_latest_close`):
1.7 ms per stock on the real database, same prices for the 10 stocks checked.

| File | Change |
|---|---|
| `execution/intraday_candle_loader.py` | New `load_latest_close()` |
| `gui/app_service.py` | `get_latest_close()` uses it |

## Tests

UT-EXE-006.001.M01.T24–T25 (newest bar wins; no bars gives None).
