# Revision Note — RN-GUI-1.56.1-20261103

**Tool:** GUI
**Version:** 1.56.1
**Date:** 2026-11-03
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Tests no longer reset the user's mode to paper (ISS-GUI-0013)

---

## Summary

Running the test suite rewrote `~/.usswing/users.json` with a default paper user, so the
user's live mode, risk values and Telegram fields were lost after each run.

SRD root cause: test isolation gap. No SRD changed.

## The fix

| File | Change |
|---|---|
| `tests/conftest.py` | Autouse fixture sends the users store to a temp folder in every test |

## Verification

- `tests/gui/test_user_dialog_keeps_settings.py` — UT-GUI-006.001.M01.T19
- Full suite with a write guard: 0 writes to the real file. Other results unchanged (11 failures and 22 errors are pre-existing, same on the old code)

## Follow-ups

- The user sets Mode to live once more and re-checks Telegram settings.
- Back up `users.json` before the app overwrites an unreadable file (TODO T85).
