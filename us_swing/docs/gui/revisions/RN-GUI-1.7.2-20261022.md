# Revision Note — RN-GUI-1.7.2-20261022

**Tool:** GUI
**Version:** 1.7.2
**Date:** 2026-10-22
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Execution feed ignores unassigned presets (ISS-GUI-0004)

---

## Summary

A manual run of preset "Test", which has no assigned users, put its 6 stocks into Trade
Execution → Filtered Stocks. The Execution feed now takes results only from presets that exist
and have at least one assigned user.

## The fault

`AppService.get_latest_screener_results()` read the newest result of every preset folder and
never checked `assigned_to`. Deleted presets were included too, under their raw id. The same
list drives the Filtered Stocks pane, the monitoring ledger and the candle fetch.

SRD root cause: **scope gap** — new **SRD-GUI-004.009** (approved by the user in chat on
2026-10-22: exclude from display and engine; hide deleted presets).

## The fix

| File | Change |
|---|---|
| `gui/app_service.py` | Skip a result folder whose preset is not found or has an empty `assigned_to` |
| `gui/app_service.py` | Log a `[Screener]` warning when admin or user presets cannot be loaded (otherwise the feed would go empty silently) — reviewer WARN |

## Verification

- `tests/gui/test_app_service_screener_feed.py` — UT-GUI-004.001.M01.T08–T10 pass
- `tests/gui/`: **235 passed**
- `ruff` clean on the new test; `mypy --strict` no new errors in `app_service.py`

## Follow-ups

- None. Another user's private preset is also skipped (not in the active user's lookup); fine
  with one account.
