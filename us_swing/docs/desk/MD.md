# Module Decomposition — Desk Harness (DSK)

**Document ID:** MD-DSK
**Version:** 0.2.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

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
| MD-DSK-001.020.M06 | SRD-DSK-001.020 |
