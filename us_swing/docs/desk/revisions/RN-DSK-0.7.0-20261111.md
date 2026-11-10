# Revision Note — RN-DSK-0.7.0-20261111

**Version:** 0.7.0
**Date:** 2026-11-11
**Tool:** DSK
**Artifact:** FO-DSK-001, FO-DSK-003, FO-DSK-007 / SRD-DSK-001.013, SRD-DSK-001.015, SRD-DSK-001.018–.020, SRD-DSK-003.013, SRD-DSK-007.005, SRD-DSK-007.007
**Type:** Feature

---

## Summary

The desk now runs one morning run per trading day, from 04:00 ET, instead of the 16:25 ET evening run. The desk starts and stops with the app, and the old Windows desk tasks are removed. A run that fails is tried again after 15 minutes, up to 3 tries a day. A run stopped by the candle check raises a "Candles not up to date" alert.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-001.015.M03 | `src/us_swing/desk/clock.py` | Adds `morning_due()` for the 04:00–16:00 ET window |
| MD-DSK-001.010.M04 | `src/us_swing/desk/process.py` | Parent watch with `pid_alive()`; access denied counts as alive; morning run handling |
| MD-DSK-001.018.M05 | `src/us_swing/desk/task.py` | `remove_old_tasks()` deletes old desk tasks; `launch()` starts a detached desk |
| MD-DSK-001.020.M06 | `src/us_swing/desk/cli.py` | Adds `--parent PID`; `install` and `uninstall` removed |
| MD-DSK-001.001.M02 | `src/us_swing/desk/store.py` | Adds `runs_since()` |
| MD-DSK-001.004.M01 | `src/us_swing/core/desk_contract.py` | Adds `MORNING_RUN`; `launch_desk(parent)` |
| MD-DSK-007.001.M21 | `src/us_swing/core/desk_alerts.py` | Adds the `candles` alert kind; alert text says up to 3 tries, then press Run now |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-001.013 | Desk started without `--resume` exits at once when saved state is Stopped | Implemented |
| SRD-DSK-001.015 | Morning run is due on NYSE trading days, 04:00–16:00 ET, until one ends ok; failed try repeats after 15 minutes, max 3 a day | Implemented |
| SRD-DSK-001.018 | Desk has no Windows tasks; each start deletes old `USSwing_Desk` and `USSwing_Desk_Evening` tasks | Implemented |
| SRD-DSK-001.019 | Desk started with `--parent PID` stops when that process is gone | Implemented |
| SRD-DSK-001.020 | `desk` command runs and controls the desk; `install` and `uninstall` removed | Implemented |
| SRD-DSK-003.013 | Run kinds are `morning`, `manual` and `event`; old `evening` runs stay readable | Implemented |
| SRD-DSK-007.005 | Morning or manual run with calls but no valid answer raises a whole-run alert (wording) | Implemented |
| SRD-DSK-007.007 | Run stopped by the candle check raises a "Candles not up to date" alert | Implemented |

---

## Design Decisions

- The morning run starts by event (app open, pre-market reached, candles checked), not by a fixed clock task.
- The desk has no Windows tasks. The app starts it with its own process id and the desk stops when that process ends.
- A failed run is repeated after 15 minutes, at most 3 tries a day.

---

## Issues Resolved

None

---

## Test Coverage

Morning run, process, task, CLI, store and alert cases in UTCD: UT-DSK-001.015.M03.T01–T06, UT-DSK-001.018.M05.T03–T06, UT-DSK-001.010.M04.T05, T11, T27–T31, UT-DSK-001.020.M06.T05–T06, UT-DSK-001.001.M02.T12, UT-DSK-007.007.M21.T01–T03. Total 23, all Pass. Full suite: 2624 passed, 12 failed; the same 12 fail on the clean branch base (TODO T112).
