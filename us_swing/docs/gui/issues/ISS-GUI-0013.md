# Issue Report — ISS-GUI-0013

**Tool:** GUI (Settings → Users; test suite)
**Severity:** Medium (user mode goes back to paper; Telegram chat id and toggles reset)
**Status:** Resolved
**Date Opened:** 2026-11-03
**Date Resolved:** 2026-11-03
**Reporter:** User (screenshot: Edit User shows Mode "paper" after it was set to live)
**Resolution:** RN-GUI-1.56.1-20261103
**Related:** ISS-GUI-0005, SRD-GUI-006.002

---

## Symptom

The user sets Mode to live. It works once, then later the user is "paper" again with all
default values. `~/.usswing/users.json` was last written at 13:29:34, during a test run.

## Root Cause

Ten GUI test files build a real `AppService` with `load_users` patched to `[]` but
`save_users` not patched. `AppService.__init__` then takes the first-run path and saves a
default paper "trader" user to the real `~/.usswing/users.json`. Every test run reset the
user's mode, risk values and Telegram fields. This is also the likely hidden cause of the
Telegram reset in ISS-GUI-0005.

**SRD root cause: test isolation gap.** No SRD change.

## Fix

| File | Change |
|---|---|
| `tests/conftest.py` | Autouse fixture points `user_store._APP_DIR` / `_STORE_FILE` at a temp folder for every test |

## Verification

- `tests/gui/test_user_dialog_keeps_settings.py` — UT-GUI-006.001.M01.T19 (new).
- Full suite run with a guard that blocks and reports writes to the real file: 0 writes.
  The real file's time stamp did not change.

## Notes

- The real file still says paper: the user must set Mode to live once more, and re-check
  Telegram settings.
- Not fixed here: if `users.json` cannot be read, `load_users()` returns `[]` and the app
  overwrites the file with a default user. A backup before that overwrite would be safer.
