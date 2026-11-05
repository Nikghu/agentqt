# Unit Test Cases — Desk Harness (DSK)

**Document ID:** UTCD-DSK
**Version:** 0.2.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.2.1: 5 test cases added after code review (T22–T26).
> v0.2.0: 57 test cases for FO-DSK-001 (P0a).
> v0.1.0: Empty.

---

## FO-DSK-001: Desk Process Shell

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-DSK-001.004.M01.T01 | MD-DSK-001.004.M01 | Positive | Seven states exist (SRD-DSK-001.004) | `DeskState` members | Running, Sleeping, Paused, Stopping, Stopped, Off, Error | Pass |
| UT-DSK-001.004.M01.T02 | MD-DSK-001.004.M01 | Positive | Off when no file (SRD-DSK-001.006) | missing `desk.db` | state Off; file still missing | Pass |
| UT-DSK-001.004.M01.T03 | MD-DSK-001.004.M01 | Negative | Off when no state row (SRD-DSK-001.006) | tables but empty `desk_state` | state Off | Pass |
| UT-DSK-001.004.M01.T04 | MD-DSK-001.004.M01 | Positive | Live state with fresh heartbeat (SRD-DSK-001.007) | Sleeping, heartbeat 5 s ago | state Sleeping | Pass |
| UT-DSK-001.004.M01.T05 | MD-DSK-001.004.M01 | Negative | Stale heartbeat (SRD-DSK-001.007) | Sleeping, heartbeat 61 s ago | state Error, message "not responding" | Pass |
| UT-DSK-001.004.M01.T06 | MD-DSK-001.004.M01 | Edge | Stopped never stale (SRD-DSK-001.007) | Stopped, heartbeat 1 day ago | state Stopped | Pass |
| UT-DSK-001.004.M01.T07 | MD-DSK-001.004.M01 | Positive | Send command adds pending row (SRD-DSK-001.005) | `send_command(PAUSE)` | one row, kind pause, status pending | Pass |
| UT-DSK-001.004.M01.T08 | MD-DSK-001.004.M01 | Negative | Send command with no desk (SRD-DSK-001.005) | missing `desk.db` | raises `FileNotFoundError`; no file created | Pass |
| UT-DSK-001.004.M01.T09 | MD-DSK-001.004.M01 | Negative | Unknown state text (SRD-DSK-001.004) | row state "Dancing" | state Error, message "unknown state" | Pass |
| UT-DSK-001.001.M02.T01 | MD-DSK-001.001.M02 | Positive | WAL mode on open (SRD-DSK-001.001) | new folder | `journal_mode` is wal; `desk.db` exists | Pass |
| UT-DSK-001.001.M02.T02 | MD-DSK-001.001.M02 | Positive | Tables and version (SRD-DSK-001.002) | new store | 3 tables; `user_version` 1 | Pass |
| UT-DSK-001.001.M02.T03 | MD-DSK-001.001.M02 | Edge | Re-open keeps rows (SRD-DSK-001.002) | write state, close, open again | state row unchanged | Pass |
| UT-DSK-001.001.M02.T04 | MD-DSK-001.001.M02 | Positive | Write state and heartbeat (SRD-DSK-001.003) | set Sleeping, beat at t | row state Sleeping, heartbeat t as UTC ISO | Pass |
| UT-DSK-001.001.M02.T05 | MD-DSK-001.001.M02 | Positive | Resume point round trip (SRD-DSK-001.003) | save `{last_run_id: 3, rerun: true}` | same dict read back | Pass |
| UT-DSK-001.001.M02.T06 | MD-DSK-001.001.M02 | Positive | Run row life (SRD-DSK-001.016) | start evening run, finish ok | row with start, end, result ok | Pass |
| UT-DSK-001.001.M02.T07 | MD-DSK-001.001.M02 | Positive | Open runs marked interrupted (SRD-DSK-001.014) | run with no end | result interrupted, end set; returns 1 | Pass |
| UT-DSK-001.001.M02.T08 | MD-DSK-001.001.M02 | Positive | Pending commands in order (SRD-DSK-001.010) | 3 commands | returned by id; marking done sets status and time | Pass |
| UT-DSK-001.001.M02.T09 | MD-DSK-001.001.M02 | Negative | Root path is a file (SRD-DSK-001.001) | root points to a file | raises `OSError`; nothing written | Pass |
| UT-DSK-001.001.M02.T10 | MD-DSK-001.001.M02 | Negative | Newer schema refused (SRD-DSK-001.002) | `desk.db` with `user_version` 2 | raises `ValueError` "newer desk data" | Pass |
| UT-DSK-001.001.M02.T11 | MD-DSK-001.001.M02 | Negative | Naive time refused (SRD-DSK-001.003) | heartbeat without time zone | raises `ValueError` | Pass |
| UT-DSK-001.015.M03.T01 | MD-DSK-001.015.M03 | Positive | Due after 16:25 ET on a weekday (SRD-DSK-001.015) | Thu 16:30 ET, last run yesterday | True | Pass |
| UT-DSK-001.015.M03.T02 | MD-DSK-001.015.M03 | Negative | Not due before time (SRD-DSK-001.015) | Thu 16:20 ET | False | Pass |
| UT-DSK-001.015.M03.T03 | MD-DSK-001.015.M03 | Negative | Not due twice (SRD-DSK-001.015) | Thu 17:00 ET, last run Thu 16:25 ET | False | Pass |
| UT-DSK-001.015.M03.T04 | MD-DSK-001.015.M03 | Edge | Weekend (SRD-DSK-001.015) | Sat 18:00 ET, last run Fri 16:25 ET | False | Pass |
| UT-DSK-001.015.M03.T05 | MD-DSK-001.015.M03 | Positive | Evening task time in IST (EST) (SRD-DSK-001.018) | 2026-11-05, local tz Asia/Kolkata | "02:50", days TUE–SAT | Pass |
| UT-DSK-001.015.M03.T06 | MD-DSK-001.015.M03 | Edge | Evening task time in IST (EDT) (SRD-DSK-001.018) | 2026-07-01, local tz Asia/Kolkata | "01:50", days TUE–SAT | Pass |
| UT-DSK-001.010.M04.T01 | MD-DSK-001.010.M04 | Negative | Second instance exits (SRD-DSK-001.008) | lock held by first `DeskProcess` | second returns at once; state not changed | Pass |
| UT-DSK-001.010.M04.T02 | MD-DSK-001.010.M04 | Positive | Heartbeat written (SRD-DSK-001.009) | fake clock moves 10 s | heartbeat updated | Pass |
| UT-DSK-001.010.M04.T03 | MD-DSK-001.010.M04 | Positive | Pause then resume (SRD-DSK-001.011) | pause, then resume commands | Paused, then Sleeping; both done | Pass |
| UT-DSK-001.010.M04.T04 | MD-DSK-001.010.M04 | Negative | Resume when Sleeping (SRD-DSK-001.011) | resume command | rejected with reason; state Sleeping | Pass |
| UT-DSK-001.010.M04.T05 | MD-DSK-001.010.M04 | Positive | No run while Paused (SRD-DSK-001.011) | Paused past 16:25 ET | no run row | Pass |
| UT-DSK-001.010.M04.T06 | MD-DSK-001.010.M04 | Positive | Stop saves and exits (SRD-DSK-001.012) | stop command | state Stopped; resume point saved; loop ends | Pass |
| UT-DSK-001.010.M04.T07 | MD-DSK-001.010.M04 | Edge | Stop during run ends after current step (SRD-DSK-001.012) | stop sent by step 1 of 2 | step 2 not called; run interrupted; Stopped | Pass |
| UT-DSK-001.010.M04.T08 | MD-DSK-001.010.M04 | Positive | Task start honours Stopped (SRD-DSK-001.013) | saved Stopped, `resume=False` | exits at once; state Stopped | Pass |
| UT-DSK-001.010.M04.T09 | MD-DSK-001.010.M04 | Positive | Start clears Stopped (SRD-DSK-001.013) | saved Stopped, `resume=True` | state Sleeping | Pass |
| UT-DSK-001.010.M04.T10 | MD-DSK-001.010.M04 | Positive | Interrupted run is rerun (SRD-DSK-001.014) | open run row at start | old row interrupted; new manual run ok | Pass |
| UT-DSK-001.010.M04.T11 | MD-DSK-001.010.M04 | Positive | Evening run calls steps (SRD-DSK-001.016) | 2 steps, clock 16:30 ET Thu | both called in order; run ok; Sleeping | Pass |
| UT-DSK-001.010.M04.T12 | MD-DSK-001.010.M04 | Edge | Zero steps (SRD-DSK-001.016) | no steps, run-now | run ok | Pass |
| UT-DSK-001.010.M04.T13 | MD-DSK-001.010.M04 | Negative | Failed step sets Error (SRD-DSK-001.017) | step raises ValueError | run failed; state Error; message names the step | Pass |
| UT-DSK-001.010.M04.T14 | MD-DSK-001.010.M04 | Positive | Good run clears Error (SRD-DSK-001.017) | Error, then run-now with good step | state Sleeping | Pass |
| UT-DSK-001.010.M04.T15 | MD-DSK-001.010.M04 | Positive | First instance takes the lock (SRD-DSK-001.008) | one `DeskProcess` | state Sleeping, pid set | Pass |
| UT-DSK-001.010.M04.T16 | MD-DSK-001.010.M04 | Negative | No heartbeat before 10 s (SRD-DSK-001.009) | fake clock moves 9 s | heartbeat unchanged | Pass |
| UT-DSK-001.010.M04.T17 | MD-DSK-001.010.M04 | Negative | Unknown command kind (SRD-DSK-001.010) | row kind "dance" | rejected "unknown command"; state unchanged | Pass |
| UT-DSK-001.010.M04.T18 | MD-DSK-001.010.M04 | Negative | Command after stop in same batch (SRD-DSK-001.012) | stop, then pause | pause rejected; state Stopped | Pass |
| UT-DSK-001.010.M04.T19 | MD-DSK-001.010.M04 | Negative | Task start runs when not Stopped (SRD-DSK-001.013) | saved Sleeping, `resume=False` | loop runs; state Sleeping | Pass |
| UT-DSK-001.010.M04.T20 | MD-DSK-001.010.M04 | Negative | No rerun when runs closed (SRD-DSK-001.014) | all runs ended | no new run row | Pass |
| UT-DSK-001.010.M04.T21 | MD-DSK-001.010.M04 | Negative | Run-now while Paused (SRD-DSK-001.016) | Paused, run-now | rejected; no run row | Pass |
| UT-DSK-001.010.M04.T22 | MD-DSK-001.010.M04 | Positive | Heartbeat stays fresh during a long step (SRD-DSK-001.009) | step takes 90 s (fake clock), beat 0.05 s | heartbeat equals the moved clock while the step runs | Pass |
| UT-DSK-001.010.M04.T23 | MD-DSK-001.010.M04 | Negative | Commands left from before start are rejected (SRD-DSK-001.010) | pending stop, then `start --resume` | stop rejected "desk was not running"; state Sleeping | Pass |
| UT-DSK-001.010.M04.T24 | MD-DSK-001.010.M04 | Negative | A crash in the loop is saved as Error (SRD-DSK-001.017) | sleep raises RuntimeError | exit code 1; state Error with the reason | Pass |
| UT-DSK-001.010.M04.T25 | MD-DSK-001.010.M04 | Negative | A pause taken during a failed run is honoured once (SRD-DSK-001.011) | step 1 sends pause, step 2 fails; resume; good run | Paused with the failure message; then Sleeping after the good run | Pass |
| UT-DSK-001.010.M04.T26 | MD-DSK-001.010.M04 | Negative | Pause cancels a run-now from the same batch (SRD-DSK-001.011) | run-now, pause, then resume | no run row | Pass |
| UT-DSK-001.018.M05.T01 | MD-DSK-001.018.M05 | Positive | Desk command when not frozen (SRD-DSK-001.018) | `sys.frozen` unset | `pythonw.exe <repo>/us_swing/run_gui.py desk` | Pass |
| UT-DSK-001.018.M05.T02 | MD-DSK-001.018.M05 | Positive | Desk command when frozen (SRD-DSK-001.018) | `sys.frozen` set | `<exe> desk` | Pass |
| UT-DSK-001.018.M05.T03 | MD-DSK-001.018.M05 | Positive | Install creates two tasks (SRD-DSK-001.018) | fake schtasks runner | 2 create calls: onlogon, weekly at the local task time and days | Pass |
| UT-DSK-001.018.M05.T04 | MD-DSK-001.018.M05 | Negative | Install reports schtasks failure (SRD-DSK-001.018) | runner returns failure | (False, message); no exception | Pass |
| UT-DSK-001.018.M05.T05 | MD-DSK-001.018.M05 | Positive | Sync re-creates on mismatch (SRD-DSK-001.019) | task at 01:50 TUE–SAT, wanted 02:50 TUE–SAT | one create call | Pass |
| UT-DSK-001.018.M05.T06 | MD-DSK-001.018.M05 | Edge | Sync skips when not installed (SRD-DSK-001.019) | query fails | no create call | Pass |
| UT-DSK-001.020.M06.T01 | MD-DSK-001.020.M06 | Positive | Status prints state (SRD-DSK-001.020) | Sleeping store | exit 0; text contains "Sleeping" | Pass |
| UT-DSK-001.020.M06.T02 | MD-DSK-001.020.M06 | Positive | Pause sends command (SRD-DSK-001.020) | `desk pause` | pending pause row; exit 0 | Pass |
| UT-DSK-001.020.M06.T03 | MD-DSK-001.020.M06 | Negative | Unknown sub-command (SRD-DSK-001.020) | `desk fly` | exit 2; usage text | Pass |
| UT-DSK-001.020.M06.T04 | MD-DSK-001.020.M06 | Negative | Command with no desk (SRD-DSK-001.020) | `desk stop`, no `desk.db` | exit 1; text "Desk is off" | Pass |
