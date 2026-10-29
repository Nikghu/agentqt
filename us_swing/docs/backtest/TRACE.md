# Traceability Matrix — Backtest Module (BKT)

**Document ID:** TRACE-BKT
**Version:** 1.0.0
**Project:** US Swing Trading System
**Last Updated:** 2026-10-29 (engine Phase 0 and 1; RN-BKT-1.2.0)

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-BKT-001 | SRD-BKT-001.001–.014 | DD-BKT-001.001.D01 | MD-BKT-001.001.M01, .004.M02, .005.M03, .006.M04, .009.M05 | UT-BKT-001.* (33 tests, Pass) | `backtest/store.py`, `backtest/settings.py`, `backtest/planner.py`, `backtest/downloader.py`, `backtest/schedule.py` | Implemented | RN-BKT-1.0.0-20261028, RN-BKT-1.1.0-20261029 |
| FO-BKT-002 | SRD-BKT-002.001–.017 | DD-BKT-002.001.D01, DD-BKT-002.010.D01 | MD-BKT-002.001.M01, .004.M02, .005.M03, .007.M04, .008.M05, .009.M06, .010.M07, .011.M08 | UT-BKT-002.* (32 tests, Pass) | `backtest/spec.py`, `backtest/universe.py`, `backtest/cache.py`, `backtest/results.py`, `backtest/service.py`, `backtest/cli.py`, `backtest/steps/stocks.py`, `core/backtest_bridge.py` | Implemented (Phase 0–1) | RN-BKT-1.2.0-20261029 |

## Reverse Traceability: Code → MD → SRD → FO

| Code File | MD ID | SRD IDs | FO ID |
|---|---|---|---|
| `backtest/store.py` | MD-BKT-001.001.M01 | SRD-BKT-001.001–.003, .010–.014 | FO-BKT-001 |
| `backtest/settings.py` | MD-BKT-001.004.M02 | SRD-BKT-001.004 | FO-BKT-001 |
| `backtest/planner.py` | MD-BKT-001.005.M03 | SRD-BKT-001.005, .008 | FO-BKT-001 |
| `backtest/downloader.py` | MD-BKT-001.006.M04 | SRD-BKT-001.006, .007 | FO-BKT-001 |
| `backtest/schedule.py` | MD-BKT-001.009.M05 | SRD-BKT-001.009 | FO-BKT-001 |
| `backtest/spec.py` | MD-BKT-002.001.M01 | SRD-BKT-002.001–.003 | FO-BKT-002 |
| `backtest/universe.py` | MD-BKT-002.004.M02 | SRD-BKT-002.004 | FO-BKT-002 |
| `backtest/cache.py` | MD-BKT-002.005.M03 | SRD-BKT-002.005, .006 | FO-BKT-002 |
| `backtest/results.py` | MD-BKT-002.007.M04 | SRD-BKT-002.007 | FO-BKT-002 |
| `backtest/service.py` | MD-BKT-002.008.M05 | SRD-BKT-002.008, .017 | FO-BKT-002 |
| `backtest/cli.py` | MD-BKT-002.009.M06 | SRD-BKT-002.009 | FO-BKT-002 |
| `backtest/steps/stocks.py` | MD-BKT-002.010.M07 | SRD-BKT-002.010–.016 | FO-BKT-002 |
| `core/backtest_bridge.py` | MD-BKT-002.011.M08 | SRD-BKT-002.011 | FO-BKT-002 |
