# Issue Report — ISS-GUI-0005

**Tool:** GUI (Settings → Users → Edit; Settings → Telegram Notifications)
**Severity:** Medium (Telegram notifications silently turned off; chat id lost)
**Status:** Resolved
**Date Opened:** 2026-10-22
**Date Resolved:** 2026-10-22
**Reporter:** User (screenshot: "Enable notifications" unticked and Chat ID empty after saving)
**Resolution:** RN-GUI-1.8.1-20261022
**Related:** FO-INF-010 (Telegram notifications), SRD-GUI-006.002 (Users tab edit)

---

## Symptom

Telegram "Enable notifications" and Chat ID did not stay saved. The Bot Token did.
`~/.usswing/users.json` held `telegram_enabled: false` and `telegram_chat_id: ""`.

## Root Cause

`_UserDialog.get_profile()` built a brand-new `UserProfile` from only the fields it shows
(name, IBKR id, mode, risk). Every field it does not show fell back to its default:
`telegram_enabled` False, `telegram_chat_id` "", the three notify toggles True, and
`strategy_config` / `screener_config` {}. Any user edit after a Telegram save wiped them. The
token survived because it is stored in the OS keychain, not in `users.json`.

**SRD root cause: code diverged — SRD-GUI-006.002** (Edit changes the user's shown details;
it must not reset others). No SRD change.

## Fix

| File | Change |
|---|---|
| `gui/settings_panel.py` | `get_profile()` uses `dataclasses.replace()` on the existing user (and its `RiskConfig`), so only the dialog's fields change |

## Verification

`tests/gui/test_user_dialog_keeps_settings.py` — UT-GUI-006.001.M01.T17 (failed before the fix,
passes after) and T18. `tests/gui/`: 256 passed. ruff and mypy clean on the change.

## Notes

- The lost values cannot be recovered; the user must tick "Enable notifications", enter the
  Chat ID and Save once more.
