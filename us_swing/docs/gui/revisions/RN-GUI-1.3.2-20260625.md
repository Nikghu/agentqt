# Revision Note — RN-GUI-1.3.2-20260625

**Tool:** GUI
**Version:** 1.3.2
**Date:** 2026-06-25
**Type:** enhancement
**Author:** Claude Opus 4.8 under user direction
**Phase:** Windows Task Scheduler — Auto Close

---

## Summary

The Windows Task Scheduler dialog (`SchedulerDialog`) could only **launch** USSwing and
Trader Workstation at a set time — there was no way to close them, so the apps sometimes
stayed open. Added an **"Auto Close"** group: a single shared close time (with an on/off
checkbox) that creates a force-close scheduled task for each configured app. When enabled,
"Update Tasks" creates `USSwing_App_Close` and `USSwing_IBKR_Close`, each running
`taskkill /IM <exe> /F` at the chosen time on that app's own days. The close config is
persisted under a new `"close"` key in `scheduler.json`. New SRD **SRD-GUI-006.017**.

## Changes

| Area | Change |
|---|---|
| Auto Close group | New `QGroupBox` in `SchedulerDialog` with a checkbox ("Close both apps automatically at") + `QTimeEdit`. Time field is disabled until the box is ticked; off by default. |
| Close tasks | `_create_close_task` builds a `schtasks` entry running `taskkill /IM <image> /F` at the close time, reusing each app's own weekday/daily schedule. `create_usswing_close_task` / `create_ibkr_close_task` derive the image name from the exe path. |
| Add / Update flow | When auto-close is on, a close task is created per configured app. Turning it off removes any previously created close tasks. The close config is saved either way. |
| Remove All Tasks | Also deletes the `*_Close` tasks and the stored close config. |
| Storage | `CloseConfig` dataclass (`enabled`, `close_time`) with `load_close_config` / `save_close_config` / `delete_close_config` under the `"close"` key. |

## Files Changed

| File | Change |
|---|---|
| `gui/scheduler_store.py` | New `CloseConfig` + load/save/delete close config |
| `gui/scheduler_dialog.py` | Auto Close UI, close-task wrappers, add/update + remove wiring |
| `tests/gui/test_scheduler_store.py` | New — UT-GUI-000.003.T01–T04 |
| `tests/gui/test_scheduler_dialog.py` | New — UT-GUI-000.004.T01–T02 |

## Traceability

| Artifact | ID |
|---|---|
| FO | FO-GUI-006 |
| SRD | SRD-GUI-006.017 (new) |
| MD | MD-GUI-000.003, MD-GUI-000.004 |
| Tests | UT-GUI-000.003.T01–T04, UT-GUI-000.004.T01–T02 |

## Tests / Checks

| Check | Result |
|---|---|
| `tests/gui/test_scheduler_store.py` | Pass (4) |
| `tests/gui/test_scheduler_dialog.py` | Pass (2) |
| `ruff` | Clean on both edited modules |
| `mypy --strict` | No new errors on the two edited files (pre-existing errors elsewhere unchanged) |

## Deferred / Notes

- Single shared close time applies to both apps by design; per-app close times were
  considered and dropped in favour of the simpler shared control.
- Auto-close uses `taskkill /F` (force) so a busy app or open dialog cannot block the close.
