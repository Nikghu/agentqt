# Revision Note — RN-GUI-1.61.0-20261111

**Version:** 1.61.0
**Date:** 2026-11-11
**Tool:** GUI
**Artifact:** FO-GUI-029, FO-GUI-034 / SRD-GUI-029.007–.008, SRD-GUI-034.068–.069
**Type:** Feature

---

## Summary

The app now starts the AI desk when it opens and stops it when it closes. The Scheduler sets Start TWS and Start USSwing 60 minutes before the 09:30 ET open, shown read-only. A background check at app start fixes any start task whose time or days no longer match. Desk labels now name the morning run.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-029.004.M02 | `src/us_swing/gui/scheduler_dialog.py` | `before_open_time()` and `sync_start_tasks()` (background, at app start) |
| MD-GUI-029.001.M01 | `src/us_swing/gui/scheduler_table.py` | Start TWS and Start USSwing rows read-only at 60 min before open |
| MD-GUI-034.002.M02 | `src/us_swing/gui/desk_control.py` | Starts the desk with the app's process id; sends Stop on close |
| MD-GUI-034.060.M34 | `src/us_swing/core/desk_overview.py` | `next_morning_run()` for the Next run tile |
| — (no MD row yet) | `src/us_swing/gui/scheduler_store.py` | Save lock; sync reloads the file before each save (review fix) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-029.007 | Start TWS and Start USSwing fixed at 60 min before the 09:30 ET open, read-only, in local time | Implemented |
| SRD-GUI-029.008 | At app start, a switched-on start task that no longer matches is re-created | Implemented |
| SRD-GUI-034.068 | App starts the desk with its own process id on open and sends Stop on close | Implemented |
| SRD-GUI-034.069 | Desk labels name the morning run: Next run, Desk settings, Team at work, empty notes, feed card title | Implemented |

---

## Design Decisions

- Start TWS and Start USSwing times are fixed (60 min before open). Only Close both stays editable.
- The start-up sync runs off the GUI thread and logs with a `[Scheduler]` prefix.
- Old `evening` runs and briefs still show in the labels as history.

---

## Issues Resolved

None

---

## Test Coverage

Scheduler cases UT-GUI-029.007–.008 (4 cases), desk control and labels UT-GUI-034.068–.069 (4 cases), UT-GUI-034.065.M34.T01 (1 case). All 9 Pass. Full suite: 2624 passed, 12 failed; the same 12 fail on the clean branch base (TODO T112).
