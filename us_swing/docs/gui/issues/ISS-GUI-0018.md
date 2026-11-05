# Issue Report — ISS-GUI-0018

**Tool:** GUI
**Severity:** Medium (Update now re-downloads all 503 stocks for one stock behind)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-05
**Date Resolved:** 2026-11-05
**Resolution:** RN-GUI-1.59.3-20261105
**Reporter:** User — "when i click on start download its downloading for all … except the HLT all are already updated"

---

## Symptom

Candle data showed "1 day behind" (HLT only at 2026-11-03). Update now then downloaded all 503 stocks ("Updating 42 of 503").

## Root Cause

| Point | Detail |
|---|---|
| Start date | Since ISS-GUI-0014 (2026-11-03) the Update start date is the oldest last candle among index stocks, so one stock behind sets it for all |
| No per-stock pick | Delta mode still sent the whole index to the download |
| Failed list empty | ISS-GUI-0017 lists HLT as failed only when an Update run finishes; the long run never finished, so the status stayed "1 day behind" |

Before ISS-GUI-0014 the status used the newest candle in the table, so one stock behind was hidden — that is why it "worked before".

**SRD root cause:** SRD-GUI-006.020 set the start date but not which stocks to download. SRD-GUI-006.023 added.

## Fix

| File | Change |
|---|---|
| `gui/app_service.py` | `_stocks_behind()`, `AppService._candle_stocks_behind()`; delta mode downloads only those stocks |
| `tests/gui/test_app_service_candle_status.py` | UT-GUI-006.001.M01.T25–T27 |

## User step

Cancel the running download, restart the app, click Update now. Only HLT downloads; it then lands in the failed list and the status shows up to date.
