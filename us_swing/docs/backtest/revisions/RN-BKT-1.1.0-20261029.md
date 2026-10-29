# Revision Note — RN-BKT-1.1.0-20261029

**Version:** 1.1.0
**Date:** 2026-10-29
**Tool:** BKT
**Artifact:** FO-BKT-001 / SRD-BKT-001.012–.014
**Type:** Feature

---

## Summary

The backtest store now keeps 15m and 1w candles as well, built from the saved 3m and 1d candles. Every 3m save rebuilds that year's 15m file, and every 1d save rebuilds the stock's 1w file. Data saved before this change is built once in the background at app start. Nothing more is downloaded from TWS. Requested by the user so the backtest engine (Engine_plan.md) can read all 4 strategy timeframes from the store.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-001.001.M01 | `backtest/store.py` | 15m/1w build on save, `build_missing()`, `StoredTf` for read/coverage, unique temp names, clear and size include built files |
| MD-GUI-030.004.M02 | `gui/app_service.py` | Stats worker calls `build_missing()` first (see RN-GUI-1.38.1-20261029) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-001.012 | 15m from 5 × 3m bars, from 09:30 ET, rebuilt on each 3m save | Implemented |
| SRD-BKT-001.013 | 1w Monday–Friday, dated by Monday, with day count, rebuilt on each 1d save | Implemented |
| SRD-BKT-001.014 | Missing or stale 15m/1w built at app start | Implemented |

---

## Tests

- 6 new tests (UT-BKT-001.012–.014); UT-BKT-001.010.M01.T01 also checks that Clear removes `15m/` and `1w/`.
- `pytest tests/backtest` + backtest GUI tests: 57 passed. `ruff` and `mypy --strict` clean on `store.py`.
- Real data (copy of AAPL, 1 year): 26 15m bars on 244 days and 14 on the 2 half-days; 52 weeks; 0.12 s per stock.

---

## Notes

- The first app start after this change builds files for all saved stocks (about 1 minute for 500 stocks), then only changed files.
- An unfinished week is kept with `days` < 5. The engine must not use it before that day's close.
