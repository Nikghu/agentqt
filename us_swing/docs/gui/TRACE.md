# Traceability Matrix — GUI Module (GUI)

**Document ID:** TRACE-GUI
**Version:** 1.14.0
**Project:** US Swing Trading System
**Last Updated:** 2026-10-30 (Backtest Reports, SRD-GUI-031.055; RN-GUI-1.46.0)

---

## Forward Traceability: FO → SRD → DD → MD → UTCD

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-GUI-000 | SRD-GUI-000.006 | DD-EXE-017.021.D01 | MD-EXE-017.017.M15 | (logic via UT-EXE-017.021.M14.T02–03) | `gui/main_window.py`, `gui/app_service.py` | Implemented | RN-EXE-1.25.0-20260612 |
| FO-GUI-000 | SRD-GUI-000.007 | — | MD-GUI-000.007.M01 | UT-GUI-000.007.M01.T01–T03 | `gui/quiet_platform.py`, `run_gui.py`, `pyi_rth_quiet_platform.py`, `usswing_installer.yaml` | Implemented | RN-GUI-1.37.1-20261027 |
| FO-GUI-000 | SRD-GUI-000.008 | — | MD-GUI-000.008.M01–M03 | UT-GUI-000.008.M01.T01–T02, M02.T01, M03.T01–T02 | `gui/theme.py`, `gui/chart_source_list.py`, `gui/app_service.py` | Implemented | RN-GUI-1.37.2-20261027 |
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
| FO-GUI-018 | SRD-GUI-018.001–011 | DD-GUI-018.001.D01 | MD-GUI-018.001.M01, MD-GUI-018.006.M02, MD-GUI-018.005.M03, MD-GUI-018.008.M04 | UT-GUI-018.* (17 tests) | `gui/sidebar.py`, `gui/reveal.py`, `gui/main_window.py`, `gui/theme.py` | Implemented | RN-GUI-1.10.0-20261023, RN-GUI-1.16.0-20261023 |
| FO-GUI-019 | SRD-GUI-019.001–008 | DD-GUI-019.001.D01 | MD-GUI-019.001.M01, MD-GUI-019.006.M02, MD-GUI-019.002.M03 | UT-GUI-019.* (10 tests) | `gui/side_panels.py`, `gui/dashboard_panel.py`, `gui/main_window.py` | Implemented | RN-GUI-1.11.0-20261023 |
| FO-GUI-019 | SRD-GUI-019.009 | — | MD-GUI-019.009.M03 | UT-GUI-019.009.M03.T01–T02 | `gui/main_window.py` | Implemented | RN-GUI-1.37.3-20261027 |
| FO-GUI-020 | SRD-GUI-020.001–005 | DD-GUI-020.001.D01 | MD-GUI-020.001.M01 | UT-GUI-020.001.M01.T01–T02, .002.M01.T01, .003.M01.T01–T02, .004.M01.T01 | `gui/chart_workspace.py`, `gui/chart_panel.py`, `gui/screener_panel.py`, `gui/main_window.py` | Implemented | RN-GUI-1.12.0-20261023 |
| FO-GUI-021 | SRD-GUI-021.001–004 | DD-GUI-021.001.D01 | MD-GUI-021.001.M01 | UT-GUI-021.001.M01.T01–T02, .002.M01.T01–T02, .003.M01.T01, .003.M02.T01, .004.M01.T01–T04, .004.M02.T01–T02 | `gui/settings_panel.py`, `gui/theme.py`, `gui/side_panels.py`, `gui/main_window.py` | Implemented | RN-GUI-1.15.0-20261023 |
| FO-GUI-022 | SRD-GUI-022.001–012 | DD-GUI-022.001.D01 | MD-GUI-022.001.M01, MD-GUI-003.001.M01 | UT-GUI-022.001.M01.T01–T02, .002.M01.T01–T05, .003.M01.T01–T02, .004.M01.T01, .005.M01.T01, .006.M01.T01, .007.M01.T01–T02, .008.M01.T01, .009.M01.T01–T02, .010.M01.T01–T02, .011.M01.T01 | `gui/screener_views.py`, `gui/screener_panel.py`, `gui/theme.py`, `gui/chart_panel.py`, `gui/ai_transcript_panel.py`, `assets/icons` | Implemented | RN-GUI-1.18.0-20261023 |
| FO-GUI-023 | SRD-GUI-023.001–004 | DD-GUI-023.001.D01 | MD-GUI-023.001.M01, MD-GUI-001.001.M01, MD-GUI-003.001.M01 | UT-GUI-023.001.M01.T01–T02 | `gui/cards.py`, `gui/main_window.py`, `gui/screener_panel.py`, `gui/theme.py` | Implemented | RN-GUI-1.19.0-20261023 |
| FO-GUI-024 | SRD-GUI-024.001–008 | DD-GUI-024.001.D01 | MD-GUI-024.001.M01, .002.M02, .003.M03, .004.M04, .006.M05, .008.M06 | UT-GUI-024.001.M01.T01–T02, .002.M02.T01–T04, .003.M03.T01–T02, .004–.005.M04.T01–T02, .006.M05.T01–T04, .008.M06.T01–T03; UT-GUI-004.001.M01.T06–T07 (moved) | `gui/execution_header.py`, `gui/execution_watchlist.py`, `gui/strategies_pane.py`, `gui/strategy_pnl_chart.py`, `gui/active_cycles_{panel,model}.py`, `gui/execution_panel.py`, `gui/theme.py` | Implemented | RN-GUI-1.20.0–1.23.0 |
| FO-GUI-025 | SRD-GUI-025.001–020 | DD-GUI-025.001.D01 | MD-GUI-025.003.M01, .001.M02, .013.M03, .016.M04, .019.M05 | UT-GUI-025.004.M01.T01–T03, .001.M01.T01, .005.M01.T01–T02, .001.M02.T01, .002.M02.T01, .006.M02.T01–T02, .008.M02.T01–T03, .009–.011.M02.T01–T02, .012.M01.T01–T03, .013.M03.T01–T04, .015.M03.T01–T03, .013.M02.T01, .014.M02.T01, .015.M02.T01, .016.M04.T01–T02, .018.M02.T01, .019.M05.T01–T06, .019.M02.T01, .020.M05.T01–T03, .020.M01.T01–T03, .020.M02.T01–T03 | `gui/watchlist_store.py`, `gui/dashboard_tiles.py`, `gui/performance_band.py`, `gui/dashboard_panel.py`, `gui/main_window.py`, `gui/position_table_model.py`, `assets/icons` | Implemented | RN-GUI-1.25.0-20261024, RN-GUI-1.26.0-20261024, RN-GUI-1.27.0-20261024, RN-GUI-1.28.0-20261024, RN-GUI-1.35.1-20261026, RN-GUI-1.35.2-20261026, RN-GUI-1.36.0-20261026 |
| FO-GUI-026 | SRD-GUI-026.001–013 | DD-GUI-026.001.D01, DD-GUI-026.011.D01 | MD-GUI-026.001.M01, .002.M02, .005.M03, .012.M04 | UT-GUI-026.001.M01.T01–T04, .002.M02.T01–T04, .003.M01.T01–T02, .004.M01.T01–T02, .005.M03.T01–T02, .005.M01.T04, .006.M03.T01–T04, .006.M01.T05–T06, .007.M03.T01–T02, .007.M01.T03, .008.M03.T01–T02, .008.M01.T03, .009.M03.T01–T02, .010.M01.T01–T02, .011.M04.T05, .011.M01.T01–T02, .012.M01.T05, .012.M04.T01–T04, .013.M02.T01–T04, .013.M01.T01–T04 | `gui/chart_workspace.py`, `gui/chart_source_list.py`, `gui/chart_inspector.py`, `gui/chart_drawings.py`, `gui/chart_panel.py`, `gui/app_service.py`, `gui/main_window.py`, `data/models.py` | Implemented | RN-GUI-1.29.0-20261024, RN-GUI-1.30.0-20261024, RN-GUI-1.31.0-20261024, RN-GUI-1.37.0-20261026 |
| FO-GUI-027 | SRD-GUI-027.001–013 | DD-GUI-027.001.D01 | MD-GUI-027.001.M01, .004.M02, .004.M03, .005.M04, .009.M05, .005.M07; MD-GUI-019.001.M01 | UT-GUI-027.001.M01.T01–T02, .003.M01.T01–T02, .004.M02.T01, .004.M03.T01, .002.M04.T01, .005.M04.T01, .007.M06.T01, .008.M02.T01–T02, .009.M05.T01, .010.M04.T01–T02, .011.M04.T01–T02, .012.M04.T01–T02, .013.M04.T01, .005.M07.T01–T04, .005.M02.T01 | `gui/settings_dialog.py`, `gui/settings_panel.py`, `gui/sidebar.py`, `gui/main_window.py`, `gui/side_panels.py`, `gui/execution_header.py`, `gui/update_popup.py` | Implemented | RN-GUI-1.32.0-20261025, RN-GUI-1.33.0-20261025 |
| FO-GUI-028 | SRD-GUI-028.001–005 | DD-GUI-028.001.D01 | MD-GUI-028.001.M01 | UT-GUI-028.001.M01.T01–T03, .002.M01.T01–T02, .003.M01.T01, .004.M01.T01, .005.M01.T01; UT-GUI-021.004.M01.T04 | `gui/settings_panel.py`, `gui/theme.py` | Implemented | RN-GUI-1.34.0-20261025 |
| FO-GUI-029 | SRD-GUI-029.001–006 | DD-GUI-029.001.D01 | MD-GUI-029.001.M01, .004.M02 | UT-GUI-029.001.M01.T01, .002.M01.T01–T02, .004.M01.T01–T02, .005.M01.T01, .006.M01.T01, .002.M02.T01, .004.M02.T01–T02 | `gui/scheduler_table.py`, `gui/scheduler_dialog.py`, `gui/scheduler_store.py`, `gui/settings_panel.py`, `gui/theme.py` | Implemented | RN-GUI-1.35.0-20261025 |
| FO-GUI-030 | SRD-GUI-030.001–010 | DD-GUI-030.001.D01 | MD-GUI-030.001.M01, .004.M02, .006.M03, .004.M04, .007.M05, .008.M06 | UT-GUI-030.* (20 tests, Pass) | `gui/backtest_data_panel.py`, `gui/app_service.py`, `gui/settings_panel.py`, `gui/system_store.py`, `gui/main_window.py` | Implemented | RN-GUI-1.38.0-20261028, RN-GUI-1.38.1-20261029 |
| FO-GUI-031 | SRD-GUI-031.001–.004, .010–.012, .020–.023, .030–.034 | DD-GUI-031.001.D01 | MD-GUI-031.001.M01, .002.M02, .003.M03 | UT-GUI-031.* (17 tests, Pass) | `gui/main_window.py`, `gui/backtest_builder.py`, `gui/backtest_workspace.py` | Implemented (Phase 0–3) | RN-GUI-1.39.0-20261029, RN-GUI-1.40.0-20261029, RN-GUI-1.41.0-20261029 |
| FO-GUI-031 | SRD-GUI-031.013 | DD-GUI-031.001.D01 | MD-GUI-031.003.M03 | UT-GUI-031.013.M03.T01 (1 test, Pass) | `gui/backtest_workspace.py` | Implemented | RN-GUI-1.42.0-20261029 |
| FO-GUI-031 | SRD-GUI-031.055 | None (minimal GUI docs) | MD-GUI-031.055.M09, MD-GUI-031.003.M03 | UT-GUI-031.055 (7 tests: M09 ×5, M03 ×2, Pass) | `gui/backtest_reports.py`, `gui/backtest_workspace.py`, `gui/backtest_dock.py` | Implemented (redesign phase 3) | RN-GUI-1.46.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.053–.054 | None (minimal GUI docs) | MD-GUI-031.053.M07, MD-GUI-031.054.M08, MD-GUI-031.003.M03 | UT-GUI-031.053–.054 (8 tests: M07 ×4, M08 ×2, M03 ×2, Pass) | `gui/backtest_trade_list.py`, `gui/backtest_use_charts.py`, `gui/backtest_workspace.py` | Implemented (redesign phase 2) | RN-GUI-1.45.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.050–.052 | None (minimal GUI docs) | MD-GUI-031.050.M05, MD-GUI-031.052.M06, MD-GUI-031.003.M03 | UT-GUI-031.050–.052 (8 tests: M05 ×2, M06 ×2, M03 ×4, Pass) | `gui/backtest_dock.py`, `gui/backtest_trade_chart.py`, `gui/backtest_workspace.py` | Implemented (redesign phase 1) | RN-GUI-1.44.0-20261030 |
| FO-GUI-031 | SRD-GUI-031.040–.045 | None yet (Phase 4a view only) | MD-GUI-031.040.M04, MD-GUI-031.003.M03 | UT-GUI-031.040–.045 (12 tests: M04 ×10, M03 ×2, Pass) | `gui/backtest_report_view.py`, `gui/backtest_workspace.py` | Implemented (Phase 4a) | RN-GUI-1.43.0-20261029 |

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
| `gui/backtest_report_view.py` | MD-GUI-031.040.M04 | SRD-GUI-031.040–.045 | FO-GUI-031 |

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
