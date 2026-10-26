# Revision Note — RN-GUI-1.37.0-20261026

**Version:** 1.37.0
**Date:** 2026-10-26
**Tool:** GUI
**Artifact:** FO-GUI-026 / SRD-GUI-026.013
**Type:** Feature

---

## Summary

When the Charts screen opens, it now shows a stock by default: the first stock of the first non-empty tab in the order Trades, Screener, Watchlist. The empty chart shows only when all three are empty. Once the user picks a tab or stock, or another screen opens a stock, the default pick stops for the session. The last-used tab is no longer remembered.

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-026.002.M02 | `gui/chart_source_list.py` | `pick_default()`, `user_chose`; remembered tab and `settings` argument removed |
| MD-GUI-026.001.M01 | `gui/chart_workspace.py` | Auto-open on show (deferred one event-loop turn) and when trades, screener or watchlist data arrives late; list is rebuilt only when the picked tab changes |

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-026.013 | Charts opens on a default stock, Trades → Screener → Watchlist | Implemented (approved by user 2026-10-26) |

## Tests

UT-GUI-026.013.* (8 cases) in `tests/gui/test_chart_source_list.py` and `test_chart_workspace.py`; UT-GUI-026.002.M02.T02 changed to "tab not remembered". GUI suite 499 passed.

## Known

SRD-GUI-026.002 (Implemented) still says "Tab remembered"; SRD-GUI-026.013 supersedes it.
