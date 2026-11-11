# Traceability Matrix — Desk Harness (DSK)

**Document ID:** TRACE-DSK
**Version:** 0.1.0
**Status:** Draft
**Last Updated:** 2026-11-11 (autonomous desk step F skill 2: FO-DSK-010 SRD .015 with RN-DSK-0.12.0-20261111; autonomous desk step E: FO-DSK-004 SRD .006–.010, FO-DSK-007 SRD .010, FO-DSK-010 SRD .001–.014 with RN-DSK-0.11.0-20261111; autonomous desk step D: FO-DSK-003 SRD .020–.025 and FO-DSK-007 SRD .009 with RN-DSK-0.10.0-20261111; memory v1, step C: FO-DSK-009 with RN-DSK-0.9.0-20261111)
**Project:** US Swing Trading System

> v0.1.0: One row per Draft FO. Columns fill as each phase completes.

---

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-DSK-001 | SRD-DSK-001.001–.020 | DD-DSK-001.001.D01 | MD-DSK-001.004.M01, .001.M02, .015.M03, .010.M04, .018.M05, .020.M06 | UT-DSK-001.* (62, Pass) | `core/desk_contract.py`, `desk/store.py`, `desk/clock.py`, `desk/process.py`, `desk/task.py`, `desk/cli.py` | Implemented | RN-DSK-0.1.0-20261105 |
| FO-DSK-001 | SRD-DSK-001.021 | — | MD-DSK-001.021.M07 | UT-DSK-001.021.M07.T01–T02 (Pass) | `core/desk_steps.py` | Implemented | RN-MKT-0.1.0-20261106 |
| FO-DSK-001 | SRD-DSK-001.022 | — | MD-DSK-001.020.M06, MD-DSK-001.021.M07 | UT-DSK-001.022.M06.T01–T02 (Pass) | `desk/cli.py`, `core/desk_steps.py` | Implemented | RN-MKT-0.4.0-20261106 |
| FO-DSK-002 | SRD-DSK-002.001–.007 | DD-DSK-002.001.D01 | MD-DSK-002.001.M08, .002.M09 | UT-DSK-002.* (17, Pass) | `core/desk_agents.py`, `desk/registry.py`, `core/desk_steps.py` | Implemented (P5a) | RN-DSK-0.2.0-20261106 |
| FO-DSK-003 | SRD-DSK-003.001–.003 | DD-DSK-002.001.D01 | MD-DSK-003.001.M10 | UT-DSK-003.* (8, Pass) | `desk/employees_step.py` | Implemented | RN-DSK-0.2.0-20261106 |
| FO-DSK-004 | SRD-DSK-004.001–.005 | DD-DSK-002.001.D01 | MD-DSK-004.001.M11, .003.M12, .005.M13 | UT-DSK-004.* (14, Pass) | `desk/gateway.py`, `desk/budget.py`, `core/desk_ai_settings.py` | Implemented (P5a) | RN-DSK-0.2.0-20261106 |
| FO-DSK-005 | SRD-DSK-005.001–.004 | DD-DSK-002.001.D01 | MD-DSK-005.001.M14 | UT-DSK-005.* (6, Pass) | `desk/recorder.py` | Implemented | RN-DSK-0.2.0-20261106 |
| FO-DSK-002 | SRD-DSK-002.008–.009 | DD-DSK-003.004.D01 | MD-DSK-003.006.M16, MD-DSK-002.002.M09 | UT-DSK-002.008.M16.T01–T04, UT-DSK-002.009.M09.T01–T03 (7, Pass) | `core/desk_agents.py`, `desk/router.py`, `desk/registry.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-003 | SRD-DSK-003.001 | DD-DSK-003.004.D01 | MD-DSK-003.001.M10 | UT-DSK-003.001.M10.T04 (1, Pass) | `desk/employees_step.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-003 | SRD-DSK-003.004 | DD-DSK-003.004.D01 | MD-DSK-003.004.M15 | UT-DSK-003.004.M15.T01–T03 (3, Pass) | `core/desk_events.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-003 | SRD-DSK-003.005 | DD-DSK-003.004.D01 | MD-DSK-003.004.M15, MD-MKT-001.011.M05 | UT-DSK-003.005.M15.T01–T02 (2, Pass) | `core/desk_events.py`, `market/step.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-003 | SRD-DSK-003.006–.007 | DD-DSK-003.004.D01 | MD-DSK-003.006.M16 | UT-DSK-003.006.M16.T01–T03, UT-DSK-003.007.M16.T01–T03 (6, Pass) | `desk/router.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-003 | SRD-DSK-003.008 | DD-DSK-003.004.D01 | MD-DSK-001.015.M03, MD-DSK-001.010.M04 | UT-DSK-003.008.M03.T01–T04, UT-DSK-003.008.M04.T01–T03 (7, Pass) | `desk/clock.py`, `desk/process.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-003 | SRD-DSK-003.009 | DD-DSK-003.004.D01 | MD-DSK-003.006.M16, MD-DSK-005.001.M14 | UT-DSK-003.009.M16.T01–T02, UT-DSK-003.009.M14.T01 (3, Pass) | `desk/router.py`, `desk/recorder.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-003 | SRD-DSK-003.010–.012 | DD-DSK-003.004.D01 | MD-DSK-003.006.M16 | UT-DSK-003.010.M16.T01–T04, UT-DSK-003.011.M16.T01–T03, UT-DSK-003.012.M16.T01–T02 (9, Pass) | `desk/router.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-005 | SRD-DSK-005.005 | DD-DSK-003.004.D01 | MD-DSK-005.005.M17, MD-DSK-004.001.M11, MD-DSK-001.020.M06 | UT-DSK-005.005.M17.T01–T04 (4, Pass) | `desk/replay.py`, `desk/gateway.py`, `desk/cli.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-005 | SRD-DSK-005.006 | DD-DSK-003.004.D01 | MD-DSK-005.005.M17, MD-DSK-005.001.M14 | UT-DSK-005.006.M17.T01–T02, UT-DSK-005.006.M14.T01 (3, Pass) | `desk/replay.py`, `desk/recorder.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-005 | SRD-DSK-005.007 | DD-DSK-003.004.D01 | MD-DSK-005.005.M17 | UT-DSK-005.007.M17.T01–T03 (3, Pass) | `desk/replay.py`, `desk/cli.py` | Implemented | RN-DSK-0.3.0-20261106 |
| FO-DSK-006 | SRD-DSK-006.001–.010 | DD-DSK-006.001.D01 | MD-DSK-006.001.M18, .004.M19, .009.M20; MD-DSK-002.002.M09, MD-DSK-004.005.M13 | UT-DSK-006.001–.010 (23, Pass) | `core/desk_hiring.py`, `desk/shadow.py`, `desk/weekly_report.py`, `desk/registry.py`, `desk/recorder.py`, `desk/gateway.py`, `desk/employees_step.py`, `core/desk_ai_settings.py`, `core/desk_steps.py` | Implemented | RN-DSK-0.4.0-20261106 |
| FO-DSK-007 | SRD-DSK-007.001–.006 | DD-DSK-007.001.D01 | MD-DSK-007.001.M21; MD-DSK-004.001.M11, MD-DSK-003.001.M10 | UT-DSK-007.001–.006 (8, Pass) | `core/desk_alerts.py`, `desk/gateway.py`, `desk/employees_step.py` | Implemented | RN-DSK-0.5.0-20261110 |
| FO-DSK-008 | SRD-DSK-008.001–.009 | DD-DSK-008.001.D01 | MD-DSK-008.001.M22; MD-DSK-002.002.M09, MD-DSK-006.001.M18, MD-DSK-005.005.M17 | UT-DSK-008.001–.009 (17, Pass) | `core/desk_employee.py`, `desk/registry.py`, `desk/replay.py`, `desk/cli.py`, `desk/gateway.py`, `core/desk_hiring.py`, `core/desk_team.py`, `market/employees/*/employee.md` | Implemented | RN-DSK-0.6.0-20261110 |
| FO-DSK-001 | SRD-DSK-001.013, .015, .018, .019, .020 (reopened 2026-11-10) | DD-DSK-001.015.D02 | MD-DSK-001.015.M03, .010.M04, .018.M05, .020.M06, .001.M02, .004.M01 | UT-DSK-001.015.M03.T01–T06, UT-DSK-001.018.M05.T03–T06, UT-DSK-001.010.M04.T05, T11, T27–T31, UT-DSK-001.020.M06.T05–T06, UT-DSK-001.001.M02.T12 (20, Pass) | `desk/clock.py`, `desk/process.py`, `desk/task.py`, `desk/cli.py`, `desk/store.py`, `core/desk_contract.py` | Implemented | RN-DSK-0.7.0-20261111 |
| FO-DSK-003 | SRD-DSK-003.013 | DD-DSK-001.015.D02 | MD-DSK-001.015.M03, MD-DSK-001.010.M04 | Shared with UT-DSK-001.015.M03 and UT-DSK-001.010.M04 (Pass) | `desk/clock.py`, `desk/process.py` | Implemented | RN-DSK-0.7.0-20261111 |
| FO-DSK-007 | SRD-DSK-007.005 (reopened, wording), .007 | DD-DSK-007.001.D01 | MD-DSK-007.001.M21; MD-MKT-001.013.M06 | UT-DSK-007.007.M21.T01–T03 (3, Pass) | `core/desk_alerts.py` | Implemented | RN-DSK-0.7.0-20261111 |
| FO-DSK-003 | SRD-DSK-003.010–.012 | DD-DSK-003.014.D01 | MD-DSK-003.006.M16 | UT-DSK-003.010.M16.T01–T04, UT-DSK-003.011.M16.T01–T03, UT-DSK-003.012.M16.T01–T02 (Pass) | `desk/router.py`, `pyproject.toml`, `USSwing.spec` | Implemented | RN-DSK-0.8.0-20261111 |
| FO-DSK-003 | SRD-DSK-003.014 | DD-DSK-003.014.D01 | MD-DSK-003.004.M15, MD-DSK-003.006.M16, MD-DSK-003.001.M10 | UT-DSK-003.014.M15.T01–T04, UT-DSK-003.014.M16.T01, UT-DSK-003.014.M10.T01 (Pass) | `core/desk_events.py`, `desk/router.py`, `desk/employees_step.py` | Implemented | RN-DSK-0.8.0-20261111 |
| FO-DSK-003 | SRD-DSK-003.015–.019 | DD-DSK-003.014.D01 | MD-DSK-003.006.M16, MD-DSK-003.001.M10 | UT-DSK-003.015.M16.T01–T04, UT-DSK-003.016.M16.T01–T04, UT-DSK-003.017.M16.T01–T02, UT-DSK-003.018.M16.T01–T03, UT-DSK-003.018.M10.T01, UT-DSK-003.019.M16.T01–T03 (Pass) | `desk/router.py`, `desk/employees_step.py` | Implemented | RN-DSK-0.8.0-20261111 |
| FO-DSK-007 | SRD-DSK-007.008 | DD-DSK-003.014.D01 | MD-DSK-007.001.M21, MD-DSK-003.001.M10 | UT-DSK-007.008.M21.T01–T03 (Pass) | `core/desk_alerts.py`, `desk/employees_step.py` | Implemented | RN-DSK-0.8.0-20261111 |
| FO-DSK-009 | SRD-DSK-009.001–.009 | DD-DSK-009.001.D01 | MD-DSK-009.001.M23, MD-DSK-001.010.M04 | UT-DSK-009.* (26, Pass) | `core/desk_lessons.py`, `desk/process.py` | Implemented | RN-DSK-0.9.0-20261111 |
| FO-DSK-003 | SRD-DSK-003.020–.025 | DD-DSK-003.020.D01 | MD-DSK-003.021.M24 (new); MD-DSK-001.015.M03, MD-DSK-001.010.M04, MD-DSK-001.020.M06, MD-DSK-001.021.M07, MD-DSK-003.004.M15 (changed) | UT-DSK-003.020–.025 (16, Pass) | `core/desk_watch.py`, `desk/clock.py`, `desk/process.py`, `desk/cli.py`, `core/desk_steps.py`, `core/desk_events.py` | Implemented | RN-DSK-0.10.0-20261111 |
| FO-DSK-007 | SRD-DSK-007.009 | DD-DSK-003.020.D01 | MD-DSK-007.001.M21 | UT-DSK-007.009.M21.T01–T02 (2, Pass) | `core/desk_alerts.py` | Implemented | RN-DSK-0.10.0-20261111 |
| FO-DSK-004 | SRD-DSK-004.006–.010 | DD-DSK-010.001.D01 | MD-DSK-008.001.M22, MD-DSK-004.003.M12, MD-DSK-004.001.M11, MD-DSK-005.001.M14, MD-DSK-003.001.M10 | UT-DSK-004.006–.010 (10, Pass) | `core/desk_employee.py`, `desk/budget.py`, `desk/gateway.py`, `desk/recorder.py`, `desk/employees_step.py` | Implemented | RN-DSK-0.11.0-20261111 |
| FO-DSK-007 | SRD-DSK-007.010 | DD-DSK-010.001.D01 | MD-DSK-007.001.M21 | UT-DSK-007.010.M21.T01–T02 (2, Pass) | `core/desk_alerts.py` | Implemented | RN-DSK-0.11.0-20261111 |
| FO-DSK-010 | SRD-DSK-010.001–.014 | DD-DSK-010.001.D01 | MD-DSK-010.001.M25 (new), MD-DSK-010.008.M26 (new); MD-DSK-001.010.M04, MD-DSK-001.020.M06, MD-DSK-003.001.M10, MD-DSK-004.001.M11, MD-DSK-004.003.M12, MD-DSK-005.001.M14, MD-DSK-003.004.M15, MD-DSK-007.001.M21, MD-DSK-008.001.M22 (changed) | UT-DSK-010.001–.014 (34, Pass) | `core/desk_research.py`, `desk/research.py`, `desk/process.py`, `desk/cli.py`, `desk/budget.py`, `desk/recorder.py`, `desk/gateway.py`, `desk/employees_step.py`, `core/desk_alerts.py`, `core/desk_events.py`, `core/desk_employee.py` | Implemented | RN-DSK-0.11.0-20261111 |
| FO-DSK-010 | SRD-DSK-010.015 | DD-DSK-010.015.D01 | MD-DSK-010.001.M25 | UT-DSK-010.015.M25.T01–T03 (3, Pass) | `core/desk_research.py` | Implemented | RN-DSK-0.12.0-20261111 |
