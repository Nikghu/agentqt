# Revision Note — RN-DSK-0.1.0-20261105

**Version:** 0.1.0
**Date:** 2026-11-05
**Tool:** DSK
**Artifact:** FO-DSK-001 / SRD-DSK-001.001–.020
**Type:** Feature

---

## Summary

Adds the desk process shell, phase P0a of the Market Analytics AI desk. The desk runs as its own process with its own `desk.db`; the app only adds rows to `commands` and reads state read-only. It covers the state machine, single-instance lock, heartbeat, evening run scheduling, Windows tasks and the `desk` CLI. No analysis steps are registered yet, so each run ends ok with zero steps.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-001.004.M01 | `us_swing/src/us_swing/core/desk_contract.py` | New shared desk types, status reader and command sender |
| MD-DSK-001.001.M02 | `us_swing/src/us_swing/desk/store.py` | New `desk.db` store (WAL, tables, state, heartbeat, commands, runs) |
| MD-DSK-001.015.M03 | `us_swing/src/us_swing/desk/clock.py` | New pure time rules for evening run and Windows task time |
| MD-DSK-001.010.M04 | `us_swing/src/us_swing/desk/process.py` | New single-instance main loop, command handling, runs, stop and resume |
| MD-DSK-001.018.M05 | `us_swing/src/us_swing/desk/task.py` | New install, remove and sync of Windows tasks; detached launch |
| MD-DSK-001.020.M06 | `us_swing/src/us_swing/desk/cli.py` | New `desk` sub-commands; `desk` dispatch added to `__main__.py` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-001.001 | The desk keeps its data in `~/.usswing/desk/desk.db`, opened in WAL mode with a busy timeout. | Implemented |
| SRD-DSK-001.002 | The desk creates the `desk_state`, `commands` and `runs` tables on first open and records a schema version. | Implemented |
| SRD-DSK-001.003 | `desk_state` holds one row: state, heartbeat time, process id, message and saved resume point. | Implemented |
| SRD-DSK-001.004 | The desk state is one of Running, Sleeping, Paused, Stopping, Stopped, Off, Error. | Implemented |
| SRD-DSK-001.005 | The app sends pause, resume, stop and run-now only by adding a pending row to `commands`. | Implemented |
| SRD-DSK-001.006 | A read-only reader reports Off when there is no `desk.db` or no state row. | Implemented |
| SRD-DSK-001.007 | The reader reports Error "not responding" when a live state has a heartbeat older than 60 seconds. | Implemented |
| SRD-DSK-001.008 | Only one desk process runs at a time; a second one exits at once without touching state. | Implemented |
| SRD-DSK-001.009 | The running desk writes a heartbeat every 10 seconds. | Implemented |
| SRD-DSK-001.010 | The desk reads pending commands every 2 seconds, applies them in order and marks each done or rejected with a reason. | Implemented |
| SRD-DSK-001.011 | Pause holds all timers and resume returns the desk to Sleeping. | Implemented |
| SRD-DSK-001.012 | Stop moves to Stopping, finishes the current step, saves the resume point, sets Stopped and exits. | Implemented |
| SRD-DSK-001.013 | A desk started by the Windows task exits at once when the saved state is Stopped. | Implemented |
| SRD-DSK-001.014 | On start, a run with no end time is marked interrupted and run again. | Implemented |
| SRD-DSK-001.015 | The evening run is due on weekdays at 16:25 New York time and is caught up once if missed that day. | Implemented |
| SRD-DSK-001.016 | Each run is a `runs` row (kind, start, end, result, note) and calls the registered desk steps in order. | Implemented |
| SRD-DSK-001.017 | A failed step ends the run as failed and sets Error with a short message; the next good run sets Sleeping. | Implemented |
| SRD-DSK-001.018 | Install creates two Windows tasks: one at logon and one 5 minutes before each weekday evening run, set in local time and local days. | Implemented |
| SRD-DSK-001.019 | Each desk start re-checks the evening task time and updates it after a US or local clock change. | Implemented |
| SRD-DSK-001.020 | `python -m us_swing desk` runs the desk; `desk start/status/pause/resume/stop/run-now/install/uninstall` control it. | Implemented |

---

## Design Decisions

- The desk is a separate process. The app and the desk share only `desk.db`: commands go in, state comes out.
- Single instance is enforced with a Windows file lock (msvcrt); the lock is released when the process dies.
- The heartbeat runs on a side thread, so it keeps going during long runs.
- Windows tasks use local time and local weekdays; the evening task time is re-checked at each desk start.
- Dev task command runs `run_gui.py desk` because the package is not installed in dev; a frozen build runs `USSwing.exe desk`.

---

## Issues Resolved

None

---

## Test Coverage

62 unit tests (`UT-DSK-001.*`) written and Pass: 57 from UTCD plus 5 added after code review. ruff and mypy --strict clean. Line coverage not measured (pytest-cov not installed). Windows tasks not installed yet; that is a user step (TODO T113).
