# Revision Note — RN-DSK-0.10.0-20261111

**Version:** 0.10.0
**Date:** 2026-11-11
**Tool:** DSK
**Artifact:** FO-DSK-003, FO-DSK-007 / SRD-DSK-003.020–.025, SRD-DSK-007.009
**Type:** Feature

---

## Summary

Step D of the autonomous desk: the desk now posts check-ins at 10:00, 12:30 and 15:30 New York time. It also runs watchers every 5 minutes in market hours and raises alerts for a stop or target touch, or a broken plan. Each watcher flag is stored once per stock, kind and hour.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-003.021.M24 | `src/us_swing/core/desk_watch.py` | New: watch flags, flag events, feed notes, open trades, live symbols |
| MD-DSK-001.015.M03 | `src/us_swing/desk/clock.py` | Changed: check-in times at 10:00, 12:30 and 15:30 New York time |
| MD-DSK-001.010.M04 | `src/us_swing/desk/process.py` | Changed: posts check-ins and runs the watchers every 5 minutes |
| MD-DSK-001.020.M06 | `src/us_swing/desk/cli.py` | Changed: loads the watchers by import path |
| MD-DSK-001.021.M07 | `src/us_swing/core/desk_steps.py` | Changed: watch and check-in skill paths |
| MD-DSK-003.004.M15 | `src/us_swing/core/desk_events.py` | Changed: event rules for check-ins and watch flags |
| MD-DSK-007.001.M21 | `src/us_swing/core/desk_alerts.py` | Changed: Trade at stop, Trade at target and Plan broken alerts |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-003.020 | Check-in event at 10:00, 12:30 and 15:30 New York time on trading days | Implemented |
| SRD-DSK-003.021 | Each watch flag is a stored row and a `watch_flag` event | Implemented |
| SRD-DSK-003.022 | Same stock and kind within one New York hour is not stored again | Implemented |
| SRD-DSK-003.023 | Watchers run every 5 minutes in market hours, unless paused | Implemented |
| SRD-DSK-003.024 | Each new flag adds a code feed note with stock, kind and price | Implemented |
| SRD-DSK-003.025 | Each watcher pass with flags logs how many and which kinds | Implemented |
| SRD-DSK-007.009 | A stop or target touch, or a broken plan, raises an alert | Implemented |

---

## Design Decisions

- Watchers are loaded by import path, the same way as the step list.
- A stop of 0 is skipped by the stop watcher.
- VIX is not watched in step D.

---

## Issues Resolved

None

---

## Test Coverage

UT-DSK-003.020–.025 — 16 cases, all Pass. UT-DSK-007.009 — 2 cases, all Pass. Full suite: 12 failed (same as TODO T112), plus the old collection error in `tests/screener/test_llm_claude_screener.py` (TODO T136).
