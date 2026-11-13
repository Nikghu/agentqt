# Unit Test Cases — Desk Harness (DSK)

**Document ID:** UTCD-DSK
**Version:** 0.4.1
**Status:** Draft
**Last Updated:** 2026-11-11
**Project:** US Swing Trading System

> v0.18.0: UT-DSK-011.033–.043, 007.011 and 008.010 M2 cases added (Not Run, 27) (2026-11-13).
> v0.17.1: UT-DSK-011 M1 cases Pass (47, 2026-11-13).
> v0.17.0: UT-DSK-011.003–.032 M1 cases added (Not Run, 47); UT-DSK-011.014.M27.T01–T02 superseded by UT-DSK-011.014.M29.T01–T02 (2026-11-13).
> v0.16.1: UT-DSK-011.001–.014, 012.001–.011 and 001.010.M04.T32–T33 Pass (52, 2026-11-13).
> v0.16.0: UT-DSK-011.001–.014 and 012.001–.011 added (Not Run, 52 cases) — AI Desk v3 M0 (2026-11-13).
> v0.15.1: UT-DSK-010.016.M25.T01–T03 Pass (2026-11-12).
> v0.15.0: UT-DSK-010.016.M25.T01–T03 added (Not Run) — owner test ticket (2026-11-12).
> v0.14.1: UT-DSK-010.015.M25.T01–T03 Pass (2026-11-11).
> v0.14.0: UT-DSK-010.015.M25.T01–T03 added (Not Run) — follow-up tickets (step F).
> v0.13.1: Step E cases Pass (46, 2026-11-11).
> v0.13.0: Autonomous desk step E (2026-11-11): UT-DSK-004.006–.010, 007.010, 010.001–.014 added (46 cases).
> v0.12.1: Step D cases Pass (18, 2026-11-11).
> v0.12.0: Autonomous desk step D (2026-11-11): UT-DSK-003.020–.025, 007.009 added (18 cases).
> v0.11.1: Step C cases Pass (23 cases, 2026-11-11).
> v0.11.0: Autonomous desk step C (2026-11-11): UT-DSK-009.* added (26 cases incl. 3 after code review).
> v0.10.1: Step B cases Pass (32 cases incl. 6 rewritten, 2026-11-11).
> v0.10.0: Autonomous desk step B (2026-11-11): UT-DSK-003.010.M16.T01/T03, 003.011.M16.T01/T03, 003.012.M16.T01/T02 rewritten (no LangGraph); UT-DSK-003.014–.019 and 007.008 added (26 cases).
> v0.9.0: Autonomous desk step A (2026-11-11): UT-DSK-001.015.M03.T01–T06, 001.018.M05.T03–T06, 001.010.M04.T05/T11 rewritten; M04.T27–T31, M06.T05–T06, M02.T12, UT-DSK-007.007.M21.T01–T03 added.
> v0.8.1: UT-DSK-008.* Pass (17 cases, 19 test runs incl. parametrize, 2026-11-10).
> v0.8.0: 17 test cases for FO-DSK-008 (employee file, migration, versions, draft test).
> v0.7.0: 23 test cases for P6 (hiring, shadow, seat caps, weekly report).
> v0.6.0: 41 test cases for P5b (events, market clock, LangGraph order, replay).
> v0.5.1: P5a cases reworded without employee names; 6 cases added for identity as data (user, 2026-11-06).
> v0.5.0: 38 test cases for the P5a lean harness.
> v0.4.0: UT-DSK-001.022.M06.T01–T02 added (`desk proof`).
> v0.3.0: UT-DSK-001.021.M07.T01–T02 added.
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
| UT-DSK-001.015.M03.T01 | MD-DSK-001.015.M03 | Positive | Due at the open of the morning window (SRD-DSK-001.015) | Wed 2026-11-11 04:00 ET, no runs | True | Pass |
| UT-DSK-001.015.M03.T02 | MD-DSK-001.015.M03 | Negative | Not due before 04:00 ET or from 16:00 ET (SRD-DSK-001.015) | Wed 03:59 ET; Wed 16:00 ET | False; False | Pass |
| UT-DSK-001.015.M03.T03 | MD-DSK-001.015.M03 | Negative | Not due after an ok morning or manual run today (SRD-DSK-001.015) | Wed 09:00 ET, morning ok at 08:31; or manual ok at 08:40 | False | Pass |
| UT-DSK-001.015.M03.T04 | MD-DSK-001.015.M03 | Edge | Weekend and NYSE holiday (SRD-DSK-001.015) | Sat 2026-11-14 09:00 ET; Thu 2026-11-26 09:00 ET | False | Pass |
| UT-DSK-001.015.M03.T05 | MD-DSK-001.015.M03 | Positive | Retry 15 min after a failed try, at most 3 (SRD-DSK-001.015) | failed morning at 08:31; now 08:45 / 08:46; 3 failed tries | False / True; False | Pass |
| UT-DSK-001.015.M03.T06 | MD-DSK-001.015.M03 | Edge | Yesterday's ok run and an interrupted try do not count (SRD-DSK-001.015, SRD-DSK-003.013) | ok morning yesterday, interrupted morning today 08:31; now 08:35 / 08:46 | False (15 min spacing) / True | Pass |
| UT-DSK-001.010.M04.T01 | MD-DSK-001.010.M04 | Negative | Second instance exits (SRD-DSK-001.008) | lock held by first `DeskProcess` | second returns at once; state not changed | Pass |
| UT-DSK-001.010.M04.T02 | MD-DSK-001.010.M04 | Positive | Heartbeat written (SRD-DSK-001.009) | fake clock moves 10 s | heartbeat updated | Pass |
| UT-DSK-001.010.M04.T03 | MD-DSK-001.010.M04 | Positive | Pause then resume (SRD-DSK-001.011) | pause, then resume commands | Paused, then Sleeping; both done | Pass |
| UT-DSK-001.010.M04.T04 | MD-DSK-001.010.M04 | Negative | Resume when Sleeping (SRD-DSK-001.011) | resume command | rejected with reason; state Sleeping | Pass |
| UT-DSK-001.010.M04.T05 | MD-DSK-001.010.M04 | Positive | No run while Paused (SRD-DSK-001.011) | Paused at 09:00 ET on a trading day | no run row | Pass |
| UT-DSK-001.010.M04.T06 | MD-DSK-001.010.M04 | Positive | Stop saves and exits (SRD-DSK-001.012) | stop command | state Stopped; resume point saved; loop ends | Pass |
| UT-DSK-001.010.M04.T07 | MD-DSK-001.010.M04 | Edge | Stop during run ends after current step (SRD-DSK-001.012) | stop sent by step 1 of 2 | step 2 not called; run interrupted; Stopped | Pass |
| UT-DSK-001.010.M04.T08 | MD-DSK-001.010.M04 | Positive | Task start honours Stopped (SRD-DSK-001.013) | saved Stopped, `resume=False` | exits at once; state Stopped | Pass |
| UT-DSK-001.010.M04.T09 | MD-DSK-001.010.M04 | Positive | Start clears Stopped (SRD-DSK-001.013) | saved Stopped, `resume=True` | state Sleeping | Pass |
| UT-DSK-001.010.M04.T10 | MD-DSK-001.010.M04 | Positive | Interrupted run is rerun (SRD-DSK-001.014) | open run row at start | old row interrupted; new manual run ok | Pass |
| UT-DSK-001.010.M04.T11 | MD-DSK-001.010.M04 | Positive | Morning run calls steps (SRD-DSK-001.016, SRD-DSK-003.013) | 2 steps, clock Wed 08:31 ET | both called in order; run kind morning, ok; Sleeping | Pass |
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
| UT-DSK-001.010.M04.T27 | MD-DSK-001.010.M04 | Positive | Parent gone stops the desk (SRD-DSK-001.019) | `parent_alive` returns False on the 2nd tick | state Stopped; resume point saved; loop ends | Pass |
| UT-DSK-001.010.M04.T28 | MD-DSK-001.010.M04 | Edge | Parent gone during a run (SRD-DSK-001.019) | parent dies during step 1 of 2 | step 2 not called; run interrupted; rerun saved | Pass |
| UT-DSK-001.010.M04.T29 | MD-DSK-001.010.M04 | Negative | No parent watch without a parent (SRD-DSK-001.019) | `parent_alive=None`, 3 ticks | state Sleeping | Pass |
| UT-DSK-001.010.M04.T30 | MD-DSK-001.010.M04 | Positive | Failed morning try is retried after 15 min (SRD-DSK-001.015) | failing step; clock 08:31, 08:40, 08:47 ET | run rows at 08:31 and 08:47 only | Pass |
| UT-DSK-001.010.M04.T31 | MD-DSK-001.010.M04 | Positive | pid_alive for this process and a dead pid (SRD-DSK-001.019) | `os.getpid()`; pid of a finished child | True; False | Pass |
| UT-DSK-001.018.M05.T01 | MD-DSK-001.018.M05 | Positive | Desk command when not frozen (SRD-DSK-001.018) | `sys.frozen` unset | `pythonw.exe <repo>/us_swing/run_gui.py desk` | Pass |
| UT-DSK-001.018.M05.T02 | MD-DSK-001.018.M05 | Positive | Desk command when frozen (SRD-DSK-001.018) | `sys.frozen` set | `<exe> desk` | Pass |
| UT-DSK-001.018.M05.T03 | MD-DSK-001.018.M05 | Positive | Old desk tasks deleted (SRD-DSK-001.018) | fake schtasks runner | 2 delete calls: USSwing_Desk, USSwing_Desk_Evening; (True, "") | Pass |
| UT-DSK-001.018.M05.T04 | MD-DSK-001.018.M05 | Negative | Missing task is not an error; other failure is (SRD-DSK-001.018) | runner says "cannot find"; runner says "access denied" | (True, ""); (False, "access denied") | Pass |
| UT-DSK-001.018.M05.T05 | MD-DSK-001.004.M01 | Positive | Launch passes the parent pid (SRD-DSK-001.019, .020) | `launch_desk(True, parent=1234)` with a fake Popen | command ends with `--resume --parent 1234` | Pass |
| UT-DSK-001.018.M05.T06 | MD-DSK-001.004.M01 | Edge | Launch without a parent (SRD-DSK-001.020) | `launch_desk(True)` | no `--parent` in the command | Pass |
| UT-DSK-001.020.M06.T01 | MD-DSK-001.020.M06 | Positive | Status prints state (SRD-DSK-001.020) | Sleeping store | exit 0; text contains "Sleeping" | Pass |
| UT-DSK-001.020.M06.T02 | MD-DSK-001.020.M06 | Positive | Pause sends command (SRD-DSK-001.020) | `desk pause` | pending pause row; exit 0 | Pass |
| UT-DSK-001.020.M06.T03 | MD-DSK-001.020.M06 | Negative | Unknown sub-command (SRD-DSK-001.020) | `desk fly` | exit 2; usage text | Pass |
| UT-DSK-001.020.M06.T04 | MD-DSK-001.020.M06 | Negative | Command with no desk (SRD-DSK-001.020) | `desk stop`, no `desk.db` | exit 1; text "Desk is off" | Pass |
| UT-DSK-001.020.M06.T05 | MD-DSK-001.020.M06 | Positive | `--parent PID` gives the loop a parent watch (SRD-DSK-001.020) | `desk --resume --parent 1234` with a fake process class | process built with resume True and a parent check for 1234 | Pass |
| UT-DSK-001.020.M06.T06 | MD-DSK-001.020.M06 | Negative | `install` is gone (SRD-DSK-001.020) | `desk install` | exit 2; usage text without install | Pass |
| UT-DSK-001.001.M02.T12 | MD-DSK-001.001.M02 | Positive | Runs since a time (SRD-DSK-001.015) | 3 runs, one older than the cut | 2 (kind, start, result) tuples, oldest first | Pass |
| UT-DSK-001.021.M07.T01 | MD-DSK-001.021.M07 | Positive | Steps load from the list (SRD-DSK-001.021) | list with one test step path | one step with its name | Pass |
| UT-DSK-001.021.M07.T02 | MD-DSK-001.021.M07 | Negative | Bad path is left out (SRD-DSK-001.021) | list with a missing module | empty list; warning logged | Pass |
| UT-DSK-001.022.M06.T01 | MD-DSK-001.020.M06 | Positive | Proof report printed (SRD-DSK-001.022) | `desk proof`; runner returns a report | report printed; exit 0 | Pass |
| UT-DSK-001.022.M06.T02 | MD-DSK-001.020.M06 | Negative | No data for proof (SRD-DSK-001.022) | `desk proof`; runner returns None | message printed; exit 1 | Pass |

