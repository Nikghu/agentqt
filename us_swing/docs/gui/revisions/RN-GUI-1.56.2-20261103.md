# Revision Note — RN-GUI-1.56.2-20261103

**Tool:** GUI
**Version:** 1.56.2
**Date:** 2026-11-03
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Candle data update no longer stuck (ISS-GUI-0014)

---

## Summary

Candle data showed "Up to date" and turned off Update now while 473 of 503 stocks were a day
behind. Status and the update start date now follow the oldest stock, not the newest one.
Retry Failed no longer wipes the resume point of an unfinished update.

## Changes

| File | Change |
|---|---|
| `gui/app_service.py` | New `_oldest_last_candle_date()`; `_CandleDbStatusWorker` takes the stock list; `_last_known_candle_date()` uses the oldest date; new `_candle_check_symbols()` (index stocks minus failed list); fix-mode download keeps the checkpoint |
| `tests/gui/test_app_service_candle_status.py` | **New** — UT-GUI-006.001.M01.T20–T23 |

## Requirements

SRD-GUI-006.020, SRD-GUI-006.021 (new, approved by user 2026-11-03, Implemented).

## Notes

- A stock in the failed list (KVUE today) is left out of the "up to date" check until a
  later run downloads it, or until a Universe Refresh drops it from the index.
- Data repair done on the user's database: 30 rows dated 2026-11-02 deleted, backup kept.

## Verification

- `pytest` candle and settings GUI tests: 38 passed (4 new)
- `ruff` / `mypy` on `app_service.py`: same counts before and after (27 / 149, all pre-existing)
