# Revision Note — RN-GUI-2.9.1-20261126

**Version:** 2.9.1
**Date:** 2026-11-26
**Tool:** GUI (+ EXE tick feed)
**Artifact:** FO-GUI-012 / ISS-GUI-0024; FO-GUI-025 / SRD-GUI-025.012
**Type:** Bug fix

---

## Summary

Change and change % on Market Watch, Watchlist and the index strip now use the right previous close. The app takes the daily candle close of the prior trading day when candles are up to date, else IBKR's own previous close, else Yahoo. The old close no longer sticks when the app stays open overnight. The Market Watch tile now shows Symbol, LTP, Chg ($) and Chg % only; Volume and the ✕ column are removed, and a stock is removed with right-click Delete, the same menu as the Watchlist. The user reopened SRD-GUI-025.012 on 2026-11-26 and its text now names right-click Delete.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-008.001.M01 | `src/us_swing/execution/live_tick_worker.py` | `prev_close` signal with IBKR's previous-day close |
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | `_prev_close` source order; `_prior_session_day`; candles re-read per day |
| MD-GUI-002.001.M01 | `src/us_swing/gui/dashboard_panel.py` | Market Watch tile shows Symbol, LTP, Chg ($), Chg % only; ✕ column and Volume removed; right-click Delete (shared row menu) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-012.003 | Tick change % on Market Watch (fix conforms, text unchanged) | Implemented |
| SRD-GUI-025.012 | Reopened by user 2026-11-26, text updated to right-click Delete | Implemented |

---

## Design Decisions

None

---

## Issues Resolved

ISS-GUI-0024

---

## Test Coverage

- UT-GUI-012.003.M01.T09–T14: Pass.
- Tick and watchlist tests: 45 passed.
- UT-GUI-025.012.M01.T01–T03: Pass; dashboard, watchlist and tick tests 92 passed.
- App check: TODO T255.
