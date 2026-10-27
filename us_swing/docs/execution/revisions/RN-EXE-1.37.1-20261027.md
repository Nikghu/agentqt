# Revision Note — RN-EXE-1.37.1-20261027

**Version:** 1.37.1
**Date:** 2026-10-27
**Tool:** EXE
**Artifact:** FO-EXE-007 / SRD-EXE-007.010
**Type:** Bugfix

---

## Summary

The live 3m and 15m tables now hold only complete candles. A Yahoo 15m bar is saved only after its window ends, and the first IBKR candle after a mid-window (re)start is not saved. This stops the flat 15m candles seen on 26 Oct; the 217 bad rows already saved were removed after a backup.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-007.001.M01 | `us_swing/src/us_swing/execution/live_bar_worker.py` | Forming Yahoo bars skipped; first partial IBKR window dropped via `_first_bar_dt` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-007.010 | `price_3m` / `price_15m` hold only complete candles | Implemented |

---

## Design Decisions

- A skipped window is not lost: charts and strategies build it from `price_1m`.
- A 5-second bar with zero volume still marks the feed start, since no trade means the window is complete from that point.

---

## Issues Resolved

ISS-EXE-0013 — flat 15m candles from the Yahoo live path.

---

## Test Coverage

3 UT cases (UT-EXE-007.001.M01.T27–T29) in `tests/execution/test_live_bar_worker.py` — all Pass, all fail on the pre-fix code.
