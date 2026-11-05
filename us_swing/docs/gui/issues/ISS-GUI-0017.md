# Issue Report — ISS-GUI-0017

**Tool:** GUI
**Severity:** Low (status looked wrong; one stock 1 day short)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-05
**Date Resolved:** 2026-11-05
**Resolution:** RN-GUI-1.59.2-20261105
**Reporter:** User — "why we are seeing 1 day behind i already download it"

---

## Symptom

Settings → Candle data showed "1 trading day behind" (Data to 2026-11-03, last trading day 2026-11-04) after a full update, and again after reopening the app.

## Root Cause

| Point | Detail |
|---|---|
| One stock short | 502 index stocks had 2026-11-04; HLT stopped at 2026-11-03 |
| IBKR gap | IBKR returns HLT daily bars only up to 2026-11-03 (checked live, read-only); AAPL in the same request has 2026-11-04; Yahoo has HLT 2026-11-04 (close 376.53) |
| Silent | The download saved the bars it got and reported no failure, so HLT never reached the failed list that the status check leaves out (SRD-GUI-006.020) |

**SRD root cause:** no requirement covered IBKR bars that stop early. SRD-GUI-006.022 added (approved by user in chat, Implemented).

## Fix

| File | Change |
|---|---|
| `gui/app_service.py` | `_missing_last_day()`; the download lists such a stock as failed, keeping its bars |
| `tests/gui/test_app_service_weekly_candles.py` | UT-GUI-006.001.M01.T24 |

## User step

Run Update now once. HLT then shows in the failed list with "IBKR has no bar for 2026-11-04" and the status shows up to date. Retry Failed asks IBKR again later.
