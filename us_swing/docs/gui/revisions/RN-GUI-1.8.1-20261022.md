# Revision Note — RN-GUI-1.8.1-20261022

**Tool:** GUI
**Version:** 1.8.1
**Date:** 2026-10-22
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** User edit keeps Telegram settings (ISS-GUI-0005)

---

## Summary

Telegram "Enable notifications" and Chat ID were lost whenever a user was edited in
Settings → Users. The Edit dialog rebuilt the whole profile from its own fields, resetting
Telegram, notify toggles and strategy/screener config to defaults.

SRD root cause: code diverged from **SRD-GUI-006.002**. No SRD changed.

## The fix

| File | Change |
|---|---|
| `gui/settings_panel.py` | `_UserDialog.get_profile()` copies the existing user with `dataclasses.replace()`; only name, display name, IBKR id, mode and risk change. A new user still starts from defaults |

## Verification

- `tests/gui/test_user_dialog_keeps_settings.py` — UT-GUI-006.001.M01.T17–T18; T17 failed on the old code
- `tests/gui/`: **256 passed**; ruff and mypy clean on the change

## Follow-ups

- The user must re-enter the Chat ID and tick "Enable notifications" once.
