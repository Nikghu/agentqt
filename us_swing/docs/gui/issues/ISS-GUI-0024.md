# Issue Report — ISS-GUI-0024

**Tool:** GUI (+ EXE tick feed)
**Severity:** Medium (wrong change shown)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-26
**Date Resolved:** 2026-11-26
**Resolution:** Code fix; no SRD text change (no SRD names the previous close source)
**Reporter:** User — "why there is difference in CHG $ and % with IBKR Desktop?"

---

## Symptom

Market Watch showed AMD −10.55% while IBKR Desktop and our own Watchlist showed about −2.7%. Price was the same; the change was measured from an older close.

## Root Cause

| Point | Detail |
|---|---|
| One-time fetch | The previous close came from Yahoo, fetched only when IBKR connects, when a stock is added, or on the refresh button. |
| Overnight | With the app open across days the old close stayed, so the change covered two days. |
| Lists differ | Each list kept the close from its own last fetch, so Watchlist and Market Watch disagreed. |

## Fix

| File | Change |
|---|---|
| `execution/live_tick_worker.py` | New `prev_close` signal sends IBKR's previous-day close for each stock |
| `gui/app_service.py` | One source order for every quote list: daily candle in candles.db when it has the prior trading day, else IBKR close, else Yahoo; candles re-read once per new day and on connect, add or refresh |
| `tests/gui/test_app_service_tick.py` | UT-GUI-012.003.M01.T09–T14 |

## User step

Restart the app and connect IBKR. CHG $ and CHG % in Market Watch, Watchlist and the index strip should match IBKR Desktop (T255).
