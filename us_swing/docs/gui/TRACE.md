# Traceability Matrix — GUI Module (GUI)

**Document ID:** TRACE-GUI
**Version:** 1.7.0
**Project:** US Swing Trading System
**Last Updated:** 2026-05-28

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-GUI-001 | SRD-GUI-001.001–004 | DD-GUI-001.001.D01 | MD-GUI-001.001.M01 | T01–T06 | `gui/main_window.py` | Draft |
| FO-GUI-002 | SRD-GUI-002.001–005 | DD-GUI-002.001.D01 | MD-GUI-002.001.M01 | — | `gui/dashboard_panel.py` | Draft |
| FO-GUI-002 | SRD-GUI-002.001–002, .005 (Reopen) | DD-GUI-002.001.D01 | MD-GUI-002.001.M02 | T01–T05 | `gui/position_table_model.py` | Reopen | RN-EXE-1.14.0-20260528 |
| FO-GUI-003 | SRD-GUI-003.001–005 | — | MD-GUI-003.001.M01 | T01–T04 | `gui/screener_panel.py` | Draft |
| FO-GUI-004 | SRD-GUI-004.001–008 | DD-GUI-004.001.D01 | MD-GUI-004.001.M01 | T01–T06 | `gui/execution_panel.py`, `gui/app_service.py`, `gui/pending_signals_table_model.py`, `data/models.py` | Draft | RN-EXE-1.8.0-20260527 |
| FO-GUI-005 | SRD-GUI-005.001–004 | — | MD-GUI-005.001.M01 | T01–T05 | `gui/position_monitor_panel.py` | Draft |
| FO-GUI-006 | SRD-GUI-006.001–005 | — | MD-GUI-006.001.M01 | T01–T04 | `gui/settings_panel.py` | Draft |
| FO-GUI-006 | SRD-GUI-006.005 | — | MD-GUI-000.004 | — | `gui/scheduler_dialog.py` | Draft | RN-GUI-1.2.1-20260519 |
| FO-GUI-007 | SRD-GUI-007.001–004 | DD-GUI-007.001.D01 | MD-GUI-007.001.M01 | T01–T04 | `gui/log_viewer_panel.py` | Draft |
| FO-GUI-007 | SRD-GUI-007.001 | DD-GUI-007.001.D01 | MD-GUI-007.001.M02 | T01 | `gui/log_bridge.py` | Draft |
| FO-GUI-011 | SRD-GUI-011.001–004 | DD-GUI-011.001.D01 | MD-GUI-011.001.M01 | — | `gui/chart_panel.py` | Implemented | RN-GUI-1.0.0-20260513 |
| FO-GUI-012 | SRD-GUI-012.001–007 | DD-GUI-012.001.D01 | MD-GUI-012.001.M01–M03 | UT-GUI-012.001.M01.T01–T19 | `gui/app_service.py`, `gui/dashboard_panel.py`, `gui/main_window.py`, `gui/execution_panel.py` | Implemented | RN-GUI-1.2.0-20260519 |
| FO-GUI-013 | SRD-GUI-013.015 | — | MD-GUI-004.001.M01 | — | `gui/execution_panel.py`, `gui/strategy_builder_dialog.py` | Implemented | RN-EXE-1.9.0-20260527 |
| FO-GUI-014 | SRD-GUI-014.001, .003–.005, .008–.012 | DD-GUI-014.002.D01 | MD-GUI-014.001.M01 | UT-GUI-014.001.M01.T01–T15 | `gui/active_cycles_panel.py` | Implemented | RN-EXE-1.10.0-20260527 |
| FO-GUI-014 | SRD-GUI-014.002, .004, .013 | DD-GUI-014.002.D01 | MD-GUI-014.001.M02 | UT-GUI-014.001.M02.T01–T11 | `gui/active_cycles_model.py` | Implemented | RN-EXE-1.10.0-20260527 |
| FO-GUI-014 | SRD-GUI-014.007 | DD-GUI-014.007.D01 | MD-GUI-014.001.M03 | — | `gui/risk_editor_widget.py` | Approved | — |
| FO-GUI-014 | SRD-GUI-014.014 | — | MD-GUI-004.001.M01 | — | `gui/app_service.py`, `gui/execution_panel.py` | Implemented | Pending |

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
| `gui/scheduler_dialog.py` | MD-GUI-000.004 | SRD-GUI-006.005 | FO-GUI-006 |
| `gui/log_viewer_panel.py` | MD-GUI-007.001.M01 | SRD-GUI-007.001–004 | FO-GUI-007 |
| `gui/log_bridge.py` | MD-GUI-007.001.M02 | SRD-GUI-007.001 | FO-GUI-007 |
| `gui/chart_panel.py` | MD-GUI-011.001.M01 | SRD-GUI-011.001–004 | FO-GUI-011 |
| `gui/app_service.py` (tick integration) | MD-GUI-004.001.M01 | SRD-GUI-012.001–007 | FO-GUI-012 |
| `gui/settings_panel.py` (tick client id) | MD-GUI-006.001.M01 | SRD-GUI-012.007 | FO-GUI-012 |
| `gui/active_cycles_panel.py` | MD-GUI-014.001.M01 | SRD-GUI-014.001, .003–.005, .008–.012 | FO-GUI-014 |
| `gui/active_cycles_model.py` | MD-GUI-014.001.M02 | SRD-GUI-014.002, .004 | FO-GUI-014 |
| `gui/risk_editor_widget.py` | MD-GUI-014.001.M03 | SRD-GUI-014.007 | FO-GUI-014 |

---

## Status Summary

| Artifact | Total Items | Draft | Approved | Implemented | Verified |
|---|---|---|---|---|---|
| FO | 10 | 8 | 1 | 1 | 0 |
| SRD | 53 | 34 | 12 | 7 | 0 |
| DD | 9 | 5 | 3 | 1 | 0 |
| MD | 15 | 10 | 3 | 2 | 0 |
| UTCD | 81 | 62 | 0 | 19 | 0 |
| Code | 15 files | — | — | 2 | 0 |
