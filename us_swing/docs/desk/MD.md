# Module Decomposition — Desk Harness (DSK)

**Document ID:** MD-DSK
**Version:** 0.2.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.5.0: MD-DSK-002–005 M08–M14 added — lean harness (P5a).
> v0.4.0: MD-DSK-001.020.M06 and .021.M07 also cover SRD-DSK-001.022 (`desk proof`).
> v0.3.0: MD-DSK-001.021.M07 added.
> v0.2.0: MD-DSK-001.*.M01–M06 added — desk process shell (P0a).
> v0.1.0: Empty.

---

## FO-DSK-001: Desk Process Shell

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-001.004.M01 | SRD-DSK-001.004 | `us_swing/src/us_swing/core/desk_contract.py` | Shared desk types, read-only status reader and command sender used by the app | `DeskState`, `CommandKind`, `DeskStatus`, `DeskStep`, `desk_home()`, `read_status()`, `send_command()` | `sqlite3` | No |
| MD-DSK-001.001.M02 | SRD-DSK-001.001 | `us_swing/src/us_swing/desk/store.py` | Opens `desk.db` (WAL), creates tables, writes state, heartbeat, commands and runs | `DeskStore` | `sqlite3`, M01 | No |
| MD-DSK-001.015.M03 | SRD-DSK-001.015 | `us_swing/src/us_swing/desk/clock.py` | Pure time rules: evening due, local time and days of the evening task | `evening_due()`, `evening_task_time()` | `zoneinfo` | No |
| MD-DSK-001.010.M04 | SRD-DSK-001.010 | `us_swing/src/us_swing/desk/process.py` | Single-instance main loop, command handling, runs, stop and resume | `DeskProcess` | M01–M03 | No |
| MD-DSK-001.018.M05 | SRD-DSK-001.018 | `us_swing/src/us_swing/desk/task.py` | Install, remove and sync Windows tasks; launch a detached desk | `desk_command()`, `install()`, `uninstall()`, `sync_evening_task()`, `launch()` | `subprocess`, M03 | No |
| MD-DSK-001.020.M06 | SRD-DSK-001.020 | `us_swing/src/us_swing/desk/cli.py` | `desk` sub-commands for `python -m us_swing` | `main(argv)` | M01, M04, M05 | No |

| MD-DSK-001.021.M07 | SRD-DSK-001.021 | `us_swing/src/us_swing/core/desk_steps.py` | Step list and loader; desk CLI passes the steps | `STEP_PATHS`, `load_steps()` | `importlib` | No |

**SRD coverage per module** (one Parent SRD per row above; each module also covers):

| Module | Covers SRDs |
|---|---|
| MD-DSK-001.004.M01 | SRD-DSK-001.004, .005, .006, .007 |
| MD-DSK-001.001.M02 | SRD-DSK-001.001, .002, .003, .016 (run rows) |
| MD-DSK-001.015.M03 | SRD-DSK-001.015, .018 (task time) |
| MD-DSK-001.010.M04 | SRD-DSK-001.008, .009, .010, .011, .012, .013, .014, .016, .017 |
| MD-DSK-001.018.M05 | SRD-DSK-001.018, .019 |
| MD-DSK-001.020.M06 | SRD-DSK-001.020, .022 (`desk proof`) |

## FO-DSK-002–005: Lean Harness (P5a)

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-002.001.M08 | SRD-DSK-002.001 | `us_swing/src/us_swing/core/desk_agents.py` | Shared employee types used by desk and tools | `Employee`, `AgentContext`, `Facts`, `FeedItem` | `pydantic` | No |
| MD-DSK-002.002.M09 | SRD-DSK-002.002 | `us_swing/src/us_swing/desk/registry.py` | Load and check job files; `employees` table | `JobSpec`, `Hire`, `load_employee()`, `load_employees()` | M08, `yaml`, `pydantic` | No |
| MD-DSK-003.001.M10 | SRD-DSK-003.001 | `us_swing/src/us_swing/desk/employees_step.py` | Desk step "AI employees" with the wake rule | `EmployeesStep` | M09, M11, M14 | No |
| MD-DSK-004.001.M11 | SRD-DSK-004.001 | `us_swing/src/us_swing/desk/gateway.py` | Model calls, schema check, retry and backup | `Gateway`, `call_model()` | M12, M14, `httpx` | No |
| MD-DSK-004.003.M12 | SRD-DSK-004.003 | `us_swing/src/us_swing/desk/budget.py` | Budget and call caps from `activity` | `Budget` | M14 | No |
| MD-DSK-004.005.M13 | SRD-DSK-004.005 | `us_swing/src/us_swing/core/desk_ai_settings.py` | Desk AI settings file and OpenRouter key (shared with the GUI) | `DeskAiSettings`, `load_settings()`, `save_settings()`, `load_key()`, `save_key()` | `keyring` | No |
| MD-DSK-005.001.M14 | SRD-DSK-005.001 | `us_swing/src/us_swing/desk/recorder.py` | Append-only `activity` and `briefs` | `Recorder`, `Attempt` | `sqlite3` | No |

SRD coverage: 002.001 by M08 and M09 (loading by path); 002.002–.004 by M09; 002.005 by M08 and M10; 003.001–.003 by M10; 004.001, .002 by M11; 004.003, .004 by M12; 004.005 by M13; 005.001–.004 by M14 (005.004 also M10).

Cross-tool: `core/desk_steps.py` (MD-DSK-001.021.M07) gets `EMPLOYEE_PATHS` and the "AI employees" step path.
