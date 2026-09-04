# Traceability Matrix — Infrastructure (INF)

**Document ID:** TRACE-INF
**Version:** 1.5.0
**Project:** US Swing Trading System
**Last Updated:** 2026-09-04 (Session 79, SRD-INF-007.006 approved)

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-INF-001 | SRD-INF-001.001 | DD-INF-001.001.D01 | MD-INF-001.001.M01 | T01–T05 | `broker/client.py` | Draft | — |
| FO-INF-001 | SRD-INF-001.005 | DD-INF-001.001.D01 | MD-INF-001.001.M02 | T01–T04 | `broker/pacing.py` | Draft | — |
| FO-INF-002 | SRD-INF-002.001–004 | DD-INF-002.001.D01 | MD-INF-002.001.M01 | T01–T04 | `universe/manager.py` | Draft | — |
| FO-INF-003 | SRD-INF-003.001–005 | DD-INF-003.001.D01 | MD-INF-003.001.M01 | T01–T05 | `data_engine/engine.py` | Draft | — |
| FO-INF-004 | SRD-INF-004.001–006 | DD-INF-004.001.D01 | MD-INF-004.001.M01 | T01–T06, T20–T21 | `db/manager.py` | Draft | — |
| FO-INF-004 | SRD-INF-004.001–002 | DD-INF-004.001.D01 | MD-INF-004.001.M02 | T05 | `db/schema.py` | Draft | — |
| FO-INF-001–005 | SRD-INF-001.001 | — | MD-INF-004.001.M03 | — | `data/models.py` | Draft | — |
| FO-INF-005 | SRD-INF-005.001–002 | DD-INF-005.001.D01 | MD-INF-005.001.M01 | T01–T02 | `monitoring/logging_setup.py` | Draft | RN-INF-1.0.1-20260519 |
| FO-INF-005 | SRD-INF-005.003 | DD-INF-005.001.D01 | MD-INF-005.001.M02 | T01–T02 | `monitoring/alerts.py` | Draft | — |
| FO-INF-005 | SRD-INF-005.004 | DD-INF-005.001.D01 | MD-INF-005.001.M03 | T01 | `monitoring/health.py` | Draft | — |
| FO-INF-001 | SRD-INF-001.001 | — | MD-INF-001.001.M03 | — | `config/settings.py` | Draft | — |
| FO-INF-006 | SRD-INF-006.001–007 | DD-INF-006.001.D01 | MD-INF-006.001.M01 | T01–T09 | `user/manager.py` | Draft | — |
| FO-INF-007 | SRD-INF-007.001–002 | DD-INF-007.001.D01 | MD-INF-007.001.M01 | — | `data/providers/ibkr_provider.py` | Draft | — |
| FO-INF-007 | SRD-INF-007.003, 005 | DD-INF-007.001.D01 | MD-INF-007.001.M02 | T01–T04 | `data/providers/dummy_provider.py` | Draft | — |
| FO-INF-007 | SRD-INF-007.006 | — | MD-INF-007.001.M03 | UT-INF-007.001.M03.T01–T05 | `core/symbols.py` | Implemented | RN-INF-1.7.0-20260904 |
| FO-INF-009 | SRD-INF-009.007 | — | MD-INF-009.004.M01 | UT-INF-009.004.M01.T01–T04 | `broker/sim.py` | Implemented | RN-INF-1.1.0-20260612 |
| FO-INF-010 | SRD-INF-010.001–008 | DD-INF-010.001.D01 | MD-INF-010.001.M01–M07 | UT-INF-010.001.M01–M07.* | `core/notifications/` | Implemented | RN-INF-1.2.0-20260709 |
| FO-INF-010 | SRD-INF-010.010–011 | DD-INF-010.001.D01 | MD-INF-010.001.M08–M09 | UT-INF-010.001.M08.* | `gui/telegram_token_store.py`, `gui/notification_worker.py` | Implemented | RN-INF-1.3.0-20260709 |
| FO-INF-010 | SRD-INF-010.009, .012–.015 | DD-INF-010.001.D01 | MD-INF-010.001.M10–M11 | UT-INF-010.001.M10.*, M11.* | `core/notifications/_inbound.py`, `gui/telegram_commands.py` | Implemented | RN-INF-1.4.0-20260709 |
| FO-INF-010 | SRD-INF-010.006, .010 | DD-INF-010.001.D01 | MD-INF-010.001.M04, M09 | UT-INF-010.001.M04.T07–09, M07.T03, M08.T06–07, M09.T01–03 | `core/notifications/_dispatcher.py`, `gui/app_service.py`, `gui/settings_panel.py`, `gui/user_store.py`, `data/models.py` | Implemented | RN-INF-1.5.0-20260710 |

