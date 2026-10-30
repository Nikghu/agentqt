# Traceability Matrix — Execution & Risk Management (EXE)

**Document ID:** TRACE-EXE
**Version:** 1.23.0
**Project:** US Swing Trading System
**Last Updated:** 2026-10-29 (SRD-EXE-006.014 closed bars only; RN-EXE-1.38.0)

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
| FO-EXE-006 | SRD-EXE-006.001–006 | DD-EXE-006.001.D01–D02 | MD-EXE-006.001.M01 | UT-EXE-006.001.M01.T01–T21 | `execution/intraday_candle_loader.py` | Implemented | RN-EXE-1.1.0-20260506, RN-EXE-1.32.3-20260904 |
| FO-EXE-006 | SRD-EXE-006.010 | DD-EXE-006.010.D01 | MD-EXE-006.001.M01 | UT-EXE-006.001.M01.T14, T15, T16 | `execution/intraday_candle_loader.py` | Implemented | RN-EXE-1.5.1-20260530 |
| FO-EXE-006 | SRD-EXE-006.012 | DD-EXE-006.012.D01 | MD-EXE-006.001.M01 | UT-EXE-006.001.M01.T17, T18, T19 | `execution/intraday_candle_loader.py`, `gui/strategy_builder_dialog.py` | Implemented | RN-EXE-1.21.0-20260610 |
| FO-EXE-006 | SRD-EXE-006.013 | DD-EXE-006.013.D01 | MD-EXE-006.013.M01 | UT-EXE-006.013.M01.T01–T04 | `gui/app_service.py` | Implemented | RN-EXE-1.29.0-20260616 |
| FO-EXE-006 | SRD-EXE-006.014 | — (no DD) | MD-EXE-006.001.M01 | UT-EXE-006.001.M01.T22–T23 | `execution/intraday_candle_loader.py` | Implemented | RN-EXE-1.38.0-20261029 |
| FO-EXE-007 | SRD-EXE-007.010 | DD-EXE-007.001.D03 | MD-EXE-007.001.M01 | UT-EXE-007.001.M01.T27–T29 | `execution/live_bar_worker.py` | Implemented | RN-EXE-1.37.1-20261027 |
| FO-EXE-008 | SRD-EXE-008.001–006 | DD-EXE-008.001.D01 | MD-EXE-008.001.M01 | UT-EXE-008.001.M01.T01–T16 | `execution/live_tick_worker.py` | Implemented | RN-EXE-1.3.1-20260519 |
| FO-EXE-009 | SRD-EXE-009.001–012 | DD-EXE-009.001.D01–D02, 009.002.D01–D02, 009.003.D01 | MD-EXE-009.001.M01–M03, 009.002.M01–M03 | UT-EXE-009.001.M01.T01–T04, 009.001.M02.T01–T03, 009.001.M03.T01–T06, 009.002.M01.T01–T14, 009.002.M02.T01–T22, 009.002.M02.T17–T17d, 009.002.M03.T01–T04; IT-EXE-009.001–005 | `core/monitoring_session/{_dto,_enums,_protocols,_events,_repository,_service}.py`, `core/monitoring_session/__init__.py` | Implemented | RN-EXE-1.3.0-20260518, RN-EXE-1.15.0-20260529, RN-EXE-1.19.0-20260608, RN-EXE-1.20.1-20260609 (ISS-EXE-0003 log level) |
| FO-EXE-010 | SRD-EXE-010.001–006 | DD-EXE-010.001.D01, 010.002.D01, 010.003.D01 | MD-EXE-010.001.M01 | UT-EXE-010.001.M01.T01–T05; IT-EXE-010.001–002 | `core/monitoring_session/_scheduler.py` | Implemented | RN-EXE-1.3.0-20260518, RN-EXE-1.19.0-20260608 |
| FO-EXE-011 | SRD-EXE-011.001–019 | DD-EXE-011.001.D01–D04, DD-EXE-011.016.D01 | MD-EXE-011.001.M01–M08 | UT-EXE-011.001.M01–M08.T01–T52 | `execution/strategy_engine/{_engine,_context,_evaluator,_router,_rex_counter,__init__}.py` | Implemented | RN-EXE-1.9.0-20260527 |
| FO-EXE-011 | SRD-EXE-011.020 | — | MD-EXE-011.001.M01, M04, M06, M09 | UT-EXE-011.001.M04.T18–T20 | `execution/strategy_engine/{_engine,_router,_signals}.py`, `execution/pending_signal_store.py` | Implemented | RN-EXE-1.10.0-20260527 |
| FO-EXE-011 | SRD-EXE-011.021 | — | MD-EXE-011.001.M04 | UT-EXE-011.001.M04.T21, T22 | `execution/strategy_engine/_router.py` | Implemented | RN-EXE-1.22.0-20260610 |
| FO-EXE-011 | SRD-EXE-011.022 | — | MD-EXE-011.001.M04 | UT-EXE-011.001.M04.T27, T28, T29 | `execution/strategy_engine/_router.py` | Implemented | RN-EXE-1.24.0-20260612 |
| FO-EXE-011 | SRD-EXE-011.023 | DD-EXE-011.023.D01 | MD-EXE-011.001.M03 | UT-EXE-011.001.M03.T10–T13 | `execution/strategy_engine/_evaluator.py` | Implemented | RN-EXE-1.29.0-20260616 |
| FO-EXE-011 | SRD-EXE-011.024 | DD-EXE-011.024.D01 | MD-EXE-011.024.M01 | UT-EXE-011.024.M01.T01–T04 | `execution/pending_signal_store.py`, `gui/app_service.py` | Implemented | RN-EXE-1.30.0-20260617 |
| FO-EXE-011 | SRD-EXE-011.025 | — | MD-EXE-011.024.M01 | UT-EXE-011.025.M01.T01–T02 | `gui/app_service.py` | Implemented | RN-EXE-1.30.0-20260617 |
| FO-EXE-012 | SRD-EXE-012.014 | — | MD-EXE-012.002.M02 | UT-EXE-012.002.M02.T19 | `execution/trade_cycle/_service.py`, `execution/trade_cycle/_protocols.py` | Implemented | RN-EXE-1.30.0-20260617 |
| FO-GUI-013 | SRD-GUI-013.015 | — | MD-GUI-004.001.M01 | — | `gui/execution_panel.py`, `gui/strategy_builder_dialog.py` | Implemented | RN-EXE-1.9.0-20260527 |
| FO-GUI-014 | SRD-GUI-014.013 | — | MD-GUI-014.001.M02 | — | `gui/active_cycles_model.py`, `gui/active_cycles_panel.py` | Implemented | RN-EXE-1.9.0-20260527 |
| FO-EXE-012 | SRD-EXE-012.001–013 | DD-EXE-012.001.D01–D02 | MD-EXE-012.001.M01–M06 | UT-EXE-012.001.M01–M06.T01–T29, 012.002.M02.T18, 012.002.M02.T20 | `execution/trade_cycle/{_schema,_repository,_service,_protocols,__init__}.py` | Verified (012.007 re-Implemented v1.23.0) | RN-EXE-1.8.0-20260527, RN-EXE-1.17.0-20260602, RN-EXE-1.23.0-20260612, RN-GUI-1.3.1-20260625 (trailing-off dto) |
| FO-EXE-014 | SRD-EXE-014.001–004 | — | MD-INF-004.001.M02, MD-INF-004.001.M03, MD-EXE-001.001.M02, MD-EXE-002.001.M01, MD-EXE-004.001.M01 | UT-EXE-014.001.M01.T01–T06 | `db/schema.py`, `db/manager.py`, `data/models.py`, `execution/execution_engine.py`, `execution/paper_engine.py`, `execution/position_tracker.py`, `gui/position_table_model.py` | Implemented | RN-EXE-1.14.0-20260528 |
| FO-EXE-014 | SRD-EXE-014.005–008 | — | MD-EXE-001.001.M02, MD-EXE-012.002.M02, MD-EXE-009.002.M02, MD-EXE-015.001.M01 | UT-EXE-014.005.M01.T01, 014.006.M01.T02, 014.007.M01.T01–T03, 014.007.M02.T01–T03, 014.007.M02.T19, 014.008.M01.T01–T05, 012.002.M02.T16–T17 | `data/models.py`, `execution/order_ingestion.py`, `execution/trade_cycle/{_service,_protocols}.py`, `core/monitoring_session/{_dto,_service}.py` | Implemented | RN-EXE-1.16.0-20260529, RN-EXE-1.17.0-20260602, RN-EXE-1.26.0-20260612 |
| FO-EXE-017 | SRD-EXE-017.001–014 | DD-EXE-017.001.D01, .003.D01, .005.D01, .007.D01, .008.D01, .010.D01 | MD-EXE-017.001.M01–M09, 017.011.M05 | UT-EXE-017.003.M01.T01–04, .005.M01.T05–06, .006.M01.T07–08, .004.M03.T01, .009.M03.T02, .010.M04.T01–02, .011.M05.T01–03, .014.M07.T01–02, .001.M09.T01–02, .002.M09.T03, .007.M09.T04–05 | `execution/risk_manager.py`, `execution/strategy_engine/{_events,_router,_engine}.py`, `gui/{app_service,active_cycles_model,settings_panel,user_store,main_window,_demo}.py`, `user/manager.py`, `data/models.py`, `config/settings.py` | Implemented | RN-EXE-1.20.0-20260609 |
| FO-EXE-017 | SRD-EXE-017.015–021 | DD-EXE-017.015.D01, .018.D01, .019.D01, .020.D01, .021.D01 | MD-EXE-017.012.M10–017.017.M15 | UT-EXE-017.015.M10.T01–02, .017.M10.T03–04, .018.M12.T01, .016.M12.T02, .017.M12.T03, .019.M14.T01, .021.M14.T02–03 | `execution/risk_manager.py`, `execution/strategy_engine/{_protocols,_router,_context}.py`, `gui/{app_service,main_window}.py` | Implemented | RN-EXE-1.25.0-20260612 |
| FO-EXE-017 | SRD-EXE-017.022 | — | MD-EXE-011.001.M07 | UT-EXE-011.001.M04.T30, T31 | `execution/strategy_engine/{_router,_context}.py`, `gui/active_cycles_panel.py` | Implemented | RN-EXE-1.27.0-20260612 |
| FO-EXE-017 | SRD-EXE-017.023–.026 | DD-EXE-017.024.D01 | MD-EXE-017.023.M03 | UT-EXE-017.024.M03.T04–T07 | `execution/strategy_engine/_router.py`, `gui/{strategy_store,strategy_builder_dialog,execution_panel}.py` | Implemented | RN-EXE-1.31.0-20260710 |
| FO-EXE-016 | SRD-EXE-016.001–006 | DD-EXE-016.001.D01, .003.D01, .006.D01 | MD-EXE-016.001.M01–M03, 016.003.M04, 016.006.M05–M06 | UTCD deferred (covered by `tests/core/monitoring_session`, `tests/integration/test_lifecycle_e2e.py`) | `core/monitoring_session/{_service,_repository,_protocols}.py`, `execution/order_ingestion.py`, `gui/app_service.py`, `db/{schema,manager}.py` | Implemented | RN-EXE-1.18.0-20260604 |
| FO-EXE-016 | SRD-EXE-016.007 | DD-EXE-016.007.D01 | MD-EXE-016.001.M01, 016.003.M04 | UT-EXE-016.007.M01.T01, .T02 | `core/monitoring_session/{_service,_repository}.py` | Implemented | RN-EXE-1.28.0-20260612 |
| FO-EXE-015 | SRD-EXE-015.001–006 | — | MD-EXE-015.001.M01, 015.002.M01, 015.003.M01 | `tests/execution/test_broker_adapter.py` (incl. fill-before-accept regression) | `execution/{order_ingestion,broker_adapter,broker_factory}.py`, `db/manager.py` | Implemented | RN-EXE-1.19.1-20260608 (ISS-EXE-0002 race fix) |
| FO-EXE-015 | SRD-EXE-015.005 | — | MD-EXE-015.001.M01 | UT-EXE-015.005.M01.T01–T15, M04.T11–T13 | `execution/order_ingestion.py`, `execution/strategy_engine/_router.py` | Implemented | RN-EXE-1.32.0-20260827 |
| FO-EXE-015 | SRD-EXE-015.004 | — | MD-EXE-015.003.M02, MD-EXE-015.004.M01 | UT-EXE-015.004.M01.T20–T36 | `broker/ibkr.py`, `execution/ibkr_order_connection.py`, `gui/app_service.py` | Implemented | RN-EXE-1.32.1-20260828 |
| FO-EXE-014 | SRD-EXE-014.007 | — | MD-EXE-014.007.M01 | UT-EXE-014.007.M01.T04–T17 | `gui/app_service.py` | Implemented | RN-EXE-1.32.0-20260827 |
| FO-INF-009 | SRD-INF-009.005 | — | MD-INF-009.005.M01 | UT-INF-009.005.M01.T10–T19 | `broker/ibkr.py` | Implemented | RN-EXE-1.32.0-20260827 |
| FO-EXE-005 | SRD-EXE-005.001–003 (Reopen) | DD-EXE-005.001.D01 | MD-EXE-002.001.M01 | UT-EXE-005.001.M01.T01–T05 | `execution/position_tracker.py` | Reopen | RN-EXE-1.14.0-20260528 |
| FO-EXE-018 | SRD-EXE-018.001–016 | DD-EXE-018.001.D01, .003.D01, .006.D01, .007.D01, .012.D01, .013.D01 | MD-EXE-018.001.M01–018.012.M10 | UT-EXE-018.001.M02.T01–03, .002.M03.T01–03, .003–.004.M04.T01–05, .005/.012/.014.M05.T01–10, .005.M06.T01–03, .006/.015.M07.T01–04, .007–.011.M08.T01–17, .016.M08.T01–02, .013.M09.T01–03, .012/.013.M10.T01–04; IT-EXE-018.001–002 | `execution/{_enums,direction,broker_adapter,signal_bridge,order_ingestion}.py`, `execution/strategy_engine/{_signals,_router,_context,_engine}.py`, `execution/trade_cycle/{_schema,_dto,_repository,_service,_protocols}.py`, `db/schema.py`, `data/models.py`, `gui/{strategy_store,app_service}.py` | Implemented | RN-EXE-1.33.0-20260917 (.016 pending RN) |
| FO-EXE-019 | SRD-EXE-019.001–004 | DD-EXE-019.001.D01 | MD-EXE-019.001.M01, .002.M02, .004.M03 | UT-EXE-019.001.M01.T01–04, .003.M01.T05, .002.M02.T01–07, .004.M03.T01–02 | `execution/trade_cycle/{_repository,_protocols,_service,_schema,_pnl_history,__init__}.py`, `db/schema.py`, `gui/app_service.py` | Implemented | RN-EXE-1.34.0-20261023 |
| FO-EXE-017 | SRD-EXE-017.027 | DD-EXE-017.027.D01 | MD-EXE-017.016.M14 | UT-EXE-017.027.M14.T01–T03 | `gui/app_service.py` | Implemented | RN-EXE-1.37.0-20261024 |
| FO-EXE-020 | SRD-EXE-020.001–008 | DD-EXE-020.001.D01 | MD-EXE-020.001.M01, .004.M02 | UT-EXE-020.001.M01.T01–T02, .002.M01.T01–T04, .003.M01.T01–T03, .005.M01.T01, .005.M02.T01, .004.M02.T01–T05, .006.M02.T01, .007.M01.T01–T02, .008.M02.T01–T04 | `execution/equity_snapshot.py`, `gui/app_service.py`, `db/schema.py` | Implemented | RN-EXE-1.35.0-20261024, RN-EXE-1.36.0-20261024 |

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
| `execution/strategy_engine/_evaluator.py` | MD-EXE-011.001.M03 | SRD-EXE-011.006, 011.023 | FO-EXE-011 |
| `gui/app_service.py` (cycle-open candle arming) | MD-EXE-006.013.M01 | SRD-EXE-006.013 | FO-EXE-006 |
| `execution/strategy_engine/__init__.py` | MD-EXE-011.001.M04 | SRD-EXE-011.001, 013, 021 | FO-EXE-011 |
| `execution/strategy_engine/_router.py` | MD-EXE-011.001.M04 | SRD-EXE-011.021, 022 | FO-EXE-011 |
| `execution/strategy_engine/_rex_counter.py` | MD-EXE-011.001.M08 | SRD-EXE-011.016–019 | FO-EXE-011 |
| `execution/trade_cycle/_schema.py` | MD-EXE-012.001.M01 | SRD-EXE-012.001 | FO-EXE-012 |
| `execution/trade_cycle/_repository.py` | MD-EXE-012.001.M02 | SRD-EXE-012.002, 004–009 | FO-EXE-012 |
| `execution/trade_cycle/_service.py` | MD-EXE-012.001.M03 | SRD-EXE-012.002–013 | FO-EXE-012 |
| `execution/trade_cycle/_protocols.py` | MD-EXE-012.001.M04 | SRD-EXE-012.010–011 | FO-EXE-012 |
| `execution/trade_cycle/__init__.py` | MD-EXE-012.001.M05 | SRD-EXE-012.001, 010–012 | FO-EXE-012 |
| `execution/direction.py` | MD-EXE-018.003.M04 | SRD-EXE-018.003–004 | FO-EXE-018 |
| `execution/trade_cycle/_pnl_history.py` | MD-EXE-019.002.M02 | SRD-EXE-019.002 | FO-EXE-019 |
| `execution/equity_snapshot.py` | MD-EXE-020.001.M01 | SRD-EXE-020.001–003, .005, .007 | FO-EXE-020 |

---

## Status Summary

| Artifact | Total Items | Draft | Approved | Implemented | Verified |
|---|---|---|---|---|---|
| FO | 12 | 8 | 1 | 3 | 0 |
| SRD | 101 | 54 | 6 | 41 | 0 |
| DD | 29 | 23 | 2 | 4 | 0 |
| MD | 37 | 30 | 1 | 6 | 0 |
| UTCD | 175 | 49 | 13 | 113 | 0 |
| Code | 27 files | — | — | 12 | 0 |
