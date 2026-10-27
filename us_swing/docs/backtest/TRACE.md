# Traceability Matrix — Backtest Module (BKT)

**Document ID:** TRACE-BKT
**Version:** 1.0.0
**Project:** US Swing Trading System
**Last Updated:** 2026-10-28 (FO-BKT-001 docs written; SRDs Draft)

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-BKT-001 | SRD-BKT-001.001–.011 | DD-BKT-001.001.D01 | MD-BKT-001.001.M01, .004.M02, .005.M03, .006.M04, .009.M05 | UT-BKT-001.* (27 tests) | `backtest/store.py`, `backtest/settings.py`, `backtest/planner.py`, `backtest/downloader.py`, `backtest/schedule.py` | Draft | — |

## Reverse Traceability: Code → MD → SRD → FO

| Code File | MD ID | SRD IDs | FO ID |
|---|---|---|---|
| `backtest/store.py` | MD-BKT-001.001.M01 | SRD-BKT-001.001–.003, .010, .011 | FO-BKT-001 |
| `backtest/settings.py` | MD-BKT-001.004.M02 | SRD-BKT-001.004 | FO-BKT-001 |
| `backtest/planner.py` | MD-BKT-001.005.M03 | SRD-BKT-001.005, .008 | FO-BKT-001 |
| `backtest/downloader.py` | MD-BKT-001.006.M04 | SRD-BKT-001.006, .007 | FO-BKT-001 |
| `backtest/schedule.py` | MD-BKT-001.009.M05 | SRD-BKT-001.009 | FO-BKT-001 |
