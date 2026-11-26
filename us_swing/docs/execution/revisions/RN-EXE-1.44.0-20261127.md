# Revision Note — RN-EXE-1.44.0-20261127

**Version:** 1.44.0
**Date:** 2026-11-27
**Tool:** EXE
**Artifact:** FO-EXE-008, FO-EXE-022 / SRD-EXE-008.007
**Type:** Bugfix

---

## Summary

On Thanksgiving (2026-11-26) the live price showed the older IBKR close of 24 Nov and 0% change. The tick worker now asks IBKR for frozen market data after connect, so a closed market shows the last close-time price. The indicator check raised a false "uses future candles" alarm on higher timeframes, and an empty old plugin folder with a taken name caused a warning; both are fixed. The holiday fix is not yet confirmed in the app.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-008.001.M01 | `execution/live_tick_worker.py` | After connect, `reqMarketDataType(2)` asks IBKR for frozen market data |
| MD-EXE-022.005.M02 | `core/indicator_plugins/_check.py` | Candle cut uses the `datetime` column too, so every timeframe is cut at the same time |
| MD-EXE-022.008.M03 | `core/indicator_plugins/_registry.py` | Empty old per-user folder with a taken name is removed quietly |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-008.007 | After connect, the tick worker asks IBKR for frozen market data so a closed market shows the last close-time price | Implemented |

No SRD change for the indicator check fix (UT-EXE-022.007.M02.T06) or the registry fix (UT-EXE-022.008.M03.T04).

---

## Design Decisions

None

---

## Issues Resolved

None

---

## Test Coverage

- New, Pass: UT-EXE-008.007.M01.T01 (frozen data asked once after connect).
- New, Pass: UT-EXE-022.007.M02.T06 (higher timeframe cut by time; bug fix).
- New, Pass: UT-EXE-022.008.M03.T04 (empty old folder removed quietly).
- Open user checks are in TODO.md (T260, T261).
