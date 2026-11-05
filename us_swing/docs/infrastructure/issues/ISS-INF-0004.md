# Issue Report — ISS-INF-0004

**Tool:** INF
**Severity:** High (secret written to disk)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-05
**Date Resolved:** 2026-11-05
**Resolution:** RN-INF-1.10.1-20261105
**Reporter:** Agent, found in `~/.usswing/logs/us_swing_2026-11-05.log` during ISS-GUI-0017; user: "fix it"

---

## Symptom

Today's log held the Telegram bot token in plain text, inside many `409 Conflict` tracebacks from the inbound command poller.

## Root Cause

| Point | Detail |
|---|---|
| Traceback text | `httpx.HTTPStatusError` puts the full request URL in its message; Telegram URLs are `.../bot<token>/getUpdates`; `log.exception` writes it |
| Earlier fix too narrow | RN-INF-1.8.1 only turned off httpx's own INFO request lines |
| 409 Conflict | Telegram allows one `getUpdates` poller per bot; two were running (most likely two app copies) |

## Fix

| File | Change |
|---|---|
| `monitoring/logging_setup.py` | `_ZonedFormatter.format` replaces `bot<id>:<token>` with `bot<hidden>` in the whole line, traceback included (file and console) |
| `tests/infrastructure/test_monitoring.py` | UT-INF-005.001.M01.T06 |

## User steps

- Get a new token from BotFather (`/revoke`) and paste it in Settings → Telegram; the old one is in old log files.
- Delete or clean old files in `~/.usswing/logs` that hold the token.
- Run only one copy of the app, so the 409 errors stop.
