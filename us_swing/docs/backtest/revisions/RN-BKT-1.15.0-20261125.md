# Revision Note — RN-BKT-1.15.0-20261125

**Version:** 1.15.0
**Date:** 2026-11-25
**Tool:** BKT
**Artifact:** FO-BKT-001 / SRD-BKT-001.018
**Type:** Enhancement

---

## Summary

Backtest Data Download and Delta now also fetch daily candles for RSP and the 11 sector ETFs (XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, XLRE, XLC), the same way as SPY. All daily-only symbols (SPY included) start 100 days before the start date, so a 3-month sector ranking has history from the first backtest day. This is the data step for the later leading-sector backtest option.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-001.005.M03 | `src/us_swing/backtest/planner.py` | `DAILY_ONLY_LEAD` (100 days); daily-only symbols start that much earlier |
| — | `src/us_swing/gui/app_service.py` | `_backtest_plan` passes SPY plus `SECTOR_SYMBOLS` as daily-only |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-001.018 | RSP and sector ETF daily candles, 100 days before start (approved by user 2026-11-25, chat) | Implemented |

---

## Design Decisions

- Daily only, no 3m: sector ranking uses daily closes.
- SPY gets the same early start (user choice); simplest, harmless extra history.
- Symbols already saved from the old start backfill the extra 100 days on the next Download; Delta only goes forward.
- Backtest Data stock count rises by 12 (the new ETF files).

---

## Issues Resolved

None

---

## Test Coverage

- UT-BKT-001.018.M03.T01–T02 (new), UT-BKT-001.015.M03.T02 (input moved earlier): Pass.
- Backtest tests: 176 passed.
- App check: Download with TWS running; 12 new files in `~/.usswing/backtest/1d/` (TODO T252).
