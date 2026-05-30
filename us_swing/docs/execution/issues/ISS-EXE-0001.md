# Issue Report — ISS-EXE-0001

**Tool:** EXE (Execution)
**Severity:** High
**Status:** Resolved
**Date Opened:** 2026-05-30
**Date Resolved:** 2026-05-30
**Reporter:** User (USSwing)
**Resolution:** RN-EXE-1.5.1-20260530

---

## Symptom

A Manual-run strategy in RUNNING state with entry condition
`RSI('Spot', 14, '3m') < 55` produced no ENTRY signals — the Active Trades panel
stayed empty — even though the filtered/monitored universe should have satisfied
the condition for many symbols.

## Root Cause

The strategy engine's candle provider (`AppService._get_candles_df` /
`_get_latest_bar`) read **only** the materialised `price_3m` / `price_15m` tables.
Those tables are populated **only** by the FO-EXE-007 live feed, during RTH, a few
bars at a time. FO-EXE-006 downloads deep 1m history into `price_1m` but never
persists the derived 3m/15m bars — `_validate_candle_counts` aggregates them only
to count for the readiness gate, then discards them.

Outside an active live session the engine therefore saw far fewer bars than an
indicator needs. With only ~9 three-minute bars available, `talib.RSI(close, 14)`
returns `NaN` (needs at least 15 bars), so `NaN < 55` is `False` and no signal is
ever enqueued. The executor logic was correct; the candle **read-path** between
FO-EXE-006 (candle readiness) and FO-EXE-011/013 (strategy evaluation) was an
unspecified scope gap.

## Diagnosis Evidence

- `price_1m`: 11,587 bars/symbol (~6 weeks) for the 9 monitored symbols.
- `price_3m`: ~9 bars/symbol (today's live feed only); `price_15m`: ~2 bars/symbol.
- `talib.RSI(8 bars, 14)` -> `NaN`; `NaN < 55` -> `False` (reproduced).
- 1d/1w rebuild (504 symbols) is a separate path and never feeds the executor.

## Fix

New SRD-EXE-006.010 specifies the execution candle provider. Implemented
aggregate-on-read: `_get_candles_df` / `_get_latest_bar` now build 3m/15m by
aggregating `price_1m` via `HistoricalDataEngine.aggregate_timeframe`, merged with
any live `price_{tf}` bars (live wins on timestamp conflict). `price_1m` is the
single source of truth; the live tables become a freshness cache.

## Affected Artifacts

| Artifact | Change |
|---|---|
| SRD-EXE-006.010 | New (Approved -> Implemented) — execution candle provider contract |
| DD-EXE-006.010.D01 | New — aggregate-on-read design |
| MD-EXE-006.001.M01 | Extended — read-path helpers |
| UT-EXE-006.001.M01.T14-T16 | New — read-path tests (Pass) |
| `execution/intraday_candle_loader.py` | + `assemble_execution_bars`, `load_execution_frames`, `load_latest_execution_bar` |
| `gui/app_service.py` | `_get_candles_df` / `_get_latest_bar` rewritten; cached source helper |

## Verification

- `tests/execution/test_execution_candle_readpath.py` — 4 passed.
- ruff + mypy clean on changed code.

[Class: D · Tool: EXE · Phase: Code]
