# Traceability Matrix — Backtest Module (BKT)

**Document ID:** TRACE-BKT
**Version:** 1.0.0
**Project:** US Swing Trading System
**Last Updated:** 2026-10-29 (closed-bar PRICE and session dates; RN-BKT-1.5.0)

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-BKT-001 | SRD-BKT-001.001–.014 | DD-BKT-001.001.D01 | MD-BKT-001.001.M01, .004.M02, .005.M03, .006.M04, .009.M05 | UT-BKT-001.* (33 tests, Pass) | `backtest/store.py`, `backtest/settings.py`, `backtest/planner.py`, `backtest/downloader.py`, `backtest/schedule.py` | Implemented | RN-BKT-1.0.0-20261028, RN-BKT-1.1.0-20261029 |
| FO-BKT-002 | SRD-BKT-002.001–.019 | DD-BKT-002.001.D01, DD-BKT-002.010.D01 | MD-BKT-002.001.M01, .004.M02, .005.M03, .007.M04, .008.M05, .009.M06, .010.M07, .011.M08 | UT-BKT-002.001–.019 (36 tests, Pass) | `backtest/spec.py`, `backtest/universe.py`, `backtest/cache.py`, `backtest/results.py`, `backtest/service.py`, `backtest/cli.py`, `backtest/steps/stocks.py`, `core/backtest_bridge.py` | Implemented (Phase 0–1) | RN-BKT-1.2.0-20261029, RN-BKT-1.3.1-20261029 |
| FO-BKT-002 | SRD-BKT-002.020–.029 | DD-BKT-002.020.D01 | MD-BKT-002.020.M09, .021.M10, .026.M11 (+ .008.M05, .009.M06, .011.M08) | UT-BKT-002.020–.029 (17 tests, Pass) | `core/expr/__init__.py`, `core/expr/series.py`, `backtest/steps/signals.py`, `backtest/service.py`, `backtest/cli.py`, `core/backtest_bridge.py` | Implemented (Phase 2) | RN-BKT-1.3.0-20261029 |
| FO-BKT-002 | SRD-BKT-002.030–.039 | DD-BKT-002.030.D01 | MD-BKT-002.030.M12 (+ .007.M04, .008.M05, .009.M06) | UT-BKT-002.030–.039 (16 tests, Pass) | `backtest/steps/portfolio.py`, `backtest/results.py`, `backtest/service.py`, `backtest/cli.py` | Implemented (Phase 3) | RN-BKT-1.4.0-20261029 |
| FO-BKT-002 | SRD-BKT-002.050 | DD-BKT-002.020.D01 | MD-BKT-002.021.M10 | UT-BKT-002.050.M10.T01–T02 (2 tests, Pass) | `core/expr/series.py` | Implemented (replaces .023) | RN-BKT-1.5.0-20261029 |
| FO-BKT-002 | SRD-BKT-002.051 | DD-BKT-002.010.D01 | MD-BKT-002.010.M07, .008.M05, .030.M12 | UT-BKT-002.051.M07.T01, UT-BKT-002.051.M12.T01 (2 tests, Pass) | `backtest/steps/stocks.py`, `backtest/steps/portfolio.py`, `backtest/service.py` | Implemented | RN-BKT-1.5.0-20261029 |

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
| `backtest/results.py` | MD-BKT-002.007.M04 | SRD-BKT-002.007, .039 | FO-BKT-002 |
| `backtest/service.py` | MD-BKT-002.008.M05 | SRD-BKT-002.008, .017 | FO-BKT-002 |
| `backtest/cli.py` | MD-BKT-002.009.M06 | SRD-BKT-002.009 | FO-BKT-002 |
| `backtest/steps/stocks.py` | MD-BKT-002.010.M07 | SRD-BKT-002.010–.016, .018, .019 | FO-BKT-002 |
| `core/backtest_bridge.py` | MD-BKT-002.011.M08 | SRD-BKT-002.011, .029 | FO-BKT-002 |
| `core/expr/__init__.py` | MD-BKT-002.020.M09 | SRD-BKT-002.020 | FO-BKT-002 |
| `core/expr/series.py` | MD-BKT-002.021.M10 | SRD-BKT-002.021–.025, .027 | FO-BKT-002 |
| `backtest/steps/signals.py` | MD-BKT-002.026.M11 | SRD-BKT-002.026, .028 | FO-BKT-002 |
| `backtest/steps/portfolio.py` | MD-BKT-002.030.M12 | SRD-BKT-002.030–.038 | FO-BKT-002 |
