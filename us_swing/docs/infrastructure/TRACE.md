# Traceability Matrix — Infrastructure (INF)

**Document ID:** TRACE-INF
**Version:** 1.1.0
**Project:** US Swing Trading System
**Last Updated:** 2026-06-05

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

---

## Reverse Traceability: MD → SRD → FO

| Module | MD ID | Parent SRD | Parent FO |
|---|---|---|---|
| `broker/client.py` | MD-INF-001.001.M01 | SRD-INF-001.001–005 | FO-INF-001 |
| `broker/pacing.py` | MD-INF-001.001.M02 | SRD-INF-001.005 | FO-INF-001 |
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

---

## Status Summary

| Artifact | Total Items | Draft | Approved | Implemented | Verified |
|---|---|---|---|---|---|
| FO | 7 | 7 | 0 | 0 | 0 |
| SRD | 35 | 35 | 0 | 0 | 0 |
| DD | 7 | 7 | 0 | 0 | 0 |
| MD | 14 | 14 | 0 | 0 | 0 |
| UTCD | 41 | 35 | 0 | 0 | 3 |
| Code | 14 files | — | — | 0 | 0 |
