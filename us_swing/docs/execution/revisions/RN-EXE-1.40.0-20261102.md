# Revision Note — RN-EXE-1.40.0-20261102

**Version:** 1.40.0
**Date:** 2026-11-02
**Tool:** EXE
**Artifact:** FO-EXE-006, FO-EXE-007 / SRD-EXE-006.015, SRD-EXE-007.011
**Type:** Feature

---

## Summary

Live strategies get a 30m timeframe. Strategy frames include 30m built from 1m history and live 30m bars, while readiness stays on 3m and 15m. The live worker forms 30m candles from IBKR and Yahoo into the new `price_30m` table, and the session cleanup clears it too.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-006.001.M01 | `execution/intraday_candle_loader.py` | `_FRAME_TIMEFRAMES` gains 30m; readiness unchanged (3m / 15m) |
| MD-EXE-007.001.M01 | `execution/live_bar_worker.py` | Forms 30m from IBKR 5-second bars and Yahoo 30m bars into `price_30m` |
| MD-EXE-009.002.M01 | `core/monitoring_session/_repository.py` | Session eviction also deletes `price_30m` rows |

Cross-tool note: `data/engine.py`, `db/schema.py` (`create_schema` creates `price_30m`) and `analysis/candle_builder.py` were changed for this work. Their MD rows belong to other tools and are not listed here.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-006.015 | Live strategy frames include 30m, built from 1m history and live 30m bars | Implemented |
| SRD-EXE-007.011 | Live worker forms 30m into `price_30m`; session cleanup clears it | Implemented |

---

## Design Decisions

- Readiness stays on 3m and 15m. 30 days give about 270 30m bars, under the 390 minimum.
- `price_30m` is created by `create_schema`, so existing databases get the table at start.

---

## Issues Resolved

None.

---

## Test Coverage

5 UT cases: UT-EXE-006.015.M01.T01–T02, UT-EXE-007.011.M01.T01–T02, UT-EXE-009.002.M01.T09 (updated). All Pass.

Known issue (not caused by this change): 9 failures in `tests/analysis/test_candle_builder.py` (naive vs aware datetime). They also fail without this change.

Pending: live check during market hours.
