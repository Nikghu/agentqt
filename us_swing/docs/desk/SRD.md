# Software Requirements — Desk Harness (DSK)

**Document ID:** SRD-DSK
**Version:** 0.2.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.4.0: SRD-DSK-001.022 added as Draft — `desk proof` sub-command (for MKT P4).
> v0.3.0: SRD-DSK-001.021 added as Draft — desk loads registered steps (for MKT P1).
> v0.2.0: SRD-DSK-001.001–.020 added — desk process shell (FO-DSK-001, phase P0a).
> v0.1.0: Empty.

---

## FO-DSK-001: Desk Process Shell

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-001.001 | FO-DSK-001 | Must | The desk keeps its data in `~/.usswing/desk/desk.db`, opened in WAL mode with a busy timeout. | folder | `desk.db` | Folder injectable for tests | Implemented |
| SRD-DSK-001.002 | FO-DSK-001 | Must | The desk creates the `desk_state`, `commands` and `runs` tables on first open and records a schema version. | — | tables | Re-open never loses rows | Implemented |
| SRD-DSK-001.003 | FO-DSK-001 | Must | `desk_state` holds one row: state, heartbeat time, process id, message and saved resume point. | — | row | Times stored as UTC ISO text | Implemented |
| SRD-DSK-001.004 | FO-DSK-001 | Must | The desk state is one of Running, Sleeping, Paused, Stopping, Stopped, Off, Error. | — | `DeskState` | Shared enum in `core/desk_contract.py` | Implemented |
| SRD-DSK-001.005 | FO-DSK-001 | Must | The app sends pause, resume, stop and run-now only by adding a pending row to `commands`. | kind | command id | App never writes other desk tables | Implemented |
| SRD-DSK-001.006 | FO-DSK-001 | Must | A read-only reader reports Off when there is no `desk.db` or no state row. | path | `DeskStatus` | Never creates the file | Implemented |
| SRD-DSK-001.007 | FO-DSK-001 | Must | The reader reports Error "not responding" when a live state has a heartbeat older than 60 seconds. | row, now | `DeskStatus` | Stopped and Off never go stale | Implemented |
| SRD-DSK-001.008 | FO-DSK-001 | Must | Only one desk process runs at a time; a second one exits at once without touching state. | lock file | exit | Lock is released when the process dies | Implemented |
| SRD-DSK-001.009 | FO-DSK-001 | Must | The running desk writes a heartbeat every 10 seconds. | clock | `desk_state` | — | Implemented |
| SRD-DSK-001.010 | FO-DSK-001 | Must | The desk reads pending commands every 2 seconds, applies them in order and marks each done or rejected with a reason. | `commands` | status | A command not valid in the current state is rejected | Implemented |
| SRD-DSK-001.011 | FO-DSK-001 | Must | Pause holds all timers and resume returns the desk to Sleeping. | command | state | Commands still read while Paused | Implemented |
| SRD-DSK-001.012 | FO-DSK-001 | Must | Stop moves to Stopping, finishes the current step, saves the resume point, sets Stopped and exits. | command | state | No step is cut half way | Implemented |
| SRD-DSK-001.013 | FO-DSK-001 | Must | A desk started by the Windows task exits at once when the saved state is Stopped. | saved state | exit | Only `start` clears Stopped | Implemented |
| SRD-DSK-001.014 | FO-DSK-001 | Must | On start, a run with no end time is marked interrupted and run again. | `runs` | new run | — | Implemented |
| SRD-DSK-001.015 | FO-DSK-001 | Must | The evening run is due on weekdays at 16:25 New York time and is caught up once if missed that day. | clock, last run | due flag | Pure function, clock passed in | Implemented |
| SRD-DSK-001.016 | FO-DSK-001 | Must | Each run is a `runs` row (kind, start, end, result, note) and calls the registered desk steps in order. | steps | row | Zero steps in P0a gives result ok | Implemented |
| SRD-DSK-001.017 | FO-DSK-001 | Must | A failed step ends the run as failed and sets Error with a short message; the next good run sets Sleeping. | exception | state | Process keeps running | Implemented |
| SRD-DSK-001.018 | FO-DSK-001 | Must | Install creates two Windows tasks: one at logon and one 5 minutes before each weekday evening run, set in local time and local days. | exe path | tasks | No console window | Implemented |
| SRD-DSK-001.019 | FO-DSK-001 | Should | Each desk start re-checks the evening task time and updates it after a US or local clock change. | clock | task | Skipped when not installed | Implemented |
| SRD-DSK-001.020 | FO-DSK-001 | Must | `python -m us_swing desk` runs the desk; `desk start/status/pause/resume/stop/run-now/install/uninstall` control it. | argv | exit code, text | `start` launches a detached process | Implemented |
| SRD-DSK-001.021 | FO-DSK-001 | Must | The desk loads its steps from the step list in `core/desk_steps.py`, and each step gets the desk folder in its context. | step list | steps | A step that fails to load is logged and left out | Implemented |
| SRD-DSK-001.022 | FO-DSK-001 | Must | `desk proof` runs the score proof on past data and prints its report. | argv | report text, exit code | Loaded by import path; exit 1 when there is no data | Implemented |
