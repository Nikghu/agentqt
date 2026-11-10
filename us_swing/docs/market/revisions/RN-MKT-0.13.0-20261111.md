# Revision Note — RN-MKT-0.13.0-20261111

**Version:** 0.13.0
**Date:** 2026-11-11
**Tool:** MKT
**Artifact:** FO-MKT-001, FO-MKT-005 / SRD-MKT-001.013–.017, SRD-MKT-005.015–.016
**Type:** Feature

---

## Summary

The morning run now starts with a "Candle check". It finds stocks whose daily bars are behind and fills only the missing days from Yahoo Finance into a desk-only copy. The main `candles.db` is never written. If SPY or more than 2% of stocks are still behind, the run stops before any AI call. The lead brief is now the morning brief and goes to the AI feed as kind `morning`.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-001.013.M06 | `src/us_swing/market/candle_check.py` | New desk step "Candle check" with Yahoo desk-only top-up and stop rule |
| MD-MKT-001.001.M01 | `src/us_swing/market/candles.py` | Adds desk-copy bars only for days `candles.db` lacks; `last_days` |
| MD-MKT-001.007.M04 | `src/us_swing/market/store.py` | Adds `candle_topup` table, trim of old copy rows, and drop of unsettled bars |
| MD-MKT-005.014.M08 | `src/us_swing/market/lead_brief.py` | Morning brief (max 1,200 characters); feed kind `morning` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-001.013 | Desk step "Candle check" runs first and finds SPY and members behind | Implemented |
| SRD-MKT-001.014 | Stocks behind get missing daily bars from Yahoo, kept in `candle_topup` in `desk.db` | Implemented |
| SRD-MKT-001.015 | Candle reader adds desk-copy bars only for days `candles.db` does not have | Implemented |
| SRD-MKT-001.016 | Run stops before any AI call when SPY or more than 2% of members are still behind | Implemented |
| SRD-MKT-001.017 | Check logs stocks behind, filled from Yahoo, and still behind | Implemented |
| SRD-MKT-005.015 | Lead answer: up to 5 picks per side and a morning brief of at most 1,200 characters | Implemented |
| SRD-MKT-005.016 | Picks kept in `lead_picks` per data day; morning brief goes to the AI feed as kind `morning` | Implemented |

---

## Design Decisions

- Yahoo data is a desk-only copy. `candles.db` (IBKR) is never changed and prices are not dividend-adjusted, as IBKR.
- Bars fetched before 16:30 ET of their own day are not final, so they are fetched again on the next check.
- Stop rule: SPY behind, or more than 2% of members behind, stops the run before any AI call.

---

## Issues Resolved

None

---

## Test Coverage

Candle check and reader cases: UT-MKT-001.013–.017 (15 cases, Pass). Morning brief and feed cases: UT-MKT-005.016.M08.T01, UT-MKT-005.018.M09.T03, UT-MKT-007.001.M02.T01 (Pass). Full suite: 2624 passed, 12 failed; the same 12 fail on the clean branch base (TODO T112).
