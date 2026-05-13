# Traceability Matrix — GUI Module (GUI)

**Document ID:** TRACE-GUI
**Version:** 1.3.0
**Project:** US Swing Trading System
**Last Updated:** 2026-05-13

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-GUI-001 | SRD-GUI-001.001–004 | DD-GUI-001.001.D01 | MD-GUI-001.001.M01 | T01–T06 | `gui/main_window.py` | Draft |
| FO-GUI-002 | SRD-GUI-002.001–005 | DD-GUI-002.001.D01 | MD-GUI-002.001.M01 | — | `gui/dashboard_panel.py` | Draft |
| FO-GUI-002 | SRD-GUI-002.001–002 | DD-GUI-002.001.D01 | MD-GUI-002.001.M02 | T01–T05 | `gui/position_table_model.py` | Draft |
| FO-GUI-003 | SRD-GUI-003.001–005 | — | MD-GUI-003.001.M01 | T01–T04 | `gui/screener_panel.py` | Draft |
| FO-GUI-004 | SRD-GUI-004.001–008 | DD-GUI-004.001.D01 | MD-GUI-004.001.M01 | T01–T06 | `gui/execution_panel.py`, `gui/app_service.py`, `data/models.py` | Draft |
| FO-GUI-005 | SRD-GUI-005.001–004 | — | MD-GUI-005.001.M01 | T01–T05 | `gui/position_monitor_panel.py` | Draft |
| FO-GUI-006 | SRD-GUI-006.001–005 | — | MD-GUI-006.001.M01 | T01–T04 | `gui/settings_panel.py` | Draft |
| FO-GUI-007 | SRD-GUI-007.001–004 | DD-GUI-007.001.D01 | MD-GUI-007.001.M01 | T01–T04 | `gui/log_viewer_panel.py` | Draft |
| FO-GUI-007 | SRD-GUI-007.001 | DD-GUI-007.001.D01 | MD-GUI-007.001.M02 | T01 | `gui/log_bridge.py` | Draft |
| FO-GUI-011 | SRD-GUI-011.001–004 | DD-GUI-011.001.D01 | MD-GUI-011.001.M01 | — | `gui/chart_panel.py` | Implemented | RN-GUI-1.0.0-20260513 |
| FO-GUI-012 | SRD-GUI-012.001–007, .011 | DD-GUI-012.001.D01–D03 | MD-GUI-012.001.M01 | T01–T16 | `gui/ibkr_session.py` | Implemented | RN-GUI-1.1.0-20260513 |
| FO-GUI-012 | SRD-GUI-012.003, .008–.012 | DD-GUI-012.001.D04–D05 | MD-GUI-012.001.M02 | T01–T14 | `gui/app_service.py`, `gui/system_store.py` | Implemented | RN-GUI-1.1.0-20260513 |

---

## Reverse Traceability

| Module | MD ID | Parent SRD | Parent FO |
|---|---|---|---|
| `gui/main_window.py` | MD-GUI-001.001.M01 | SRD-GUI-001.001–004 | FO-GUI-001 |
| `gui/dashboard_panel.py` | MD-GUI-002.001.M01 | SRD-GUI-002.001–005 | FO-GUI-002 |
| `gui/position_table_model.py` | MD-GUI-002.001.M02 | SRD-GUI-002.001–002 | FO-GUI-002 |
| `gui/screener_panel.py` | MD-GUI-003.001.M01 | SRD-GUI-003.001–005 | FO-GUI-003 |
| `gui/execution_panel.py` | MD-GUI-004.001.M01 | SRD-GUI-004.001–008 | FO-GUI-004 |
| `gui/app_service.py` (screener bridge) | MD-GUI-004.001.M01 | SRD-GUI-004.008 | FO-GUI-004 |
| `data/models.py` (FilteredStockEntry) | MD-GUI-004.001.M01 | SRD-GUI-004.007 | FO-GUI-004 |
| `gui/position_monitor_panel.py` | MD-GUI-005.001.M01 | SRD-GUI-005.001–004 | FO-GUI-005 |
| `gui/settings_panel.py` | MD-GUI-006.001.M01 | SRD-GUI-006.001–005 | FO-GUI-006 |
| `gui/log_viewer_panel.py` | MD-GUI-007.001.M01 | SRD-GUI-007.001–004 | FO-GUI-007 |
| `gui/log_bridge.py` | MD-GUI-007.001.M02 | SRD-GUI-007.001 | FO-GUI-007 |
| `gui/chart_panel.py` | MD-GUI-011.001.M01 | SRD-GUI-011.001–004 | FO-GUI-011 |
| `gui/ibkr_session.py` | MD-GUI-012.001.M01 | SRD-GUI-012.001–007, .011 | FO-GUI-012 |
| `gui/app_service.py` (IBKR bridge) | MD-GUI-012.001.M02 | SRD-GUI-012.003, .008–.012 | FO-GUI-012 |
| `gui/system_store.py` (clientId cleanup) | MD-GUI-012.001.M02 | SRD-GUI-012.011 | FO-GUI-012 |

---

## Status Summary

| Artifact | Total Items | Draft | Approved | Implemented | Verified |
|---|---|---|---|---|---|
| FO | 9 | 8 | 0 | 1 | 0 |
| SRD | 46 | 34 | 0 | 12 | 0 |
| DD | 10 | 5 | 0 | 5 | 0 |
| MD | 12 | 10 | 0 | 2 | 0 |
| UTCD | 66 | 36 | 0 | 30 | 0 |
| Code | 12 files | — | — | 2 | 0 |
