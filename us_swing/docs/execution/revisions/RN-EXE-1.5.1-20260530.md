# Revision Note — RN-EXE-1.5.1-20260530

**Tool:** EXE (Execution)
**Version:** 1.5.1
**Date:** 2026-05-30
**Author:** Claude (Opus 4.8)
**Status:** Implemented

---

## Summary

Fixed the strategy executor producing no ENTRY signals because its candle
read-path ignored stored 1m history. The engine read only the live-fed
`price_3m` / `price_15m` tables, so indicators (e.g. RSI(14) on 3m) had too few
bars and returned NaN. Implemented aggregate-on-read (SRD-EXE-006.010): 3m/15m are
derived from `price_1m` and merged with live bars. Resolves ISS-EXE-0001.

---

## Changes

| SRD | Description | Files |
|---|---|---|
| SRD-EXE-006.010 | Execution candle provider derives 3m/15m from `price_1m`, merges live bars | `execution/intraday_candle_loader.py`, `gui/app_service.py` |
| UT-EXE-006.001.M01.T14-T16 | Read-path unit tests | `tests/execution/test_execution_candle_readpath.py` |

---

## Notes

- Root cause: scope gap — the strategy engine's candle read-path was unspecified.
  FO-EXE-006 persists only 1m; FO-EXE-007 live-writes 3m/15m sparsely; the consumer
  read only the sparse live tables.
- SRD-EXE-006.010 added (Approved this session per user direction) per the
  fix-issue scope-gap rule, then set to Implemented.
- New helpers reuse the pure `HistoricalDataEngine.aggregate_timeframe`; `price_1m`
  is the single source of truth, live `price_{tf}` rows win on timestamp conflict.
- Window = 30 calendar days (matches the FO-EXE-006 download window), giving >=390
  bars for both 3m and 15m.
- Tests: 4 new cases, all passing. ruff + mypy clean on changed code.

---

## Traceability

**FO:** FO-EXE-006
**SRD:** SRD-EXE-006.010
**DD:** DD-EXE-006.010.D01
**MD:** MD-EXE-006.001.M01
**Tests:** `tests/execution/test_execution_candle_readpath.py` (UT-EXE-006.001.M01.T14-T16)
**Issue:** ISS-EXE-0001

---

[Class: D · Tool: EXE · Phase: Code]