## FO-DSK-002–005: Lean Harness (P5a)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-DSK-002.002.M09.T01 | MD-DSK-002.002.M09 | Positive | Job file loads (SRD-DSK-002.002) | valid soul.md + job.yaml | Hire with spec, soul text and hash | Pass |
| UT-DSK-002.002.M09.T02 | MD-DSK-002.002.M09 | Negative | Bad job file (SRD-DSK-002.002) | missing models or id; unknown key; bad trigger or level | None; one warning each | Pass |
| UT-DSK-002.002.M09.T03 | MD-DSK-002.002.M09 | Negative | Missing soul.md (SRD-DSK-002.002) | folder without soul.md | None; warning | Pass |
| UT-DSK-002.004.M09.T01 | MD-DSK-002.002.M09 | Positive | Roster table (SRD-DSK-002.004) | load twice | one row with id, name, title, level, reports_to, skill, version, hash | Pass |
| UT-DSK-002.004.M09.T02 | MD-DSK-002.002.M09 | Edge | Changed file, same version (SRD-DSK-002.004) | edit soul.md, keep version | new hash stored; warning logged | Pass |
| UT-DSK-002.001.M09.T01 | MD-DSK-002.002.M09 | Negative | Unknown skill (SRD-DSK-002.001) | job file naming a skill not in the list | that employee asleep; warning; others load | Pass |
| UT-DSK-002.001.M09.T02 | MD-DSK-002.002.M09 | Positive | Defaults seeded (SRD-DSK-002.001) | shipped default folders | copied once; each uses a known skill | Pass |
| UT-DSK-002.003.M11.T01 | MD-DSK-004.001.M11 | Positive | Soul is the system prompt (SRD-DSK-002.003) | fake model records its input | system text starts with soul.md; model from job.yaml | Pass |
| UT-DSK-002.003.M11.T02 | MD-DSK-004.001.M11 | Negative | Soul cannot change rules (SRD-DSK-002.003) | soul.md names another model | job.yaml model still used | Pass |
| UT-DSK-002.004.M09.T03 | MD-DSK-002.002.M09 | Negative | Bad file not stored (SRD-DSK-002.004) | invalid job.yaml | no roster row | Pass |
| UT-DSK-002.005.M10.T01 | MD-DSK-003.001.M10 | Positive | Context is ask only (SRD-DSK-002.005) | employee inspects its context | home and ask, plus talk, drafts, send and asked with talk off | Pass |
| UT-DSK-002.005.M10.T02 | MD-DSK-003.001.M10 | Negative | Job files untouched (SRD-DSK-002.005) | full run | job file hashes unchanged | Pass |
| UT-DSK-002.006.M09.T01 | MD-DSK-002.002.M09 | Positive | Rename and restructure (SRD-DSK-002.006) | change name, level and reports_to in job.yaml | loaded with the new values; no code change | Pass |
| UT-DSK-002.006.M09.T02 | MD-DSK-002.002.M09 | Negative | Repeated id (SRD-DSK-002.006) | two folders with one id | second stays asleep; warning | Pass |
| UT-DSK-002.007.M09.T01 | MD-DSK-002.002.M09 | Negative | Edits never overwritten (SRD-DSK-002.007) | edited copy, seed again | 0 copied; edit kept | Pass |
| UT-DSK-002.007.M09.T02 | MD-DSK-002.002.M09 | Positive | Defaults seeded into the desk folder (SRD-DSK-002.007) | empty desk folder | default folders copied | Pass |
| UT-DSK-003.001.M10.T01 | MD-DSK-003.001.M10 | Positive | Wakes after run (SRD-DSK-003.001) | fake employee, fresh facts, fake model | act called once; brief written | Pass |
| UT-DSK-003.001.M10.T02 | MD-DSK-003.001.M10 | Negative | Failing employee (SRD-DSK-003.001) | act raises; second employee ok | error logged; second runs; desk run ok | Pass |
| UT-DSK-003.001.M10.T03 | MD-DSK-003.001.M10 | Positive | Step order (SRD-DSK-003.001) | loaded step list | AI employees after Ideas | Pass |
| UT-DSK-003.002.M10.T01 | MD-DSK-003.001.M10 | Negative | Once per data day (SRD-DSK-003.002) | run twice on same day | act called once | Pass |
| UT-DSK-003.002.M10.T02 | MD-DSK-003.001.M10 | Edge | Failed day tried again (SRD-DSK-003.002) | first run no valid answer | second run calls again | Pass |
| UT-DSK-003.002.M10.T03 | MD-DSK-003.001.M10 | Positive | Next day wakes again (SRD-DSK-003.002) | done yesterday, new data day | act called | Pass |
| UT-DSK-003.002.M10.T04 | MD-DSK-003.001.M10 | Negative | Rename keeps the day (SRD-DSK-003.002) | rename after a run, same day | not woken again | Pass |
| UT-DSK-003.003.M10.T01 | MD-DSK-003.001.M10 | Negative | Stale data (SRD-DSK-003.003) | facts fresh False | act not called; reason logged | Pass |
| UT-DSK-003.003.M10.T02 | MD-DSK-003.001.M10 | Positive | Fresh data wakes (SRD-DSK-003.003) | facts fresh True | act called | Pass |
| UT-DSK-004.001.M11.T01 | MD-DSK-004.001.M11 | Positive | OpenRouter reply read (SRD-DSK-004.001) | fake HTTP reply with usage | text, tokens and cost | Pass |
| UT-DSK-004.001.M11.T02 | MD-DSK-004.001.M11 | Positive | Claude CLI reply read (SRD-DSK-004.001) | fake CLI JSON with usage and total_cost_usd | text and tokens; cost 0 | Pass |
| UT-DSK-004.001.M11.T03 | MD-DSK-004.001.M11 | Negative | Source switched off (SRD-DSK-004.001) | primary source off in settings | primary skipped; backup used | Pass |
| UT-DSK-004.002.M11.T01 | MD-DSK-004.001.M11 | Positive | Valid answer (SRD-DSK-004.002) | JSON inside text | typed result; 1 valid try | Pass |
| UT-DSK-004.002.M11.T02 | MD-DSK-004.001.M11 | Negative | Retry then backup (SRD-DSK-004.002) | primary bad twice, backup good | result from backup; 3 tries, 2 invalid with errors | Pass |
| UT-DSK-004.002.M11.T03 | MD-DSK-004.001.M11 | Negative | All tries bad (SRD-DSK-004.002) | all answers bad or errors | None; 4 tries recorded | Pass |
| UT-DSK-004.003.M12.T01 | MD-DSK-004.003.M12 | Negative | Budget used up (SRD-DSK-004.003) | spent 10.00 of 10.00 | refused; no call; refusal logged | Pass |
| UT-DSK-004.003.M12.T02 | MD-DSK-004.003.M12 | Negative | Employee cap used up (SRD-DSK-004.003) | employee spent 3.00 of 3.00 | refused | Pass |
| UT-DSK-004.003.M12.T03 | MD-DSK-004.003.M12 | Positive | Last month not counted (SRD-DSK-004.003) | 9.99 spent last month | allowed | Pass |
| UT-DSK-004.004.M12.T01 | MD-DSK-004.003.M12 | Negative | Claude CLI daily token cap (SRD-DSK-004.004) | 200,000 CLI tokens today, cap 200,000 | refused; OpenRouter still allowed | Pass |
| UT-DSK-004.004.M12.T02 | MD-DSK-004.003.M12 | Negative | Employee calls per day (SRD-DSK-004.004) | calls_per_day 3, 12 tries today (4 per call) | refused | Pass |
| UT-DSK-004.004.M12.T03 | MD-DSK-004.003.M12 | Positive | Under the caps (SRD-DSK-004.004) | 150,000 CLI tokens, cap 200,000 | allowed | Pass |
| UT-DSK-004.005.M13.T01 | MD-DSK-004.005.M13 | Positive | Settings round trip (SRD-DSK-004.005) | save then load | same values | Pass |
| UT-DSK-004.005.M13.T02 | MD-DSK-004.005.M13 | Negative | No or broken settings file (SRD-DSK-004.005) | missing or bad JSON | defaults: both sources off, USD 10, 200,000 CLI tokens | Pass |
| UT-DSK-005.001.M14.T01 | MD-DSK-005.001.M14 | Positive | Try recorded (SRD-DSK-005.001) | one attempt | row with every field | Pass |
| UT-DSK-005.001.M14.T02 | MD-DSK-005.001.M14 | Negative | Call error recorded (SRD-DSK-005.001) | source raises | invalid row with error text, no answer | Pass |
| UT-DSK-005.001.M14.T03 | MD-DSK-005.001.M14 | Edge | Old tables get id columns (SRD-DSK-005.001) | briefs made before employee_id | column added on open | Pass |
| UT-DSK-005.002.M14.T01 | MD-DSK-005.001.M14 | Negative | Append-only (SRD-DSK-005.002) | UPDATE and DELETE on activity and briefs | sqlite error; rows unchanged | Pass |
| UT-DSK-005.002.M14.T02 | MD-DSK-005.001.M14 | Positive | Inserts still work (SRD-DSK-005.002) | refused update, then new try | new row added | Pass |
| UT-DSK-005.003.M14.T01 | MD-DSK-005.001.M14 | Positive | Brief stored (SRD-DSK-005.003) | feed item | briefs row with time and data day | Pass |
| UT-DSK-005.003.M14.T02 | MD-DSK-005.001.M14 | Negative | Empty brief (SRD-DSK-005.003) | feed item with empty text | ValueError; nothing stored | Pass |

