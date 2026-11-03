# Revision Note — RN-INF-1.8.1-20261103

**Tool:** INF
**Version:** 1.8.1
**Date:** 2026-11-03
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Telegram bot token no longer written to the log

---

## Summary

The `httpx` library logged every request URL at INFO. Telegram request URLs hold the bot token, so the
token was written to `~/.usswing/logs` every 25 s. `configure_logging` now sets the `httpx` logger to
WARNING, the same as `ib_insync`.

## Changes

| File | Change |
|---|---|
| `monitoring/logging_setup.py` | `httpx` logger set to WARNING |
| `tests/infrastructure/test_monitoring.py` | UT-INF-005.001.M01.T05 |

## Requirements

SRD-INF-005.001 (MD-INF-005.001.M01); no SRD text change.

## Verification

- `pytest tests/infrastructure/test_monitoring.py`: 8 passed
- `ruff` clean; the 3 `mypy --strict` notes in `logging_setup.py` are the same on main

## User action

Old log files still hold the token: revoke it in BotFather (`/revoke`), paste the new token in
Settings → Telegram, and delete the old files in `~/.usswing/logs` if you want them gone.
