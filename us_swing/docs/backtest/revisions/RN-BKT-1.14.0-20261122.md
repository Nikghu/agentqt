# Revision Note — RN-BKT-1.14.0-20261122

**Version:** 1.14.0
**Date:** 2026-11-22
**Tool:** BKT (+ GUI, see RN-GUI-2.8.0-20261122)
**Artifact:** FO-BKT-001 / SRD-BKT-001.001, SRD-BKT-001.005
**Type:** Bugfix (ISS-BKT-0003, planner and store parts)

---

## Summary

On IBKR Error 162, empty 3m answers saved fake floors for 224 stocks, so those missing days were never asked again. The store now finds 3m gap days inside the range, and the planner asks for them again as short jobs. A `gaps.json` cache keeps the Universe fast to read. A real store check found 492 of 504 stocks missed some 3m days (for example 2024-01-05).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-001.001.M01 | `src/us_swing/backtest/store.py` | `gap_days()`, `refresh_gaps()`, `cached_gaps()` with `gaps.json` cache; `clear()` removes it; `BacktestStats.partial_stocks` added |
| MD-BKT-001.005.M03 | `src/us_swing/backtest/planner.py` | Gap days on or after the range start become short jobs ("1 D", "2 D"…), joined when next to each other; delta runs skip them |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-001.001 | 1d and 3m candles stored as Parquet files; gap days and partial count added | Implemented |
| SRD-BKT-001.005 | Download plan finishes one stock before the next; gap days asked again | Implemented |

SRD rows are not edited (status Implemented). The gap-day behaviour goes beyond the SRD-BKT-001.005 wording "skipping ranges already saved".

---

## Design Decisions

- A gap day is a 3m day that the stock's 1d data has, on or after the range start, and that the 3m store lacks.
- Full downloads ask for gap days again. Delta runs skip them.
- SRD-BKT-001.005 is not reopened by the agent. The user decides whether to Reopen it.

---

## Issues Resolved

- ISS-BKT-0003 (planner and store parts). GUI part in RN-GUI-2.8.0-20261122. App check open (TODO T223).

---

## Test Coverage

- New: UT-BKT-001.001.M01.T03–T04; UT-BKT-001.005.M03.T06.
- Status per `docs/backtest/UTCD.md` (Pass).
- Real store check (no TWS): 492 of 504 stocks missed 3m days; 2024-01-05 is missing for 263 stocks.
