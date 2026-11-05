# Revision Note — RN-INF-1.10.1-20261105

**Tool:** INF
**Version:** 1.10.1
**Date:** 2026-11-05
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Telegram bot token hidden in log tracebacks (ISS-INF-0004)

---

## Summary

`409 Conflict` errors from the Telegram poller wrote the request URL, and so the bot token, into the log file through their traceback. The log formatter now hides any `bot<id>:<token>` text as `bot<hidden>` in the full line, traceback included.

## Changes

| File | Change |
|---|---|
| `monitoring/logging_setup.py` | Token hidden in `_ZonedFormatter.format` |
| `tests/infrastructure/test_monitoring.py` | UT-INF-005.001.M01.T06 |

## Requirements

SRD-INF-005.001 (MD-INF-005.001.M01); no SRD text change.

## Verification

Monitoring tests pass (9); ruff clean; no new mypy errors in `logging_setup.py`.

## User steps

New token from BotFather; clean old log files; run one app copy (409 Conflict).