## FO-DSK-002, -003, -005: Events, Market Clock, LangGraph Order and Replay (P5b)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-DSK-002.008.M16.T01 | MD-DSK-003.006.M16 | Positive | Needs set the order (SRD-DSK-002.008) | fake skills A, B needs A, C needs A and B | order A, B, C | Pass |
| UT-DSK-002.008.M16.T02 | MD-DSK-003.006.M16 | Negative | Unknown need key (SRD-DSK-002.008) | skill needs a key nobody has | left out; warning; skill still runs | Pass |
| UT-DSK-002.008.M16.T03 | MD-DSK-003.006.M16 | Edge | reports_to is not order (SRD-DSK-002.008) | lead skill's employee reports to an expert | lead still runs after that expert's skill | Pass |
| UT-DSK-002.009.M09.T01 | MD-DSK-002.002.M09 | Positive | Trigger list (SRD-DSK-002.009) | `trigger: [after_run, market_close]` | spec trigger has both kinds | Pass |
| UT-DSK-002.009.M09.T02 | MD-DSK-002.002.M09 | Positive | Single trigger still loads (SRD-DSK-002.009) | P5a file with `trigger: after_run` | trigger ("after_run",) | Pass |
| UT-DSK-002.009.M09.T03 | MD-DSK-002.002.M09 | Negative | Unknown event kind (SRD-DSK-002.009) | `trigger: [after_run, lunch]` | asleep; warning | Pass |
| UT-DSK-003.004.M15.T01 | MD-DSK-003.004.M15 | Positive | Event stored (SRD-DSK-003.004) | post `market_close` | row with priority, deadline, expiry, state waiting | Pass |
| UT-DSK-003.004.M15.T02 | MD-DSK-003.004.M15 | Negative | Repeat ignored (SRD-DSK-003.004) | post `market_close` twice for one day | one row; second post returns False | Pass |
| UT-DSK-003.004.M15.T03 | MD-DSK-003.004.M15 | Edge | after_run per run (SRD-DSK-003.004) | post `after_run` for runs 7 and 8, same day | two rows | Pass |
| UT-DSK-003.005.M15.T01 | MD-DSK-003.004.M15 | Positive | Kind rules (SRD-DSK-003.005) | each kind | P0 regime_change, P1 after_run, P2 clock events | Pass |
| UT-DSK-003.005.M15.T02 | MD-DSK-003.004.M15 | Negative | Unknown kind (SRD-DSK-003.005) | post `lunch` | ValueError; no row | Pass |
| UT-DSK-003.006.M16.T01 | MD-DSK-003.006.M16 | Positive | Priority order (SRD-DSK-003.006) | waiting P2, P1, P0 posted in that order | handled P0, P1, P2 | Pass |
| UT-DSK-003.006.M16.T02 | MD-DSK-003.006.M16 | Edge | Same priority by time (SRD-DSK-003.006) | two P2 events, 09:30 then 16:00 | older first | Pass |
| UT-DSK-003.006.M16.T03 | MD-DSK-003.006.M16 | Negative | No listener (SRD-DSK-003.006) | event no employee listens to | marked done; nobody woken; has_work False | Pass |
| UT-DSK-003.007.M16.T01 | MD-DSK-003.006.M16 | Negative | Expired (SRD-DSK-003.007) | P2 event 31 minutes old | state expired; not handled; logged | Pass |
| UT-DSK-003.007.M16.T02 | MD-DSK-003.006.M16 | Negative | Late (SRD-DSK-003.007) | P0 event handled 20 minutes after posting | state late; logged | Pass |
| UT-DSK-003.007.M16.T03 | MD-DSK-003.006.M16 | Positive | On time (SRD-DSK-003.007) | P1 event handled after 10 minutes | state done | Pass |
| UT-DSK-003.008.M03.T01 | MD-DSK-001.015.M03 | Positive | Clock events due (SRD-DSK-003.008) | trading day 09:31 and 16:01 New York | market_open; then market_close | Pass |
| UT-DSK-003.008.M03.T02 | MD-DSK-001.015.M03 | Negative | Not a trading day (SRD-DSK-003.008) | Saturday; NYSE holiday | nothing due | Pass |
| UT-DSK-003.008.M03.T03 | MD-DSK-001.015.M03 | Negative | Before the open (SRD-DSK-003.008) | trading day 09:29 | nothing due | Pass |
| UT-DSK-003.008.M04.T01 | MD-DSK-001.010.M04 | Positive | Event run from the loop (SRD-DSK-003.008) | fake clock 16:01, employee on market_close | one `event` run; market steps not called; employee woken | Pass |
| UT-DSK-003.008.M04.T02 | MD-DSK-001.010.M04 | Negative | Paused desk (SRD-DSK-003.008) | paused, 16:01 | no run | Pass |
| UT-DSK-003.009.M16.T01 | MD-DSK-003.006.M16 | Negative | No wake within 30 minutes (SRD-DSK-003.009) | last wake 12 minutes ago, P2 event | not woken; reason logged | Pass |
| UT-DSK-003.009.M16.T02 | MD-DSK-003.006.M16 | Positive | P0 passes the 30-minute rule (SRD-DSK-003.009) | last wake 12 minutes ago, P0 event | woken | Pass |
| UT-DSK-003.009.M14.T01 | MD-DSK-005.001.M14 | Edge | Replay is not a wake (SRD-DSK-003.009) | only replay tries 5 minutes ago | last_wake None | Pass |
| UT-DSK-003.010.M16.T01 | MD-DSK-003.006.M16 | Positive | Chain run order (SRD-DSK-003.010) | 3 experts, risk, lead with real skill needs, fake model | lead last; risk after setup review; each once | Pass |
| UT-DSK-003.010.M16.T02 | MD-DSK-003.006.M16 | Negative | Loop in needs (SRD-DSK-003.010) | A needs B, B needs A | nobody woken; one warning | Pass |
| UT-DSK-003.010.M16.T03 | MD-DSK-003.006.M16 | Edge | Whole chain in one pass (SRD-DSK-003.010) | nothing fails | one `handle()` wakes every employee; all events done | Pass |
| UT-DSK-003.011.M16.T01 | MD-DSK-003.006.M16 | Negative | Failed step (SRD-DSK-003.011) | one expert fails 3 times | experts that do not need it still run; lead runs partial | Pass |
| UT-DSK-003.011.M16.T02 | MD-DSK-003.006.M16 | Positive | Missing view noted (SRD-DSK-003.011) | needed expert asleep (stale) | dependent runs; its facts say the view is missing | Pass |
| UT-DSK-003.012.M16.T01 | MD-DSK-003.006.M16 | Positive | No LangGraph in the desk (SRD-DSK-003.012) | scan all `us_swing` sources | no `langgraph` import | Pass |
| UT-DSK-003.012.M16.T02 | MD-DSK-003.006.M16 | Negative | Dependency removed (SRD-DSK-003.012) | read `pyproject.toml` and `USSwing.spec` | no `langgraph` or `langchain_core` | Pass |
| UT-DSK-003.001.M10.T04 | MD-DSK-003.001.M10 | Positive | Step posts after_run (SRD-DSK-003.001) | desk run with fresh facts | one after_run event, then done | Pass |
| UT-DSK-005.005.M17.T01 | MD-DSK-005.005.M17 | Positive | Replay re-sends (SRD-DSK-005.005) | recorded run, fake model | same system and user text sent; recorded model used | Pass |
| UT-DSK-005.005.M17.T02 | MD-DSK-005.005.M17 | Positive | Options (SRD-DSK-005.005) | `--employee` and `--model` | only that employee; given model | Pass |
| UT-DSK-005.005.M17.T03 | MD-DSK-005.005.M17 | Negative | Budget applies (SRD-DSK-005.005) | budget used up | no call; report says refused | Pass |
| UT-DSK-005.006.M17.T01 | MD-DSK-005.005.M17 | Positive | Replay tries marked (SRD-DSK-005.006) | replay one employee | activity rows with replay 1 | Pass |
| UT-DSK-005.006.M17.T02 | MD-DSK-005.005.M17 | Negative | Nothing else written (SRD-DSK-005.006) | replay a run | briefs, events and view tables unchanged; act not called | Pass |
| UT-DSK-005.007.M17.T01 | MD-DSK-005.005.M17 | Positive | Report (SRD-DSK-005.007) | old valid, new valid with one field changed | ASCII lines name the employee, both checks and the field | Pass |
| UT-DSK-005.007.M17.T02 | MD-DSK-005.005.M17 | Negative | Unknown run (SRD-DSK-005.007) | run id with no tries | exit 1; message | Pass |
| UT-DSK-005.007.M17.T03 | MD-DSK-005.005.M17 | Edge | Employee gone (SRD-DSK-005.007) | recorded employee folder removed | "employee not found"; no call | Pass |
| UT-DSK-002.008.M16.T04 | MD-DSK-003.006.M16 | Edge | Same skill is not an edge (SRD-DSK-002.008) | two employees with one skill that needs itself | both run; no wait | Pass |
| UT-DSK-003.008.M03.T04 | MD-DSK-001.015.M03 | Edge | Clock window (SRD-DSK-003.008) | trading day 12:00, 16:01, 16:31 | nothing; market_close; nothing | Pass |
| UT-DSK-003.008.M04.T03 | MD-DSK-001.010.M04 | Negative | Event check error (SRD-DSK-003.008) | has_work raises a locked-database error | logged; no run; desk keeps going | Pass |
| UT-DSK-003.010.M16.T04 | MD-DSK-003.006.M16 | Negative | Loop event closed (SRD-DSK-003.010) | woken skills need each other | event done with note loop in needs | Pass |
| UT-DSK-003.011.M16.T03 | MD-DSK-003.006.M16 | Negative | Pass error (SRD-DSK-003.011) | router raises outside a wake | logged; event closed with note failed | Pass |
| UT-DSK-005.005.M17.T04 | MD-DSK-005.005.M17 | Edge | Soul with rule lines (SRD-DSK-005.005) | soul.md holds --- between blank lines | same system and user text sent again | Pass |
| UT-DSK-005.006.M14.T01 | MD-DSK-005.001.M14 | Positive | Replays use no live quota (SRD-DSK-005.006) | one live and one replay try today | day_tries 1; cost of both counted | Pass |

## FO-DSK-006: Hiring Pipeline and Process Analytics

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-DSK-006.001.M18.T01 | MD-DSK-006.001.M18 | Positive | Start a hire (SRD-DSK-006.001) | skill setup_review, expert, made-up name, claude default | new folder with status shadow, hired_on, version 1, chosen model; soul from the default | Pass |
| UT-DSK-006.001.M18.T02 | MD-DSK-006.001.M18 | Edge | Next id (SRD-DSK-006.001) | folders emp-001, emp-003, emp-010 | new id emp-011 | Pass |
| UT-DSK-006.002.M18.T01 | MD-DSK-006.001.M18 | Negative | Refused hires (SRD-DSK-006.002) | unknown skill; lead level; name used (other case); expert cap full | each refused with a reason; no folder made | Pass |
| UT-DSK-006.003.M13.T01 | MD-DSK-004.005.M13 | Positive | Cap defaults and save (SRD-DSK-006.003) | no file; save caps 9/6/31 | 8/5/30; then 9/6/31 after load | Pass |
| UT-DSK-006.003.M13.T02 | MD-DSK-004.005.M13 | Negative | Bad cap (SRD-DSK-006.003) | cap 0 | refused | Pass |
| UT-DSK-006.003.M18.T01 | MD-DSK-006.001.M18 | Positive | Seat count (SRD-DSK-006.003) | 2 active, 1 shadow, 1 retired experts | expert count 3 | Pass |
| UT-DSK-006.004.M19.T01 | MD-DSK-006.004.M19 | Positive | Shadow answer recorded only (SRD-DSK-006.004) | shadow hire, fresh facts, valid answer | activity rows with shadow 1; act not called; no briefs | Pass |
| UT-DSK-006.004.M19.T02 | MD-DSK-006.004.M19 | Negative | One answer per day (SRD-DSK-006.004) | shadow already answered for the data day | not asked again | Pass |
| UT-DSK-006.004.M19.T03 | MD-DSK-006.004.M19 | Positive | Through the employees step (SRD-DSK-006.004) | holder and shadow for one skill, after_run | holder writes its brief; shadow writes only shadow tries | Pass |
| UT-DSK-006.005.M18.T01 | MD-DSK-006.001.M18 | Positive | Ready after 14 days (SRD-DSK-006.005) | 13, then 14 shadow data days | not ready, then ready | Pass |
| UT-DSK-006.005.M19.T01 | MD-DSK-006.004.M19 | Negative | No calls after 14 days (SRD-DSK-006.005) | shadow with 14 days | not asked; one [Hiring] line when day 14 is reached | Pass |
| UT-DSK-006.006.M18.T01 | MD-DSK-006.001.M18 | Positive | Shadow report (SRD-DSK-006.006) | 3 shadow days, holder tries on 2 of them | days, valid share, tokens, cost per row; agreement over common days | Pass |
| UT-DSK-006.006.M18.T02 | MD-DSK-006.001.M18 | Edge | No holder (SRD-DSK-006.006) | skill without an active holder | holder rows empty; agreement None | Pass |
| UT-DSK-006.006.M18.T03 | MD-DSK-006.001.M18 | Positive | Agreement values (SRD-DSK-006.006) | same answers; one grade differs; only free text differs | 1.0; between 0 and 1; 1.0 | Pass |
| UT-DSK-006.007.M18.T01 | MD-DSK-006.001.M18 | Positive | Replace (SRD-DSK-006.007) | ready hire with one holder | approvals row; holder retired, hire active; versions + 1; comments kept | Pass |
| UT-DSK-006.007.M18.T02 | MD-DSK-006.001.M18 | Positive | Add and Reject (SRD-DSK-006.007) | ready hire without holder; another hire | Add makes it active; Reject retires it | Pass |
| UT-DSK-006.007.M18.T03 | MD-DSK-006.001.M18 | Negative | Refused decisions (SRD-DSK-006.007) | Replace before ready; Add with an active holder; unknown hire | refused with a reason; no row; files unchanged | Pass |
| UT-DSK-006.007.M18.T04 | MD-DSK-006.001.M18 | Negative | Approvals append-only (SRD-DSK-006.007) | UPDATE and DELETE on approvals | both refused | Pass |
| UT-DSK-006.008.M09.T01 | MD-DSK-002.002.M09 | Positive | Status read (SRD-DSK-006.008) | files with retired, shadow and no status | retired not loaded; shadow loaded; no status = active | Pass |
| UT-DSK-006.009.M20.T01 | MD-DSK-006.009.M20 | Positive | Friday report (SRD-DSK-006.009) | Friday run, tries of 2 employees and a shadow hire | one desk_reports row with per-employee figures and shadow days | Pass |
| UT-DSK-006.009.M20.T02 | MD-DSK-006.009.M20 | Negative | Once per week (SRD-DSK-006.009) | second run the same week | no new row | Pass |
| UT-DSK-006.009.M20.T03 | MD-DSK-006.009.M20 | Edge | Missed Friday (SRD-DSK-006.009) | first run on Monday | report for the Friday before; Saturday–Friday period | Pass |
| UT-DSK-006.010.M18.T01 | MD-DSK-006.001.M18 | Positive | Log lines (SRD-DSK-006.010) | start, decide, weekly report | [Hiring] and [Report] lines with no internal names | Pass |

