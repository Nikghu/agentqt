# Revision Note — RN-GUI-1.59.2-20261105

**Tool:** GUI
**Version:** 1.59.2
**Date:** 2026-11-05
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Candle data no longer stuck "behind" by one IBKR gap (ISS-GUI-0017)

---

## Summary

IBKR has no 2026-11-04 daily bar for HLT, so the oldest-last-candle check kept the whole candle database "1 day behind" after every update. The download now lists a stock whose IBKR daily bars end before the last trading day as failed ("IBKR has no bar for <day>"), keeping the bars it did get. The failed list is already left out of the status check, so the status shows up to date and Retry Failed asks IBKR again. User picked this over filling the gap from Yahoo.

## Changes

| File | Change |
|---|---|
| `gui/app_service.py` | `_missing_last_day()`; early-ending stock emitted as failed |
| `tests/gui/test_app_service_weekly_candles.py` | UT-GUI-006.001.M01.T24 |

## Requirements

SRD-GUI-006.022 added, approved by user 2026-11-05 in chat → Implemented.

## Verification

- Candle download and status tests pass (11); ruff and mypy show no new errors in `app_service.py`.
- Live, read-only: IBKR HLT daily bars end 2026-11-03; AAPL has 2026-11-04.
- Full test run not done (user asked to run tests later).
