# Revision Note — RN-GUI-1.35.2-20261026

**Version:** 1.35.2
**Date:** 2026-10-26
**Tool:** GUI
**Artifact:** SRD-GUI-025.019 / ISS-GUI-0007
**Type:** Fix

---

## Summary

The right-panel watchlist now shows the saved stocks as soon as the app opens, without waiting for the feed.

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-025.001.M02 | `gui/dashboard_panel.py` | `_WatchlistTab` loads its list once when built |

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-025.019 | Watchlist saved per user and restored at start | Implemented |

## Tests

UT-GUI-025.019.M02.T01 in `tests/gui/test_dashboard_tiles.py`.