## FO-DSK-007: AI Problem Alerts

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-DSK-007.001.M21.T01 | MD-DSK-007.001.M21 | Positive | Spot problems (SRD-DSK-007.001) | login, key, credit and form errors | login, key, credit, none | Pass |
| UT-DSK-007.002.M21.T01 | MD-DSK-007.001.M21 | Positive | Once a day (SRD-DSK-007.002) | same problem twice, then next day | one row and one send; new row next day | Pass |
| UT-DSK-007.003.M21.T01 | MD-DSK-007.001.M21 | Negative | Failed send (SRD-DSK-007.003) | Telegram send fails | alert not marked sent; still open | Pass |
| UT-DSK-007.003.M21.T02 | MD-DSK-007.001.M21 | Positive | Telegram target (SRD-DSK-007.003) | users file, keychain | first user with Telegram on; none sends nothing | Pass |
| UT-DSK-007.004.M11.T01 | MD-DSK-004.001.M11 | Positive | Skip to backup (SRD-DSK-007.004) | Claude login error | alert; backup used; next employee skips Claude; next run tries Claude | Pass |
| UT-DSK-007.004.M11.T02 | MD-DSK-004.001.M11 | Negative | Bad form is not a problem (SRD-DSK-007.001) | wrong answer form | retried on the same source; no alert | Pass |
| UT-DSK-007.005.M10.T01 | MD-DSK-003.001.M10 | Positive | Whole run failed (SRD-DSK-007.005) | all calls bad; all good | one alert; none | Pass |
| UT-DSK-007.006.M21.T01 | MD-DSK-007.001.M21 | Positive | Close when fixed (SRD-DSK-007.006) | later valid calls; 25 hours later | closes by source; run alert by any; old alerts gone | Pass |
| UT-DSK-007.007.M21.T01 | MD-DSK-007.001.M21 | Positive | Candles alert stored and sent once a day (SRD-DSK-007.007) | `raise_alert(kind='candles')` twice the same day | one row titled "Candles not up to date"; one send | Pass |
| UT-DSK-007.007.M21.T02 | MD-DSK-007.001.M21 | Positive | Candles alert closed by a later ok run (SRD-DSK-007.007) | alert at 08:31 ET; morning run ok at 08:47 | not in `open_alerts` | Pass |
| UT-DSK-007.007.M21.T03 | MD-DSK-007.001.M21 | Negative | Candles alert stays after a failed run or a valid AI answer (SRD-DSK-007.007) | failed morning run later; valid activity row later | still open | Pass |

## FO-DSK-008: Employee File and Versions

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-DSK-008.001.M22.T01 | MD-DSK-008.001.M22 | Positive | Read employee.md (SRD-DSK-008.001) | valid file | spec fields and prompt; render then parse gives the same | Pass |
| UT-DSK-008.001.M22.T02 | MD-DSK-008.001.M22 | Negative | Wrong file (SRD-DSK-008.001) | no front matter; unknown source | ValueError with a plain reason | Pass |
| UT-DSK-008.002.M22.T01 | MD-DSK-008.001.M22 | Positive | One set of rules (SRD-DSK-008.002) | registry and core | registry uses the core JobSpec; same file checks the same in both | Pass |
| UT-DSK-008.002.M22.T02 | MD-DSK-008.001.M22 | Negative | No desk import (SRD-DSK-008.002) | import core.desk_employee in a clean process | no `us_swing.desk` module loaded | Pass |
| UT-DSK-008.003.M22.T01 | MD-DSK-008.001.M22 | Positive | Move old pair (SRD-DSK-008.003) | job.yaml + soul.md | employee.md with same spec and prompt; old files in history; version same | Pass |
| UT-DSK-008.003.M22.T02 | MD-DSK-008.001.M22 | Negative | Broken old pair (SRD-DSK-008.003) | job.yaml with an unknown source | not moved; old files stay; employee stays asleep | Pass |
| UT-DSK-008.003.M22.T03 | MD-DSK-008.001.M22 | Edge | Already moved (SRD-DSK-008.003) | employee.md present | nothing changed | Pass |
| UT-DSK-008.004.M09.T01 | MD-DSK-002.002.M09 | Positive | Defaults load (SRD-DSK-008.004) | empty desk folder | every shipped employee seeded as employee.md and loaded with its skill | Pass |
| UT-DSK-008.004.M09.T02 | MD-DSK-002.002.M09 | Negative | Edits kept (SRD-DSK-008.004) | edited employee.md, seed again | file not overwritten | Pass |
| UT-DSK-008.005.M22.T01 | MD-DSK-008.001.M22 | Positive | Save (SRD-DSK-008.005) | new prompt | version + 1; old file in history/v1.md; registry loads new prompt | Pass |
| UT-DSK-008.005.M22.T02 | MD-DSK-008.001.M22 | Negative | Refused save (SRD-DSK-008.005) | calls_per_day 0 | reason returned; file and history unchanged | Pass |
| UT-DSK-008.006.M22.T01 | MD-DSK-008.001.M22 | Positive | Restore (SRD-DSK-008.006) | restore v1 after 2 saves | version 4 with v1 prompt; versions lists 1–4 | Pass |
| UT-DSK-008.007.M18.T01 | MD-DSK-006.001.M18 | Positive | Hire file (SRD-DSK-008.007) | start a hire | new folder with employee.md, status shadow, version 1 | Pass |
| UT-DSK-008.007.M18.T02 | MD-DSK-006.001.M18 | Negative | Refused hire (SRD-DSK-008.007) | seats full | reason; no new folder | Pass |
| UT-DSK-008.008.M17.T01 | MD-DSK-005.005.M17 | Positive | Draft replay (SRD-DSK-008.008) | recorded run + draft | fake caller gets the draft prompt as system; try recorded as replay | Pass |
| UT-DSK-008.009.M22.T01 | MD-DSK-008.001.M22 | Negative | Seats full (SRD-DSK-008.009) | junior to expert with expert seats full | reason names the full level; file unchanged | Pass |
| UT-DSK-008.009.M22.T02 | MD-DSK-008.001.M22 | Positive | Free seat (SRD-DSK-008.009) | junior to expert with a free expert seat | saved; level expert | Pass |

## FO-DSK-003, -007: Baton, Retries and Partial Plan (Autonomous desk step B)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-DSK-003.014.M15.T01 | MD-DSK-003.004.M15 | Positive | step_done stored (SRD-DSK-003.014) | post for a P1 trigger | row with parent, trigger's priority, day and expiry; waiting | Pass |
| UT-DSK-003.014.M15.T02 | MD-DSK-003.004.M15 | Negative | Repeat ignored (SRD-DSK-003.014) | same trigger, employee and try twice | one row | Pass |
| UT-DSK-003.014.M15.T03 | MD-DSK-003.004.M15 | Edge | Old desk.db (SRD-DSK-003.014) | events table without parent and due | columns added; old rows load | Pass |
| UT-DSK-003.014.M15.T04 | MD-DSK-003.004.M15 | Negative | Tools cannot post it (SRD-DSK-003.014) | `post_event('step_done')` | ValueError; no row | Pass |
| UT-DSK-003.014.M16.T01 | MD-DSK-003.006.M16 | Positive | One step_done per step (SRD-DSK-003.014) | chain of 3, all ok | 3 step_done rows with result ok | Pass |
| UT-DSK-003.014.M10.T01 | MD-DSK-003.001.M10 | Positive | Wake result (SRD-DSK-003.014) | valid answer; stale facts; budget refused; no valid answer; exception | ok; slept; slept; failed; failed | Pass |
| UT-DSK-003.015.M16.T01 | MD-DSK-003.006.M16 | Positive | Wake when need is done (SRD-DSK-003.015) | B needs A | B woken only after A's step_done ok | Pass |
| UT-DSK-003.015.M16.T02 | MD-DSK-003.006.M16 | Positive | Wait for all needs (SRD-DSK-003.015) | C needs A and B | C woken once, after both | Pass |
| UT-DSK-003.015.M16.T03 | MD-DSK-003.006.M16 | Edge | Need outside the chain (SRD-DSK-003.015) | B needs a skill nobody in the chain has | B runs at once | Pass |
| UT-DSK-003.015.M16.T04 | MD-DSK-003.006.M16 | Negative | Need not done yet (SRD-DSK-003.015) | B needs A; A failed once and waits for its retry | B not woken | Pass |
| UT-DSK-003.016.M16.T01 | MD-DSK-003.006.M16 | Positive | Retry after 5 minutes (SRD-DSK-003.016) | A fails once, then ok | not woken at +4 min; woken at +5 min; chain goes on | Pass |
| UT-DSK-003.016.M16.T02 | MD-DSK-003.006.M16 | Negative | At most 2 retries (SRD-DSK-003.016) | A always fails | 3 wakes; step failed; no 4th wake | Pass |
| UT-DSK-003.016.M16.T03 | MD-DSK-003.006.M16 | Edge | Retry skips wake rules (SRD-DSK-003.016) | A woke 5 minutes ago and failed | retry passes the 30-minute rule; wake gets retry True | Pass |
| UT-DSK-003.016.M16.T04 | MD-DSK-003.006.M16 | Positive | Retry wakes the desk (SRD-DSK-003.016) | step_done due in 5 minutes | has_work False before due, True at due | Pass |
| UT-DSK-003.017.M16.T01 | MD-DSK-003.006.M16 | Negative | Chain stops (SRD-DSK-003.017) | A fails 3 times; B needs A; C needs B | B and C skipped, not woken; one log line each | Pass |
| UT-DSK-003.017.M16.T02 | MD-DSK-003.006.M16 | Positive | Other branch goes on (SRD-DSK-003.017) | A fails 3 times; D needs nothing | D still runs | Pass |
| UT-DSK-003.018.M16.T01 | MD-DSK-003.006.M16 | Positive | Lead runs partial (SRD-DSK-003.018) | lead needs A and B; A fails 3 times | lead runs once after B; gets A's name as missing | Pass |
| UT-DSK-003.018.M16.T02 | MD-DSK-003.006.M16 | Negative | Lead fails (SRD-DSK-003.018) | lead fails 3 times | no plan; alert for the lead | Pass |
| UT-DSK-003.018.M16.T03 | MD-DSK-003.006.M16 | Edge | Full chain (SRD-DSK-003.018) | nothing fails | lead gets no missing names; trigger note chain full | Pass |
| UT-DSK-003.018.M10.T01 | MD-DSK-003.001.M10 | Positive | Partial plan line (SRD-DSK-003.018) | wake with one missing name | each brief starts with the partial plan line naming it | Pass |
| UT-DSK-003.019.M16.T01 | MD-DSK-003.006.M16 | Positive | Carry on after restart (SRD-DSK-003.019) | new router over a desk.db with a waiting step_done | chain goes on; finished employees not woken again | Pass |
| UT-DSK-003.019.M16.T02 | MD-DSK-003.006.M16 | Edge | Cut wake (SRD-DSK-003.019) | steps row running at restart | counts as failed try 1; retried after 5 minutes | Pass |
| UT-DSK-003.019.M16.T03 | MD-DSK-003.006.M16 | Negative | Expired chain (SRD-DSK-003.019) | restart after the trigger expired | step_done expired; nobody woken | Pass |
| UT-DSK-007.008.M21.T01 | MD-DSK-007.001.M21 | Positive | Partial alert (SRD-DSK-007.008) | step failed 3 times | one partial alert with name and last error; Telegram sent | Pass |
| UT-DSK-007.008.M21.T02 | MD-DSK-007.001.M21 | Negative | Once a day (SRD-DSK-007.008) | same step fails in 2 chains on one day | one alert | Pass |
| UT-DSK-007.008.M21.T03 | MD-DSK-007.001.M21 | Positive | Alert closes (SRD-DSK-007.008) | later event with note chain full | alert no longer open | Pass |