---

## Reverse Traceability: MD → SRD → FO

| Module | MD ID | Parent SRD | Parent FO |
|---|---|---|---|
| `broker/client.py` | MD-INF-001.001.M01 | SRD-INF-001.001–005 | FO-INF-001 |
| `broker/pacing.py` | MD-INF-001.001.M02 | SRD-INF-001.005 | FO-INF-001 |
| `broker/sim.py` | MD-INF-009.004.M01 | SRD-INF-009.004, .007 | FO-INF-009 |
| `universe/manager.py` | MD-INF-002.001.M01 | SRD-INF-002.001–004 | FO-INF-002 |
| `data_engine/engine.py` | MD-INF-003.001.M01 | SRD-INF-003.001–005 | FO-INF-003 |
| `db/manager.py` | MD-INF-004.001.M01 | SRD-INF-004.001–006 | FO-INF-004 |
| `db/schema.py` | MD-INF-004.001.M02 | SRD-INF-004.001–002 | FO-INF-004 |
| `data/models.py` | MD-INF-004.001.M03 | SRD-INF-001.001 | FO-INF-001–005 |
| `monitoring/logging_setup.py` | MD-INF-005.001.M01 | SRD-INF-005.001–002 | FO-INF-005 |
| `monitoring/alerts.py` | MD-INF-005.001.M02 | SRD-INF-005.003 | FO-INF-005 |
| `monitoring/health.py` | MD-INF-005.001.M03 | SRD-INF-005.004 | FO-INF-005 |
| `config/settings.py` | MD-INF-001.001.M03 | SRD-INF-001.001 | FO-INF-001 |
| `user/manager.py` | MD-INF-006.001.M01 | SRD-INF-006.001–007 | FO-INF-006 |
| `data/providers/ibkr_provider.py` | MD-INF-007.001.M01 | SRD-INF-007.001–002 | FO-INF-007 |
| `data/providers/dummy_provider.py` | MD-INF-007.001.M02 | SRD-INF-007.003, 005 | FO-INF-007 |
| `core/symbols.py` | MD-INF-007.001.M03 | SRD-INF-007.006 | FO-INF-007 |
| `core/notifications/_events.py` | MD-INF-010.001.M01 | SRD-INF-010.001 | FO-INF-010 |
| `core/notifications/_protocols.py` | MD-INF-010.001.M02 | SRD-INF-010.002, .014 | FO-INF-010 |
| `core/notifications/_telegram.py` | MD-INF-010.001.M03 | SRD-INF-010.003 | FO-INF-010 |
| `core/notifications/_dispatcher.py` | MD-INF-010.001.M04 | SRD-INF-010.004, .006, .007 | FO-INF-010 |
| `core/notifications/_formatters.py` | MD-INF-010.001.M05 | SRD-INF-010.005 | FO-INF-010 |
| `core/notifications/_dto.py` | MD-INF-010.001.M06 | SRD-INF-010.006 | FO-INF-010 |
| `core/notifications/__init__.py` | MD-INF-010.001.M07 | SRD-INF-010.008 | FO-INF-010 |
| `gui/telegram_token_store.py` | MD-INF-010.001.M08 | SRD-INF-010.011 | FO-INF-010 |
| `gui/notification_worker.py` | MD-INF-010.001.M09 | SRD-INF-010.004, .010, .012 | FO-INF-010 |
| `core/notifications/_inbound.py` | MD-INF-010.001.M10 | SRD-INF-010.012, .013, .014 | FO-INF-010 |
| `gui/telegram_commands.py` | MD-INF-010.001.M11 | SRD-INF-010.015 | FO-INF-010 |

---

## Status Summary

| Artifact | Total Items | Draft | Approved | Implemented | Verified |
|---|---|---|---|---|---|
| FO | 8 | 8 | 0 | 0 | 0 |
| SRD | 50 | 35 | 0 | 15 | 0 |
| DD | 8 | 8 | 0 | 0 | 0 |
| MD | 25 | 14 | 7 | 4 | 0 |
| UTCD | 79 | 35 | 0 | 0 | 3 |
| Code | 25 files | — | — | 11 | 0 |

> UTCD note: the 38 FO-INF-010 cases (`UT-INF-010.001.M01–M11.*`) are all `Pass`.
