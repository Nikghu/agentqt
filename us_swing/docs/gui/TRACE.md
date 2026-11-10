# Traceability Matrix — GUI Module (GUI)

**Document ID:** TRACE-GUI
**Version:** 1.16.0
**Project:** US Swing Trading System
**Last Updated:** 2026-11-10 (AI Desk Team at work FO-GUI-035 with RN-GUI-1.13.0-20261110; Market Floor and AI Desk frames FO-GUI-034; SRD-GUI-034.011 with RN-MKT-0.1.0-20261106; SRD-GUI-034.012 with RN-MKT-0.2.0-20261106; SRD-GUI-034.013 with RN-MKT-0.3.0-20261106; SRD-GUI-034.014 with RN-MKT-0.4.0-20261106; SRD-GUI-034.015–.017 with RN-DSK-0.2.0-20261106)

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-GUI-000 | SRD-GUI-000.006 | DD-EXE-017.021.D01 | MD-EXE-017.017.M15 | (logic via UT-EXE-017.021.M14.T02–03) | `gui/main_window.py`, `gui/app_service.py` | Implemented | RN-EXE-1.25.0-20260612 |
| FO-GUI-000 | SRD-GUI-000.007 | — | MD-GUI-000.007.M01 | UT-GUI-000.007.M01.T01–T03 | `gui/quiet_platform.py`, `run_gui.py`, `pyi_rth_quiet_platform.py`, `usswing_installer.yaml` | Implemented | RN-GUI-1.37.1-20261027 |
| FO-GUI-000 | SRD-GUI-000.008 | — | MD-GUI-000.008.M01–M03 | UT-GUI-000.008.M01.T01–T02, M02.T01, M03.T01–T02 | `gui/theme.py`, `gui/chart_source_list.py`, `gui/app_service.py` | Implemented | RN-GUI-1.37.2-20261027 |
| FO-GUI-000 | SRD-GUI-000.009 | — | MD-GUI-000.009.M01–M02 | UT-GUI-000.009.M01.T01–T02, M02.T01–T02 | `gui/popups.py`, `gui/{settings_panel,execution_panel,strategies_pane,screener_panel,position_monitor_panel,dashboard_panel,sidebar}.py` | Implemented | RN-GUI-1.57.1-20261103 |
| FO-GUI-001 | SRD-GUI-001.001–004 | DD-GUI-001.001.D01 | MD-GUI-001.001.M01 | T01–T06 | `gui/main_window.py` | Draft |
| FO-GUI-002 | SRD-GUI-002.001–005 | DD-GUI-002.001.D01 | MD-GUI-002.001.M01 | — | `gui/dashboard_panel.py` | Draft |
| FO-GUI-002 | SRD-GUI-002.001–002, .005 (Reopen) | DD-GUI-002.001.D01 | MD-GUI-002.001.M02 | T01–T05 | `gui/position_table_model.py` | Reopen | RN-EXE-1.14.0-20260528 |
| FO-GUI-003 | SRD-GUI-003.001–005 | — | MD-GUI-003.001.M01 | T01–T04 | `gui/screener_panel.py` | Draft |
| FO-GUI-004 | SRD-GUI-004.001–008 | DD-GUI-004.001.D01 | MD-GUI-004.001.M01 | T01–T09 | `gui/execution_panel.py`, `gui/app_service.py`, `gui/pending_signals_table_model.py`, `data/models.py` | Draft | RN-EXE-1.8.0-20260527, RN-GUI-1.2.3-20260529, RN-GUI-1.3.0-20260602 |
| FO-GUI-005 | SRD-GUI-005.001–004 | — | MD-GUI-005.001.M01 | T01–T05 | `gui/position_monitor_panel.py` | Draft |
| FO-GUI-006 | SRD-GUI-006.001–005 | — | MD-GUI-006.001.M01 | T01–T04 | `gui/settings_panel.py` | Draft | RN-GUI-1.3.0-20260602 |
| FO-GUI-006 | SRD-GUI-006.005 | — | MD-GUI-000.004 | — | `gui/scheduler_dialog.py` | Draft | RN-GUI-1.2.1-20260519 |
| FO-GUI-006 | SRD-GUI-006.017 | — | MD-GUI-000.003, MD-GUI-000.004 | UT-GUI-000.003.T01–T04, UT-GUI-000.004.T01–T02 | `gui/scheduler_store.py`, `gui/scheduler_dialog.py` | Implemented | RN-GUI-1.3.2-20260625 |
| FO-GUI-006 | SRD-GUI-006.018 | — | MD-GUI-006.001.M01 | UT-GUI-006.001.M01.T05–T06 | `gui/app_service.py`, `gui/settings_panel.py` | Implemented | RN-GUI-1.4.1-20260904 |
| FO-GUI-006 | SRD-GUI-006.019 | — | MD-GUI-006.001.M01 | UT-GUI-006.001.M01.T11–T16 | `gui/app_service.py` | Implemented | RN-GUI-1.7.1-20261022 |
| FO-GUI-006 | SRD-GUI-006.020–.021 | — | MD-GUI-006.001.M01 | UT-GUI-006.001.M01.T20–T23 | `gui/app_service.py` | Implemented | RN-GUI-1.56.2-20261103 |
| FO-GUI-006 | SRD-GUI-006.022 | — | MD-GUI-006.001.M01 | UT-GUI-006.001.M01.T24 | `gui/app_service.py` | Implemented | RN-GUI-1.59.2-20261105 |
| FO-GUI-006 | SRD-GUI-006.023 | — | MD-GUI-006.001.M01 | UT-GUI-006.001.M01.T25, T26, T27 | `gui/app_service.py` | Implemented | RN-GUI-1.59.3-20261105 |
| FO-GUI-004 | SRD-GUI-004.009 | — | MD-GUI-004.001.M01 | UT-GUI-004.001.M01.T08–T10 | `gui/app_service.py` | Implemented | RN-GUI-1.7.2-20261022 |
| FO-GUI-004 | SRD-GUI-004.010 | — | MD-GUI-004.001.M01, MD-GUI-004.001.M02 | UT-GUI-004.001.M01.T11–T14 | `gui/manual_picks_store.py`, `gui/app_service.py` | Implemented | RN-GUI-1.8.0-20261022 |
| FO-GUI-004 | SRD-GUI-004.011 | — | MD-GUI-004.001.M01 | UT-GUI-004.001.M01.T15–T16, T19 | `gui/execution_panel.py`, `gui/app_service.py` | Implemented | RN-GUI-1.8.0-20261022 |
| FO-GUI-004 | SRD-GUI-004.012 | — | MD-GUI-004.001.M01 | UT-GUI-004.001.M01.T17–T18, T20 | `gui/app_service.py` | Implemented | RN-GUI-1.8.0-20261022 |
| FO-GUI-004 | SRD-GUI-004.013 | — | MD-GUI-004.001.M01, MD-GUI-004.001.M03 | UT-GUI-004.001.M01.T21–T25 | `gui/intraday_cleanup.py`, `gui/app_service.py` | Implemented | RN-GUI-1.8.0-20261022 |
| FO-GUI-007 | SRD-GUI-007.001–004 | DD-GUI-007.001.D01 | MD-GUI-007.001.M01 | T01–T04 | `gui/log_viewer_panel.py` | Draft |
| FO-GUI-007 | SRD-GUI-007.001 | DD-GUI-007.001.D01 | MD-GUI-007.001.M02 | T01 | `gui/log_bridge.py` | Draft |
| FO-GUI-011 | SRD-GUI-011.001–004 | DD-GUI-011.001.D01 | MD-GUI-011.001.M01 | — | `gui/chart_panel.py` | Implemented | RN-GUI-1.0.0-20260513 |
| FO-GUI-012 | SRD-GUI-012.001–009 | DD-GUI-012.001.D01 | MD-GUI-012.001.M01–M03 | UT-GUI-012.001.M01.T01–T28 | `gui/app_service.py`, `gui/dashboard_panel.py`, `gui/main_window.py`, `gui/execution_panel.py` | Implemented | RN-GUI-1.2.0-20260519, RN-GUI-1.4.0-20260826 |
| FO-GUI-013 | SRD-GUI-013.015 | — | MD-GUI-004.001.M01 | — | `gui/execution_panel.py`, `gui/strategy_builder_dialog.py` | Implemented | RN-EXE-1.9.0-20260527 |
| FO-GUI-014 | SRD-GUI-014.001, .003–.005, .008–.012 | DD-GUI-014.002.D01 | MD-GUI-014.001.M01 | UT-GUI-014.001.M01.T01–T15 | `gui/active_cycles_panel.py` | Implemented | RN-EXE-1.10.0-20260527, RN-GUI-1.3.0-20260602 |
| FO-GUI-014 | SRD-GUI-014.002, .004, .013 | DD-GUI-014.002.D01 | MD-GUI-014.001.M02 | UT-GUI-014.001.M02.T01–T11 | `gui/active_cycles_model.py` | Implemented | RN-EXE-1.10.0-20260527, RN-GUI-1.3.0-20260602 |
| FO-GUI-014 | SRD-GUI-014.007 | DD-GUI-014.007.D01 | MD-GUI-014.001.M03 | UT-GUI-014.001.M03.T09–T10 | `gui/risk_editor_widget.py` | Implemented | RN-GUI-1.3.1-20260625 |
| FO-GUI-014 | SRD-GUI-014.014 | — | MD-GUI-004.001.M01 | — | `gui/app_service.py`, `gui/execution_panel.py` | Implemented | Pending |
| FO-GUI-014 | SRD-GUI-014.015 | — | MD-GUI-014.001.M01 | — | `gui/active_cycles_panel.py` | Implemented | RN-EXE-1.22.0-20260610 |
| FO-GUI-013 | SRD-GUI-013.016–.021 | DD-GUI-013.016.D01 | MD-GUI-013.001.M01, MD-GUI-004.001.M01, MD-GUI-004.001.M02 | UT-GUI-013.016–.018.M01.T01–08, .020.M01.T01, .021.M01.T01–03, .019.M02.T01–02, .020.M02.T02 | `gui/strategy_builder_dialog.py`, `gui/execution_panel.py`, `gui/strategy_table_model.py` | Implemented | RN-GUI-1.5.0-20260917 (.020/.021 pending RN) |
| FO-GUI-013 | SRD-GUI-013.022 | DD-EXE-011.026.D01 | MD-GUI-013.001.M01 | UT-GUI-013.022.M01.T01–T02 (2 tests, Pass) | `gui/strategy_builder_dialog.py` | Implemented | RN-EXE-1.39.0-20261031 |
| FO-GUI-013 | SRD-GUI-013.023 | DD-GUI v1.29.0 note | MD-GUI-013.001.M01 | UT-GUI-013.023.M01.T01 | `gui/strategy_builder_dialog.py` | Implemented | RN-GUI-1.54.0-20261102 |
| FO-GUI-013 | SRD-GUI-013.024 | DD-EXE-011.027.D01 | MD-GUI-013.001.M01 | UT-GUI-013.024.M01.T01–T02 (2 tests, Pass) | `gui/strategy_builder_dialog.py` | Implemented | RN-EXE-1.41.0-20261102 |
| FO-GUI-014 | SRD-GUI-014.016–.018 | DD-GUI-014.016.D01 | MD-GUI-014.001.M01–M03 | UT-GUI-014.016.M02.T01–03, .017.M01.T01–05, .018.M03.T01–04 | `gui/active_cycles_model.py`, `gui/active_cycles_panel.py`, `gui/risk_editor_widget.py` | Implemented | RN-GUI-1.5.0-20260917 |
| FO-GUI-002 | SRD-GUI-002.005 (Reopen; fix conforms to SRD-EXE-018.003) | — | MD-GUI-004.001.M01 | UT-GUI-002.005.M01.T01–T03 | `gui/app_service.py` | Implemented (ISS-GUI-0002 fix only; SRD stays Reopen) | RN-GUI-1.5.1-20261016 |
| FO-GUI-015 | SRD-GUI-015.002 | DD-GUI-015.001.D01 | MD-GUI-015.002.M01 | UT-GUI-015.002.M01.T01–T02 | `gui/frameless_dialog.py` | Implemented | RN-GUI-1.6.0-20261022 |
| FO-GUI-015 | SRD-GUI-015.008, .009, .012 | DD-GUI-015.001.D01 | MD-GUI-015.008.M02 | UT-GUI-015.008.M02.T01–T03, .009.M02.T01–T03, .012.M02.T01–T02 | `gui/indicator_rule_model.py` | Implemented | RN-GUI-1.6.0-20261022 |
| FO-GUI-015 | SRD-GUI-015.009, .010, .012, .015 | DD-GUI-015.001.D01 | MD-GUI-015.009.M03 | UT-GUI-015.009.M03.T01, .010.M03.T01–T02, .012.M03.T01–T03, .015.M03.T01–T02 | `gui/indicator_rule_delegates.py` | Implemented | RN-GUI-1.6.0-20261022 |
| FO-GUI-015 | SRD-GUI-015.003–.006 | DD-GUI-015.001.D01 | MD-GUI-015.003.M04 | UT-GUI-015.003.M04.T01–T03, .004.M04.T01–T02, .005.M04.T01–T02, .006.M04.T01–T02 | `gui/indicator_library_model.py` | Implemented | RN-GUI-1.6.0-20261022 |
| FO-GUI-015 | SRD-GUI-015.011 | DD-GUI-015.001.D01 | MD-GUI-015.011.M05 | UT-GUI-015.011.M05.T01–T02 | `gui/indicator_params_dialog.py` | Implemented | RN-GUI-1.6.0-20261022 |
| FO-GUI-015 | SRD-GUI-015.001, .007, .013 | DD-GUI-015.001.D01 | MD-GUI-015.001.M06 | UT-GUI-015.001.M06.T01–T02, .007.M06.T01–T03, .013.M06.T01–T03 | `gui/indicator_rules_dialog.py` | Implemented | RN-GUI-1.6.0-20261022 |
| FO-GUI-015 | SRD-GUI-015.014 | DD-GUI-015.001.D01 | MD-GUI-003.001.M01 | UT-GUI-015.014.M01.T01–T02 | `gui/screener_panel.py` | Implemented | RN-GUI-1.6.0-20261022 |
| FO-GUI-016 | SRD-GUI-016.004, .008 | DD-GUI-016.001.D01 | MD-GUI-016.004.M07 | UT-GUI-016.004.M07.T01–T02, .008.M07.T01–T02 | `gui/pattern_rule_model.py` | Implemented | RN-GUI-1.7.0-20261022 |
| FO-GUI-016 | SRD-GUI-016.001, .003, .006, .007, .009, .011 | DD-GUI-016.001.D01 | MD-GUI-016.001.M08 | UT-GUI-016.001.M08.T01–T02, .003.M08.T01–T03, .006.M08.T01, .007.M08.T01–T03, .009.M08.T01–T03, .011.M08.T01–T02 | `gui/price_action_rules_dialog.py` | Implemented | RN-GUI-1.7.0-20261022 |
| FO-GUI-016 | SRD-GUI-016.002 | DD-GUI-016.001.D01 | MD-GUI-015.003.M04 | UT-GUI-016.002.M04.T01–T02 | `gui/indicator_library_model.py` | Implemented | RN-GUI-1.7.0-20261022 |
| FO-GUI-016 | SRD-GUI-016.005 | DD-GUI-016.001.D01 | MD-GUI-015.009.M03 | UT-GUI-016.005.M03.T01–T02 | `gui/indicator_rule_delegates.py`, `gui/indicator_rule_model.py` | Implemented | RN-GUI-1.7.0-20261022 |
| FO-GUI-016 | SRD-GUI-016.006 | DD-GUI-016.001.D01 | MD-GUI-015.011.M05 | UT-GUI-016.006.M05.T01 | `gui/indicator_params_dialog.py` | Implemented | RN-GUI-1.7.0-20261022 |
| FO-GUI-016 | SRD-GUI-016.010 | DD-GUI-016.001.D01 | MD-GUI-003.001.M01 | UT-GUI-016.010.M01.T01–T02 | `gui/screener_panel.py` | Implemented | RN-GUI-1.7.0-20261022 |
| FO-GUI-017 | SRD-GUI-017.001–005 | DD-GUI-017.001.D01 | MD-GUI-017.001.M02, MD-GUI-017.003.M01 | UT-GUI-017.* (10 tests) | `gui/theme.py`, `gui/icons.py`, `gui/main_window.py`, `gui/dashboard_panel.py`, `gui/screener_panel.py`, `gui/execution_panel.py`, `gui/settings_panel.py`, `gui/log_viewer_panel.py`, `gui/scheduler_dialog.py`, `gui/indicator_rules_dialog.py`, `gui/price_action_rules_dialog.py` | Implemented | RN-GUI-1.9.0-20261023 |
| FO-GUI-018 | SRD-GUI-018.001–012 | DD-GUI-018.001.D01 | MD-GUI-018.001.M01, MD-GUI-018.006.M02, MD-GUI-018.005.M03, MD-GUI-018.008.M04, MD-GUI-018.012.M05 | UT-GUI-018.* (19 tests) | `gui/sidebar.py`, `gui/reveal.py`, `gui/main_window.py`, `gui/theme.py` | Implemented | RN-GUI-1.10.0-20261023, RN-GUI-1.16.0-20261023 |
| FO-GUI-019 | SRD-GUI-019.001–008 | DD-GUI-019.001.D01 | MD-GUI-019.001.M01, MD-GUI-019.006.M02, MD-GUI-019.002.M03 | UT-GUI-019.* (10 tests) | `gui/side_panels.py`, `gui/dashboard_panel.py`, `gui/main_window.py` | Implemented | RN-GUI-1.11.0-20261023 |
| FO-GUI-019 | SRD-GUI-019.009 | — | MD-GUI-019.009.M03 | UT-GUI-019.009.M03.T01–T02 | `gui/main_window.py` | Implemented | RN-GUI-1.37.3-20261027 |
| FO-GUI-019 | SRD-GUI-019.010 | — | MD-GUI-019.010.M03 | UT-GUI-019.010.M03.T01–T02 | `gui/main_window.py` | Implemented | RN-GUI-1.56.4-20261103 |
| FO-GUI-020 | SRD-GUI-020.001–005 | DD-GUI-020.001.D01 | MD-GUI-020.001.M01 | UT-GUI-020.001.M01.T01–T02, .002.M01.T01, .003.M01.T01–T02, .004.M01.T01 | `gui/chart_workspace.py`, `gui/chart_panel.py`, `gui/screener_panel.py`, `gui/main_window.py` | Implemented | RN-GUI-1.12.0-20261023 |
| FO-GUI-021 | SRD-GUI-021.001–004 | DD-GUI-021.001.D01 | MD-GUI-021.001.M01 | UT-GUI-021.001.M01.T01–T02, .002.M01.T01–T02, .003.M01.T01, .003.M02.T01, .004.M01.T01–T04, .004.M02.T01–T02 | `gui/settings_panel.py`, `gui/theme.py`, `gui/side_panels.py`, `gui/main_window.py` | Implemented | RN-GUI-1.15.0-20261023 |
| FO-GUI-022 | SRD-GUI-022.001–012 | DD-GUI-022.001.D01 | MD-GUI-022.001.M01, MD-GUI-003.001.M01 | UT-GUI-022.001.M01.T01–T02, .002.M01.T01–T05, .003.M01.T01–T02, .004.M01.T01, .005.M01.T01, .006.M01.T01, .007.M01.T01–T02, .008.M01.T01, .009.M01.T01–T02, .010.M01.T01–T02, .011.M01.T01–T07 | `gui/screener_views.py`, `gui/screener_panel.py`, `gui/theme.py`, `gui/chart_panel.py`, `gui/ai_transcript_panel.py`, `assets/icons` | Implemented | RN-GUI-1.18.0-20261023, RN-GUI-1.57.0-20261103 |
| FO-GUI-023 | SRD-GUI-023.001–004 | DD-GUI-023.001.D01 | MD-GUI-023.001.M01, MD-GUI-001.001.M01, MD-GUI-003.001.M01 | UT-GUI-023.001.M01.T01–T02 | `gui/cards.py`, `gui/main_window.py`, `gui/screener_panel.py`, `gui/theme.py` | Implemented | RN-GUI-1.19.0-20261023 |
| FO-GUI-024 | SRD-GUI-024.001–008 | DD-GUI-024.001.D01 | MD-GUI-024.001.M01, .002.M02, .003.M03, .004.M04, .006.M05, .008.M06 | UT-GUI-024.001.M01.T01–T02, .002.M02.T01–T04, .003.M03.T01–T02, .004–.005.M04.T01–T02, .006.M05.T01–T04, .008.M06.T01–T03; UT-GUI-004.001.M01.T06–T07 (moved) | `gui/execution_header.py`, `gui/execution_watchlist.py`, `gui/strategies_pane.py`, `gui/strategy_pnl_chart.py`, `gui/active_cycles_{panel,model}.py`, `gui/execution_panel.py`, `gui/theme.py` | Implemented | RN-GUI-1.20.0–1.23.0 |
| FO-GUI-025 | SRD-GUI-025.001–020 | DD-GUI-025.001.D01 | MD-GUI-025.003.M01, .001.M02, .013.M03, .016.M04, .019.M05 | UT-GUI-025.004.M01.T01–T03, .001.M01.T01, .005.M01.T01–T02, .001.M02.T01, .002.M02.T01, .006.M02.T01–T02, .008.M02.T01–T03, .009–.011.M02.T01–T02, .012.M01.T01–T03, .013.M03.T01–T04, .015.M03.T01–T03, .013.M02.T01, .014.M02.T01, .015.M02.T01, .016.M04.T01–T02, .018.M02.T01, .019.M05.T01–T06, .019.M02.T01, .020.M05.T01–T03, .020.M01.T01–T03, .020.M02.T01–T03 | `gui/watchlist_store.py`, `gui/dashboard_tiles.py`, `gui/performance_band.py`, `gui/dashboard_panel.py`, `gui/main_window.py`, `gui/position_table_model.py`, `assets/icons` | Implemented | RN-GUI-1.25.0-20261024, RN-GUI-1.26.0-20261024, RN-GUI-1.27.0-20261024, RN-GUI-1.28.0-20261024, RN-GUI-1.35.1-20261026, RN-GUI-1.35.2-20261026, RN-GUI-1.36.0-20261026 |
| FO-GUI-026 | SRD-GUI-026.001–013 | DD-GUI-026.001.D01, DD-GUI-026.011.D01 | MD-GUI-026.001.M01, .002.M02, .005.M03, .012.M04 | UT-GUI-026.001.M01.T01–T04, .002.M02.T01–T04, .003.M01.T01–T02, .004.M01.T01–T02, .005.M03.T01–T02, .005.M01.T04, .006.M03.T01–T04, .006.M01.T05–T06, .007.M03.T01–T02, .007.M01.T03, .008.M03.T01–T02, .008.M01.T03, .009.M03.T01–T02, .010.M01.T01–T02, .011.M04.T05, .011.M01.T01–T02, .012.M01.T05, .012.M04.T01–T04, .013.M02.T01–T04, .013.M01.T01–T04 | `gui/chart_workspace.py`, `gui/chart_source_list.py`, `gui/chart_inspector.py`, `gui/chart_drawings.py`, `gui/chart_panel.py`, `gui/app_service.py`, `gui/main_window.py`, `data/models.py` | Implemented | RN-GUI-1.29.0-20261024, RN-GUI-1.30.0-20261024, RN-GUI-1.31.0-20261024, RN-GUI-1.37.0-20261026, RN-GUI-1.56.6-20261103 |
| FO-GUI-027 | SRD-GUI-027.001–013 | DD-GUI-027.001.D01 | MD-GUI-027.001.M01, .004.M02, .004.M03, .005.M04, .009.M05, .005.M07; MD-GUI-019.001.M01 | UT-GUI-027.001.M01.T01–T02, .003.M01.T01–T02, .004.M02.T01, .004.M03.T01, .002.M04.T01, .005.M04.T01, .007.M06.T01, .008.M02.T01–T02, .009.M05.T01, .010.M04.T01–T02, .011.M04.T01–T02, .012.M04.T01–T02, .013.M04.T01, .005.M07.T01–T04, .005.M02.T01 | `gui/settings_dialog.py`, `gui/settings_panel.py`, `gui/sidebar.py`, `gui/main_window.py`, `gui/side_panels.py`, `gui/execution_header.py`, `gui/update_popup.py` | Implemented | RN-GUI-1.32.0-20261025, RN-GUI-1.33.0-20261025, RN-GUI-1.56.6-20261103 |
| FO-GUI-028 | SRD-GUI-028.001–005 | DD-GUI-028.001.D01 | MD-GUI-028.001.M01 | UT-GUI-028.001.M01.T01–T03, .002.M01.T01–T02, .003.M01.T01, .004.M01.T01, .005.M01.T01; UT-GUI-021.004.M01.T04 | `gui/settings_panel.py`, `gui/theme.py` | Implemented | RN-GUI-1.34.0-20261025 |
| FO-GUI-029 | SRD-GUI-029.001–006 | DD-GUI-029.001.D01 | MD-GUI-029.001.M01, .004.M02 | UT-GUI-029.001.M01.T01, .002.M01.T01–T02, .004.M01.T01–T02, .005.M01.T01, .006.M01.T01, .002.M02.T01, .004.M02.T01–T02 | `gui/scheduler_table.py`, `gui/scheduler_dialog.py`, `gui/scheduler_store.py`, `gui/settings_panel.py`, `gui/theme.py` | Implemented | RN-GUI-1.35.0-20261025 |
| FO-GUI-030 | SRD-GUI-030.001–010 | DD-GUI-030.001.D01 | MD-GUI-030.001.M01, .004.M02, .006.M03, .004.M04, .007.M05, .008.M06 | UT-GUI-030.* (20 tests, Pass) | `gui/backtest_data_panel.py`, `gui/app_service.py`, `gui/settings_panel.py`, `gui/system_store.py`, `gui/main_window.py` | Implemented | RN-GUI-1.38.0-20261028, RN-GUI-1.38.1-20261029 |
| FO-GUI-030 | SRD-GUI-030.012 | DD-GUI-030.001.D01 | MD-GUI-030.012.M02, .012.M06 | UT-GUI-030.012.M02.T01, .M06.T01 (2 tests, Pass) | `gui/app_service.py`, `gui/settings_panel.py` | Implemented | RN-GUI-1.58.0-20261104 |
| FO-GUI-030 | SRD-GUI-030.011 (ISS-BKT-0002) | DD-GUI-030.001.D01 | MD-GUI-030.011.M02 | UT-GUI-030.011.M02.T01 (1 test, Pass) | `gui/app_service.py`, `gui/settings_panel.py` | Implemented | RN-BKT-1.13.0-20261104 |
| FO-GUI-031 | SRD-GUI-031.001–.004, .010–.012, .020–.023, .030–.034 | DD-GUI-031.001.D01 | MD-GUI-031.001.M01, .002.M02, .003.M03 | UT-GUI-031.* (17 tests, Pass) | `gui/main_window.py`, `gui/backtest_builder.py`, `gui/backtest_workspace.py` | Implemented (Phase 0–3) | RN-GUI-1.39.0-20261029, RN-GUI-1.40.0-20261029, RN-GUI-1.41.0-20261029 |
| FO-GUI-031 | SRD-GUI-031.013 | DD-GUI-031.001.D01 | MD-GUI-031.003.M03 | UT-GUI-031.013.M03.T01 (1 test, Pass) | `gui/backtest_workspace.py` | Implemented | RN-GUI-1.42.0-20261029 |
| FO-GUI-031 | SRD-GUI-031.078 | None (minimal GUI docs) | MD-GUI-031.002.M02 | UT-GUI-031.078.M02.T01 (Pass) | `gui/backtest_builder.py` | Implemented | RN-GUI-1.50.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.076–.077 | None (minimal GUI docs) | MD-GUI-031.052.M06, MD-GUI-031.050.M05, MD-GUI-031.003.M03 | UT-GUI-031.052.M06.T03–T05, UT-GUI-031.052.M03.T01 (Pass) | `gui/backtest_trade_chart.py`, `gui/backtest_dock.py`, `gui/backtest_workspace.py` | Implemented | RN-GUI-1.50.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.079–.081 | None (minimal GUI docs) | MD-GUI-031.040.M04, MD-GUI-031.080.M13, MD-GUI-031.003.M03 | UT-GUI-031.079.M04.T01–T02, UT-GUI-031.080.M13.T01, UT-GUI-031.081.M13.T01–T03 (Pass) | `gui/backtest_report_view.py`, `gui/backtest_report_chart.py`, `gui/backtest_workspace.py` | Implemented | RN-GUI-1.53.0-20261031 |
| FO-GUI-031 | SRD-GUI-031.068 | None (minimal GUI docs) | MD-GUI-031.003.M03 | UT-GUI-031.068.M03.T01 (Pass) | `gui/backtest_workspace.py` | Implemented | RN-GUI-1.52.0-20261031 |
| FO-GUI-031 | SRD-GUI-031.062–.067 | None (minimal GUI docs) | MD-GUI-031.062.M12, MD-GUI-031.040.M04, MD-GUI-031.053.M07, MD-GUI-031.003.M03 | UT-GUI-031.062–.067 (11 tests, Pass) | `gui/backtest_breakdown.py`, `gui/backtest_report_view.py`, `gui/backtest_trade_list.py`, `gui/backtest_workspace.py`, `gui/theme.py` | Implemented | RN-GUI-1.51.0-20261031 |
| FO-GUI-031 | SRD-GUI-031.075 | None (minimal GUI docs) | MD-GUI-031.075.M11, MD-GUI-031.003.M03 | UT-GUI-031.075.M11.T01 (Pass) | `gui/backtest_header.py`, `gui/backtest_workspace.py`, `gui/theme.py` | Implemented | RN-GUI-1.50.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.070–.074 | None (minimal GUI docs) | MD-GUI-031.071.M10, MD-GUI-031.002.M02, MD-GUI-031.003.M03 | UT-GUI-031.070–.074 (8 tests, Pass) | `gui/backtest_setup.py`, `gui/backtest_builder.py`, `gui/backtest_workspace.py` | Implemented | RN-GUI-1.49.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.060–.061 | None (minimal GUI docs) | MD-GUI-031.002.M02, MD-GUI-031.003.M03 | UT-GUI-031.060–.061 (3 tests, Pass) | `gui/backtest_builder.py`, `gui/backtest_workspace.py`, `gui/screener_panel.py`, `gui/main_window.py` | Implemented (Phase 5) | RN-GUI-1.48.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.046–.048 | None (minimal GUI docs) | MD-GUI-031.040.M04, MD-GUI-031.003.M03 | UT-GUI-031.046–.048.M04 (3 tests, Pass) | `gui/backtest_report_view.py`, `gui/backtest_workspace.py` | Implemented (Phase 4b) | RN-GUI-1.47.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.055 | None (minimal GUI docs) | MD-GUI-031.055.M09, MD-GUI-031.003.M03 | UT-GUI-031.055 (8 tests: M09 ×6, M03 ×2, Pass) | `gui/backtest_reports.py`, `gui/backtest_workspace.py`, `gui/backtest_dock.py` | Implemented (redesign phase 3; multi-delete fix) | RN-GUI-1.46.0-20261030, RN-GUI-1.50.1-20261031 |
| FO-GUI-031 | SRD-GUI-031.053–.054 | None (minimal GUI docs) | MD-GUI-031.053.M07, MD-GUI-031.054.M08, MD-GUI-031.003.M03 | UT-GUI-031.053–.054 (8 tests: M07 ×4, M08 ×2, M03 ×2, Pass) | `gui/backtest_trade_list.py`, `gui/backtest_use_charts.py`, `gui/backtest_workspace.py` | Implemented (redesign phase 2) | RN-GUI-1.45.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.050–.052 | None (minimal GUI docs) | MD-GUI-031.050.M05, MD-GUI-031.052.M06, MD-GUI-031.003.M03 | UT-GUI-031.050–.052 (8 tests: M05 ×2, M06 ×2, M03 ×4, Pass) | `gui/backtest_dock.py`, `gui/backtest_trade_chart.py`, `gui/backtest_workspace.py` | Implemented (redesign phase 1) | RN-GUI-1.44.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.040–.045 | None yet (Phase 4a view only) | MD-GUI-031.040.M04, MD-GUI-031.003.M03 | UT-GUI-031.040–.045 (12 tests: M04 ×10, M03 ×2, Pass) | `gui/backtest_report_view.py`, `gui/backtest_workspace.py` | Implemented (Phase 4a) | RN-GUI-1.43.0-20261029 |
| FO-GUI-031 | SRD-GUI-031.082–.084 | DD-GUI-031.001.D01 | MD-GUI-031.055.M09, MD-GUI-031.083.M14, MD-GUI-031.003.M03 | UT-GUI-031.082.M09.T01, UT-GUI-031.083.M14.T01, UT-GUI-031.084.M03.T01 | `gui/backtest_reports.py`, `core/dates.py`, `gui/backtest_workspace.py` | Implemented | RN-GUI-1.54.0-20261102 |
| FO-GUI-031 | SRD-GUI-031.085 | None (minimal GUI docs) | MD-GUI-031.003.M03 | UT-GUI-031.085.M01.T01, .M03.T01 | `gui/backtest_builder.py`, `gui/backtest_workspace.py`, `gui/backtest_reports.py` | Implemented | Pending |
| FO-GUI-031 | SRD-GUI-031.086 | None (minimal GUI docs) | MD-GUI-031.002.M02 | UT-GUI-031.086.M02.T01 (Pass) | `gui/backtest_builder.py`, `gui/backtest_workspace.py` | Implemented | RN-GUI-1.55.0-20261103 |
| FO-GUI-031 | SRD-GUI-031.087 | None (minimal GUI docs) | MD-GUI-031.002.M02, MD-GUI-031.003.M03 | UT-GUI-031.087.M02.T01–T02 (2 tests, Pass) | `gui/backtest_builder.py`, `gui/backtest_workspace.py` | Implemented | RN-BKT-1.12.0-20261103 |
| FO-GUI-032 | SRD-GUI-032.001 | DD-GUI-032.001.D01 | MD-GUI-032.001.M01 | UT-GUI-032.001.M01.T01 (Pass) | `gui/execution_panel.py`, `gui/theme.py` | Implemented | RN-GUI-1.56.0-20261103 |
| FO-GUI-032 | SRD-GUI-032.002 | DD-GUI-032.001.D01 | MD-GUI-032.003.M03 | UT-GUI-032.002.M03.T01–T02 (Pass) | `gui/strategies_pane.py`, `assets/icons/table.svg` | Implemented | RN-GUI-1.56.0-20261103 |
| FO-GUI-032 | SRD-GUI-032.003 | DD-GUI-032.001.D01 | MD-GUI-032.002.M02 | UT-GUI-032.003.M02.T01 (Pass); UT-GUI-032.003.M03.T01 (Pass) | `gui/strategies_views.py`, `gui/strategies_pane.py`, `gui/theme.py` | Implemented | RN-GUI-1.56.0-20261103 |
| FO-GUI-032 | SRD-GUI-032.004 | DD-GUI-032.001.D01 | MD-GUI-032.002.M02 | UT-GUI-032.004.M02.T01 (Pass) | `gui/strategies_views.py`, `gui/theme.py` | Implemented | RN-GUI-1.56.0-20261103 |
| FO-GUI-032 | SRD-GUI-032.005 | DD-GUI-032.001.D01 | MD-GUI-032.003.M03 | UT-GUI-032.005.M03.T01–T02 (Pass) | `gui/strategies_pane.py`, `gui/strategies_views.py`, `gui/theme.py` | Implemented | RN-GUI-1.56.0-20261103 |
| FO-GUI-032 | SRD-GUI-032.006 | DD-GUI-032.001.D01 | MD-GUI-032.003.M03 | UT-GUI-032.006.M03.T01–T02 (Pass) | `gui/strategies_pane.py`, `gui/theme.py` | Implemented | RN-GUI-1.56.0-20261103 |
| FO-GUI-032 | SRD-GUI-032.007 | DD-GUI-032.001.D01 | MD-GUI-032.003.M03 | UT-GUI-032.007.M03.T01 (Pass) | `gui/strategies_pane.py` | Implemented | RN-GUI-1.56.0-20261103 |
| FO-GUI-032 | SRD-GUI-032.008 | DD-GUI-032.001.D01 | MD-GUI-032.002.M02 | UT-GUI-032.008.M02.T01 (Pass) | `gui/strategies_views.py`, `gui/theme.py` | Implemented | RN-GUI-1.56.0-20261103 |
| FO-GUI-033 | SRD-GUI-033.001 | DD-GUI-033.001.D01 | MD-GUI-033.001.M01 | UT-GUI-033.001.M01.T01 (Pass) | `gui/ai_settings_block.py` | Implemented | RN-GUI-1.59.0-20261105 |
| FO-GUI-033 | SRD-GUI-033.002 | DD-GUI-033.001.D01 | MD-GUI-033.001.M01 | UT-GUI-033.002.M01.T01–T02 (Pass) | `gui/ai_settings_block.py` | Implemented | RN-GUI-1.59.0-20261105 |
| FO-GUI-033 | SRD-GUI-033.003 | DD-GUI-033.001.D01 | MD-GUI-033.001.M01 | UT-GUI-033.003.M01.T01–T02 (Pass) | `gui/ai_settings_block.py` | Implemented | RN-GUI-1.59.0-20261105 |
| FO-GUI-033 | SRD-GUI-033.004 | DD-GUI-033.001.D01 | MD-GUI-033.001.M01, MD-GUI-033.004.M02 | UT-GUI-033.004.M01.T01, UT-GUI-033.004.M02.T01 (Pass) | `gui/ai_settings_block.py`, `gui/settings_panel.py`, `gui/settings_dialog.py` | Implemented | RN-GUI-1.59.0-20261105 |
| FO-GUI-033 | SRD-GUI-033.005 | DD-GUI-033.001.D01 | MD-GUI-033.004.M02, MD-GUI-033.005.M03 | UT-GUI-033.005.M02.T01–T02 (Pass) | `gui/settings_panel.py`, `gui/user_store.py`, `data/models.py` | Implemented | RN-GUI-1.59.0-20261105 |
| FO-GUI-033 | SRD-GUI-033.006 | DD-GUI-033.001.D01 | MD-GUI-033.001.M01, MD-GUI-033.004.M02 | UT-GUI-033.006.M01.T01, UT-GUI-033.006.M02.T01 (Pass) | `gui/ai_settings_block.py`, `gui/settings_panel.py` | Implemented | RN-GUI-1.59.0-20261105 |
| FO-GUI-033 | SRD-GUI-033.007 | DD-GUI-033.001.D01 | MD-GUI-033.001.M01 | UT-GUI-033.007.M01.T01–T02 (Pass) | `gui/ai_settings_block.py` | Removed (user, 2026-11-05) | RN-GUI-1.59.1-20261105 |
| FO-GUI-034 | SRD-GUI-034.001 | DD-GUI-034.001.D01 | MD-GUI-034.001.M01 | UT-GUI-034.001.M01.T01 (Pass) | `gui/main_window.py` | Implemented | RN-GUI-1.60.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.002 | DD-GUI-034.001.D01 | MD-GUI-034.002.M02 | UT-GUI-034.002.M02.T01 (Pass) | `gui/desk_control.py` | Implemented | RN-GUI-1.60.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.003 | DD-GUI-034.001.D01 | MD-GUI-034.002.M02, MD-GUI-034.003.M09 | UT-GUI-034.003.M02.T01–T04, UT-GUI-034.003.M09.T01 (Pass) | `gui/desk_control.py`, `core/desk_contract.py` | Implemented | RN-GUI-1.60.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.004 | DD-GUI-034.001.D01 | MD-GUI-034.004.M04 | UT-GUI-034.004.M04.T01–T03 (Pass) | `gui/market_floor.py`, `gui/floor_feed.py` | Implemented | RN-GUI-1.60.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.005 | DD-GUI-034.001.D01 | MD-GUI-034.005.M05 | UT-GUI-034.005.M05.T01–T09 (Pass) | `gui/floor_grid_model.py`, `gui/floor_grid.py` | Implemented | RN-GUI-1.60.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.006 | DD-GUI-034.001.D01 | MD-GUI-034.006.M06 | UT-GUI-034.006.M06.T01–T03 (Pass) | `gui/floor_panel.py`, `gui/floor_dialogs.py` | Implemented | RN-GUI-1.60.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.007 | DD-GUI-034.001.D01 | MD-GUI-034.006.M06 | UT-GUI-034.007.M06.T01–T02 (Pass) | `gui/floor_panel.py` | Implemented | RN-GUI-1.60.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.008 | DD-GUI-034.001.D01 | MD-GUI-034.008.M07 | UT-GUI-034.008.M07.T01–T09 (Pass) | `gui/floor_layouts.py` | Implemented | RN-GUI-1.60.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.009 | DD-GUI-034.001.D01 | MD-GUI-034.009.M08 | UT-GUI-034.009.M08.T01–T02 (Pass) | `gui/ai_desk.py`, `gui/ai_desk_sample.py`, `gui/ai_desk_sections.py`, `gui/ai_desk_sections2.py`, `gui/ai_desk_sections3.py` | Implemented | RN-GUI-1.60.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.010 | DD-GUI-034.001.D01 | MD-GUI-034.010.M03 | UT-GUI-034.010.M03.T01–T02 (Pass) | `gui/floor_sample.py`, `core/desk_contract.py` | Implemented | RN-GUI-1.60.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.011 | — | MD-GUI-034.011.M10 | UT-GUI-034.011.M10.T01–T03 (Pass) | `core/desk_floor.py`, `gui/market_floor.py` | Implemented | RN-MKT-0.1.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.012 | — | MD-GUI-034.012.M11 | UT-GUI-034.012.M11.T01–T02 (Pass) | `core/desk_floor.py` | Implemented | RN-MKT-0.2.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.013 | — | MD-GUI-034.013.M12 | UT-GUI-034.013.M12.T01–T02 (Pass) | `core/desk_floor.py`, `gui/floor_panel.py` | Implemented | RN-MKT-0.3.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.014 | — | MD-GUI-034.014.M13 | UT-GUI-034.014.M13.T01–T02 (Pass) | `core/desk_floor.py` | Implemented | RN-MKT-0.4.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.015–.017 | — | MD-GUI-034.015.M14, .016.M15, .017.M16 | UT-GUI-034.015–.017 (Pass) | `core/desk_floor.py`, `gui/floor_feed.py`, `gui/market_floor.py`, `gui/ai_desk_settings.py`, `gui/ai_desk.py`, `gui/ai_desk_sections3.py` | Implemented | RN-DSK-0.2.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.018 | — | MD-GUI-034.018.M17 | UT-GUI-034.018.M17.T01–T03 (3, Pass) | `core/desk_floor.py` | Implemented | RN-MKT-0.7.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.019–.020 | — | MD-GUI-034.018.M17 | UT-GUI-034.019.M17.T01–T02, UT-GUI-034.020.M17.T01–T03 (5, Pass) | `core/desk_floor.py` | Implemented | RN-MKT-0.7.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.021 | — | MD-GUI-034.021.M18 | UT-GUI-034.021.M18.T01–T02 (2, Pass) | `gui/floor_layouts.py` | Implemented | RN-MKT-0.7.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.022–.026 | DD-MKT-007.001.D01 | MD-GUI-034.022.M19, .024.M20 | UT-GUI-034.022.M19.T01–T04, .023.M19.T01, .024.M20.T01, .025.M20.T01–T02, .026.M19.T01 (9, Pass) | `gui/ai_desk_pages.py`, `gui/sealed_view.py`, `core/desk_floor.py`, `gui/ai_desk.py` | Implemented | RN-MKT-0.8.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.027–.033 | DD-DSK-006.001.D01 | MD-GUI-034.027.M21, .032.M22, .033.M23 | UT-GUI-034.027–.033 (13, Pass) | `gui/ai_desk_hiring.py`, `gui/ai_desk.py`, `gui/ai_desk_sections.py`, `gui/ai_desk_sections3.py`, `gui/ai_desk_settings.py`, `core/desk_floor.py` | Implemented | RN-DSK-0.4.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.034–.036 | DD-MKT-008.001.D01 | MD-GUI-034.034.M24 | UT-GUI-034.034.M24.T01–T03, .035.M24.T01–T04, .036.M24.T01 (Pass) | `gui/ai_desk_hiring.py`, `gui/ai_desk.py`, `gui/main_window.py` | Implemented | RN-MKT-0.9.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.037–.038 | DD-MKT-009.001.D01 | MD-GUI-034.037.M25 | UT-GUI-034.037.M25.T01–T02, .038.M25.T01–T03 (Pass) | `gui/ai_desk_results.py`, `gui/ai_desk.py` | Implemented | RN-MKT-0.10.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.039–.041 | DD-MKT-010.001.D01 | MD-GUI-034.039.M26 | UT-GUI-034.039.M26.T01–T02, .040.M26.T01–T02, .041.M26.T01–T03 (Pass) | `gui/ai_desk_chat.py`, `gui/ai_desk_sections.py`, `gui/ai_desk.py` | Implemented | RN-MKT-0.11.0-20261106 |
| FO-GUI-034 | SRD-GUI-034.042–.044 | DD-MKT-011.001.D01 | MD-GUI-034.042.M37, MD-GUI-034.043.M38 | UT-GUI-034.042.M37.T01–T02, .043.M38.T01–T03, .044.M38.T01–T02 (7, Pass) | `gui/floor_dialogs.py`, `gui/market_floor.py`, `gui/floor_feed.py`, `gui/ai_desk_hiring.py`, `core/desk_feed.py` | Implemented | RN-MKT-0.12.0-20261110 |
| FO-GUI-034 | SRD-GUI-034.045–.052 | DD-GUI-034.045.D01 | MD-GUI-034.045.M28, MD-GUI-034.047.M27, MD-GUI-034.047.M29, MD-GUI-034.052.M30 | UT-GUI-034.045.M28.T01–T02, .046.M28.T01–T02, .047.M29.T01, .047.M27.T01, .048.M27.T01, .049.M27.T01, .050.M27.T01, .051.M27.T01, .052.M30.T01–T02 (Pass) | `gui/floor_charts.py`, `gui/floor_panel.py`, `gui/market_floor.py`, `gui/floor_layouts.py`, `gui/floor_sample.py`, `core/desk_floor.py` | Implemented | RN-GUI-1.10.0-20261107 |
| FO-GUI-034 | SRD-GUI-034.053–.058 | DD-GUI-034.053.D01 | MD-GUI-034.053.M31, MD-GUI-034.054.M32 | UT-GUI-034.053.M31.T01, .054.M32.T01–T02, .055.M31.T01, .056.M31.T01–T02, .057.M31.T01, .058.M31.T01 (Pass) | `gui/floor_feed.py`, `core/desk_feed.py`, `gui/market_floor.py`, `gui/main_window.py`, `gui/floor_sample.py`, `core/desk_floor.py`, `gui/ai_desk_hiring.py` | Implemented | RN-GUI-1.11.0-20261107 |
| FO-GUI-034 | SRD-GUI-034.059–.064 | DD-GUI-034.059.D01 | MD-GUI-034.059.M33, MD-GUI-034.060.M34, MD-GUI-034.061.M35, MD-GUI-034.062.M36 | UT-GUI-034.059.M33.T01–T02, .060.M34.T01, .060.M33.T01–T02, .061.M35.T01, .062.M36.T01, .063.M36.T01, .064.M36.T01 (Pass); reopened .034–.036 retested as cards (UT-GUI-034.034–.036.M24, Pass) | `gui/ai_desk.py`, `core/desk_overview.py`, `gui/ai_desk_chat.py`, `gui/ai_desk_hiring.py`, `gui/ai_desk_sections.py`, `gui/floor_feed.py`, `core/desk_feed.py`, `gui/main_window.py` | Implemented | RN-GUI-1.12.0-20261107 |
| FO-GUI-034 | SRD-GUI-034.065–.066 | DD-GUI-034.065.D01 | MD-GUI-034.065.M39, MD-GUI-034.060.M34, MD-GUI-034.002.M02, MD-GUI-034.027.M21 | UT-GUI-034.065.M34.T01, .065.M39.T01–T02, .066.M39.T01, .066.M21.T01; .060.M33.T01–T02 and .037–.038.M25 updated (Pass) | `gui/ai_desk_console.py`, `gui/ai_desk.py`, `gui/desk_control.py`, `gui/ai_desk_hiring.py`, `gui/ai_desk_pages.py`, `gui/ai_desk_results.py`, `gui/ai_desk_sections3.py`, `gui/ai_desk_settings.py`, `core/desk_overview.py`, `core/desk_contract.py` | Implemented | RN-GUI-1.16.0-20261110 |
| FO-GUI-035 | SRD-GUI-035.001–.012 | DD-GUI-035.001.D01 | MD-GUI-035.001.M01, MD-GUI-035.002.M02, MD-GUI-035.006.M03, MD-GUI-035.007.M04 | UT-GUI-035.002.M02.T01, .004.M02.T01–T02, .006.M02.T01, .009.M02.T01, .002.M01.T01, .008.M04.T01–T02, .006.M03.T01–T02, .007.M04.T01, .009.M01.T01, .010.M01.T01 (Pass) | `gui/ai_desk_team.py`, `gui/ai_desk_team_log.py`, `gui/ai_desk_team_pane.py`, `core/desk_team.py`, `gui/ai_desk.py`, `core/desk_feed.py` | Implemented | RN-GUI-1.13.0-20261110, RN-DSK-0.5.0-20261110 |

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
| `gui/settings_panel.py` | MD-GUI-006.001.M01 | SRD-GUI-006.001–005, SRD-GUI-006.018 | FO-GUI-006 |
| `gui/settings_panel.py` (ISS-GUI-0005 fix) | MD-GUI-006.001.M01 | SRD-GUI-006.002 | FO-GUI-006 |
| `tests/conftest.py` (ISS-GUI-0013 fix, UT-GUI-006.001.M01.T19) | MD-GUI-006.001.M01 | SRD-GUI-006.002 | FO-GUI-006 |
| `gui/scheduler_dialog.py` | MD-GUI-000.004 | SRD-GUI-006.005, SRD-GUI-006.017 | FO-GUI-006 |
| `gui/scheduler_store.py` | MD-GUI-000.003 | SRD-GUI-006.005, SRD-GUI-006.017 | FO-GUI-006 |
| `gui/log_viewer_panel.py` | MD-GUI-007.001.M01 | SRD-GUI-007.001–004 | FO-GUI-007 |
| `gui/log_bridge.py` | MD-GUI-007.001.M02 | SRD-GUI-007.001 | FO-GUI-007 |
| `gui/chart_panel.py` | MD-GUI-011.001.M01 | SRD-GUI-011.001–004 | FO-GUI-011 |
| `gui/app_service.py` (tick integration) | MD-GUI-004.001.M01 | SRD-GUI-012.001–007 | FO-GUI-012 |
| `gui/app_service.py` (tick watchdog) | MD-GUI-004.001.M01 | SRD-GUI-012.008–009 | FO-GUI-012 |
| `gui/app_service.py` (Trade History side) | MD-GUI-004.001.M01 | SRD-GUI-002.005 | FO-GUI-002 |
| `gui/settings_panel.py` (tick client id) | MD-GUI-006.001.M01 | SRD-GUI-012.007 | FO-GUI-012 |
| `gui/active_cycles_panel.py` | MD-GUI-014.001.M01 | SRD-GUI-014.001, .003–.005, .008–.012 | FO-GUI-014 |
| `gui/active_cycles_model.py` | MD-GUI-014.001.M02 | SRD-GUI-014.002, .004 | FO-GUI-014 |
| `gui/risk_editor_widget.py` | MD-GUI-014.001.M03 | SRD-GUI-014.007 | FO-GUI-014 |
| `gui/frameless_dialog.py` | MD-GUI-015.002.M01 | SRD-GUI-015.002 | FO-GUI-015 |
| `gui/indicator_rule_model.py` | MD-GUI-015.008.M02 | SRD-GUI-015.008 | FO-GUI-015 |
| `gui/indicator_rule_delegates.py` | MD-GUI-015.009.M03 | SRD-GUI-015.009 | FO-GUI-015 |
| `gui/indicator_library_model.py` | MD-GUI-015.003.M04 | SRD-GUI-015.003 | FO-GUI-015 |
| `gui/indicator_params_dialog.py` | MD-GUI-015.011.M05 | SRD-GUI-015.011 | FO-GUI-015 |
| `gui/indicator_rules_dialog.py` | MD-GUI-015.001.M06 | SRD-GUI-015.001 | FO-GUI-015 |
| `gui/pattern_rule_model.py` | MD-GUI-016.004.M07 | SRD-GUI-016.004 | FO-GUI-016 |
| `gui/price_action_rules_dialog.py` | MD-GUI-016.001.M08 | SRD-GUI-016.001 | FO-GUI-016 |
| `gui/settings_dialog.py` | MD-GUI-027.001.M01 | SRD-GUI-027.001–.003 | FO-GUI-027 |
| `gui/update_popup.py` | MD-GUI-027.005.M07 | SRD-GUI-027.005 | FO-GUI-027 |
| `gui/scheduler_table.py` | MD-GUI-029.001.M01 | SRD-GUI-029.001–.006 | FO-GUI-029 |
| `gui/backtest_data_panel.py` | MD-GUI-030.001.M01 | SRD-GUI-030.001–.006, .009, .010 | FO-GUI-030 |
| `gui/backtest_builder.py` | MD-GUI-031.002.M02 | SRD-GUI-031.002, .010, .020, .030 | FO-GUI-031 |
| `gui/backtest_workspace.py` | MD-GUI-031.003.M03 | SRD-GUI-031.003, .004, .011, .012, .021–.023, .031–.034, .040–.045, .050–.055 | FO-GUI-031 |
| `gui/backtest_dock.py` | MD-GUI-031.050.M05 | SRD-GUI-031.050 | FO-GUI-031 |
| `gui/backtest_trade_chart.py` | MD-GUI-031.052.M06 | SRD-GUI-031.052 | FO-GUI-031 |
| `gui/backtest_trade_list.py` | MD-GUI-031.053.M07 | SRD-GUI-031.053 | FO-GUI-031 |
| `gui/backtest_use_charts.py` | MD-GUI-031.054.M08 | SRD-GUI-031.054 | FO-GUI-031 |
| `gui/backtest_reports.py` | MD-GUI-031.055.M09 | SRD-GUI-031.055 | FO-GUI-031 |
| `gui/backtest_breakdown.py` | MD-GUI-031.062.M12 | SRD-GUI-031.062 | FO-GUI-031 |
| `gui/backtest_report_chart.py` | MD-GUI-031.080.M13 | SRD-GUI-031.080 | FO-GUI-031 |
| `gui/backtest_setup.py` | MD-GUI-031.071.M10 | SRD-GUI-031.071, .074 | FO-GUI-031 |
| `gui/backtest_report_view.py` | MD-GUI-031.040.M04 | SRD-GUI-031.040–.045 | FO-GUI-031 |
| `gui/ai_settings_block.py` | MD-GUI-033.001.M01 | SRD-GUI-033.001–.004, .006 | FO-GUI-033 |
| `gui/ai_desk_team.py` | MD-GUI-035.001.M01 | SRD-GUI-035.001, .003–.005, .009, .012 | FO-GUI-035 |
| `core/desk_team.py` | MD-GUI-035.002.M02 | SRD-GUI-035.002, .004–.007 | FO-GUI-035 |
| `gui/ai_desk_team_log.py` | MD-GUI-035.006.M03 | SRD-GUI-035.006 | FO-GUI-035 |
| `gui/ai_desk_team_pane.py` | MD-GUI-035.007.M04 | SRD-GUI-035.007–.008 | FO-GUI-035 |

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