## FO-DSK-009: Desk Memory — Lessons

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-DSK-009.001.M23.T01 | MD-DSK-009.001.M23 | Positive | Lesson stored (SRD-DSK-009.001) | add a candidate | row with tags, claim, proof, numbers, status candidate, author desk | Pass |
| UT-DSK-009.001.M23.T02 | MD-DSK-009.001.M23 | Negative | Bad lesson (SRD-DSK-009.001) | claim `maybe`; 4 tags; unknown tag key | ValueError; no row | Pass |
| UT-DSK-009.002.M23.T01 | MD-DSK-009.001.M23 | Positive | Active at 5 cases (SRD-DSK-009.002) | worse claim; 5 matching picks below the average | status active; active_on set | Pass |
| UT-DSK-009.002.M23.T02 | MD-DSK-009.001.M23 | Negative | Too few cases (SRD-DSK-009.002) | 3 matching picks | stays candidate | Pass |
| UT-DSK-009.002.M23.T03 | MD-DSK-009.001.M23 | Negative | Cases do not back it (SRD-DSK-009.002) | worse claim; 5 matching picks above the average | stays candidate | Pass |
| UT-DSK-009.002.M23.T04 | MD-DSK-009.001.M23 | Edge | Unproved for 30 days (SRD-DSK-009.002) | candidate made 31 days ago | retired by the review | Pass |
| UT-DSK-009.003.M23.T01 | MD-DSK-009.001.M23 | Positive | Same lesson updated (SRD-DSK-009.003) | two candidates, same tags and claim | one row; newer text | Pass |
| UT-DSK-009.003.M23.T02 | MD-DSK-009.001.M23 | Edge | Other claim is new (SRD-DSK-009.003) | same tags, claims better and worse | two rows | Pass |
| UT-DSK-009.003.M23.T03 | MD-DSK-009.001.M23 | Negative | Retired lesson not revived (SRD-DSK-009.003) | candidate matching a retired lesson | new candidate row; retired row unchanged | Pass |
| UT-DSK-009.003.M23.T04 | MD-DSK-009.001.M23 | Negative | Master text kept (SRD-DSK-009.003) | Master-edited lesson, then a desk candidate like it | Master's text stays | Pass |
| UT-DSK-009.003.M23.T05 | MD-DSK-009.001.M23 | Edge | No flapping (SRD-DSK-009.003) | candidate like a lesson retired in the last 90 days, 5 backing picks | stays candidate | Pass |
| UT-DSK-009.004.M23.T01 | MD-DSK-009.001.M23 | Positive | Top 5, pinned first (SRD-DSK-009.004) | 7 matching active lessons, one pinned with low confidence | 5 lines; pinned first, then by confidence | Pass |
| UT-DSK-009.004.M23.T02 | MD-DSK-009.001.M23 | Negative | Nothing to show (SRD-DSK-009.004) | only candidates; or no idea matches | empty text | Pass |
| UT-DSK-009.004.M23.T03 | MD-DSK-009.001.M23 | Edge | Token cap (SRD-DSK-009.004) | 5 long lessons | block at most 3,200 characters | Pass |
| UT-DSK-009.004.M23.T04 | MD-DSK-009.001.M23 | Negative | Memory error (SRD-DSK-009.004) | lessons block raises a locked-database error | plain facts; one warning | Pass |
| UT-DSK-009.005.M23.T01 | MD-DSK-009.001.M23 | Negative | Limits never read lessons (SRD-DSK-009.005) | scan `execution`, `broker`, `core/desk_trades.py`, `market/idea_step.py` | no `desk_lessons` import | Pass |
| UT-DSK-009.005.M23.T02 | MD-DSK-009.001.M23 | Positive | Same risk result (SRD-DSK-009.005) | risk check passed list with and without an active lesson | identical | Pass |
| UT-DSK-009.006.M23.T01 | MD-DSK-009.001.M23 | Positive | Uses kept (SRD-DSK-009.006) | block shows 2 lessons to setup review | 2 `lesson_uses` rows for that day and skill | Pass |
| UT-DSK-009.006.M23.T02 | MD-DSK-009.001.M23 | Negative | No uses when nothing shown (SRD-DSK-009.006) | block with no matching lesson | no `lesson_uses` row | Pass |
| UT-DSK-009.007.M23.T01 | MD-DSK-009.001.M23 | Negative | Later picks do not back it (SRD-DSK-009.007) | active worse lesson; 10 later shown picks above the average | retired with the reason | Pass |
| UT-DSK-009.007.M23.T02 | MD-DSK-009.001.M23 | Positive | Confirmed (SRD-DSK-009.007) | a later shown pick on the claimed side | last_confirmed moves; stays active | Pass |
| UT-DSK-009.007.M23.T03 | MD-DSK-009.001.M23 | Edge | 90 days and pinned (SRD-DSK-009.007) | two lessons last confirmed 91 days ago, one pinned | unpinned retired; pinned stays active | Pass |
| UT-DSK-009.008.M23.T01 | MD-DSK-009.001.M23 | Positive | Edits applied (SRD-DSK-009.008) | pin, edit, retire, delete rows | each applied; edit keeps id and numbers, author master | Pass |
| UT-DSK-009.008.M23.T02 | MD-DSK-009.001.M23 | Negative | Unknown lesson (SRD-DSK-009.008) | edit for a missing id | applied with note lesson not found | Pass |
| UT-DSK-009.008.M04.T01 | MD-DSK-001.010.M04 | Positive | Tick applies edits (SRD-DSK-009.008) | pending pin row, one desk tick | lesson pinned; row applied | Pass |
| UT-DSK-009.009.M23.T01 | MD-DSK-009.001.M23 | Positive | Log lines (SRD-DSK-009.009) | add, promote, retire | three `[Memory]` lines | Pass |

## FO-DSK-003, -007 (step D): Check-ins and Watchers

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-DSK-003.020.M03.T01 | MD-DSK-001.015.M03 | Positive | Check-ins due (SRD-DSK-003.020) | trading day 10:01, 12:31, 15:31 | slots 1000, 1230, 1530 | Pass |
| UT-DSK-003.020.M03.T02 | MD-DSK-001.015.M03 | Negative | No check-in (SRD-DSK-003.020) | Saturday 10:01; trading day 10:31 | nothing due | Pass |
| UT-DSK-003.020.M04.T01 | MD-DSK-001.010.M04 | Positive | Loop posts each check-in once (SRD-DSK-003.020) | ticks at 10:01 and 10:05 | one market_checkin event for slot 1000 | Pass |
| UT-DSK-003.021.M15.T01 | MD-DSK-003.004.M15 | Positive | Event rules (SRD-DSK-003.021) | post market_checkin and watch_flag | P2 30 min expiry; P0, 5 min deadline, 30 min expiry; one row per id | Pass |
| UT-DSK-003.021.M24.T01 | MD-DSK-003.021.M24 | Positive | Flag stored with event (SRD-DSK-003.021) | add_flag trigger_hit | watch_flags row; waiting watch_flag event with the flag id | Pass |
| UT-DSK-003.022.M24.T01 | MD-DSK-003.021.M24 | Negative | Once an hour (SRD-DSK-003.022) | same stock and kind twice in one hour | second add_flag None; one event | Pass |
| UT-DSK-003.022.M24.T02 | MD-DSK-003.021.M24 | Positive | Next hour (SRD-DSK-003.022) | same stock and kind an hour later | new flag | Pass |
| UT-DSK-003.023.M04.T01 | MD-DSK-001.010.M04 | Positive | Watch every 5 minutes (SRD-DSK-003.023) | ticks at 10:00, 10:02, 10:05 New York | watch called at 10:00 and 10:05 | Pass |
| UT-DSK-003.023.M04.T02 | MD-DSK-001.010.M04 | Negative | Not out of hours or paused (SRD-DSK-003.023) | tick at 08:00; paused at 11:00 | watch not called | Pass |
| UT-DSK-003.023.M04.T03 | MD-DSK-001.010.M04 | Negative | Watch error (SRD-DSK-003.023) | watch raises | logged; desk keeps going | Pass |
| UT-DSK-003.023.M07.T01 | MD-DSK-001.021.M07 | Positive | Watch path loads (SRD-DSK-003.023) | load_watch() | the market run_watch function | Pass |
| UT-DSK-003.021.M24.T03 | MD-DSK-003.021.M24 | Negative | Unknown flag kind (SRD-DSK-003.021) | add_flag kind lunch | ValueError; no row, no event | Pass |
| UT-DSK-003.024.M24.T02 | MD-DSK-003.021.M24 | Negative | No note for a repeat (SRD-DSK-003.024) | same flag twice in one hour | one briefs row | Pass |
| UT-DSK-003.024.M24.T01 | MD-DSK-003.021.M24 | Positive | Code feed note (SRD-DSK-003.024) | add_flag stop_touch at 47.10 | briefs row by Watchers with stock, label and price | Pass |
| UT-DSK-003.025.M01.T01 | MD-MKT-013.001.M01 | Positive | Pass log (SRD-DSK-003.025) | pass with 2 flags | `[Watch] 2 new flag(s)` with the kinds | Pass |
| UT-DSK-007.009.M21.T01 | MD-DSK-007.001.M21 | Positive | Trade and plan alerts (SRD-DSK-007.009) | raise trade_stop, trade_target, plan_broken | titles Trade at stop, Trade at target, Plan broken | Pass |
| UT-DSK-007.009.M21.T02 | MD-DSK-007.001.M21 | Negative | Once a day (SRD-DSK-007.009) | trade_stop for one stock twice a day | one alert | Pass |
| UT-DSK-003.021.M24.T02 | MD-DSK-003.021.M24 | Positive | Open trades and live symbols (SRD-DSK-003.021) | write 2 trades; ideas and picks of the day | trades read back; live symbols listed, picks, then SPY | Pass |

