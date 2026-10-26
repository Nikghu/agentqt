# Issue Report — ISS-GUI-0006

**Tool:** GUI (Dashboard → Watchlist)
**Severity:** Medium (the user's watchlist is lost on every restart)
**Status:** Resolved
**Date Opened:** 2026-10-26
**Date Resolved:** 2026-10-26
**Reporter:** User ("I close the tool and open again, the watchlist is empty")
**Resolution:** RN-GUI-1.35.1-20261026
**Related:** FO-GUI-025, SRD-GUI-025.012

---

## Symptom

Stocks added to the watchlist are gone after the app is closed and opened again.

## Root Cause

`AppService._watchlist` was only an in-memory list. `add_to_watchlist` and `remove_from_watchlist` never saved it, and nothing loaded it at start. `DatabaseManager.upsert_watchlist` and `fetch_watchlist` were never called; they are removed (dead code).

**SRD root cause: SRD gap.** No SRD asked for the watchlist to persist. New row SRD-GUI-025.019 (Draft, waiting for user approval).

## Fix

| File | Change |
|---|---|
| `gui/watchlist_store.py` | New. Per-user JSON file, atomic write (same pattern as manual picks) |
| `gui/app_service.py` | Load the saved watchlist at start; save on add and remove |

## Verification

`tests/gui/test_watchlist_store.py` — UT-GUI-025.019.M05.T01–T06. `tests/gui/`: 479 passed. ruff and mypy clean on the new files.
