# Revision Note — RN-GUI-1.35.0-20261025

**Version:** 1.35.0
**Date:** 2026-10-25
**Tool:** GUI
**Artifact:** FO-GUI-029 / SRD-GUI-029.001–.006 (new)
**Type:** Feature (user design choice: Option D, https://claude.ai/artifact/Gh6UQNmQUXdHbWtsuKHSww)

---

## Summary

The separate Windows Task Scheduler window is removed. Settings → Scheduler now holds a task table under the market hours: Start TWS, Start USSwing and Close both, each with an on/off switch, time, days, program (with a search button to choose it) and a Windows pill — INSTALLED or MISSING from a background check, CHANGED while the row has edits not yet applied. A folded "TWS login" line opens username, password with a show toggle, fill in automatically and Fill TWS login now. Apply or OK writes every task (switched-off ones are deleted) and saves the password, on a background thread; a switched-on task missing in Windows marks the section changed so Apply re-creates it. A red "Remove all tasks…" link deletes every task, the saved configs and the password after a frameless confirm.

Task names (USSwing_IBKR, USSwing_App, *_Close) and `scheduler.json` stay the same; the configs gain `enabled` (old files load as on; never-configured rows start off so Apply creates nothing). schtasks now runs without a console window. GUI tests use a fake scheduler store, keyring and schtasks (`tests/gui/conftest.py`).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-029.001.M01 | `us_swing/src/us_swing/gui/scheduler_table.py` | New: `SchedulerTable` |
| MD-GUI-029.004.M02 | `us_swing/src/us_swing/gui/scheduler_dialog.py` | `task_states`, `write_tasks`, `remove_tasks`; `SchedulerDialog` removed |
| MD-GUI-000.003 | `us_swing/src/us_swing/gui/scheduler_store.py` | `enabled` on both app configs |
| MD-GUI-027.005.M04 | `us_swing/src/us_swing/gui/settings_panel.py` | Table on the Scheduler page; Apply writes tasks; `QTimeEdit` change tracking |
| — | `us_swing/src/us_swing/gui/theme.py` | `task_pill`, `link_danger`, `login_fold` |
| — | `us_swing/src/us_swing/gui/main_window.py` | Auto-fill hint points to Settings → Scheduler |

## Tests

UT-GUI-029.* (10 cases) in `tests/gui/test_scheduler_table.py` and `test_settings_sections.py`. GUI suite 457 passed. The pytest process still exits with 0xC0000409 at shutdown; this happens on main too.

## Known

The TWS password is still passed on the task's command line when auto fill is on (existing behaviour, unchanged).