## FO-DSK-004, -007, -010 (step E): Token Split and Research Queue

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-DSK-004.006.M22.T01 | MD-DSK-008.001.M22 | Positive | Default daily tokens (SRD-DSK-004.006) | employee file without `tokens_per_day` | 60,000 | Pass |
| UT-DSK-004.006.M22.T02 | MD-DSK-008.001.M22 | Negative | Too small a budget (SRD-DSK-004.006) | `tokens_per_day: 500` | file refused with the field named | Pass |
| UT-DSK-004.007.M12.T01 | MD-DSK-004.003.M12 | Positive | Split 50/20/30 (SRD-DSK-004.007) | 60,000 tokens a day | plan 30,000, market 12,000, research 18,000 | Pass |
| UT-DSK-004.008.M10.T01 | MD-DSK-003.001.M10 | Positive | Part by event (SRD-DSK-004.008) | wakes by watch_flag, market_checkin, after_run | activity part market, market, plan | Pass |
| UT-DSK-004.008.M14.T01 | MD-DSK-005.001.M14 | Edge | Old rows count as plan (SRD-DSK-004.008) | activity rows with no part or payer | summed in the employee's plan part | Pass |
| UT-DSK-004.009.M12.T01 | MD-DSK-004.003.M12 | Positive | Used-up part refuses (SRD-DSK-004.009) | market part used 12,000 of 12,000 | watch flag call refused; plan call allowed | Pass |
| UT-DSK-004.009.M12.T02 | MD-DSK-004.003.M12 | Negative | Ticket paid by the raiser (SRD-DSK-004.009) | doer's research used up, raiser's not; then raiser's used up | allowed; then refused | Pass |
| UT-DSK-004.009.M11.T01 | MD-DSK-004.001.M11 | Edge | Ticket cap between tries (SRD-DSK-004.009) | first try reaches the ticket cap, answer invalid | no second try; refused reason names the ticket | Pass |
| UT-DSK-004.010.M11.T01 | MD-DSK-004.001.M11 | Positive | Part refusal log (SRD-DSK-004.010) | plan part used up | `[Budget]` line with name, part and tokens | Pass |
| UT-DSK-007.010.M21.T01 | MD-DSK-007.001.M21 | Positive | Waiting ticket alert (SRD-DSK-007.010) | raise a 30,000-token ticket; then approve it | one Research ticket waiting alert with goal and cap; closed after approve | Pass |
| UT-DSK-007.010.M21.T02 | MD-DSK-007.001.M21 | Negative | No alert when auto approved (SRD-DSK-007.010) | raise an 8,000-token ticket | no alert | Pass |
| UT-DSK-010.001.M25.T01 | MD-DSK-010.001.M25 | Positive | Ticket row (SRD-DSK-010.001) | lead raises one ticket | row with kind, topic, goal, done test, caps, raiser, status, made | Pass |
| UT-DSK-010.002.M25.T01 | MD-DSK-010.001.M25 | Negative | Only leads raise (SRD-DSK-010.002) | skill held by an expert | no row; refused note | Pass |
| UT-DSK-010.002.M25.T02 | MD-DSK-010.001.M25 | Edge | 3 a day (SRD-DSK-010.002) | 4th ticket by one lead on one day | refused; next day allowed | Pass |
| UT-DSK-010.003.M25.T01 | MD-DSK-010.001.M25 | Positive | Auto approval limit (SRD-DSK-010.003) | caps 10,000 and 10,001 | approved by auto; waiting | Pass |
| UT-DSK-010.003.M25.T02 | MD-DSK-010.001.M25 | Edge | Book tickets wait (SRD-DSK-010.003) | book_to_strategy, cap 5,000 | waiting | Pass |
| UT-DSK-010.004.M25.T01 | MD-DSK-010.001.M25 | Positive | Approve with new cap (SRD-DSK-010.004) | edit approve, cap 20,000 | approved by master, cap 20,000, edit applied | Pass |
| UT-DSK-010.004.M25.T02 | MD-DSK-010.001.M25 | Positive | Reject and cap change (SRD-DSK-010.004) | edit reject on one; edit cap on another | rejected; still waiting with new cap | Pass |
| UT-DSK-010.004.M25.T03 | MD-DSK-010.001.M25 | Negative | Edit on a ticket not waiting (SRD-DSK-010.004) | approve on an approved ticket | edit applied; ticket unchanged | Pass |
| UT-DSK-010.005.M25.T01 | MD-DSK-010.001.M25 | Edge | Expiry after 3 days (SRD-DSK-010.005) | waiting ticket 2 days and 3 days 1 minute old | first still waiting; second expired | Pass |
| UT-DSK-010.006.M25.T01 | MD-DSK-010.001.M25 | Negative | Repeat refused (SRD-DSK-010.006) | same kind and goal (other case and spaces) done 10 days ago; then 31 days ago | refused; then added | Pass |
| UT-DSK-010.007.M25.T01 | MD-DSK-010.001.M25 | Positive | Topic parked (SRD-DSK-010.007) | 3 ended no-gain tickets on a topic; then one with gain among them | new ticket refused; then allowed | Pass |
| UT-DSK-010.008.M26.T01 | MD-DSK-010.008.M26 | Positive | Quiet gap (SRD-DSK-010.008) | waiting event; flag 10 minutes ago; flag 25 minutes ago | not quiet; not quiet; quiet | Pass |
| UT-DSK-010.008.M26.T02 | MD-DSK-010.008.M26 | Positive | Ticket order (SRD-DSK-010.008) | running, paused and two approved tickets | running first, then paused, then oldest approved | Pass |
| UT-DSK-010.008.M04.T01 | MD-DSK-001.010.M04 | Positive | Market work first (SRD-DSK-010.008) | approved ticket and a waiting watch_flag event | event run handles the flag; no research step that tick | Pass |
| UT-DSK-010.009.M26.T01 | MD-DSK-010.008.M26 | Positive | Doer by kind (SRD-DSK-010.009) | fake research skill for setup_tuning, one step | step done by its employee; activity part research, payer raiser, ticket id | Pass |
| UT-DSK-010.009.M26.T02 | MD-DSK-010.008.M26 | Negative | No doer (SRD-DSK-010.009) | approved stock_study ticket, no skill for it, two ticks | stays approved; one log line a day | Pass |
| UT-DSK-010.010.M26.T01 | MD-DSK-010.008.M26 | Positive | Done test met (SRD-DSK-010.010) | skill outcome done, gain true | status done, gain 1, note in result | Pass |
| UT-DSK-010.010.M26.T02 | MD-DSK-010.008.M26 | Edge | Hard token cap (SRD-DSK-010.010) | cap 10,000, spent 7,000, step estimate 4,000 | no call; done with reason token cap | Pass |
| UT-DSK-010.010.M26.T03 | MD-DSK-010.008.M26 | Edge | Step and time caps (SRD-DSK-010.010) | 8 steps done; 61 minutes of call time | done with step cap; done with time cap | Pass |
| UT-DSK-010.011.M26.T01 | MD-DSK-010.008.M26 | Negative | Stall stops a ticket (SRD-DSK-010.011) | two steps with no note; same call twice | stuck; stuck | Pass |
| UT-DSK-010.012.M26.T01 | MD-DSK-010.008.M26 | Positive | Pause and resume (SRD-DSK-010.012) | running ticket, new flag; 20 minutes later | paused after the step; resumed and running | Pass |
| UT-DSK-010.012.M26.T02 | MD-DSK-010.008.M26 | Negative | Research part used up (SRD-DSK-010.012) | raiser's research part used up | paused; no call made | Pass |
| UT-DSK-010.012.M25.T01 | MD-DSK-010.001.M25 | Positive | Pause on app close (SRD-DSK-010.012) | ticket running when the desk starts | paused with reason app closed | Pass |
| UT-DSK-010.013.M26.T01 | MD-DSK-010.008.M26 | Positive | research_done event (SRD-DSK-010.013) | ticket ends | one research_done event for its id; closed as nobody listens | Pass |
| UT-DSK-010.014.M26.T01 | MD-DSK-010.008.M26 | Positive | Ticket logs (SRD-DSK-010.014) | raise, start, pause, end | `[Research]` lines with id and status | Pass |
| UT-DSK-004.007.M12.T02 | MD-DSK-004.003.M12 | Edge | Split of an odd budget (SRD-DSK-004.007) | 1,001 tokens a day | parts 500, 200, 300; never more than the budget | Pass |
| UT-DSK-010.001.M25.T02 | MD-DSK-010.001.M25 | Edge | Tables made twice (SRD-DSK-010.001) | open desk.db twice with tickets in it | rows kept; no error | Pass |
| UT-DSK-010.002.M25.T03 | MD-DSK-010.001.M25 | Positive | Lead raises (SRD-DSK-010.002) | active lead holds the skill; 3 tickets in a day | 3 rows raised by that lead's id and name | Pass |
| UT-DSK-010.005.M25.T02 | MD-DSK-010.001.M25 | Positive | Approved in time (SRD-DSK-010.005) | waiting ticket approved on day 2, checked on day 4 | approved, not expired | Pass |
| UT-DSK-010.006.M25.T02 | MD-DSK-010.001.M25 | Positive | New goal added (SRD-DSK-010.006) | same kind, different goal as a recent done ticket | added | Pass |
| UT-DSK-010.007.M25.T02 | MD-DSK-010.001.M25 | Negative | Not parked yet (SRD-DSK-010.007) | 2 no-gain tickets; 3 no-gain, last ended 31 days ago | new ticket allowed; allowed | Pass |
| UT-DSK-010.008.M26.T03 | MD-DSK-010.008.M26 | Negative | No work without tickets (SRD-DSK-010.008) | quiet, only waiting and ended tickets | has_work false; no run | Pass |
| UT-DSK-010.011.M26.T02 | MD-DSK-010.008.M26 | Positive | Progress keeps it running (SRD-DSK-010.011) | 3 steps each with a new note and a new call | still running; 3 notes in result | Pass |
| UT-DSK-010.013.M26.T02 | MD-DSK-010.008.M26 | Negative | No event for rejected or expired (SRD-DSK-010.013) | ticket rejected; ticket expired | no research_done event | Pass |
| UT-DSK-010.012.M26.T03 | MD-DSK-010.008.M26 | Edge | Other refusal backs off (SRD-DSK-010.012) | doer over its calls a day | ticket paused with the reason; no work for 15 minutes | Pass |
| UT-DSK-010.015.M25.T01 | MD-DSK-010.001.M25 | Positive | Follow-up in the lead's name (SRD-DSK-010.015) | active lead id, ask with cap 8,000 | row raised by that lead, approved by auto | Pass |
| UT-DSK-010.015.M25.T02 | MD-DSK-010.001.M25 | Negative | Lead gone (SRD-DSK-010.015) | retired lead id; expert id | every ask refused; no rows | Pass |
| UT-DSK-010.015.M25.T03 | MD-DSK-010.001.M25 | Negative | Lead limits (SRD-DSK-010.015) | lead with 3 tickets today | refused: 3 tickets a day | Pass |
| UT-DSK-010.016.M25.T01 | MD-DSK-010.001.M25 | Positive | Owner test ticket (SRD-DSK-010.016) | active lead with lead_brief, card 3 | row approved, topic SC-3, raised by the lead, approved_by master | Pass |
| UT-DSK-010.016.M25.T02 | MD-DSK-010.001.M25 | Negative | No lead (SRD-DSK-010.016) | no active lead holds lead_brief | refused; no row | Pass |
| UT-DSK-010.016.M25.T03 | MD-DSK-010.001.M25 | Negative | Repeat (SRD-DSK-010.016) | open SC-3 test, raise again | refused; one row | Pass |

## FO-DSK-011 / FO-DSK-012 (AI Desk v3 M0): Message Format and Tool Registry

