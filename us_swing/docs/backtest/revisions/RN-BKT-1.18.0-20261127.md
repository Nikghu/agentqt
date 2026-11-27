# Revision Note — RN-BKT-1.18.0-20261127

**Version:** 1.18.0
**Date:** 2026-11-27
**Tool:** BKT
**Artifact:** FO-BKT-002 / SRD-BKT-002.092–.097
**Type:** Feature

---

## Summary

S&P 500 and sector runs now skip entries before a stock's Added date. A new Leading sectors option trades longs only in the strongest sectors and shorts only in the weakest, against RSP. The equal-weight benchmark now uses the same Added-date rule, and the report adds Same stocks return, Same stocks worst drop and Edge.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-BKT-002.030.M12 | `us_swing/src/us_swing/backtest/steps/portfolio.py` | Skips entries before Added date (not_in_index_yet); sector skips (sector_not_leading, sector_not_weak) |
| MD-BKT-002.008.M05 | `us_swing/src/us_swing/backtest/service.py` | `_added_dates`, `_sector_errors`, `_sector_inputs`; passes Added dates to reports |
| MD-BKT-002.001.M01 | `us_swing/src/us_swing/backtest/spec.py` | SectorFilterSpec: on/off, Top N, range, Must beat RSP |
| MD-BKT-002.093.M16 | `us_swing/src/us_swing/backtest/steps/sectors.py` (new) | `sector_gates`, `missing_symbols` |
| MD-BKT-002.040.M13 | `us_swing/src/us_swing/backtest/steps/report.py` | `equal_weight_benchmark(..., added)`; `benchmark_stats` adds Same stocks return, Same stocks worst drop, Edge |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-BKT-002.092 | Entries on a day before a stock's Added date are skipped (not_in_index_yet) | Implemented |
| SRD-BKT-002.093 | Leading sectors: longs only in top N sectors vs RSP; shorts only in bottom N | Implemented |
| SRD-BKT-002.094 | Plan holds Leading sectors setting: on/off, Top N, range, Must beat RSP | Implemented |
| SRD-BKT-002.095 | Estimate and Run refuse when RSP or a sector ETF has no saved data; names missing symbols | Implemented |
| SRD-BKT-002.096 | Equal-weight benchmark counts a stock only from its Added date | Implemented |
| SRD-BKT-002.097 | Report adds Same stocks return, Same stocks worst drop, Edge | Implemented |

---

## Design Decisions

- Added-date rule is always on for S&P 500 and sector runs; typed-names runs are not filtered; saved runs are unchanged. See DD-BKT-002.092 entry.
- Leading sectors is off by default (Top 3, 1M, Must beat RSP). Ranking uses the previous day's closes; open trades are kept. See DD-BKT-002.093.D01.
- Benchmark uses the same Added-date rule. Edge = strategy return minus Same stocks return. See DD-BKT-002.096.D01.

---

## Issues Resolved

None

---

## Test Coverage

- New, Pass (15 tests): UT-BKT-002.092.M12.T01–T02, .092.M05.T01; UT-BKT-002.093.M12.T01–T03, .093.M16.T01–T03, .094.M01.T01, .095.M16.T01, .095.M05.T01; UT-BKT-002.096.M13.T01, .097.M13.T01–T02.

---

## Open items

- Findings: S&P 500 2021–2026 run +20.6% with filter off vs +84.5% with Leading sectors on. Same-stocks benchmark +91.3%. Saved run 4bf5075a Edge −1.3%.
- User checks T269, T270 (TODO.md).
