# Module Decomposition — Desk Harness (DSK)

**Document ID:** MD-DSK
**Version:** 0.3.0
**Status:** Draft
**Last Updated:** 2026-11-06
**Project:** US Swing Trading System

> v0.6.0: MD-DSK M15–M17 added — events, router with LangGraph, replay (P5b).
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
| MD-DSK-002.001.M08 | SRD-DSK-002.001 | `us_swing/src/us_swing/core/desk_agents.py` | Shared skill types and generic levels used by desk and tools | `Skill`, `AgentContext`, `Facts`, `FeedItem`, `LEVELS` | `pydantic` | No |
| MD-DSK-002.002.M09 | SRD-DSK-002.002 | `us_swing/src/us_swing/desk/registry.py` | Employee folders in the desk folder: seed defaults, load and check files, skills by key; `roster` table | `JobSpec`, `Hire`, `seed_employees()`, `default_folders()`, `load_employee()`, `load_employees()`, `record_employees()` | M08, `yaml`, `pydantic` | No |
| MD-DSK-003.001.M10 | SRD-DSK-003.001 | `us_swing/src/us_swing/desk/employees_step.py` | Desk step "AI employees" with the wake rule | `EmployeesStep` | M09, M11, M14 | No |
| MD-DSK-004.001.M11 | SRD-DSK-004.001 | `us_swing/src/us_swing/desk/gateway.py` | Model calls, schema check, retry and backup | `Gateway`, `call_model()` | M12, M14, `httpx` | No |
| MD-DSK-004.003.M12 | SRD-DSK-004.003 | `us_swing/src/us_swing/desk/budget.py` | Budget and call caps from `activity` | `Budget` | M14 | No |
| MD-DSK-004.005.M13 | SRD-DSK-004.005 | `us_swing/src/us_swing/core/desk_ai_settings.py` | Desk AI settings file and OpenRouter key (shared with the GUI) | `DeskAiSettings`, `load_settings()`, `save_settings()`, `load_key()`, `save_key()` | `keyring` | No |
| MD-DSK-005.001.M14 | SRD-DSK-005.001 | `us_swing/src/us_swing/desk/recorder.py` | Append-only `activity` and `briefs` | `Recorder`, `Attempt` | `sqlite3` | No |

SRD coverage: 002.001 by M08 and M09 (skills by key); 002.002–.004, .006, .007 by M09; 002.005 by M08 and M10; 003.001–.003 by M10; 004.001, .002 by M11; 004.003, .004 by M12; 004.005 by M13; 005.001–.004 by M14 (005.004 also M10).

Cross-tool: `core/desk_steps.py` (MD-DSK-001.021.M07) gets `SKILL_PATHS`, `DEFAULT_EMPLOYEE_PACKAGES` and the "AI employees" step path.

## FO-DSK-002, -003, -005: Events, Market Clock, LangGraph Order and Replay (P5b)

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-003.004.M15 | SRD-DSK-003.004 | `us_swing/src/us_swing/core/desk_events.py` | `events` table, event kinds and rules, posting from any tool | `EVENT_KINDS`, `EVENT_RULES`, `Event`, `post_event()` | `sqlite3` | No |
| MD-DSK-003.006.M16 | SRD-DSK-003.006 | `us_swing/src/us_swing/desk/router.py` | Expire, order and handle events; build and run the LangGraph graph of woken employees | `Router`, `run_order()` | M09, M11, M14, M15, `langgraph` | No |
| MD-DSK-005.005.M17 | SRD-DSK-005.005 | `us_swing/src/us_swing/desk/replay.py` | Re-send a recorded run's prompts and compare the answers | `replay()`, `ReplayLine` | M09, M11, M14 | No |

Changed P0a/P5a modules: M08 (`needs`, `answer`, feed kind `evening`), M09 (trigger list), M10 (posts `after_run`, then calls the router), M03 (`market_events_due()`), M04 (posts clock events, `event` runs), M11 (`Gateway.resend()`), M14 (`replay` column, `last_wake()`), M06 (`desk replay`).

SRD coverage: 002.008 by M08 and M16; 002.009 by M09; 003.004, .005 by M15; 003.006, .007, .009–.011 by M16 (.009 also M14); 003.008 by M03 and M04; 003.012 by M16 with `pyproject.toml` and `USSwing.spec`; 005.005–.007 by M17 (.005 also M11 and M06; .006 also M14).

Cross-tool: `market/step.py` posts `regime_change` through M15 (see MKT DD-MKT-005.006.D01).