| ID | Module | Type | Title | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-DSK-011.001.M27.T01 | MD-DSK-011.001.M27 | Positive | Round trip of every type (SRD-DSK-011.001) | one valid message of each of the 9 types | dump then load gives an equal model; dump has no schema key | Pass |
| UT-DSK-011.001.M27.T02 | MD-DSK-011.001.M27 | Negative | Broken envelope (SRD-DSK-011.001) | message with no body; with no at; with an extra header key | each refused with a plain reason | Pass |
| UT-DSK-011.002.M27.T01 | MD-DSK-011.001.M27 | Positive | Thread row (SRD-DSK-011.002) | thread id 701, starter emp-003, 2 messages, 1 round, open | valid; round trip equal | Pass |
| UT-DSK-011.002.M27.T02 | MD-DSK-011.001.M27 | Negative | Bad thread state (SRD-DSK-011.002) | state paused; rounds -1 | refused; refused | Pass |
| UT-DSK-011.003.M27.T01 | MD-DSK-011.001.M27 | Positive | Header rules met (SRD-DSK-011.003) | first ask with no parent and a due; reply with parent and no due | both valid | Pass |
| UT-DSK-011.003.M27.T02 | MD-DSK-011.001.M27 | Negative | Header rules broken (SRD-DSK-011.003) | handover with due; reply with no parent; time without zone | each refused with a plain reason | Pass |
| UT-DSK-011.004.M27.T01 | MD-DSK-011.001.M27 | Positive | Good addresses (SRD-DSK-011.004) | emp-003, skill:news_review, champion:technical, boss, master; meeting to a list | all valid | Pass |
| UT-DSK-011.004.M27.T02 | MD-DSK-011.001.M27 | Negative | Bad addresses (SRD-DSK-011.004) | "Expert 3"; skill:News; list on an ask; to on a reply; no to on an ask; meeting to an empty list | each refused | Pass |
| UT-DSK-011.005.M27.T01 | MD-DSK-011.001.M27 | Positive | Type picks the body (SRD-DSK-011.005) | body dicts with type ask and decision | AskBody and DecisionBody; message type equals body type | Pass |
| UT-DSK-011.005.M27.T02 | MD-DSK-011.001.M27 | Negative | Foreign and unknown keys (SRD-DSK-011.005) | ask with verdict; reply with colour key; type chat | each refused | Pass |
| UT-DSK-011.006.M27.T01 | MD-DSK-011.001.M27 | Positive | Refused reply needs only a reason (SRD-DSK-011.006) | reply verdict refused with reason, no text or data | valid | Pass |
| UT-DSK-011.006.M27.T02 | MD-DSK-011.001.M27 | Negative | Missing required fields (SRD-DSK-011.006) | ask with no subject; reply done with no text or data; refused with no reason; task with no want | each refused | Pass |
| UT-DSK-011.007.M27.T01 | MD-DSK-011.001.M27 | Positive | Limits at the edge (SRD-DSK-011.007) | subject 80 chars, text 600, 20 about, 5 flags | valid | Pass |
| UT-DSK-011.007.M27.T02 | MD-DSK-011.001.M27 | Negative | Limits passed (SRD-DSK-011.007) | subject 81; subject with a newline; text 601; 21 about; 6 flags; reason 201 | each refused | Pass |
| UT-DSK-011.008.M27.T01 | MD-DSK-011.001.M27 | Positive | Want on a task (SRD-DSK-011.008) | task want with goal, done test, schema, cols, tools step.regime@1 | valid; max_tokens 0 left out of the dump | Pass |
| UT-DSK-011.008.M27.T02 | MD-DSK-011.001.M27 | Negative | Bad want (SRD-DSK-011.008) | ask want with tools; goal 121 chars; tool without version | each refused | Pass |
| UT-DSK-011.009.M27.T01 | MD-DSK-011.001.M27 | Positive | Verdicts by type (SRD-DSK-011.009) | reply partial; send_back fix; decision decided with agreed and disagreed | all valid | Pass |
| UT-DSK-011.009.M27.T02 | MD-DSK-011.001.M27 | Negative | Verdict of another type (SRD-DSK-011.009) | send_back done; reply decided; reply with agreed | each refused | Pass |
| UT-DSK-011.010.M27.T01 | MD-DSK-011.001.M27 | Positive | Data block forms (SRD-DSK-011.010) | 200 rows inline; ref with n 480 | both valid | Pass |
| UT-DSK-011.010.M27.T02 | MD-DSK-011.001.M27 | Negative | Bad data block (SRD-DSK-011.010) | 201 rows; rows and ref; neither; ref without n; n with rows; schema scores_v1 | each refused | Pass |
| UT-DSK-011.011.M27.T01 | MD-DSK-011.001.M27 | Positive | Meta only when set (SRD-DSK-011.011) | message with no meta; with meta used only | no meta key; meta holds only used | Pass |
| UT-DSK-011.011.M27.T02 | MD-DSK-011.001.M27 | Negative | Bad meta (SRD-DSK-011.011) | meta schema desk.msg/1; meta cost key | each refused | Pass |
| UT-DSK-011.012.M27.T01 | MD-DSK-011.001.M27 | Positive | State names (SRD-DSK-011.012) | `State` | the 8 A2A names in order | Pass |
| UT-DSK-011.012.M27.T02 | MD-DSK-011.001.M27 | Negative | Unknown state (SRD-DSK-011.012) | message state open; state blocked | each refused | Pass |
| UT-DSK-011.013.M27.T01 | MD-DSK-011.001.M27 | Positive | JSON Schema accepts the dumps (SRD-DSK-011.013) | message schema; one dump of each type | every dump passes the JSON Schema check | Pass |
| UT-DSK-011.013.M27.T02 | MD-DSK-011.001.M27 | Negative | JSON Schema refuses what models refuse (SRD-DSK-011.013) | ask body with no subject; ask body with an extra key | JSON Schema check fails for both | Pass |
| UT-DSK-011.014.M27.T01 | MD-DSK-011.001.M27 | Positive | Format only (SRD-DSK-011.014) | all source files except desk_msg and desk_registry | none imports `desk_msg` | Superseded |
| UT-DSK-011.014.M27.T02 | MD-DSK-011.001.M27 | Negative | No message tables (SRD-DSK-011.014) | desk.db after a desk start | no messages or threads table | Superseded |
| UT-DSK-012.001.M28.T01 | MD-DSK-012.001.M28 | Positive | Tool row in MCP shape (SRD-DSK-012.001) | code tool and mcp tool | dump has inputSchema and outputSchema; round trip equal | Pass |
| UT-DSK-012.001.M28.T02 | MD-DSK-012.001.M28 | Negative | Kind and name disagree (SRD-DSK-012.001) | kind mcp named step.x; kind code named mcp:a/b; status paused | each refused | Pass |
| UT-DSK-012.002.M28.T01 | MD-DSK-012.001.M28 | Positive | Good names (SRD-DSK-012.002) | step.regime; mcp:backtest/bt_run; step.regime@1 as a reference | names and reference valid | Pass |
| UT-DSK-012.002.M28.T02 | MD-DSK-012.001.M28 | Negative | Bad names (SRD-DSK-012.002) | Step.Regime; regime; mcp:backtest; step.regime@x | each refused | Pass |
| UT-DSK-012.003.M28.T01 | MD-DSK-012.001.M28 | Positive | Format row (SRD-DSK-012.003) | setup_table.v1 with 3 columns | name setup_table, version 1; round trip equal | Pass |
| UT-DSK-012.003.M28.T02 | MD-DSK-012.001.M28 | Negative | Bad format (SRD-DSK-012.003) | id setup_table; no columns; two columns named symbol | each refused | Pass |
| UT-DSK-012.004.M28.T01 | MD-DSK-012.001.M28 | Positive | Tables made (SRD-DSK-012.004) | fill on a new home | tools and schemas tables with rows; key is name and version | Pass |
| UT-DSK-012.004.M28.T02 | MD-DSK-012.001.M28 | Negative | Same key twice (SRD-DSK-012.004) | plain insert of a tool row with a name and version already kept | refused by the key; one row | Pass |
| UT-DSK-012.004.M28.T03 | MD-DSK-012.001.M28 | Edge | Tables made twice (SRD-DSK-012.004) | fill, then open the tables again | rows kept; no error | Pass |
| UT-DSK-012.005.M28.T01 | MD-DSK-012.001.M28 | Positive | Steps seeded (SRD-DSK-012.005) | `seed_tools()` | one code tool per `STEP_PATHS` entry, e.g. step.candle_check and step.weekly_report, with the step name as description | Pass |
| UT-DSK-012.005.M28.T02 | MD-DSK-012.001.M28 | Negative | Bad step path (SRD-DSK-012.005) | step list with a path to a missing module | seed fails with an error that names the module | Pass |
| UT-DSK-012.006.M28.T01 | MD-DSK-012.001.M28 | Positive | Research skills seeded (SRD-DSK-012.006) | `seed_tools()` | research tools equal the skill keys that are research kinds; ai true; input is the ticket ask schema | Pass |
| UT-DSK-012.006.M28.T02 | MD-DSK-012.001.M28 | Negative | Kind with no skill (SRD-DSK-012.006) | research kind stock_study has no skill | no research.stock_study row | Pass |
| UT-DSK-012.007.M28.T01 | MD-DSK-012.001.M28 | Positive | Recipe and formats seeded (SRD-DSK-012.007) | `seed_tools()`, `seed_formats()` | data.recipe with the recipe schema; one `<source>.v1` format per menu source with its columns | Pass |
| UT-DSK-012.007.M28.T02 | MD-DSK-012.001.M28 | Negative | Recipe input refuses unknown source (SRD-DSK-012.007) | data.recipe input schema; recipe with source orders | JSON Schema check fails | Pass |
| UT-DSK-012.008.M28.T01 | MD-DSK-012.001.M28 | Positive | Backtest MCP seeded (SRD-DSK-012.008) | `seed_tools()` | one mcp tool per Backtest tool name; bt_status input requires job_id | Pass |
| UT-DSK-012.008.M28.T02 | MD-DSK-012.001.M28 | Negative | MCP input refuses missing args (SRD-DSK-012.008) | bt_status input schema; empty arguments | JSON Schema check fails | Pass |
| UT-DSK-012.009.M28.T01 | MD-DSK-012.001.M28 | Positive | Fill twice, no copies (SRD-DSK-012.009) | `fill_registry()` twice | same rows and counts both times | Pass |
| UT-DSK-012.009.M28.T02 | MD-DSK-012.001.M28 | Edge | Removed tool set off (SRD-DSK-012.009) | active row step.old not in the seed, then fill | step.old kept with status off | Pass |
| UT-DSK-001.010.M04.T32 | MD-DSK-001.010.M04 | Positive | Desk start fills the registry (SRD-DSK-012.009) | desk start on a new home | registry lists every seed tool | Pass |
| UT-DSK-001.010.M04.T33 | MD-DSK-001.010.M04 | Negative | Registry error does not stop the desk (SRD-DSK-012.009) | fill raises an error on start | desk starts; error logged with `[Tools]` | Pass |
| UT-DSK-012.010.M28.T01 | MD-DSK-012.001.M28 | Positive | Read functions (SRD-DSK-012.010) | filled registry; tool x.y in versions 1 and 2 | lists ordered by name; get gives version 2 by default and 1 when asked; get_format scores.v1 | Pass |
| UT-DSK-012.010.M28.T02 | MD-DSK-012.001.M28 | Negative | No database yet (SRD-DSK-012.010) | read on a home with no desk.db; unknown name | empty lists and None; no file made | Pass |
| UT-DSK-012.011.M28.T01 | MD-DSK-012.001.M28 | Positive | Fill is logged (SRD-DSK-012.011) | `fill_registry()` | one `[Tools]` info line with the tool and format counts | Pass |

## FO-DSK-011 (AI Desk v3 M1): Messages and the Reply Path

