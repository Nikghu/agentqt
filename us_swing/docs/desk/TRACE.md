# Traceability Matrix — Desk Harness (DSK)

**Document ID:** TRACE-DSK
**Version:** 0.1.0
**Status:** Draft
**Last Updated:** 2026-11-06
**Project:** US Swing Trading System

> v0.1.0: One row per Draft FO. Columns fill as each phase completes.

---

| FO ID | SRD ID | DD ID | MD ID | UTCD IDs | Code File | Status | RN |
|---|---|---|---|---|---|---|---|
| FO-DSK-001 | SRD-DSK-001.001–.020 | DD-DSK-001.001.D01 | MD-DSK-001.004.M01, .001.M02, .015.M03, .010.M04, .018.M05, .020.M06 | UT-DSK-001.* (62, Pass) | `core/desk_contract.py`, `desk/store.py`, `desk/clock.py`, `desk/process.py`, `desk/task.py`, `desk/cli.py` | Implemented | RN-DSK-0.1.0-20261105 |
| FO-DSK-001 | SRD-DSK-001.021 | — | MD-DSK-001.021.M07 | UT-DSK-001.021.M07.T01–T02 (Pass) | `core/desk_steps.py` | Implemented | RN-MKT-0.1.0-20261106 |
| FO-DSK-001 | SRD-DSK-001.022 | — | MD-DSK-001.020.M06, MD-DSK-001.021.M07 | UT-DSK-001.022.M06.T01–T02 (Pass) | `desk/cli.py`, `core/desk_steps.py` | Implemented | RN-MKT-0.4.0-20261106 |
| FO-DSK-002 | SRD-DSK-002.001–.005 | DD-DSK-002.001.D01 | MD-DSK-002.001.M08, .002.M09 | UT-DSK-002.* (13, Pass) | `core/desk_agents.py`, `desk/registry.py`, `core/desk_steps.py` | Implemented (P5a) | RN-DSK-0.2.0-20261106 |
| FO-DSK-003 | SRD-DSK-003.001–.003 | DD-DSK-002.001.D01 | MD-DSK-003.001.M10 | UT-DSK-003.* (8, Pass) | `desk/employees_step.py` | Implemented (P5a; router P5b) | RN-DSK-0.2.0-20261106 |
| FO-DSK-004 | SRD-DSK-004.001–.005 | DD-DSK-002.001.D01 | MD-DSK-004.001.M11, .003.M12, .005.M13 | UT-DSK-004.* (14, Pass) | `desk/gateway.py`, `desk/budget.py`, `core/desk_ai_settings.py` | Implemented (P5a) | RN-DSK-0.2.0-20261106 |
| FO-DSK-005 | SRD-DSK-005.001–.004 | DD-DSK-002.001.D01 | MD-DSK-005.001.M14 | UT-DSK-005.* (6, Pass) | `desk/recorder.py` | Implemented (P5a; replay P5b) | RN-DSK-0.2.0-20261106 |
| FO-DSK-006 | — | — | — | — | — | Draft | — |
