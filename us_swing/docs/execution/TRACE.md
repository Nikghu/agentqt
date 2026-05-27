# Traceability Matrix — Execution & Risk Management (EXE)

**Document ID:** TRACE-EXE
**Version:** 1.7.0
**Project:** US Swing Trading System
**Last Updated:** 2026-05-27

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-EXE-001 | SRD-EXE-001.001–002, 005.004 | DD-EXE-001.001.D01 | MD-EXE-001.001.M01 | T01–T06, 005.004.T01–T03 | `execution/risk_manager.py` | Implemented | RN-EXE-1.7.0-20260526 |
| FO-EXE-001 | SRD-EXE-001.003–006, 002.003, 004.005, 005.005 | DD-EXE-001.001.D02 | MD-EXE-001.001.M02 | T01–T07, 005.005.T01–T03 | `execution/execution_engine.py` | Implemented | RN-EXE-1.7.0-20260526 |
| FO-EXE-002 | SRD-EXE-002.001–005, 005.001–003, 005.006 | DD-EXE-002.001.D01 | MD-EXE-002.001.M01 | T01–T05, 005.001.T01–T09 | `execution/position_tracker.py` | Implemented | RN-EXE-1.7.0-20260526 |
| FO-EXE-003 | SRD-EXE-003.001–002 | DD-EXE-003.001.D01 | MD-EXE-003.001.M01 | T01–T05 | `execution/circuit_breaker.py` | Draft | Pending |
| FO-EXE-003 | SRD-EXE-003.003–006 | DD-EXE-003.001.D01 | MD-EXE-003.001.M02 | T01–T06 | `execution/emergency.py` | Draft | Pending |
| FO-EXE-004 | SRD-EXE-004.001–004 | DD-EXE-004.001.D01 | MD-EXE-004.001.M01 | T01–T07 | `execution/paper_engine.py` | Implemented | RN-EXE-1.7.0-20260526 |
| FO-EXE-004 | SRD-EXE-004.005 | DD-EXE-004.001.D01 | MD-EXE-004.001.M02 | T01–T03 | `execution/execution_router.py` | Implemented | RN-EXE-1.7.0-20260526 |
| FO-EXE-005 | SRD-EXE-005.001–003, 005.006 | DD-EXE-005.001.D01 | MD-EXE-002.001.M01 | 005.001.T01–T09 | `execution/position_tracker.py` | Implemented | RN-EXE-1.7.0-20260526 |
| FO-EXE-006 | SRD-EXE-006.001–006 | DD-EXE-006.001.D01–D02 | MD-EXE-006.001.M01 | UT-EXE-006.001.M01.T01–T13 | `execution/intraday_candle_loader.py` | Implemented | RN-EXE-1.1.0-20260506 |
| FO-EXE-008 | SRD-EXE-008.001–006 | DD-EXE-008.001.D01 | MD-EXE-008.001.M01 | UT-EXE-008.001.M01.T01–T16 | `execution/live_tick_worker.py` | Implemented | RN-EXE-1.3.1-20260519 |
| FO-EXE-009 | SRD-EXE-009.001–012 | DD-EXE-009.001.D01–D02, 009.002.D01–D02, 009.003.D01 | MD-EXE-009.001.M01–M03, 009.002.M01–M03 | UT-EXE-009.001.M01.T01–T04, 009.001.M02.T01–T03, 009.001.M03.T01–T06, 009.002.M01.T01–T14, 009.002.M02.T01–T21, 009.002.M03.T01–T04; IT-EXE-009.001–005 | `core/monitoring_session/{_dto,_enums,_protocols,_events,_repository,_service}.py`, `core/monitoring_session/__init__.py` | Implemented | RN-EXE-1.3.0-20260518 |
| FO-EXE-010 | SRD-EXE-010.001–006 | DD-EXE-010.001.D01, 010.002.D01, 010.003.D01 | MD-EXE-010.001.M01 | UT-EXE-010.001.M01.T01–T05; IT-EXE-010.001–002 | `core/monitoring_session/_scheduler.py` | Implemented | RN-EXE-1.3.0-20260518 |
| FO-EXE-011 | SRD-EXE-011.001–019 | DD-EXE-011.001.D01–D04, DD-EXE-011.016.D01 | MD-EXE-011.001.M01–M08 | UT-EXE-011.001.M01–M08.T01–T52 | `execution/strategy_engine/{_engine,_context,_evaluator,_router,_rex_counter,__init__}.py` | Implemented | RN-EXE-1.9.0-20260527 |
| FO-GUI-013 | SRD-GUI-013.015 | — | MD-GUI-004.001.M01 | — | `gui/execution_panel.py`, `gui/strategy_builder_dialog.py` | Implemented | RN-EXE-1.9.0-20260527 |
| FO-GUI-014 | SRD-GUI-014.013 | — | MD-GUI-014.001.M02 | — | `gui/active_cycles_model.py`, `gui/active_cycles_panel.py` | Implemented | RN-EXE-1.9.0-20260527 |
| FO-EXE-012 | SRD-EXE-012.001–013 | DD-EXE-012.001.D01–D02 | MD-EXE-012.001.M01–M06 | UT-EXE-012.001.M01–M06.T01–T29 | `execution/trade_cycle/{_schema,_repository,_service,_protocols,__init__}.py` | Verified | RN-EXE-1.8.0-20260527 |

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
| `execution/live_tick_worker.py` | MD-EXE-008.001.M01 | SRD-EXE-008.001–006 | FO-EXE-008 |
| `core/monitoring_session/_dto.py` + `_enums.py` | MD-EXE-009.001.M01 | SRD-EXE-009.012 | FO-EXE-009 |
| `core/monitoring_session/_protocols.py` | MD-EXE-009.001.M02 | SRD-EXE-009.010, 009.011 | FO-EXE-009 |
| `core/monitoring_session/_events.py` | MD-EXE-009.001.M03 | SRD-EXE-009.011 | FO-EXE-009 |
| `core/monitoring_session/_repository.py` | MD-EXE-009.002.M01 | SRD-EXE-009.001, 005–007, 009; 010.002 | FO-EXE-009/010 |
| `core/monitoring_session/_service.py` | MD-EXE-009.002.M02 | SRD-EXE-009.004–010 | FO-EXE-009 |
| `core/monitoring_session/__init__.py` | MD-EXE-009.002.M03 | SRD-EXE-009.010, 009.012 | FO-EXE-009 |
| `core/monitoring_session/_scheduler.py` | MD-EXE-010.001.M01 | SRD-EXE-010.004 | FO-EXE-010 |
| `execution/strategy_engine/_engine.py` | MD-EXE-011.001.M01 | SRD-EXE-011.001–003, 007–015 | FO-EXE-011 |
| `execution/strategy_engine/_context.py` | MD-EXE-011.001.M02 | SRD-EXE-011.004–007 | FO-EXE-011 |
| `execution/strategy_engine/_evaluator.py` | MD-EXE-011.001.M03 | SRD-EXE-011.006 | FO-EXE-011 |
| `execution/strategy_engine/__init__.py` | MD-EXE-011.001.M04 | SRD-EXE-011.001, 013 | FO-EXE-011 |
| `execution/strategy_engine/_rex_counter.py` | MD-EXE-011.001.M08 | SRD-EXE-011.016–019 | FO-EXE-011 |
| `execution/trade_cycle/_schema.py` | MD-EXE-012.001.M01 | SRD-EXE-012.001 | FO-EXE-012 |
| `execution/trade_cycle/_repository.py` | MD-EXE-012.001.M02 | SRD-EXE-012.002, 004–009 | FO-EXE-012 |
| `execution/trade_cycle/_service.py` | MD-EXE-012.001.M03 | SRD-EXE-012.002–013 | FO-EXE-012 |
| `execution/trade_cycle/_protocols.py` | MD-EXE-012.001.M04 | SRD-EXE-012.010–011 | FO-EXE-012 |
| `execution/trade_cycle/__init__.py` | MD-EXE-012.001.M05 | SRD-EXE-012.001, 010–012 | FO-EXE-012 |

---

## Status Summary

| Artifact | Total Items | Draft | Approved | Implemented | Verified |
|---|---|---|---|---|---|
| FO | 11 | 8 | 1 | 2 | 0 |
| SRD | 85 | 54 | 6 | 25 | 0 |
| DD | 21 | 17 | 2 | 2 | 0 |
| MD | 26 | 20 | 1 | 5 | 0 |
| UTCD | 142 | 49 | 13 | 80 | 0 |
| Code | 26 files | — | — | 11 | 0 |