| ID | Module | Type | Title | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-DSK-011.003.M27.T03 | MD-DSK-011.001.M27 | Positive | First send-back starts a thread (SRD-DSK-011.003) | send_back with to emp-003 and no parent | valid | Pass |
| UT-DSK-011.003.M27.T04 | MD-DSK-011.001.M27 | Negative | Send-back needs parent or to (SRD-DSK-011.003) | send_back with both; with neither | each refused | Pass |
| UT-DSK-011.004.M27.T03 | MD-DSK-011.001.M27 | Positive | Send-back with a parent has no to (SRD-DSK-011.004) | send_back with parent 5 and no to | valid | Pass |
| UT-DSK-011.004.M27.T04 | MD-DSK-011.001.M27 | Negative | To on an answering send-back (SRD-DSK-011.004) | send_back with parent 5 and to emp-003 | refused | Pass |
| UT-DSK-011.016.M27.T01 | MD-DSK-011.001.M27 | Positive | Answer with messages (SRD-DSK-011.016) | `with_messages(SetupReview)` twice | subclass with the old fields and a messages list; same class both times | Pass |
| UT-DSK-011.016.M27.T02 | MD-DSK-011.001.M27 | Negative | Too many drafts (SRD-DSK-011.016) | answer with 6 drafts | refused | Pass |
| UT-DSK-011.016.M11.T01 | MD-DSK-004.001.M11 | Positive | Talking gateway (SRD-DSK-011.016) | talk on, fake model answers with 1 draft | prompt schema has messages; `drafts` holds 1 | Pass |
| UT-DSK-011.016.M11.T02 | MD-DSK-004.001.M11 | Negative | Quiet gateway (SRD-DSK-011.016) | talk off | prompt schema has no messages; `drafts` empty | Pass |
| UT-DSK-011.015.M29.T01 | MD-DSK-011.015.M29 | Positive | Store and read back (SRD-DSK-011.015) | accept one ask | one messages row and one thread row; reads back as an equal Message | Pass |
| UT-DSK-011.015.M29.T02 | MD-DSK-011.015.M29 | Negative | No database (SRD-DSK-011.015) | reads on a home with no desk.db | empty lists; no file made | Pass |
| UT-DSK-011.014.M29.T01 | MD-DSK-011.015.M29 | Positive | One writer (SRD-DSK-011.014) | all source files | only `core/desk_messages.py` writes the messages and threads tables | Pass |
| UT-DSK-011.014.M29.T02 | MD-DSK-011.015.M29 | Negative | Nothing stored while off (SRD-DSK-011.014) | full morning run on a desk copy with messages off and drafts in the answers | no messages rows | Pass |
| UT-DSK-011.017.M29.T01 | MD-DSK-011.015.M29 | Positive | M1 types (SRD-DSK-011.017) | an ask, a reply and a first send_back | all stored | Pass |
| UT-DSK-011.017.M29.T02 | MD-DSK-011.015.M29 | Negative | Type not in use (SRD-DSK-011.017) | handover; escalate | handover refused: not in use yet; escalate dropped while escalation is off (M2, SRD-DSK-011.033) | Pass |
| UT-DSK-011.018.M29.T01 | MD-DSK-011.015.M29 | Positive | Receivers (SRD-DSK-011.018) | to emp-006; to skill:news_review held by emp-007 and emp-006 | emp-006 both times | Pass |
| UT-DSK-011.018.M29.T02 | MD-DSK-011.015.M29 | Negative | Nobody to take it (SRD-DSK-011.018) | unknown id; retired employee; skill nobody holds; boss | each refused | Pass |
| UT-DSK-011.019.M29.T01 | MD-DSK-011.015.M29 | Positive | Bad draft refused alone (SRD-DSK-011.019) | 3 drafts, the middle one with an unknown key | first and last stored; one refusal line | Pass |
| UT-DSK-011.019.M29.T02 | MD-DSK-011.015.M29 | Negative | Unknown data format (SRD-DSK-011.019) | reply with data in format nope.v1 | refused at the data step | Pass |
| UT-DSK-011.020.M29.T01 | MD-DSK-011.015.M29 | Positive | Within limits (SRD-DSK-011.020) | 6th message of a thread; 2nd send-back; 20th started today | all stored | Pass |
| UT-DSK-011.020.M29.T02 | MD-DSK-011.015.M29 | Negative | Over limits (SRD-DSK-011.020) | 7th message; 3rd send-back; 21st started today | each refused | Pass |
| UT-DSK-011.021.M29.T01 | MD-DSK-011.015.M29 | Positive | Reply to an open ask (SRD-DSK-011.021) | ask emp-003 to emp-006; reply by emp-006 with parent | stored to emp-003 | Pass |
| UT-DSK-011.021.M29.T02 | MD-DSK-011.015.M29 | Negative | Bad reply (SRD-DSK-011.021) | second reply; reply by emp-007; reply to a reply | each refused | Pass |
| UT-DSK-011.021.M29.T03 | MD-DSK-011.015.M29 | Positive | Missing verdict filled (SRD-DSK-011.021) | reply with no verdict to an ask; to a send-back with no data | parent completed; parent failed (dropped) | Pass |
| UT-DSK-011.022.M29.T01 | MD-DSK-011.015.M29 | Negative | Loop refused (SRD-DSK-011.022) | emp-006 asks emp-003 while emp-003's ask to it is open in the thread | refused | Pass |
| UT-DSK-011.022.M29.T02 | MD-DSK-011.015.M29 | Positive | Third employee in a thread (SRD-DSK-011.022) | emp-006 asks emp-004 in the same thread | stored | Pass |
| UT-DSK-011.023.M29.T01 | MD-DSK-011.015.M29 | Positive | Expiry (SRD-DSK-011.023) | open ask, 11 minutes later | parent expired; failed reply in the receiver's name; event for the asker | Pass |
| UT-DSK-011.023.M29.T02 | MD-DSK-011.015.M29 | Negative | Not yet due (SRD-DSK-011.023) | open ask, 9 minutes later | still submitted; nothing written | Pass |
| UT-DSK-011.024.M29.T01 | MD-DSK-011.015.M29 | Positive | Wake event (SRD-DSK-011.024) | stored ask | one waiting message event, key message id, target receiver, priority 1 | Pass |
| UT-DSK-011.024.M29.T02 | MD-DSK-011.015.M29 | Negative | No event for a refusal (SRD-DSK-011.024) | refused draft | no event | Pass |
| UT-DSK-011.025.M16.T01 | MD-DSK-003.006.M16 | Positive | Addressed wake (SRD-DSK-011.025) | message event to emp-006, which listens only to after_run, plus two other employees | only emp-006 woken | Pass |
| UT-DSK-011.025.M16.T02 | MD-DSK-003.006.M16 | Negative | Target not loaded (SRD-DSK-011.025) | message event to an id not in the roster | closed as nobody listens; nobody woken | Pass |
| UT-DSK-011.025.M16.T03 | MD-DSK-003.006.M16 | Edge | No rewake gap (SRD-DSK-011.025) | employee woke 5 minutes ago | message wake runs; its after_run wake later is not blocked by the message turn | Pass |
| UT-DSK-011.026.M29.T01 | MD-DSK-011.015.M29 | Positive | Inbox block (SRD-DSK-011.026) | one ask and one reply to emp-003 | block with ids, sender id and name, text and the reply hint | Pass |
| UT-DSK-011.026.M29.T02 | MD-DSK-011.015.M29 | Negative | Seen rows not shown again (SRD-DSK-011.026) | inbox after `mark_seen` | empty | Pass |
| UT-DSK-011.027.M29.T01 | MD-DSK-011.015.M29 | Positive | Reply closes the parent (SRD-DSK-011.027) | replies done, failed and refused | parent completed, failed and refused; asker event each | Pass |
| UT-DSK-011.027.M29.T02 | MD-DSK-011.015.M29 | Negative | Closed parent unchanged (SRD-DSK-011.027) | reply to an expired ask | refused; parent stays expired | Pass |
| UT-DSK-011.027.M10.T01 | MD-DSK-003.001.M10 | Positive | Ask and reply in one run (SRD-DSK-011.027) | desk copy, messages on; setup review asks news review | in one events pass: ask, reply, setup review woken again; 2 messages | Pass |
| UT-DSK-011.028.M10.T01 | MD-DSK-003.001.M10 | Positive | Receiver cannot work (SRD-DSK-011.028) | ask to an employee whose facts are stale | refused reply with the stale reason at once; asker woken | Pass |
| UT-DSK-011.028.M10.T02 | MD-DSK-003.001.M10 | Negative | Receiver works (SRD-DSK-011.028) | ask to a fresh employee that answers | no refused reply | Pass |
| UT-DSK-011.029.M16.T01 | MD-DSK-003.006.M16 | Positive | Chain waits for the reply (SRD-DSK-011.029) | setup review with an open ask; risk check needs it | risk check not woken; after the reply setup review's step_done comes and risk check runs | Pass |
| UT-DSK-011.029.M16.T02 | MD-DSK-003.006.M16 | Negative | Nothing open (SRD-DSK-011.029) | turn with no ask | step_done at once, as today | Pass |
| UT-DSK-011.029.M16.T03 | MD-DSK-003.006.M16 | Edge | Expiry releases the chain (SRD-DSK-011.029) | ask never answered, 11 minutes | asker step ok after the failed reply; chain goes on | Pass |
| UT-DSK-011.030.M10.T01 | MD-DSK-003.001.M10 | Positive | Starter pays (SRD-DSK-011.030) | news review answers emp-003's ask | activity row of emp-006 with payer emp-003, part plan, message id | Pass |
| UT-DSK-011.030.M10.T02 | MD-DSK-003.001.M10 | Negative | Starter out of tokens (SRD-DSK-011.030) | emp-003 plan part used up | no call; refused reply with the budget reason | Pass |
| UT-DSK-011.031.M10.T01 | MD-DSK-003.001.M10 | Positive | Messages on (SRD-DSK-011.031) | messages_on true | talking skills get the messages field; drafts stored | Pass |
| UT-DSK-011.031.M10.T02 | MD-DSK-003.001.M10 | Negative | Messages off (SRD-DSK-011.031) | messages_on false, fake model returns grades only | no messages field in prompts; no rows; same results as today | Pass |
| UT-DSK-011.031.M13.T01 | MD-DSK-004.005.M13 | Positive | Setting saved and read (SRD-DSK-011.031) | old desk_ai.json without the key; then save true | false; then true | Pass |
| UT-DSK-011.032.M29.T01 | MD-DSK-011.015.M29 | Positive | Message logs (SRD-DSK-011.032) | store, refuse, expire | `[Messages]` info lines, no class names | Pass |
| UT-DSK-003.014.M10.T02 | MD-DSK-003.001.M10 | Positive | Code-only turn is ok (SRD-DSK-003.014) | skill ends its turn with no model call | step ok after 1 try; no retry, no alert | Pass |

## FO-DSK-011 (AI Desk v3 M2): Escalation and Deputies

| ID | Module | Type | Title | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-DSK-011.033.M29.T01 | MD-DSK-011.015.M29 | Positive | Escalate accepted (SRD-DSK-011.033) | escalation on, escalate to boss | stored, state submitted, due in 5 minutes | Not Run |
| UT-DSK-011.033.M29.T02 | MD-DSK-011.015.M29 | Negative | Escalate when off (SRD-DSK-011.033) | escalation off: escalate; on: handover | escalate dropped with no row and no refusal line; handover refused | Not Run |
| UT-DSK-011.034.M29.T01 | MD-DSK-011.015.M29 | Positive | Boss address (SRD-DSK-011.034) | sender with boss emp-005 | receiver emp-005 | Not Run |
| UT-DSK-011.034.M29.T02 | MD-DSK-011.015.M29 | Edge | No boss (SRD-DSK-011.034) | sender with no boss | receiver master, state input_required, one escalation alert | Not Run |
| UT-DSK-011.035.M15.T01 | MD-DSK-003.004.M15 | Positive | Priority by type (SRD-DSK-011.035) | store an escalate and an ask | event priority 0 and 1 | Not Run |
| UT-DSK-011.035.M15.T02 | MD-DSK-003.004.M15 | Edge | Repost key (SRD-DSK-011.035) | post_message twice, second with again | two events; same call without again adds none | Not Run |
| UT-DSK-011.036.M29.T01 | MD-DSK-011.015.M29 | Positive | Move up after 5 minutes (SRD-DSK-011.036) | escalate to lead whose boss is chief, 6 minutes later | receiver chief, new due, event for chief | Not Run |
| UT-DSK-011.036.M29.T02 | MD-DSK-011.015.M29 | Negative | No move before due (SRD-DSK-011.036) | 4 minutes later | unchanged | Not Run |
| UT-DSK-011.036.M29.T03 | MD-DSK-011.015.M29 | Edge | Past the top boss (SRD-DSK-011.036) | chief has no boss, 11 minutes | state input_required, receiver master, one alert | Not Run |
| UT-DSK-011.036.M16.T01 | MD-DSK-003.006.M16 | Positive | Router moves escalates (SRD-DSK-011.036) | router has_work with a due escalate | escalate moved to the next boss | Not Run |
| UT-DSK-011.037.M29.T01 | MD-DSK-011.015.M29 | Positive | Move writes reason (SRD-DSK-011.037) | one move up | meta.blocked names the lead; thread msgs 2 | Not Run |
| UT-DSK-011.037.M29.T02 | MD-DSK-011.015.M29 | Edge | Thread full (SRD-DSK-011.037) | due escalate in a thread with 6 messages | goes to master, no move | Not Run |
| UT-DSK-011.038.M29.T01 | MD-DSK-011.015.M29 | Positive | Escalate free of day cap (SRD-DSK-011.038) | sender started 20 today | escalate stored | Not Run |
| UT-DSK-011.038.M29.T02 | MD-DSK-011.015.M29 | Negative | Escalates not counted (SRD-DSK-011.038) | 19 asks and 3 escalates, then two more asks | first ask stored; the second refused | Not Run |
| UT-DSK-011.039.M10.T01 | MD-DSK-003.001.M10 | Positive | Reply-only turn (SRD-DSK-011.039) | boss woken by an escalate | one call with the InboxReply schema; skill act not run; reply stored | Not Run |
| UT-DSK-011.039.M10.T02 | MD-DSK-003.001.M10 | Negative | Only replies kept (SRD-DSK-011.039) | boss answers with a reply and an ask | reply stored, ask not stored | Not Run |
| UT-DSK-011.040.M10.T01 | MD-DSK-003.001.M10 | Positive | Reply as feed note (SRD-DSK-011.040) | boss reply: take AAPL off today | feed note from the boss with the subject and text | Not Run |
| UT-DSK-011.040.M29.T01 | MD-DSK-011.015.M29 | Negative | Reply wakes nobody (SRD-DSK-011.040) | reply to an escalate | no message event for the sender; open_started false | Not Run |
| UT-DSK-011.041.M29.T01 | MD-DSK-011.015.M29 | Positive | Hand to deputy (SRD-DSK-011.041) | open ask to emp-006 with deputy emp-009 | receiver emp-009, handed emp-006, meta.blocked set, event for emp-009 | Not Run |
| UT-DSK-011.041.M29.T02 | MD-DSK-011.015.M29 | Negative | No deputy or handed once (SRD-DSK-011.041) | no deputy; a row already handed | rows returned for refusal | Not Run |
| UT-DSK-011.041.M10.T01 | MD-DSK-003.001.M10 | Positive | Sleeping receiver to deputy (SRD-DSK-011.041) | asked employee sleeps, deputy awake | deputy's wake shows the ask and replies | Not Run |
| UT-DSK-011.042.M10.T01 | MD-DSK-003.001.M10 | Negative | Off keeps M1 refusal (SRD-DSK-011.042) | escalation off, sleeping receiver with deputy | refused reply at once, no hand | Not Run |
| UT-DSK-011.042.M13.T01 | MD-DSK-004.005.M13 | Positive | Setting saved and read (SRD-DSK-011.042) | default, then save true | false, then true | Not Run |
| UT-DSK-011.043.M29.T01 | MD-DSK-011.015.M29 | Positive | Escalation logs (SRD-DSK-011.043) | move up, hand, reach master | `[Messages]` info lines with names, no class names | Not Run |
| UT-DSK-007.011.M21.T01 | MD-DSK-007.001.M21 | Positive | Escalation alert (SRD-DSK-007.011) | raise kind escalation twice | one row titled Escalation not answered, open all day | Not Run |
| UT-DSK-008.010.M22.T01 | MD-DSK-008.001.M22 | Positive | Deputy saved (SRD-DSK-008.010) | save deputy emp-009; render a spec without deputy | read back emp-009; no deputy line | Not Run |
| UT-DSK-008.010.M22.T02 | MD-DSK-008.001.M22 | Negative | Bad deputy (SRD-DSK-008.010) | deputy itself; deputy emp-999 | each refused with a plain reason | Not Run |
