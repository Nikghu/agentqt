# Revision Note — RN-BKT-1.7.0-20261030

**Version:** 1.7.0
**Date:** 2026-10-30
**Tool:** BKT
**Artifact:** FO-BKT-001 / SRD-BKT-001.015, FO-BKT-002 / SRD-BKT-002.052
**Type:** Feature

---

## Summary

Screeners with the RS rule (for example Momentun_Price) could not run in backtest because SPY was never downloaded. User asked on 2026-10-30 to keep SPY for RS. The backtest download and the daily delta now also fetch SPY daily candles (no 3m). When an RS screener is picked and SPY is missing, the data check lists SPY as missing 1d and says to press Download, so the Download button works from the Backtest screen. Once SPY is saved, Step 1 already uses it (no engine change).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-001.005.M03 | `backtest/planner.py` | `plan(daily_only=...)`: extra symbols get 1d jobs only |
| MD-BKT-002.008.M05 | `backtest/service.py` | `estimate()` adds SPY to missing 1d for an RS screener |
| MD-BKT-002.007.M04 | `backtest/steps/stocks.py` | RS message now says to press Download |
| — | `gui/app_service.py` | Download plan passes `daily_only=(SPY,)` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-001.015 | Download and delta also fetch SPY daily candles | Implemented |
| SRD-BKT-002.052 | RS screener with no SPY: SPY counted missing; message asks to download | Implemented |

---

## Tests

4 new tests; backtest suite 170 passed. Real check: Momentun_Price shows "Its daily candles are not saved yet, so press Download first"; SPY in missing 1d; Run off until SPY is saved. Real TWS download of SPY not run here (needs TWS).
