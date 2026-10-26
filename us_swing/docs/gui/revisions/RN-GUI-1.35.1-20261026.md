# Revision Note — RN-GUI-1.35.1-20261026

**Version:** 1.35.1
**Date:** 2026-10-26
**Tool:** GUI
**Artifact:** SRD-GUI-025.019 / ISS-GUI-0006
**Type:** Fix

---

## Summary

The watchlist now stays after the app is closed and opened again. It is saved per user in `~/.usswing/watchlist.json`.

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-025.019.M05 | `gui/watchlist_store.py` | New load and save functions |
| MD-GUI-004.001.M01 | `gui/app_service.py` | Load at start; save on add and remove |

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-025.019 | Watchlist saved per user and restored at start | Draft (user to approve) |

## Tests

UT-GUI-025.019.M05.T01–T06 in `tests/gui/test_watchlist_store.py`. GUI suite 479 passed.

## Known

The package version number was not changed. Old watchlists from before this fix cannot be recovered; they were never saved.
