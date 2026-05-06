# Traceability Matrix — Execution & Risk Management (EXE)

**Document ID:** TRACE-EXE
**Version:** 1.2.0
**Project:** US Swing Trading System
**Last Updated:** 2026-05-06

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-EXE-001 | SRD-EXE-001.001–002, 005.004 | DD-EXE-001.001.D01 | MD-EXE-001.001.M01 | T01–T06, 005.004.T01–T03 | `execution/risk_manager.py` | Draft | Pending |
| FO-EXE-001 | SRD-EXE-001.003–006, 002.003, 004.005, 005.005 | DD-EXE-001.001.D02 | MD-EXE-001.001.M02 | T01–T07, 005.005.T01–T03 | `execution/execution_engine.py` | Draft | Pending |
| FO-EXE-002 | SRD-EXE-002.001–005, 005.001–003, 005.006 | DD-EXE-002.001.D01 | MD-EXE-002.001.M01 | T01–T05, 005.001.T01–T09 | `execution/position_tracker.py` | Draft | Pending |
| FO-EXE-003 | SRD-EXE-003.001–002 | DD-EXE-003.001.D01 | MD-EXE-003.001.M01 | T01–T05 | `execution/circuit_breaker.py` | Draft | Pending |
| FO-EXE-003 | SRD-EXE-003.003–006 | DD-EXE-003.001.D01 | MD-EXE-003.001.M02 | T01–T06 | `execution/emergency.py` | Draft | Pending |
| FO-EXE-004 | SRD-EXE-004.001–004 | DD-EXE-004.001.D01 | MD-EXE-004.001.M01 | T01–T07 | `execution/paper_engine.py` | Draft | Pending |
| FO-EXE-004 | SRD-EXE-004.005 | DD-EXE-004.001.D01 | MD-EXE-004.001.M02 | T01–T03 | `execution/execution_router.py` | Draft | Pending |
| FO-EXE-005 | SRD-EXE-005.001–003, 005.006 | DD-EXE-005.001.D01 | MD-EXE-002.001.M01 | 005.001.T01–T09 | `execution/position_tracker.py` | Draft | Pending |
| FO-EXE-006 | SRD-EXE-006.001–006 | DD-EXE-006.001.D01–D02 | MD-EXE-006.001.M01 | UT-EXE-006.001.M01.T01–T13 | `execution/intraday_candle_loader.py` | Implemented | RN-EXE-1.1.0-20260506 |

---

## Reverse Traceability

| Module | MD ID | Parent SRD | Parent FO |
|---|---|---|---|
| `execution/risk_manager.py` | MD-EXE-001.001.M01 | SRD-EXE-001.001–002, 005.004 | FO-EXE-001/005 |
| `execution/execution_engine.py` | MD-EXE-001.001.M02 | SRD-EXE-001.003–006, 002.003, 004.005, 005.005 | FO-EXE-001/002/004/005 |
| `execution/position_tracker.py` | MD-EXE-002.001.M01 | SRD-EXE-002.001–005, 005.001–003, 005.006 | FO-EXE-002/005 |
| `execution/circuit_breaker.py` | MD-EXE-003.001.M01 | SRD-EXE-003.001–002 | FO-EXE-003 |
| `execution/emergency.py` | MD-EXE-003.001.M02 | SRD-EXE-003.003–006 | FO-EXE-003 |
| `execution/paper_engine.py` | MD-EXE-004.001.M01 | SRD-EXE-004.001–004 | FO-EXE-004 |
| `execution/execution_router.py` | MD-EXE-004.001.M02 | SRD-EXE-004.005 | FO-EXE-004 |
| `execution/intraday_candle_loader.py` | MD-EXE-006.001.M01 | SRD-EXE-006.001–006 | FO-EXE-006 |

---

## Status Summary

| Artifact | Total Items | Draft | Approved | Implemented | Verified |
|---|---|---|---|---|---|
| FO | 6 | 5 | 1 | 0 | 0 |
| SRD | 34 | 28 | 6 | 0 | 0 |
| DD | 8 | 6 | 2 | 0 | 0 |
| MD | 8 | 7 | 1 | 0 | 0 |
| UTCD | 67 | 54 | 13 | 0 | 0 |
| Code | 8 files | — | — | 1 | 0 |
